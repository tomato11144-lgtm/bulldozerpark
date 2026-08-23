"""Claude 호출 경로 — 실제 API 를 부르지 않고 요청/응답 모양만 검증합니다."""

import json
import sys
import types

import pytest

from cardnews.config import Settings
from cardnews.content import _to_cardnews, generate, resolve_mode
from cardnews.prompts import CARDNEWS_SCHEMA, build_user_prompt

VALID_RESPONSE = {
    "title": "성수동 파스타 BEST 3",
    "caption": "성수동 파스타 정리했습니다.",
    "hashtags": ["성수동맛집", "#파스타"],
    "notes": "가격은 방문 전 확인하세요.",
    "cards": [
        {
            "kind": "cover", "badge": "파스타", "eyebrow": "", "title": "성수동\n파스타 3곳",
            "subtitle": "", "body": "", "bullets": [], "meta": {},
            "footnote": "", "image_query": "pasta closeup", "image_keywords": ["파스타"],
        },
        {
            "kind": "place", "badge": "01", "eyebrow": "", "title": "가게",
            "subtitle": "한줄평", "body": "", "bullets": [],
            "meta": {"가격대": "2만원대", "위치": "성수동", "빈값": ""},
            "footnote": "", "image_query": "pasta", "image_keywords": [],
            "정체불명필드": "무시되어야 함",
        },
        {
            "kind": "outro", "badge": "", "eyebrow": "", "title": "저장해두세요",
            "subtitle": "", "body": "", "bullets": [], "meta": {},
            "footnote": "", "image_query": "", "image_keywords": [],
        },
    ],
}


class _FakeUsage:
    input_tokens = 100
    output_tokens = 200


class _FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeResponse:
    stop_reason = "end_turn"
    stop_details = None
    usage = _FakeUsage()

    def __init__(self, payload):
        self.content = [_FakeBlock(json.dumps(payload, ensure_ascii=False))]


@pytest.fixture
def fake_anthropic(monkeypatch):
    """anthropic 모듈을 가짜로 갈아끼우고, 마지막 요청 kwargs 를 돌려줍니다."""
    captured: dict = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponse(captured.pop("_payload", None) or VALID_RESPONSE)

    class FakeClient:
        def __init__(self, api_key=None, **_):
            self.api_key = api_key
            self.messages = FakeMessages()

    module = types.ModuleType("anthropic")
    module.Anthropic = FakeClient
    monkeypatch.setitem(sys.modules, "anthropic", module)
    return captured


def _settings():
    return Settings(anthropic_api_key="sk-test", model="claude-opus-5")


def test_request_shape(fake_anthropic):
    generate("성수동 파스타 맛집", settings=_settings(), card_count=5)
    assert fake_anthropic["model"] == "claude-opus-5"
    assert fake_anthropic["thinking"] == {"type": "adaptive"}
    fmt = fake_anthropic["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"] is CARDNEWS_SCHEMA
    assert fake_anthropic["messages"][0]["role"] == "user"
    assert "성수동 파스타 맛집" in fake_anthropic["messages"][0]["content"]


def test_response_is_parsed(fake_anthropic):
    news = generate("성수동 파스타 맛집", settings=_settings())
    assert news.source == "claude"
    assert news.title == "성수동 파스타 BEST 3"
    assert [c.kind for c in news.cards] == ["cover", "place", "outro"]
    # '#' 은 저장 시 떼어 둡니다 (full_caption 이 다시 붙입니다).
    assert news.hashtags == ["성수동맛집", "파스타"]


def test_unknown_fields_and_empty_meta_are_dropped(fake_anthropic):
    news = generate("성수동 파스타 맛집", settings=_settings())
    place = news.cards[1]
    assert "빈값" not in place.meta
    assert list(place.meta) == ["위치", "가격대"]


def test_falls_back_to_offline_when_api_fails(monkeypatch):
    class Boom:
        def __init__(self, **_):
            raise RuntimeError("연결 실패")

    module = types.ModuleType("anthropic")
    module.Anthropic = Boom
    monkeypatch.setitem(sys.modules, "anthropic", module)

    news = generate("성수동 파스타 맛집 TOP 2", settings=_settings())
    assert news.source == "offline"
    assert "연결 실패" in news.notes


def test_no_api_key_uses_offline():
    news = generate("성수동 파스타 맛집", settings=Settings())
    assert news.source == "offline"


def test_offline_flag_skips_api(fake_anthropic):
    news = generate("성수동 파스타 맛집", settings=_settings(), offline=True)
    assert news.source == "offline"
    assert not fake_anthropic


def test_mode_resolution():
    assert resolve_mode(None, "") == "placeholder"
    assert resolve_mode(None, "가게 정보") == "facts"
    assert resolve_mode("facts", "") == "placeholder"   # 자료 없으면 강등
    assert resolve_mode("guide", "") == "guide"


def test_facts_are_embedded_in_prompt():
    prompt = build_user_prompt(
        "성수동 파스타", card_count=5, tone="t", audience="a",
        mode="facts", facts="라 트라토리아 / 성수동",
    )
    assert "<verified_facts>" in prompt
    assert "라 트라토리아" in prompt


def test_to_cardnews_raises_without_cards():
    from cardnews.content import ContentError

    with pytest.raises(ContentError):
        _to_cardnews({"cards": []}, topic="t", theme="warm", handle="")
