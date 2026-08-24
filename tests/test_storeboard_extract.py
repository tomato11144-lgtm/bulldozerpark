"""캡처 판독 — API 호출 없이 확인할 수 있는 부분."""

from pathlib import Path

import pytest

from storeboard.config import Settings
from storeboard.extract import Capture, ExtractError, _to_report, collect, extract_one, guess_kind
from storeboard.prompts import schema, user_prompt


@pytest.mark.parametrize("name,kind", [
    ("주간매출_0812.png", "sales"),
    ("POS_정산.jpg", "sales"),
    ("naver_place_inflow.png", "traffic"),
    ("네이버플레이스_유입.png", "traffic"),
    ("메타광고_리포트.jpg", "ads"),
    ("google_ads_0812.png", "ads"),
    ("스크린샷 2026-08-12.png", ""),
])
def test_guess_kind_from_filename(name, kind):
    assert guess_kind(Path(name)) == kind


def test_collect_walks_folders_and_skips_non_images(tmp_path):
    (tmp_path / "shots").mkdir()
    (tmp_path / "shots" / "매출.png").write_bytes(b"x")
    (tmp_path / "shots" / "메모.txt").write_text("x")
    (tmp_path / "광고.jpg").write_bytes(b"x")
    found = collect([tmp_path / "shots", tmp_path / "광고.jpg"])
    assert [c.path.name for c in found] == ["매출.png", "광고.jpg"]
    assert [c.kind for c in found] == ["sales", "ads"]


def test_extract_requires_an_api_key(tmp_path):
    shot = tmp_path / "매출.png"
    shot.write_bytes(b"x")
    with pytest.raises(ExtractError, match="ANTHROPIC_API_KEY"):
        extract_one(Capture(path=shot), settings=Settings(anthropic_api_key=""))


def test_rows_without_a_period_take_the_fallback():
    data = {
        "kind": "sales",
        "period": "",
        "sales": [{"store": "강남점", "period": "", "revenue": 100}],
        "ads": [], "traffic": [], "warnings": [],
    }
    report = _to_report(data, Capture(path=Path("매출.png")), fallback_period="2026-W33")
    assert report.sales[0].period == "2026-W33"


def test_rows_are_dropped_when_no_period_can_be_resolved():
    # 기간을 모르면 지표를 어디에 붙일지 알 수 없습니다. 지어내는 대신 버리고 경고합니다.
    data = {
        "kind": "sales", "period": "",
        "sales": [{"store": "강남점", "period": "", "revenue": 100}],
        "ads": [], "traffic": [], "warnings": [],
    }
    report = _to_report(data, Capture(path=Path("매출.png")))
    assert report.sales == []
    assert any("기간" in w for w in report.warnings)


def test_warnings_are_prefixed_with_the_capture_name():
    data = {"kind": "ads", "period": "2026-W33", "sales": [], "ads": [], "traffic": [],
            "warnings": ["CPC 열이 잘렸습니다"]}
    report = _to_report(data, Capture(path=Path("광고.png")))
    assert report.warnings == ["광고.png: CPC 열이 잘렸습니다"]


def test_schema_channel_enum_matches_the_model_keys():
    from storeboard.models import CHANNELS

    channel = schema()["properties"]["ads"]["items"]["properties"]["channel"]
    assert channel["enum"] == list(CHANNELS)


def test_prompt_carries_known_store_names():
    text = user_prompt(filename="a.png", kind="sales", period="2026-W33",
                       stores=["강남점", "홍대점"])
    assert "강남점, 홍대점" in text and "2026-W33" in text
