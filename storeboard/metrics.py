"""원본 데이터 -> 보고서에 실을 지표.

여기서 만드는 값은 전부 파생 지표입니다. report.json 에는 저장하지 않고
빌드할 때마다 다시 계산합니다 — 원본을 고치면 지표가 항상 따라옵니다.

없는 값은 0 이 아니라 '없음'으로 다룹니다. 전주 매출이 없는데 증감률을
0% 로 찍으면 보고 자리에서 잘못된 결론이 나옵니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import periods
from .models import ALL_STORES, AdPoint, Report, SalesPoint, TrafficPoint, channel_label


def ratio(numerator: float, denominator: float) -> float:
    """0 나누기를 막은 나눗셈."""
    return numerator / denominator if denominator else 0.0


@dataclass
class Delta:
    """전기·전년 대비 증감. base 가 없으면 available=False 로 비교를 생략합니다."""

    current: float = 0.0
    base: float = 0.0
    label: str = ""

    @property
    def available(self) -> bool:
        return bool(self.base)

    @property
    def diff(self) -> float:
        return self.current - self.base

    @property
    def pct(self) -> float:
        return ratio(self.diff, self.base) * 100 if self.base else 0.0

    @property
    def direction(self) -> str:
        if not self.available or abs(self.pct) < 0.05:
            return "flat"
        return "up" if self.diff > 0 else "down"


def _sum_sales(rows: list[SalesPoint]) -> SalesPoint:
    return SalesPoint(
        store=ALL_STORES,
        period=rows[0].period if rows else "",
        revenue=sum(r.revenue for r in rows),
        orders=sum(r.orders for r in rows),
        customers=sum(r.customers for r in rows),
    )


def _store_rows_only(report: Report, period: str) -> list[SalesPoint]:
    """매장별 행만. 매장 분리가 없으면 전체 행을 그대로 씁니다."""
    rows = [s for s in report.sales_for(period) if s.store != ALL_STORES]
    return rows or report.sales_for(period, ALL_STORES)


def revenue_of(report: Report, period: str, store: str | None = None) -> int:
    """기간(과 매장)의 매출 합계. 매장별 행이 있으면 그 합, 없으면 전체 행."""
    if store and store != ALL_STORES:
        return sum(s.revenue for s in report.sales_for(period, store))
    rows = _store_rows_only(report, period)
    return sum(s.revenue for s in rows)


def totals(report: Report, period: str) -> SalesPoint:
    """기간 전체 합계 (매출·건수·고객수)."""
    rows = _store_rows_only(report, period)
    total = _sum_sales(rows)
    total.period = period
    return total


def ad_spend(report: Report, period: str, store: str | None = None) -> int:
    rows = report.ads_for(period)
    if store and store != ALL_STORES:
        rows = [a for a in rows if a.store == store]
    return sum(a.spend for a in rows)


def ad_revenue(report: Report, period: str, store: str | None = None) -> int:
    rows = report.ads_for(period)
    if store and store != ALL_STORES:
        rows = [a for a in rows if a.store == store]
    return sum(a.revenue for a in rows)


# --------------------------------------------------------------------------
# 시계열
# --------------------------------------------------------------------------

@dataclass
class SeriesPoint:
    period: str
    label: str
    revenue: int = 0
    has_data: bool = True


def revenue_series(
    report: Report, *, period: str = "", count: int = 8, store: str | None = None
) -> list[SeriesPoint]:
    """기준 기간을 마지막으로 하는 매출 추이. 데이터가 없는 구간은 잘라냅니다."""
    period = period or report.period
    if not period:
        return []
    keys = periods.series_back(period, count)
    points = [
        SeriesPoint(
            period=key,
            label=periods.label(key, short=True),
            revenue=revenue_of(report, key, store),
            has_data=bool(revenue_of(report, key, store)),
        )
        for key in keys
    ]
    # 앞쪽의 빈 구간은 버리고, 중간의 구멍은 남겨 둡니다(누락이 보이도록).
    while points and not points[0].has_data:
        points.pop(0)
    return points


def yoy_series(report: Report, points: list[SeriesPoint], store: str | None = None):
    """추이 그래프에 겹쳐 그릴 전년 동기 값."""
    return [
        SeriesPoint(
            period=periods.last_year(p.period),
            label=p.label,
            revenue=revenue_of(report, periods.last_year(p.period), store),
            has_data=bool(revenue_of(report, periods.last_year(p.period), store)),
        )
        for p in points
    ]


# --------------------------------------------------------------------------
# 매장별
# --------------------------------------------------------------------------

@dataclass
class StoreRow:
    store: str
    revenue: int = 0
    orders: int = 0
    customers: int = 0
    ticket: int = 0
    spend: int = 0
    traffic_views: int = 0
    traffic_actions: int = 0
    share: float = 0.0            # 전체 매출에서 차지하는 비중(%)
    prev: Delta = field(default_factory=Delta)
    yoy: Delta = field(default_factory=Delta)

    @property
    def ad_ratio(self) -> float:
        """매출 대비 광고비 비율(%)."""
        return ratio(self.spend, self.revenue) * 100

    @property
    def roas(self) -> float:
        """매장 매출 기준 광고 효율(배). 채널 리포트 전환매출이 아니라 실매출 기준입니다."""
        return ratio(self.revenue, self.spend)


def store_rows(report: Report, period: str = "") -> list[StoreRow]:
    """매장별 한 줄 요약. 매출 큰 순서."""
    period = period or report.period
    rows: list[StoreRow] = []
    for sale in _store_rows_only(report, period):
        traffic = report.traffic_for(period, sale.store)
        row = StoreRow(
            store=sale.store,
            revenue=sale.revenue,
            orders=sale.orders,
            customers=sale.customers,
            ticket=sale.ticket,
            spend=ad_spend(report, period, sale.store),
            traffic_views=sum(t.views for t in traffic),
            traffic_actions=sum(t.actions for t in traffic),
            prev=Delta(sale.revenue, revenue_of(report, periods.prev(period), sale.store),
                       periods.PREV_LABEL[periods.grain_of(period)]),
            yoy=Delta(sale.revenue, revenue_of(report, periods.last_year(period), sale.store),
                      "전년 동기 대비"),
        )
        rows.append(row)
    rows.sort(key=lambda r: r.revenue, reverse=True)
    total = sum(r.revenue for r in rows)
    for row in rows:
        row.share = ratio(row.revenue, total) * 100
    return rows


# --------------------------------------------------------------------------
# 채널별
# --------------------------------------------------------------------------

@dataclass
class ChannelRow:
    channel: str
    label: str = ""
    spend: int = 0
    impressions: int = 0
    clicks: int = 0
    conversions: float = 0.0
    revenue: int = 0
    spend_share: float = 0.0
    prev_spend: int = 0

    @property
    def ctr(self) -> float:
        return ratio(self.clicks, self.impressions) * 100

    @property
    def cpc(self) -> float:
        return ratio(self.spend, self.clicks)

    @property
    def cvr(self) -> float:
        return ratio(self.conversions, self.clicks) * 100

    @property
    def cpa(self) -> float:
        """전환 1건당 비용."""
        return ratio(self.spend, self.conversions)

    @property
    def roas(self) -> float:
        return ratio(self.revenue, self.spend)

    @property
    def has_revenue(self) -> bool:
        """전환매출을 주지 않는 채널(브랜딩·플레이스광고 등)이 있습니다."""
        return bool(self.revenue)


def channel_rows(report: Report, period: str = "") -> list[ChannelRow]:
    """채널별 한 줄 요약. 광고비 큰 순서."""
    period = period or report.period
    merged: dict[str, ChannelRow] = {}
    for ad in report.ads_for(period):
        row = merged.setdefault(ad.channel, ChannelRow(ad.channel, channel_label(ad.channel)))
        row.spend += ad.spend
        row.impressions += ad.impressions
        row.clicks += ad.clicks
        row.conversions += ad.conversions
        row.revenue += ad.revenue

    prev_period = periods.prev(period)
    for ad in report.ads_for(prev_period):
        if ad.channel in merged:
            merged[ad.channel].prev_spend += ad.spend

    rows = sorted(merged.values(), key=lambda r: r.spend, reverse=True)
    total = sum(r.spend for r in rows)
    for row in rows:
        row.spend_share = ratio(row.spend, total) * 100
    return rows


@dataclass
class FunnelStage:
    label: str
    value: float
    rate: float = 0.0      # 직전 단계 대비 전환율(%)
    unit: str = ""


def funnel(report: Report, period: str = "") -> list[FunnelStage]:
    """노출 -> 클릭 -> 전환. 광고 전체를 합친 퍼널."""
    period = period or report.period
    rows = channel_rows(report, period)
    impressions = sum(r.impressions for r in rows)
    clicks = sum(r.clicks for r in rows)
    conversions = sum(r.conversions for r in rows)
    if not impressions and not clicks:
        return []
    return [
        FunnelStage("노출", impressions, 100.0, "회"),
        FunnelStage("클릭", clicks, ratio(clicks, impressions) * 100, "회"),
        FunnelStage("전환", conversions, ratio(conversions, clicks) * 100, "건"),
    ]


# --------------------------------------------------------------------------
# 네이버 유입
# --------------------------------------------------------------------------

@dataclass
class TrafficSummary:
    views: int = 0
    actions: int = 0
    saves: int = 0
    reviews: int = 0
    review_score: float = 0.0
    inflow: dict[str, int] = field(default_factory=dict)
    keywords: list[dict] = field(default_factory=list)
    views_delta: Delta = field(default_factory=Delta)
    action_rate_delta: Delta = field(default_factory=Delta)

    @property
    def action_rate(self) -> float:
        """조회 대비 행동 전환율(%) — 예약·전화·길찾기 기준."""
        return ratio(self.actions, self.views) * 100

    @property
    def has_data(self) -> bool:
        return bool(self.views or self.actions)


def _traffic_totals(rows: list[TrafficPoint]) -> tuple[int, int]:
    return sum(t.views for t in rows), sum(t.actions for t in rows)


def traffic_summary(report: Report, period: str = "") -> TrafficSummary:
    """네이버 플레이스 유입 요약 (전 매장 합)."""
    period = period or report.period
    rows = report.traffic_for(period)
    summary = TrafficSummary()
    if not rows:
        return summary

    summary.views, summary.actions = _traffic_totals(rows)
    summary.saves = sum(t.saves for t in rows)
    summary.reviews = sum(t.reviews for t in rows)
    scored = [t.review_score for t in rows if t.review_score]
    summary.review_score = round(sum(scored) / len(scored), 2) if scored else 0.0

    for row in rows:
        for key, value in row.inflow.items():
            summary.inflow[key] = summary.inflow.get(key, 0) + value

    counts: dict[str, int] = {}
    for row in rows:
        for kw in row.keywords:
            counts[kw["term"]] = counts.get(kw["term"], 0) + kw["count"]
    summary.keywords = [
        {"term": term, "count": count}
        for term, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    ][:8]

    prev_rows = report.traffic_for(periods.prev(period))
    prev_views, prev_actions = _traffic_totals(prev_rows)
    summary.views_delta = Delta(summary.views, prev_views,
                                periods.PREV_LABEL[periods.grain_of(period)])
    summary.action_rate_delta = Delta(
        summary.action_rate, ratio(prev_actions, prev_views) * 100, "전기 대비"
    )
    return summary


# --------------------------------------------------------------------------
# 한 장 요약
# --------------------------------------------------------------------------

@dataclass
class Summary:
    period: str = ""
    revenue: int = 0
    orders: int = 0
    ticket: int = 0
    spend: int = 0
    ad_revenue: int = 0
    prev: Delta = field(default_factory=Delta)
    yoy: Delta = field(default_factory=Delta)
    spend_prev: Delta = field(default_factory=Delta)
    traffic: TrafficSummary = field(default_factory=TrafficSummary)
    stores: list[StoreRow] = field(default_factory=list)
    channels: list[ChannelRow] = field(default_factory=list)

    @property
    def ad_ratio(self) -> float:
        """매출 대비 광고비 비율(%). 외식업에서 가장 먼저 보는 방어선입니다."""
        return ratio(self.spend, self.revenue) * 100

    @property
    def blended_roas(self) -> float:
        """전체 매출 ÷ 전체 광고비. 채널 리포트 합보다 이 값이 실제에 가깝습니다."""
        return ratio(self.revenue, self.spend)

    @property
    def reported_roas(self) -> float:
        """채널 리포트가 스스로 집계한 전환매출 기준 ROAS."""
        return ratio(self.ad_revenue, self.spend)

    @property
    def cac(self) -> float:
        """결제 1건당 광고비."""
        return ratio(self.spend, self.orders)

    @property
    def best_store(self) -> StoreRow | None:
        ranked = [s for s in self.stores if s.prev.available]
        return max(ranked, key=lambda s: s.prev.pct) if ranked else None

    @property
    def worst_store(self) -> StoreRow | None:
        ranked = [s for s in self.stores if s.prev.available]
        return min(ranked, key=lambda s: s.prev.pct) if ranked else None

    @property
    def best_channel(self) -> ChannelRow | None:
        ranked = [c for c in self.channels if c.has_revenue and c.spend]
        return max(ranked, key=lambda c: c.roas) if ranked else None

    @property
    def worst_channel(self) -> ChannelRow | None:
        ranked = [c for c in self.channels if c.has_revenue and c.spend]
        return min(ranked, key=lambda c: c.roas) if ranked else None


def summarize(report: Report, period: str = "") -> Summary:
    """보고서 한 부에 필요한 지표를 한 번에 계산합니다."""
    period = period or report.period
    total = totals(report, period)
    grain = periods.grain_of(period) if period else periods.WEEKLY

    summary = Summary(
        period=period,
        revenue=total.revenue,
        orders=total.orders,
        ticket=total.ticket,
        spend=ad_spend(report, period),
        ad_revenue=ad_revenue(report, period),
        prev=Delta(total.revenue, revenue_of(report, periods.prev(period)),
                   periods.PREV_LABEL[grain]),
        yoy=Delta(total.revenue, revenue_of(report, periods.last_year(period)),
                  "전년 동기 대비"),
        spend_prev=Delta(ad_spend(report, period), ad_spend(report, periods.prev(period)),
                         periods.PREV_LABEL[grain]),
        traffic=traffic_summary(report, period),
        stores=store_rows(report, period),
        channels=channel_rows(report, period),
    )
    return summary
