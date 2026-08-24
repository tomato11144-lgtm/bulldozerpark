"""지표 -> 코멘트와 다음 액션.

기본은 규칙 기반입니다. 계산된 숫자에서만 문장을 만들기 때문에
API 키가 없어도, 호출이 실패해도 보고서는 항상 완성됩니다.
ANTHROPIC_API_KEY 가 있으면 같은 숫자를 Claude 에게 넘겨 문장을 다듬습니다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field

from . import fmt, periods
from .config import Settings
from .metrics import Summary
from .models import Report, inflow_label

log = logging.getLogger(__name__)

TONES = ("good", "warn", "critical", "info")


@dataclass
class Callout:
    """슬라이드에 박스로 들어가는 코멘트 한 개."""

    tone: str = "info"          # good | warn | critical | info
    title: str = ""
    body: str = ""

    def __post_init__(self) -> None:
        if self.tone not in TONES:
            self.tone = "info"


@dataclass
class Action:
    """다음 기간에 할 일."""

    text: str = ""
    owner: str = ""
    due: str = ""


@dataclass
class Insights:
    headline: str = ""
    callouts: list[Callout] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    source: str = "rules"       # rules | claude

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# 규칙 기반
# --------------------------------------------------------------------------

def _revenue_line(summary: Summary) -> str:
    grain = periods.GRAIN_LABEL[periods.grain_of(summary.period)]
    head = f"{periods.label(summary.period)} {grain} 매출 {fmt.won_compact(summary.revenue)}원"
    bits = []
    if summary.prev.available:
        bits.append(f"{summary.prev.label} {fmt.signed_pct(summary.prev.pct)}")
    if summary.yoy.available:
        bits.append(f"전년 동기 {fmt.signed_pct(summary.yoy.pct)}")
    return f"{head} ({', '.join(bits)})" if bits else head


def build_rule_insights(report: Report, summary: Summary) -> Insights:
    """계산된 값에서만 문장을 만듭니다. 없는 데이터는 아예 언급하지 않습니다."""
    callouts: list[Callout] = []
    actions: list[Action] = []

    # 1) 매출 방향
    if summary.prev.available:
        up = summary.prev.direction == "up"
        callouts.append(Callout(
            tone="good" if up else "warn",
            title=f"전체 매출 {fmt.signed_pct(summary.prev.pct)}",
            body=(
                f"{summary.prev.label} {fmt.won_compact(abs(summary.prev.diff))}원 "
                f"{'늘었습니다' if up else '줄었습니다'}. "
                f"객단가 {fmt.won(summary.ticket)}, 결제 {fmt.num(summary.orders)}건."
            ),
        ))

    # 2) 매장 편차 — 잘 나온 곳과 빠진 곳
    best, worst = summary.best_store, summary.worst_store
    if best and worst and best.store != worst.store:
        callouts.append(Callout(
            tone="info",
            title=f"매장 편차 {abs(best.prev.pct - worst.prev.pct):.0f}%p",
            body=(
                f"{best.store} {fmt.signed_pct(best.prev.pct)} · "
                f"{worst.store} {fmt.signed_pct(worst.prev.pct)}. "
                f"매출 1위는 {summary.stores[0].store}"
                f"({summary.stores[0].share:.0f}% 비중)입니다."
            ),
        ))
        if worst.prev.direction == "down" and worst.prev.pct < -5:
            actions.append(Action(
                text=(f"{worst.store} 하락 원인 점검 — 유입·객단가·리뷰 중 어디가 빠졌는지 "
                      f"주간 단위로 쪼개 확인"),
                owner="매장 담당", due="다음 보고 전",
            ))

    # 3) 광고비 방어선
    if summary.spend:
        limit = report.goal.ad_ratio
        over = bool(limit and summary.ad_ratio > limit)
        callouts.append(Callout(
            tone="critical" if over else "good",
            title=f"매출 대비 광고비 {fmt.pct(summary.ad_ratio)}",
            body=(
                f"광고비 {fmt.won_compact(summary.spend)}원, 실매출 기준 "
                f"{fmt.multiple(summary.blended_roas)}"
                + (f" · 목표 상한 {fmt.pct(limit)}을 넘었습니다." if over
                   else f" · 목표 상한 {fmt.pct(limit)} 안입니다." if limit else ".")
            ),
        ))

    # 4) 채널 효율
    best_ch, worst_ch = summary.best_channel, summary.worst_channel
    if best_ch and worst_ch and best_ch.channel != worst_ch.channel:
        callouts.append(Callout(
            tone="info",
            title=f"채널 효율 1위 {best_ch.label} {fmt.multiple(best_ch.roas)}",
            body=(
                f"CPA {fmt.won(best_ch.cpa)} · CTR {fmt.pct(best_ch.ctr, 2)}. "
                f"최하위는 {worst_ch.label} {fmt.multiple(worst_ch.roas)}"
                f"(CPA {fmt.won(worst_ch.cpa)})."
            ),
        ))
        target = report.goal.roas
        if target and worst_ch.roas < target:
            actions.append(Action(
                text=(f"{worst_ch.label} 예산 {fmt.won_compact(int(worst_ch.spend * 0.3))}원 "
                      f"(30%)을 {best_ch.label}로 이관 후 2주 재측정"),
                owner="마케팅", due="이번 주",
            ))

    # 5) 네이버 유입 -> 행동
    traffic = summary.traffic
    if traffic.has_data:
        top_path = max(traffic.inflow.items(), key=lambda kv: kv[1], default=None)
        body = f"조회 {fmt.num(traffic.views)}회 → 예약·전화·길찾기 {fmt.num(traffic.actions)}회"
        if top_path:
            share = top_path[1] / max(sum(traffic.inflow.values()), 1) * 100
            body += f". 유입 1위 경로는 {inflow_label(top_path[0])}({share:.0f}%)."
        callouts.append(Callout(
            tone="good" if traffic.action_rate >= 8 else "warn",
            title=f"플레이스 행동 전환율 {fmt.pct(traffic.action_rate)}",
            body=body,
        ))
        if traffic.action_rate < 8:
            actions.append(Action(
                text="플레이스 대표사진·메뉴판·영업시간 최신화 후 행동 전환율 재측정",
                owner="매장 담당", due="2주 내",
            ))

    # 6) 목표 달성률
    if report.goal.revenue:
        rate = summary.revenue / report.goal.revenue * 100
        callouts.append(Callout(
            tone="good" if rate >= 100 else "warn" if rate >= 90 else "critical",
            title=f"매출 목표 달성률 {fmt.pct(rate, 0)}",
            body=(f"목표 {fmt.won_compact(report.goal.revenue)}원 대비 "
                  f"{fmt.won_compact(summary.revenue - report.goal.revenue)}원."),
        ))

    if not actions:
        actions.append(Action(text="이번 기간에는 구조 변경 없이 현재 배분 유지",
                              owner="마케팅", due="다음 보고"))

    return Insights(
        headline=_revenue_line(summary),
        callouts=callouts[:6],
        actions=actions[:5],
        source="rules",
    )


# --------------------------------------------------------------------------
# Claude 로 문장 다듬기
# --------------------------------------------------------------------------

SYSTEM = """\
당신은 외식·리테일 직영점의 마케팅·매출 데이터를 읽고 경영진 보고 문장을 쓰는 분석가입니다.

