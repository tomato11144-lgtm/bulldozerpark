"""주제 -> 카드뉴스 문안.

기본 경로는 Claude Messages API 의 구조화 출력(output_config.format)입니다.
API 키가 없거나 호출이 실패하면 offline.py 의 템플릿 생성기로 자동 폴백합니다.
"""

from __future__ import annotations

import json
import logging

from .config import Settings
from .locales import get_locale
from .models import Card, CardNews
from .offline import build_offline
from .offline_intl import build_offline_intl
from .prompts import build_user_prompt, cardnews_schema, system_prompt

log = logging.getLogger(__name__)

DEFAULT_TONE = "친근한 존댓말, 과장 없이"
DEFAULT_AUDIENCE = "20~30대 직장인"
DEFAULT_TONE_EN = "friendly and specific, no hype"
DEFAULT_AUDIENCE_EN = "people aged 20-35 deciding where to eat this week"

# facts 없이 특정 가게를 나열해 달라고 하면 지어낼 위험이 커서, 기본은 placeholder.
MODES = ("placeholder", "facts", "unverified", "guide")


class ContentError(RuntimeError):
    """문안 생성 실패."""


def resolve_mode(mode: str | None, facts: str) -> str:
    if mode and mode in MODES:
        # 사용자가 facts 모드를 골랐는데 정작 자료가 없으면 자리표시자로 내립니다.
        if mode == "facts" and not facts.strip():
            log.warning("검증 자료가 비어 있어 placeholder 모드로 전환합니다.")
            return "placeholder"
        return mode
    return "facts" if facts.strip() else "placeholder"


def build_offline_any(
    topic: str, lang: str, *, card_count: int, mode: str, facts: str, handle: str
) -> CardNews:
    """언어에 맞는 오프라인 생성기를 고릅니다."""
    locale = get_locale(lang)
    if locale.code == "ko":
        news = build_offline(
            topic, card_count=card_count, mode=mode, facts=facts, handle=handle
        )
        news.lang = "ko"
        return news
    return build_offline_intl(
        topic, locale, card_count=card_count, mode=mode, facts=facts, handle=handle
    )


def generate(
    topic: str,
    *,
    settings: Settings | None = None,
    card_count: int = 7,
    tone: str = "",
    audience: str = "",
    mode: str | None = None,
    facts: str = "",
    handle: str = "",
    extra: str = "",
    theme: str = "warm",
    lang: str = "ko",
    offline: bool = False,
) -> CardNews:
    """주제 문장 하나로 카드뉴스 문안 한 세트를 만듭니다."""
    settings = settings or Settings.from_env()
    locale = get_locale(lang)
    mode = resolve_mode(mode, facts)
    card_count = max(3, min(card_count, 12))
    tone = tone or (DEFAULT_TONE if locale.code == "ko" else DEFAULT_TONE_EN)
    audience = audience or (
        DEFAULT_AUDIENCE if locale.code == "ko" else DEFAULT_AUDIENCE_EN
    )

    if offline or not settings.has_llm:
        if not offline:
            log.info("ANTHROPIC_API_KEY 가 없어 오프라인 템플릿 생성기를 사용합니다.")
        news = build_offline_any(
            topic, locale.code, card_count=card_count, mode=mode,
            facts=facts, handle=handle,
        )
        news.theme = theme
        return news

    try:
        return _generate_with_claude(
            topic,
            settings=settings,
            card_count=card_count,
            tone=tone,
            audience=audience,
            mode=mode,
            facts=facts,
            handle=handle,
            extra=extra,
            theme=theme,
            lang=locale.code,
        )
    except Exception as exc:  # noqa: BLE001 - 어떤 실패든 결과물은 내보냅니다
        log.warning("Claude 호출 실패(%s) — 오프라인 생성기로 폴백합니다.", exc)
        news = build_offline_any(
            topic, locale.code, card_count=card_count, mode=mode,
            facts=facts, handle=handle,
        )
        news.theme = theme
        news.notes = (news.notes + f"\n(문안 자동 생성 실패: {exc})").strip()
        return news


def _generate_with_claude(
    topic: str,
    *,
    settings: Settings,
    card_count: int,
    tone: str,
    audience: str,
    mode: str,
    facts: str,
    handle: str,
    extra: str,
    theme: str,
    lang: str,
) -> CardNews:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - 설치 안내
        raise ContentError("anthropic 패키지가 필요합니다: pip install anthropic") from exc

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    user_prompt = build_user_prompt(
        topic,
        card_count=card_count,
        tone=tone,
        audience=audience,
        mode=mode,
        facts=facts,
        handle=handle,
        extra=extra,
        lang=lang,
    )
    locale = get_locale(lang)

    response = client.messages.create(
        model=settings.model,
        max_tokens=16000,
        system=system_prompt(locale),
        messages=[{"role": "user", "content": user_prompt}],
        thinking={"type": "adaptive"},
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": cardnews_schema(lang)},
        },
    )

    if getattr(response, "stop_reason", None) == "refusal":
        detail = getattr(response, "stop_details", None)
        raise ContentError(f"모델이 응답을 거부했습니다: {detail}")

    text = next((b.text for b in response.content if b.type == "text"), "")
    if not text.strip():
        raise ContentError("모델이 빈 응답을 반환했습니다.")

    data = json.loads(text)
    news = _to_cardnews(data, topic=topic, theme=theme, handle=handle, lang=lang)
    news.source = "claude"
    news.meta.update(
        {
            "model": settings.model,
            "mode": mode,
            "lang": lang,
            "input_tokens": getattr(response.usage, "input_tokens", None),
            "output_tokens": getattr(response.usage, "output_tokens", None),
        }
    )
    return news


def _to_cardnews(
    data: dict, *, topic: str, theme: str, handle: str, lang: str = "ko"
) -> CardNews:
    """모델이 돌려준 dict 를 CardNews 로. 알 수 없는 키는 조용히 버립니다."""
    allowed = set(Card.__dataclass_fields__)
    cards: list[Card] = []
    for raw in data.get("cards", []):
        if not isinstance(raw, dict):
            continue
        payload = {k: v for k, v in raw.items() if k in allowed}
        meta = payload.get("meta") or {}
        payload["meta"] = {str(k): str(v) for k, v in meta.items() if v}
        payload["bullets"] = [str(b) for b in (payload.get("bullets") or []) if str(b).strip()]
        cards.append(Card(**payload))

    if not cards:
        raise ContentError("카드가 하나도 생성되지 않았습니다.")

    return CardNews(
        topic=topic,
        title=(data.get("title") or topic).strip(),
        cards=cards,
        caption=(data.get("caption") or "").strip(),
        hashtags=[str(h).lstrip("#").strip() for h in data.get("hashtags", []) if str(h).strip()],
        theme=theme,
        lang=lang,
        handle=handle,
        notes=(data.get("notes") or "").strip(),
    )
