"""차트 · 슬라이드 구성 · 렌더링 · CLI."""

import json

import pytest

from storeboard import charts, theme
from storeboard.cli import normalize
from storeboard.deck import build_deck
from storeboard.insights import Insights, build_rule_insights
from storeboard.metrics import summarize
from storeboard.models import Report
from storeboard.render.html import build_html
from storeboard.sample import build_sample


@pytest.fixture()
def sample():
    report = build_sample()
    summary = summarize(report)
    return report, summary, build_rule_insights(report, summary)


# --------------------------------------------------------------------------
# 차트
# --------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [(1.099e8, 1.2e8), (95, 100), (0, 1.0)])
def test_nice_max_rounds_up_to_clean_ticks(value, expected):
    assert charts.nice_max(value) == pytest.approx(expected)


def test_columns_labels_only_the_last_primary_bar():
    chart = charts.columns(
        ["1주", "2주"], [("올해", [10, 20]), ("전년", [11, 21])],
        value_fmt=lambda v: f"{v:.0f}만",
    )
    # 두 계열 모두에 값을 달면 마지막 기간에서 라벨이 겹칩니다.
    assert chart.svg.count("20만") == 1
    assert "21만" not in chart.svg
    assert len(chart.legend) == 2


def test_single_series_column_has_no_legend_box():
    chart = charts.columns(["1주"], [("매출", [10])])
    assert chart.legend == []


def test_bars_widen_the_label_gutter_for_long_names():
    short = charts.bars([("A", 10)])
    long = charts.bars([("네이버 플레이스광고", 10)])
    assert len(long.svg) and len(short.svg)
    # 긴 이름이면 막대 시작점이 더 오른쪽으로 밀립니다.
    assert _first_bar_x(long.svg) > _first_bar_x(short.svg)


def _first_bar_x(svg: str) -> float:
    marker = '<path d="M'
    start = svg.index(marker) + len(marker)
    return float(svg[start:].split(",", 1)[0])


def test_stacked_uses_palette_order_and_reports_shares():
    chart = charts.stacked([("검색", 60), ("지도", 40)])
    assert theme.SERIES[0] in chart.svg and theme.SERIES[1] in chart.svg
    assert [item.value for item in chart.legend] == ["60 · 60%", "40 · 40%"]


def test_stacked_skips_inline_label_that_would_not_fit():
    chart = charts.stacked([("큰 조각", 99), ("아주 작은 조각", 1)], width=400)
    # 안 들어가는 조각의 값은 잘라 넣지 않고 범례가 들고 갑니다.
    assert chart.svg.count(">1%<") == 0
    assert any("1%" in item.value for item in chart.legend)


def test_funnel_uses_the_ordinal_ramp():
    chart = charts.funnel([("노출", 100, 100, "회"), ("클릭", 10, 10.0, "회")])
    assert theme.ORDINAL[0] in chart.svg and theme.ORDINAL[1] in chart.svg
    assert chart.table_rows[1] == ["클릭", "10회", "10.00%"]


def test_diverging_splits_by_sign():
    chart = charts.diverging([("A", 5.0), ("B", -5.0)])
    assert theme.DIVERGE_POS in chart.svg and theme.DIVERGE_NEG in chart.svg


def test_every_chart_carries_a_table_twin():
    for chart in (
        charts.columns(["1주"], [("매출", [1])]),
        charts.bars([("A", 1)]),
        charts.stacked([("A", 1)]),
        charts.funnel([("노출", 1, 100, "회")]),
        charts.diverging([("A", 1.0)]),
    ):
        assert chart.table_head and chart.table_rows


# --------------------------------------------------------------------------
# 슬라이드 구성
# --------------------------------------------------------------------------

def test_deck_order_on_full_data(sample):
    deck = build_deck(*sample)
    assert [s.kind for s in deck.slides] == [
        "cover", "summary", "trend", "stores", "channels", "funnel",
        "naver", "actions", "appendix",
    ]


def test_slides_without_data_are_skipped():
    report = Report(period="2026-W33", sales=[
        {"store": "A", "period": "2026-W33", "revenue": 1_000_000}])
    summary = summarize(report)
    kinds = [s.kind for s in build_deck(report, summary, Insights()).slides]
    assert kinds == ["cover", "summary", "actions"]     # 광고·유입·매장비교 없음


def test_store_table_drops_columns_without_data(sample):
    deck = build_deck(*sample)
    table = next(b for s in deck.slides if s.kind == "stores"
                 for b in s.blocks if b.kind == "table")
    # 샘플의 광고비는 매장별로 나뉘지 않습니다 -> 열을 세우지 않고 각주로 밝힙니다.
    assert "광고비" not in table.table_head
    assert "광고 리포트가 매장별로" in table.footnote
    assert len(table.table_head) == len(table.table_rows[0])


