"""지표 -> 슬라이드.

한 슬라이드 = 한 질문에 대한 답. 순서는 보고 자리에서 실제로 나오는 질문 순서입니다.

    1 표지          누구의 · 언제 실적인가
    2 한눈에        이번 기간 결론은 무엇인가
    3 매출 추이     흐름이 좋아지고 있는가 (전년 대비 포함)
    4 매장별        어느 매장이 끌고 어느 매장이 빠지는가
    5 채널 효율     광고비를 어디에 썼고 무엇이 남았는가
    6 광고 퍼널     어느 단계에서 새는가
    7 네이버 유입   찾아오는 사람은 늘고 있는가, 행동으로 이어지는가
    8 인사이트·액션 그래서 다음 기간에 무엇을 할 것인가
    9 부록          원본 캡처와 읽지 못한 항목
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from . import charts, fmt, periods, theme
from .charts import Chart
from .insights import Action, Callout, Insights
from .metrics import Summary, funnel as funnel_metric
from .models import Report, inflow_label

# 슬라이드 폭을 12칸으로 나눠 씁니다.
FULL, HALF, THIRD, TWO_THIRDS = 12, 6, 4, 8

# 카드 안쪽 폭(px). SVG 는 100% 로 늘어나므로, 칸 폭과 다른 값을 주면
# 차트마다 글자 크기가 달라 보입니다. 여기 값에 맞춰 그립니다.
CHART_FULL = 1700
CHART_TWO_THIRDS = 1120
CHART_HALF = 810
CHART_THIRD = 530


@dataclass
class Kpi:
    """지표 타일 하나."""

    label: str = ""
    value: str = ""
    unit: str = ""
    delta: str = ""
    delta_note: str = ""
    delta_color: str = theme.INK_MUTED
    value_color: str = ""       # 값 자체가 증감인 타일에서만 씁니다
    hint: str = ""
    spark: str = ""


@dataclass
class Block:
    """슬라이드 안의 한 덩어리."""

    kind: str = "text"          # kpis | chart | table | callouts | actions | text | images | meter | group
    span: int = FULL
    title: str = ""
    subtitle: str = ""
    text: str = ""
    kpis: list[Kpi] = field(default_factory=list)
    chart: Chart | None = None
    table_head: list[str] = field(default_factory=list)
    table_rows: list[list[str]] = field(default_factory=list)
    table_align: list[str] = field(default_factory=list)
    callouts: list[Callout] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    children: list["Block"] = field(default_factory=list)   # kind="group" 일 때 세로로 쌓입니다
    footnote: str = ""


@dataclass
class Slide:
    kind: str = "content"
    eyebrow: str = ""
    title: str = ""
    subtitle: str = ""
    blocks: list[Block] = field(default_factory=list)
    footnote: str = ""


@dataclass
class Deck:
    title: str = ""
    brand: str = ""
    period_label: str = ""
    generated: str = ""
    slides: list[Slide] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.slides)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------
# 표기 도우미
# --------------------------------------------------------------------------

def _delta_kpi(delta, *, up_is_good: bool = True) -> tuple[str, str, str]:
    """Delta -> (표기, 설명, 색). 비교 대상이 없으면 빈 값."""
    if not delta.available:
        return "", "비교 기간 자료 없음", theme.INK_MUTED
    return (
        fmt.signed_pct(delta.pct),
        delta.label,
        theme.delta_color(delta.direction, up_is_good=up_is_good),
    )


def _won_axis(value: float) -> str:
    return fmt.won_compact(value, unit=False)


# --------------------------------------------------------------------------
# 슬라이드 하나씩
# --------------------------------------------------------------------------

def cover_slide(report: Report, summary: Summary) -> Slide:
    stores = ", ".join(report.stores) if report.stores else "전체"
    return Slide(
        kind="cover",
        eyebrow=report.brand or "직영점 리포트",
        title=report.title,
        subtitle=periods.label(summary.period),
        blocks=[Block(kind="text", text=f"대상 매장 {len(report.stores) or 1}개 · {stores}")],
        footnote=f"작성 {date.today().isoformat()}",
    )


def summary_slide(report: Report, summary: Summary, insights: Insights) -> Slide:
    grain = periods.grain_of(summary.period)
    prev_pct, prev_note, prev_color = _delta_kpi(summary.prev)
    yoy_pct, yoy_note, yoy_color = _delta_kpi(summary.yoy)
    spend_pct, spend_note, spend_color = _delta_kpi(summary.spend_prev, up_is_good=False)

    kpis = [
        Kpi(label="매출", value=fmt.won_compact(summary.revenue), unit="원",
            delta=prev_pct, delta_note=prev_note, delta_color=prev_color),
        Kpi(label="전년 동기 대비", value=yoy_pct or "—", value_color=yoy_color,
            hint=(f"전년 {fmt.won_compact(summary.yoy.base)}원"
                  if summary.yoy.available else yoy_note)),
        Kpi(label="객단가", value=fmt.num(summary.ticket), unit="원",
            hint=f"결제 {fmt.num(summary.orders)}건"),
        Kpi(label="광고비", value=fmt.won_compact(summary.spend), unit="원",
            delta=spend_pct, delta_note=spend_note, delta_color=spend_color),
        Kpi(label="매출 대비 광고비", value=fmt.pct(summary.ad_ratio),
            hint=f"목표 상한 {fmt.pct(report.goal.ad_ratio)}" if report.goal.ad_ratio else "",
            delta_color=(theme.CRITICAL if report.goal.ad_ratio
                         and summary.ad_ratio > report.goal.ad_ratio else theme.INK_MUTED)),
        Kpi(label="ROAS (실매출 기준)", value=fmt.multiple(summary.blended_roas),
            hint=f"채널 리포트 기준 {fmt.multiple(summary.reported_roas)}"
                 if summary.reported_roas else ""),
    ]

    side: list[Block] = []
    if report.goal.revenue:
        rate = summary.revenue / report.goal.revenue * 100
        side.append(Block(
            kind="meter", title="매출 목표 달성률",
            text=f"{rate:.0f}%",
            subtitle=(f"{fmt.won_compact(summary.revenue)}원 / "
                      f"목표 {fmt.won_compact(report.goal.revenue)}원"),
            chart=charts.meter(summary.revenue, report.goal.revenue, width=CHART_THIRD),
        ))
    if summary.stores:
        side.append(Block(
            kind="table", title="매장별 매출 비중",
            table_head=["매장", "매출", "비중"],
            table_align=["left", "right", "right"],
            table_rows=[[s.store, f"{fmt.won_compact(s.revenue)}원", f"{s.share:.0f}%"]
                        for s in summary.stores],
        ))

    # 코멘트 개수에 맞춰 오른쪽 칸을 한 덩어리로 묶습니다 — 따로 두면 줄이 넘쳐
    # 표가 슬라이드 밖으로 밀립니다.
    blocks = [
        Block(kind="kpis", span=FULL, kpis=kpis),
        Block(kind="callouts", span=TWO_THIRDS, title="이번 기간에 확인된 것",
              callouts=insights.callouts[:4]),
        Block(kind="group", span=THIRD, children=side),
    ]

    return Slide(
        kind="summary",
        eyebrow="한눈에",
        title=insights.headline,
        subtitle=f"{periods.label(summary.period)} · {periods.GRAIN_LABEL[grain]} 기준",
        blocks=blocks,
        footnote="ROAS(실매출 기준) = 전체 매출 ÷ 전체 광고비. 채널 리포트 합계보다 보수적인 값입니다.",
    )


def trend_slide(report: Report, summary: Summary, series, ly_series) -> Slide:
    labels = [p.label for p in series]
    columns = charts.columns(
        labels,
        [("올해", [p.revenue for p in series]),
         ("전년 동기", [p.revenue for p in ly_series])]
        if any(p.revenue for p in ly_series) else [("매출", [p.revenue for p in series])],
        width=CHART_FULL, height=420,
        value_fmt=lambda v: f"{fmt.won_compact(v)}원",
        tick_fmt=_won_axis,
    )
    # 기간을 열로 눕힙니다 — 기간마다 한 줄씩 쌓으면 슬라이드 한 장을 넘어갑니다.
    diffs = [
        ((p.revenue - ly.revenue) / ly.revenue * 100) if ly.revenue else None
        for p, ly in zip(series, ly_series)
    ]
    rows = [
        ["올해", *[f"{fmt.won_compact(p.revenue)}원" for p in series]],
        ["전년 동기", *[f"{fmt.won_compact(p.revenue)}원" if p.revenue else "—"
                    for p in ly_series]],
        ["전년비", *[fmt.signed_pct(d) if d is not None else "—" for d in diffs]],
    ]
    return Slide(
        kind="trend",
        eyebrow="매출 추이",
        title=f"최근 {len(series)}개 기간 흐름",
        subtitle=f"{periods.GRAIN_LABEL[periods.grain_of(summary.period)]} 매출 · 전년 동기 비교",
        blocks=[
            Block(kind="chart", span=FULL, chart=columns),
            Block(kind="table", span=FULL, table_head=["구분", *labels],
                  table_align=["left", *["right"] * len(labels)], table_rows=rows),
        ],
    )


def stores_slide(report: Report, summary: Summary) -> Slide:
    rows = summary.stores
    bar = charts.bars(
        [(s.store, s.revenue) for s in rows],
        width=CHART_HALF,
        value_fmt=lambda v: f"{fmt.won_compact(v)}원",
        notes=[f"비중 {s.share:.0f}%" for s in rows],
    )
    delta = charts.diverging(
        [(s.store, s.prev.pct) for s in rows if s.prev.available], width=CHART_HALF
    )
    # 매장별로 안 나뉘는 지표는 열 자체를 세우지 않습니다 — "—" 만 늘어선 열은 지면 낭비입니다.
    has_spend = any(s.spend for s in rows)
    has_traffic = any(s.traffic_views for s in rows)
    head = ["매장", "매출", "비중", summary.prev.label, "전년 동기", "객단가"]
    align = ["left", "right", "right", "right", "right", "right"]
    if has_spend:
        head += ["광고비", "매출 대비 광고비"]
        align += ["right", "right"]
    if has_traffic:
        head += ["플레이스 조회", "행동"]
        align += ["right", "right"]

    table = []
    for s in rows:
        row = [
            s.store,
            f"{fmt.won_compact(s.revenue)}원",
            f"{s.share:.0f}%",
            fmt.signed_pct(s.prev.pct) if s.prev.available else "—",
            fmt.signed_pct(s.yoy.pct) if s.yoy.available else "—",
            fmt.num(s.ticket),
        ]
        if has_spend:
            row += [f"{fmt.won_compact(s.spend)}원" if s.spend else "—",
                    fmt.pct(s.ad_ratio) if s.spend else "—"]
        if has_traffic:
            row += [fmt.num(s.traffic_views), fmt.num(s.traffic_actions)]
        table.append(row)
    blocks = [
        Block(kind="chart", span=HALF, title="매장별 매출", chart=bar),
        Block(kind="chart", span=HALF,
              title=f"매장별 {summary.prev.label} 증감",
              subtitle="파랑은 증가, 빨강은 감소", chart=delta),
        Block(kind="table", span=FULL, table_head=head, table_align=align,
              table_rows=table,
              footnote=("" if has_spend else
                        "광고 리포트가 매장별로 나뉘지 않아 광고비 열은 넣지 않았습니다.")),
    ]
    return Slide(
        kind="stores",
        eyebrow="매장별",
        title="어느 매장이 끌고, 어디가 빠졌나",
        subtitle=periods.label(summary.period),
        blocks=blocks,
    )


def channels_slide(report: Report, summary: Summary) -> Slide:
    rows = summary.channels
    spend_mix = charts.stacked(
        [(c.label, c.spend) for c in rows], width=CHART_FULL, height=56,
        value_fmt=lambda v: f"{fmt.won_compact(v)}원",
    )
    roas_rows = [(c.label, c.roas) for c in rows if c.has_revenue]
    roas = charts.bars(
        roas_rows, width=CHART_HALF,
        value_fmt=lambda v: fmt.multiple(v),
        target=report.goal.roas,
        target_label=f"목표 {fmt.multiple(report.goal.roas)}" if report.goal.roas else "",
        notes=[f"CPA {fmt.won(c.cpa)}" for c in rows if c.has_revenue],
    ) if roas_rows else None

    table = [
        [
            c.label,
            f"{fmt.won_compact(c.spend)}원",
            f"{c.spend_share:.0f}%",
            fmt.num(c.impressions),
            fmt.num(c.clicks),
            fmt.pct(c.ctr, 2),
            fmt.num(c.cpc),
            fmt.num(c.conversions),
            fmt.pct(c.cvr, 2),
            fmt.num(c.cpa),
            fmt.multiple(c.roas) if c.has_revenue else "—",
        ]
        for c in rows
    ]
    blocks = [
        Block(kind="chart", span=FULL, title="광고비 배분", chart=spend_mix),
    ]
    if roas:
        blocks.append(Block(kind="chart", span=HALF, title="채널별 ROAS",
                            subtitle="채널 리포트가 집계한 전환매출 기준", chart=roas))
    blocks.append(Block(
        kind="table", span=HALF if roas else FULL,
        title="채널 성과 상세",
        table_head=["채널", "광고비", "비중", "노출", "클릭", "CTR", "CPC",
                    "전환", "CVR", "CPA", "ROAS"],
        table_align=["left"] + ["right"] * 10,
        table_rows=table,
        footnote="전환매출을 제공하지 않는 채널은 ROAS 를 —로 둡니다. 합산 평균에 넣지 않습니다.",
    ))
    return Slide(
        kind="channels",
        eyebrow="마케팅 채널 효율",
        title="광고비를 어디에 썼고, 무엇이 남았나",
        subtitle=f"{periods.label(summary.period)} · 총 {fmt.won_compact(summary.spend)}원",
        blocks=blocks,
    )


def funnel_slide(report: Report, summary: Summary) -> Slide:
    stages = funnel_metric(report, summary.period)
    chart = charts.funnel(
        [(s.label, s.value, s.rate, s.unit) for s in stages], width=CHART_HALF,
        value_fmt=lambda v: f"{v:,.0f}",
    )
    cpa_rows = [(c.label, c.cpa) for c in summary.channels if c.conversions]
    cpa = charts.bars(
        cpa_rows, width=CHART_HALF, value_fmt=lambda v: f"{v:,.0f}원",
        notes=[f"전환 {fmt.num(c.conversions)}건"
               for c in summary.channels if c.conversions],
    ) if cpa_rows else None

    blocks = [Block(kind="chart", span=HALF, title="광고 전체 퍼널", chart=chart)]
    if cpa:
        blocks.append(Block(kind="chart", span=HALF, title="채널별 전환 단가(CPA)",
                            subtitle="낮을수록 좋습니다", chart=cpa))

    # 퍼널 두 구간(노출→클릭, 클릭→전환)에서 어느 채널이 끌고 어디가 새는지.
    steps = [
        ("노출 → 클릭", "CTR", [c for c in summary.channels if c.impressions],
         lambda c: c.ctr, stages[1].rate if len(stages) > 1 else 0.0),
        ("클릭 → 전환", "CVR", [c for c in summary.channels if c.clicks and c.conversions],
         lambda c: c.cvr, stages[2].rate if len(stages) > 2 else 0.0),
    ]
    notes: list[Callout] = []
    for title, metric, pool, key, overall in steps:
        if len(pool) < 2:
            continue
        best, worst = max(pool, key=key), min(pool, key=key)
        notes.append(Callout(
            tone="info",
            title=f"{title} {fmt.pct(overall, 2)}",
            body=(f"{metric} 1위 {best.label} {fmt.pct(key(best), 2)} · "
                  f"최하위 {worst.label} {fmt.pct(key(worst), 2)}"),
        ))
    if notes:
        blocks.append(Block(kind="callouts", span=FULL, title="구간별로 보면",
                            callouts=notes))
    return Slide(
        kind="funnel",
        eyebrow="광고 퍼널",
        title="어느 단계에서 새고 있나",
        subtitle=periods.label(summary.period),
        blocks=blocks,
        footnote="전환 정의는 채널마다 다릅니다(예약·주문·전화). 채널 간 CPA 비교는 참고용입니다.",
    )


def naver_slide(report: Report, summary: Summary) -> Slide:
    traffic = summary.traffic
    views_pct, views_note, views_color = _delta_kpi(traffic.views_delta)
    rate_pct, rate_note, rate_color = _delta_kpi(traffic.action_rate_delta)

    kpis = [
        Kpi(label="플레이스 조회수", value=fmt.num(traffic.views), unit="회",
            delta=views_pct, delta_note=views_note, delta_color=views_color),
        Kpi(label="행동 수", value=fmt.num(traffic.actions), unit="회",
            hint="예약 · 전화 · 길찾기 합계"),
        Kpi(label="행동 전환율", value=fmt.pct(traffic.action_rate),
            delta=rate_pct, delta_note=rate_note, delta_color=rate_color),
        Kpi(label="저장", value=fmt.num(traffic.saves), unit="회"),
        Kpi(label="신규 리뷰", value=fmt.num(traffic.reviews), unit="건",
            hint=f"평점 {traffic.review_score}" if traffic.review_score else ""),
    ]
    blocks = [Block(kind="kpis", span=FULL, kpis=kpis)]

    if traffic.inflow:
        mix = charts.stacked(
            [(inflow_label(k), v) for k, v in
             sorted(traffic.inflow.items(), key=lambda kv: kv[1], reverse=True)],
            width=CHART_FULL, height=56, value_fmt=lambda v: f"{v:,.0f}회",
        )
        blocks.append(Block(kind="chart", span=FULL, title="유입 경로 구성", chart=mix))
    if traffic.keywords:
        blocks.append(Block(
            kind="table", span=HALF, title="유입 상위 검색어",
            table_head=["검색어", "유입"], table_align=["left", "right"],
            table_rows=[[k["term"], fmt.num(k["count"])] for k in traffic.keywords[:6]],
        ))
    return Slide(
        kind="naver",
        eyebrow="네이버 플레이스 유입",
        title="찾아온 사람이 행동으로 이어졌나",
        subtitle=periods.label(summary.period),
        blocks=blocks,
    )


def action_slide(report: Report, summary: Summary, insights: Insights) -> Slide:
    return Slide(
        kind="actions",
        eyebrow="인사이트 · 액션",
        title="다음 기간에 할 것",
        subtitle=insights.headline,
        blocks=[
            Block(kind="callouts", span=HALF, title="정리", callouts=insights.callouts),
            Block(kind="actions", span=HALF, title="액션 아이템", actions=insights.actions),
        ],
        footnote=("코멘트 생성: Claude" if insights.source == "claude"
                  else "코멘트 생성: 규칙 기반(지표에서 직접 도출)"),
    )


def appendix_slide(report: Report) -> Slide:
    blocks: list[Block] = []
    if report.captures:
        blocks.append(Block(kind="images", span=FULL, title="원본 캡처",
                            images=list(report.captures)))
    if report.warnings:
        blocks.append(Block(
            kind="callouts", span=FULL, title="캡처에서 읽지 못한 항목",
            callouts=[Callout(tone="warn", title="확인 필요", body=w)
                      for w in report.warnings[:6]],
        ))
    if report.notes:
        blocks.append(Block(kind="text", span=FULL, title="메모", text=report.notes))
    return Slide(
        kind="appendix",
        eyebrow="부록",
        title="원본 자료와 확인할 항목",
        blocks=blocks,
        footnote="수치가 실제와 다르면 report.json 을 고친 뒤 다시 빌드하세요.",
    )


# --------------------------------------------------------------------------
# 조립
# --------------------------------------------------------------------------

def build_deck(
    report: Report, summary: Summary, insights: Insights, *, history: int = 8
) -> Deck:
    """데이터가 있는 슬라이드만 담아 한 부를 만듭니다."""
    from .metrics import revenue_series, yoy_series

    series = revenue_series(report, period=summary.period, count=history)
    ly = yoy_series(report, series)

    slides = [cover_slide(report, summary), summary_slide(report, summary, insights)]
    if len(series) >= 2:
        slides.append(trend_slide(report, summary, series, ly))
    if report.has_store_split():
        slides.append(stores_slide(report, summary))
    if summary.channels:
        slides.append(channels_slide(report, summary))
        if funnel_metric(report, summary.period):
            slides.append(funnel_slide(report, summary))
    if summary.traffic.has_data:
        slides.append(naver_slide(report, summary))
    slides.append(action_slide(report, summary, insights))
    if report.captures or report.warnings or report.notes:
        slides.append(appendix_slide(report))

    return Deck(
        title=report.title,
        brand=report.brand,
        period_label=periods.label(summary.period),
        generated=date.today().isoformat(),
        slides=slides,
        meta={"insights": insights.source, "period": summary.period,
              "stores": report.stores, **report.meta},
    )