규칙
- 주어진 숫자만 씁니다. 자료에 없는 수치·매장·채널·기간을 절대 만들지 않습니다.
- 숫자는 받은 값을 그대로 인용합니다. 반올림해서 새로 계산하지 않습니다.
- "대박", "완벽한", "폭발적" 같은 과장 표현을 쓰지 않습니다.
- 원인을 단정하지 않습니다. 데이터로 확인된 것과 추정을 구분해 씁니다.
  (추정이면 "~로 보입니다", "확인이 필요합니다" 로 끝냅니다)
- 액션은 실행 가능해야 합니다. 대상·행동·기한이 한 문장 안에 들어갑니다.
- 존댓말, 보고서 문체. 문장은 짧게.
"""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headline", "callouts", "actions"],
    "properties": {
        "headline": {"type": "string", "description": "핵심 한 줄. 40자 내외"},
        "callouts": {
            "type": "array", "minItems": 3, "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["tone", "title", "body"],
                "properties": {
                    "tone": {"type": "string", "enum": list(TONES)},
                    "title": {"type": "string", "description": "지표 한 줄. 20자 내외"},
                    "body": {"type": "string", "description": "2문장 이내 해석"},
                },
            },
        },
        "actions": {
            "type": "array", "minItems": 2, "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "owner", "due"],
                "properties": {
                    "text": {"type": "string"},
                    "owner": {"type": "string", "description": "담당 (예: 마케팅, 매장 담당)"},
                    "due": {"type": "string", "description": "기한 (예: 이번 주, 2주 내)"},
                },
            },
        },
    },
}


def metrics_payload(report: Report, summary: Summary) -> dict:
    """모델에 넘길 숫자 묶음. 계산은 전부 끝난 상태로 건넵니다."""
    return {
        "기간": periods.label(summary.period),
        "매출": {
            "합계": summary.revenue,
            "전기대비_퍼센트": round(summary.prev.pct, 1) if summary.prev.available else None,
            "전년대비_퍼센트": round(summary.yoy.pct, 1) if summary.yoy.available else None,
            "결제건수": summary.orders,
            "객단가": summary.ticket,
            "목표": report.goal.revenue or None,
        },
        "광고": {
            "총광고비": summary.spend,
            "매출대비_광고비_퍼센트": round(summary.ad_ratio, 1),
            "실매출기준_ROAS": round(summary.blended_roas, 2),
            "채널리포트_ROAS": round(summary.reported_roas, 2),
            "목표_ROAS": report.goal.roas or None,
            "채널별": [
                {
                    "채널": c.label, "광고비": c.spend, "노출": c.impressions,
                    "클릭": c.clicks, "CTR_퍼센트": round(c.ctr, 2),
                    "CPC": round(c.cpc), "전환": c.conversions,
                    "CVR_퍼센트": round(c.cvr, 2), "CPA": round(c.cpa),
                    "ROAS": round(c.roas, 2) if c.has_revenue else None,
                }
                for c in summary.channels
            ],
        },
        "매장별": [
            {
                "매장": s.store, "매출": s.revenue, "비중_퍼센트": round(s.share, 1),
                "전기대비_퍼센트": round(s.prev.pct, 1) if s.prev.available else None,
                "전년대비_퍼센트": round(s.yoy.pct, 1) if s.yoy.available else None,
                "객단가": s.ticket, "광고비": s.spend,
                "매출대비_광고비_퍼센트": round(s.ad_ratio, 1),
            }
            for s in summary.stores
        ],
        "네이버_플레이스": {
            "조회수": summary.traffic.views,
            "행동수_예약전화길찾기": summary.traffic.actions,
            "행동_전환율_퍼센트": round(summary.traffic.action_rate, 1),
            "유입경로": {inflow_label(k): v for k, v in summary.traffic.inflow.items()},
            "상위검색어": summary.traffic.keywords[:5],
        } if summary.traffic.has_data else None,
        "읽지_못한_항목": report.warnings,
    }


def build_insights(
    report: Report,
    summary: Summary,
    *,
    settings: Settings | None = None,
    offline: bool = False,
) -> Insights:
    """코멘트를 만듭니다. 실패하면 규칙 기반 결과를 그대로 돌려줍니다."""
    fallback = build_rule_insights(report, summary)
    settings = settings or Settings.from_env()
    if offline or not settings.has_llm:
        return fallback

    try:
        return _with_claude(report, summary, settings)
    except Exception as exc:  # noqa: BLE001 - 코멘트 때문에 보고서를 못 내면 안 됩니다
        log.warning("Claude 코멘트 생성 실패(%s) — 규칙 기반 문장을 씁니다.", exc)
        return fallback


def _with_claude(report: Report, summary: Summary, settings: Settings) -> Insights:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    payload = json.dumps(metrics_payload(report, summary), ensure_ascii=False, indent=2)
    user = (
        f"{report.brand or '직영점'} {periods.label(summary.period)} 실적입니다.\n"
        "아래 계산된 지표만 근거로 보고용 코멘트와 다음 액션을 써 주세요.\n"
        "금액은 원 단위 정수입니다.\n\n"
        f"```json\n{payload}\n```"
    )
    response = client.messages.create(
        model=settings.model,
        max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
        thinking={"type": "adaptive"},
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
    )
    if getattr(response, "stop_reason", None) == "refusal":
        raise RuntimeError(f"모델이 응답을 거부했습니다: {getattr(response, 'stop_details', None)}")

    text = next((b.text for b in response.content if b.type == "text"), "")
    data = json.loads(text or "{}")
    return Insights(
        headline=(data.get("headline") or "").strip() or _revenue_line(summary),
        callouts=[Callout(**{k: str(v).strip() for k, v in c.items()})
                  for c in data.get("callouts", [])][:6],
        actions=[Action(**{k: str(v).strip() for k, v in a.items()})
                 for a in data.get("actions", [])][:5],
        source="claude",
    )