def test_summary_slide_leads_with_one_hero_number(sample):
    deck = build_deck(*sample)
    kpis = next(b for s in deck.slides if s.kind == "summary"
                for b in s.blocks if b.kind == "kpis").kpis
    assert kpis[0].label == "매출"
    assert len(kpis) == 6


def test_trend_table_lays_periods_across_columns(sample):
    deck = build_deck(*sample)
    slide = next(s for s in deck.slides if s.kind == "trend")
    table = next(b for b in slide.blocks if b.kind == "table")
    assert [row[0] for row in table.table_rows] == ["올해", "전년 동기", "전년비"]


# --------------------------------------------------------------------------
# 코멘트
# --------------------------------------------------------------------------

def test_rule_insights_only_cite_available_numbers():
    report = Report(period="2026-W33", sales=[
        {"store": "A", "period": "2026-W33", "revenue": 1_000_000}])
    insights = build_rule_insights(report, summarize(report))
    body = " ".join(c.title + c.body for c in insights.callouts)
    # 광고·유입 자료가 없으면 ROAS 나 유입 이야기를 꺼내지 않습니다.
    assert "ROAS" not in body and "조회" not in body
    assert insights.actions                       # 액션은 늘 한 줄이라도 남깁니다


def test_rule_insights_flag_a_broken_ad_ratio_ceiling():
    report = Report(
        period="2026-W33",
        sales=[{"store": "A", "period": "2026-W33", "revenue": 1_000_000}],
        ads=[{"channel": "meta", "period": "2026-W33", "spend": 300_000}],
        goal={"ad_ratio": 12.0},
    )
    insights = build_rule_insights(report, summarize(report))
    assert any(c.tone == "critical" and "광고비" in c.title for c in insights.callouts)


# --------------------------------------------------------------------------
# 렌더링
# --------------------------------------------------------------------------

def test_html_has_one_section_per_slide(sample):
    doc = build_html(build_deck(*sample))
    assert doc.html.count('class="slide ') == doc.count
    assert len(doc.pages) == doc.count
    assert (doc.width, doc.height) == (1920, 1080)


def test_single_slide_pages_keep_their_number(sample):
    doc = build_html(build_deck(*sample))
    assert 'id="card-3"' in doc.pages[2]
    assert doc.pages[2].count('class="slide ') == 1
    assert "3 / 9" in doc.pages[2]


def test_html_escapes_report_text():
    report = Report(title="<script>x</script>", period="2026-W33",
                    sales=[{"store": "A", "period": "2026-W33", "revenue": 1}])
    doc = build_html(build_deck(report, summarize(report), Insights()))
    assert "<script>x</script>" not in doc.html
    assert "&lt;script&gt;" in doc.html


def test_capture_images_are_routed(tmp_path):
    from PIL import Image

    shot = tmp_path / "매출.png"
    Image.new("RGB", (40, 30), "white").save(shot)
    report = Report(period="2026-W33", captures=[str(shot)],
                    sales=[{"store": "A", "period": "2026-W33", "revenue": 1}])
    doc = build_html(build_deck(report, summarize(report), Insights()))
    assert any(path == shot for path in doc.routes.values())
    assert "/__img/01.png" in doc.html


def test_missing_capture_file_is_ignored():
    report = Report(period="2026-W33", captures=["/does/not/exist.png"],
                    sales=[{"store": "A", "period": "2026-W33", "revenue": 1}])
    doc = build_html(build_deck(report, summarize(report), Insights()))
    assert "/__img/" not in doc.html


def test_status_tone_is_never_colour_alone(sample):
    doc = build_html(build_deck(*sample))
    # 코멘트 상태는 색 + 부호로 함께 표시합니다.
    assert "callout__mark" in doc.html


# --------------------------------------------------------------------------
# 파이프라인 · CLI
# --------------------------------------------------------------------------

def test_pipeline_writes_sidecars_without_a_browser(tmp_path):
    from storeboard.pipeline import build

    result = build(build_sample(), out_dir=tmp_path, formats=("html",), offline=True)
    assert result.html.is_file()
    assert result.json_path.is_file() and result.summary_path.is_file()
    text = result.summary_path.read_text(encoding="utf-8")
    assert "매출" in text and "강남점" in text
    saved = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert saved["period"] == "2026-W33"


def test_pipeline_rejects_a_report_without_a_period():
    from storeboard.pipeline import build

    with pytest.raises(ValueError):
        build(Report())


@pytest.mark.parametrize("argv,expected", [
    (["report.json"], ["build", "report.json"]),
    (["shots/"], ["report", "shots/"]),
    (["-v", "out/x.json"], ["-v", "build", "out/x.json"]),
    (["build", "a.json"], ["build", "a.json"]),
    (["--help"], ["--help"]),
])
def test_cli_fills_in_the_missing_subcommand(argv, expected):
    assert normalize(argv) == expected
