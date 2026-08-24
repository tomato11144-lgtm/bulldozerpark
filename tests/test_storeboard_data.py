"""기간 계산 · 모델 · 지표."""

import pytest

from storeboard import periods
from storeboard.metrics import Delta, funnel, revenue_series, store_rows, summarize
from storeboard.models import ALL_STORES, AdPoint, Report, SalesPoint, TrafficPoint, _int
from storeboard.sample import build_sample


# --------------------------------------------------------------------------
# 기간
# --------------------------------------------------------------------------

@pytest.mark.parametrize("value,grain", [
    ("2026-08-24", "daily"), ("2026-W33", "weekly"),
    ("2026-08", "monthly"), ("2026", "yearly"),
])
def test_grain_detection(value, grain):
    assert periods.grain_of(value) == grain


def test_unknown_period_raises():
    with pytest.raises(periods.PeriodError):
        periods.grain_of("2026년 8월")


def test_normalize_pads_numbers():
    assert periods.normalize("2026-w3") == "2026-W03"
    assert periods.normalize("2026-8") == "2026-08"


def test_prev_crosses_year_boundaries():
    assert periods.prev("2026-W01") == "2025-W52"
    assert periods.prev("2026-01") == "2025-12"
    assert periods.prev("2026") == "2025"


def test_weekly_last_year_is_364_days_back():
    # 주차 번호를 그냥 빼면 요일 구성이 어긋납니다. 364일 전 같은 요일로 잡습니다.
    start = periods.start_date("2026-W33")
    ly = periods.start_date(periods.last_year("2026-W33"))
    assert (start - ly).days == 364
    assert start.weekday() == ly.weekday()


def test_series_back_is_oldest_first():
    keys = periods.series_back("2026-W33", 4)
    assert keys == ["2026-W30", "2026-W31", "2026-W32", "2026-W33"]


# --------------------------------------------------------------------------
# 모델
# --------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("1,234,000", 1_234_000), ("12,000원", 12_000), ("1.2억", 120_000_000),
    ("340만", 3_400_000), ("", 0), (None, 0), ("읽을 수 없음", 0),
])
def test_int_parsing(raw, expected):
    assert _int(raw) == expected


def test_ticket_prefers_customers_over_orders():
    point = SalesPoint(store="A", period="2026-W33", revenue=100_000,
                       orders=10, customers=20)
    assert point.ticket == 5_000


def test_report_detects_stores_and_period():
    report = Report(sales=[
        {"store": "강남점", "period": "2026-W32", "revenue": 100},
        {"store": "홍대점", "period": "2026-W33", "revenue": 200},
    ])
    assert report.stores == ["강남점", "홍대점"]
    assert report.period == "2026-W33"        # 가장 최근 기간


def test_report_roundtrips_through_json(tmp_path):
    report = build_sample()
    path = report.save_json(tmp_path / "report.json")
    again = Report.load_json(path)
    assert len(again.sales) == len(report.sales)
    assert again.goal.roas == report.goal.roas


def test_merge_replaces_same_key_and_appends_new():
    base = Report(sales=[{"store": "A", "period": "2026-W33", "revenue": 100}])
    other = Report(
        sales=[{"store": "A", "period": "2026-W33", "revenue": 250},
               {"store": "B", "period": "2026-W33", "revenue": 70}],
        warnings=["표가 잘렸습니다"],
    )
    base.merge(other)
    assert [s.revenue for s in base.sales] == [250, 70]
    assert base.warnings == ["표가 잘렸습니다"]


# --------------------------------------------------------------------------
# 지표
# --------------------------------------------------------------------------

def test_delta_without_base_is_not_available():
    delta = Delta(current=100, base=0)
    assert not delta.available
    assert delta.direction == "flat"
    assert delta.pct == 0


def test_delta_percentages():
    delta = Delta(current=110, base=100)
    assert delta.pct == pytest.approx(10.0)
    assert delta.direction == "up"


def test_totals_sum_store_rows_only():
    # 매장별 행과 합계 행이 같이 있으면 두 번 세면 안 됩니다.
    report = Report(period="2026-W33", sales=[
        {"store": "A", "period": "2026-W33", "revenue": 100},
        {"store": "B", "period": "2026-W33", "revenue": 200},
        {"store": ALL_STORES, "period": "2026-W33", "revenue": 300},
    ])
    assert summarize(report).revenue == 300


def test_summary_metrics_on_sample():
    report = build_sample()
    summary = summarize(report)
    assert summary.revenue > 0
    assert summary.prev.available and summary.yoy.available
    assert summary.ad_ratio == pytest.approx(summary.spend / summary.revenue * 100)
    assert summary.blended_roas == pytest.approx(summary.revenue / summary.spend)
    assert [s.store for s in summary.stores] == sorted(
        (s.store for s in summary.stores),
        key=lambda name: -next(r.revenue for r in summary.stores if r.store == name),
    )


def test_store_shares_add_up():
    summary = summarize(build_sample())
    assert sum(s.share for s in summary.stores) == pytest.approx(100.0)


def test_channel_rates_are_derived_not_stored():
    summary = summarize(build_sample())
    channel = summary.channels[0]
    assert channel.ctr == pytest.approx(channel.clicks / channel.impressions * 100)
    assert channel.cpc == pytest.approx(channel.spend / channel.clicks)
    assert channel.roas == pytest.approx(channel.revenue / channel.spend)


def test_channel_without_revenue_is_excluded_from_roas_ranking():
    report = Report(period="2026-W33", sales=[
        {"store": "A", "period": "2026-W33", "revenue": 1_000_000}],
        ads=[{"channel": "naver_sa", "period": "2026-W33", "spend": 100, "revenue": 500},
             {"channel": "naver_place", "period": "2026-W33", "spend": 100}])
    summary = summarize(report)
    assert summary.best_channel.channel == "naver_sa"
    assert summary.worst_channel.channel == "naver_sa"    # 전환매출 없는 채널은 순위 밖


def test_funnel_is_empty_without_ad_data():
    report = Report(period="2026-W33",
                    sales=[{"store": "A", "period": "2026-W33", "revenue": 10}])
    assert funnel(report) == []


def test_revenue_series_trims_leading_gaps():
    report = Report(period="2026-W33", sales=[
        {"store": "A", "period": "2026-W32", "revenue": 10},
        {"store": "A", "period": "2026-W33", "revenue": 20},
    ])
    series = revenue_series(report, count=8)
    assert [p.period for p in series] == ["2026-W32", "2026-W33"]


def test_traffic_action_rate():
    report = Report(period="2026-W33", traffic=[TrafficPoint(
        store="A", period="2026-W33", views=1000,
        reservations=50, calls=30, directions=20,
    )])
    summary = summarize(report)
    assert summary.traffic.actions == 100
    assert summary.traffic.action_rate == pytest.approx(10.0)


def test_ad_point_normalizes_channel_and_numbers():
    ad = AdPoint(channel="meta", period="2026-8", spend="1,200,000", conversions="12.5")
    assert ad.period == "2026-08" and ad.spend == 1_200_000 and ad.conversions == 12.5
