"""기간 문자열 한 가지 규칙.

    2026-08-24   일간
    2026-W33     주간 (ISO 주차)
    2026-08      월간
    2026         연간

전주/전월 대비와 전년 동기 대비를 이 문자열만 보고 계산합니다.
주간 전년 동기는 '52주 전 같은 요일'(364일 전)로 잡습니다 —
주차 번호를 그대로 빼면 해마다 요일 구성이 어긋나 유통업 비교가 망가집니다.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

DAILY = "daily"
WEEKLY = "weekly"
MONTHLY = "monthly"
YEARLY = "yearly"
GRAINS = (DAILY, WEEKLY, MONTHLY, YEARLY)

GRAIN_LABEL = {
    DAILY: "일간",
    WEEKLY: "주간",
    MONTHLY: "월간",
    YEARLY: "연간",
}
# 전기 대비를 부르는 이름 (WoW / MoM / YoY)
PREV_LABEL = {
    DAILY: "전일 대비",
    WEEKLY: "전주 대비",
    MONTHLY: "전월 대비",
    YEARLY: "전년 대비",
}

_DAILY_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_WEEKLY_RE = re.compile(r"^(\d{4})-W(\d{1,2})$", re.IGNORECASE)
_MONTHLY_RE = re.compile(r"^(\d{4})-(\d{1,2})$")
_YEARLY_RE = re.compile(r"^(\d{4})$")


class PeriodError(ValueError):
    """알 수 없는 기간 표기."""


def grain_of(period: str) -> str:
    """기간 문자열이 어떤 단위인지."""
    p = (period or "").strip()
    if _DAILY_RE.match(p):
        return DAILY
    if _WEEKLY_RE.match(p):
        return WEEKLY
    if _MONTHLY_RE.match(p):
        return MONTHLY
    if _YEARLY_RE.match(p):
        return YEARLY
    raise PeriodError(f"기간 표기를 알 수 없습니다: {period!r} (예: 2026-W33, 2026-08)")


def normalize(period: str) -> str:
    """2026-8 -> 2026-08, 2026-w3 -> 2026-W03 처럼 표기를 통일합니다."""
    p = (period or "").strip()
    if m := _WEEKLY_RE.match(p):
        return f"{int(m.group(1)):04d}-W{int(m.group(2)):02d}"
    if m := _MONTHLY_RE.match(p):
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    grain_of(p)          # 나머지는 형식 검증만
    return p


def start_date(period: str) -> date:
    """기간의 첫날."""
    p = normalize(period)
    if m := _DAILY_RE.match(p):
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if m := _WEEKLY_RE.match(p):
        return date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    if m := _MONTHLY_RE.match(p):
        return date(int(m.group(1)), int(m.group(2)), 1)
    return date(int(p), 1, 1)


def end_date(period: str) -> date:
    """기간의 마지막 날."""
    p = normalize(period)
    grain = grain_of(p)
    start = start_date(p)
    if grain == DAILY:
        return start
    if grain == WEEKLY:
        return start + timedelta(days=6)
    if grain == MONTHLY:
        year, month = start.year, start.month
        return date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    return date(start.year, 12, 31)


def _from_date(d: date, grain: str) -> str:
    if grain == DAILY:
        return d.isoformat()
    if grain == WEEKLY:
        iso = d.isocalendar()
        return f"{iso.year:04d}-W{iso.week:02d}"
    if grain == MONTHLY:
        return f"{d.year:04d}-{d.month:02d}"
    return f"{d.year:04d}"


def prev(period: str) -> str:
    """직전 기간 (전일/전주/전월/전년)."""
    p = normalize(period)
    grain = grain_of(p)
    start = start_date(p)
    if grain == DAILY:
        return _from_date(start - timedelta(days=1), grain)
    if grain == WEEKLY:
        return _from_date(start - timedelta(days=7), grain)
    if grain == MONTHLY:
        return _from_date(start - timedelta(days=1), grain)
    return f"{start.year - 1:04d}"


def last_year(period: str) -> str:
    """전년 동기. 주간은 364일 전(=52주 전 같은 요일)."""
    p = normalize(period)
    grain = grain_of(p)
    start = start_date(p)
    if grain == WEEKLY:
        return _from_date(start - timedelta(days=364), grain)
    if grain == DAILY:
        return _from_date(start - timedelta(days=364), grain)
    if grain == MONTHLY:
        return f"{start.year - 1:04d}-{start.month:02d}"
    return f"{start.year - 1:04d}"


def series_back(period: str, count: int) -> list[str]:
    """period 를 마지막으로 하는 연속 기간 목록 (오래된 것부터)."""
    out = [normalize(period)]
    for _ in range(max(0, count - 1)):
        out.append(prev(out[-1]))
    return list(reversed(out))


def label(period: str, *, short: bool = False) -> str:
    """사람이 읽는 기간 이름."""
    p = normalize(period)
    grain = grain_of(p)
    start, end = start_date(p), end_date(p)
    if grain == DAILY:
        return f"{start.month}/{start.day}" if short else f"{start.year}년 {start.month}월 {start.day}일"
    if grain == WEEKLY:
        week = int(p.split("W")[1])
        if short:
            return f"{week}주"
        return (
            f"{start.year}년 {week}주차 "
            f"({start.month}/{start.day}~{end.month}/{end.day})"
        )
    if grain == MONTHLY:
        return f"{start.month}월" if short else f"{start.year}년 {start.month}월"
    return f"{start.year}" if short else f"{start.year}년"
