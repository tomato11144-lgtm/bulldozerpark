"""차트 = 인라인 SVG.

자바스크립트도 외부 라이브러리도 쓰지 않습니다. 슬라이드는 PNG/PDF 로 나가고,
브라우저 없이 열어도 그대로 보여야 하기 때문입니다.

공통 규칙(전부 여기서만 지키면 됩니다)
  · 막대 두께 24px 상한, 데이터 끝만 4px 라운드, 바닥은 각지게
  · 선 2px, 마커 지름 8px 이상 + 바탕색 2px 링
  · 격자·축은 실선 헤어라인, 바탕에서 한 단계만 떨어진 회색
  · 맞닿는 면 사이에는 바탕색 2px 간격 (테두리를 그리지 않습니다)
  · 값 라벨은 골라서만 답니다 (끝점·최댓값·이야기의 주인공)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Sequence

from . import theme

# 라벨이 막대 안에 들어가는지 재는 대략치. 한글은 한 글자 = 폰트 크기와 거의 같고,
# 라틴·숫자는 그 절반쯤입니다. 정확한 측정 대신 보수적으로 잡습니다.
_WIDE = 1.0
_NARROW = 0.56


def text_width(text: str, size: float) -> float:
    total = 0.0
    for ch in text:
        total += _WIDE if ord(ch) > 0x2E80 else _NARROW
    return total * size


@dataclass
class LegendItem:
    label: str
    color: str
    value: str = ""


@dataclass
class Chart:
    """SVG 한 장 + 그 옆에 붙는 것들.

    범례와 표는 HTML 로 그립니다 — 글자는 SVG 밖에 있어야 크기가 안 깨집니다.
    """

    svg: str = ""
    legend: list[LegendItem] = field(default_factory=list)
    caption: str = ""
    table_head: list[str] = field(default_factory=list)
    table_rows: list[list[str]] = field(default_factory=list)

    @property
    def has_legend(self) -> bool:
        return len(self.legend) >= 2


# --------------------------------------------------------------------------
# SVG 조각
# --------------------------------------------------------------------------

def _svg(width: float, height: float, body: str) -> str:
    return (
        f'<svg viewBox="0 0 {width:.0f} {height:.0f}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'style="display:block;overflow:visible">{body}</svg>'
    )


def _text(x: float, y: float, content: str, *, size: float = 20,
          fill: str = theme.INK_SUB, weight: int = 400, anchor: str = "start",
          tabular: bool = False) -> str:
    extra = ' style="font-variant-numeric:tabular-nums"' if tabular else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:.0f}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}"{extra}>{escape(content)}</text>'
    )


def _bar_up(x: float, y: float, w: float, h: float, fill: str, radius: float = 4) -> str:
    """바닥에서 자라는 세로 막대. 위쪽 끝만 둥글게."""
    if h <= 0.5:
        return ""
    r = min(radius, w / 2, h)
    return (
        f'<path d="M{x:.1f},{y + h:.1f} L{x:.1f},{y + r:.1f} '
        f'Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} L{x + w - r:.1f},{y:.1f} '
        f'Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} L{x + w:.1f},{y + h:.1f} Z" '
        f'fill="{fill}"/>'
    )


def _bar_right(x: float, y: float, w: float, h: float, fill: str, radius: float = 4) -> str:
    """왼쪽 기준선에서 자라는 가로 막대. 오른쪽 끝만 둥글게."""
    if w <= 0.5:
        return ""
    r = min(radius, h / 2, w)
    return (
        f'<path d="M{x:.1f},{y:.1f} L{x + w - r:.1f},{y:.1f} '
        f'Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} L{x + w:.1f},{y + h - r:.1f} '
        f'Q{x + w:.1f},{y + h:.1f} {x + w - r:.1f},{y + h:.1f} L{x:.1f},{y + h:.1f} Z" '
        f'fill="{fill}"/>'
    )


def _grid_line(x1: float, y: float, x2: float, *, color: str = theme.GRID) -> str:
    return (f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" '
            f'stroke="{color}" stroke-width="1"/>')


def nice_max(value: float, ticks: int = 4) -> float:
    """축 눈금이 깔끔한 숫자로 떨어지게 올림합니다."""
    if value <= 0:
        return 1.0
    step = value / ticks
    magnitude = 10 ** (len(str(int(step))) - 1)
    # 눈금이 너무 헐거워지지 않게 촘촘한 배수까지 봅니다 (1.05억이 2억 축에 눌리지 않도록).
    for factor in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if step <= magnitude * factor:
            step = magnitude * factor
            break
    return step * ticks


# --------------------------------------------------------------------------
# 세로 막대 — 기간별 추이 (올해 / 전년 두 계열까지)
# --------------------------------------------------------------------------

def columns(
    labels: Sequence[str],
    series: Sequence[tuple[str, Sequence[float]]],
    *,
    width: float = 1080,
    height: float = 380,
    value_fmt=lambda v: f"{v:,.0f}",
    tick_fmt=None,
) -> Chart:
    """기간 × 계열(1~2개) 세로 막대. 마지막 기간에만 값 라벨을 답니다."""
    tick_fmt = tick_fmt or value_fmt
    pad_l, pad_r, pad_t, pad_b = 104, 24, 34, 46
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    base_y = pad_t + plot_h

    values = [v for _, vals in series for v in vals]
    top = nice_max(max(values) if values else 0)
    parts: list[str] = []

    for i in range(5):
        y = base_y - plot_h * i / 4
        parts.append(_grid_line(pad_l, y, pad_l + plot_w,
                                color=theme.AXIS if i == 0 else theme.GRID))
        parts.append(_text(pad_l - 16, y + 7, tick_fmt(top * i / 4), size=18,
                           fill=theme.INK_MUTED, anchor="end", tabular=True))

    band = plot_w / max(len(labels), 1)
    bar_w = min(24.0, band / (len(series) + 1.2))
    gap = 2.0
    group_w = bar_w * len(series) + gap * (len(series) - 1)

    for col, label in enumerate(labels):
        cx = pad_l + band * (col + 0.5)
        for s, (_, vals) in enumerate(series):
            value = vals[col] if col < len(vals) else 0
            h = plot_h * (value / top) if top else 0
            x = cx - group_w / 2 + s * (bar_w + gap)
            color = theme.SERIES[0] if s == 0 else theme.AXIS
            parts.append(_bar_up(x, base_y - h, bar_w, h, color))
            # 값은 마지막 기간의 주 계열에만 답니다.
            # 모든 막대에 숫자를 달면 아무도 안 읽고, 두 계열에 달면 서로 겹칩니다.
            if col == len(labels) - 1 and value and s == 0:
                parts.append(_text(x + bar_w / 2, base_y - h - 12, value_fmt(value),
                                   size=19, fill=theme.INK, weight=600, anchor="middle"))
        parts.append(_text(cx, base_y + 28, label, size=18, fill=theme.INK_MUTED,
                           anchor="middle"))

    legend = [
        LegendItem(name, theme.SERIES[0] if i == 0 else theme.AXIS)
        for i, (name, _) in enumerate(series)
    ]
    return Chart(
        svg=_svg(width, height, "".join(parts)),
        legend=legend if len(series) > 1 else [],
        table_head=["기간", *[name for name, _ in series]],
        table_rows=[
            [label, *[value_fmt(vals[i] if i < len(vals) else 0) for _, vals in series]]
            for i, label in enumerate(labels)
        ],
    )


# --------------------------------------------------------------------------
# 가로 막대 — 매장별·채널별 비교
# --------------------------------------------------------------------------

def bars(
    rows: Sequence[tuple[str, float]],
    *,
    width: float = 900,
    height: float = 0,
    value_fmt=lambda v: f"{v:,.0f}",
    notes: Sequence[str] = (),
    color: str = theme.SERIES[0],
    colors: Sequence[str] = (),
    target: float = 0.0,
    target_label: str = "",
    label_w: float = 0,
) -> Chart:
    """한 계열 가로 막대. 값은 막대 끝에, 보조 문구(증감 등)는 그 뒤에 답니다."""
    row_h, bar_h = 54.0, 24.0
    # 이름이 막대에 먹히지 않도록 가장 긴 라벨에 맞춰 자리를 잡습니다.
    label_w = label_w or min(
        max((text_width(name, 21) for name, _ in rows), default=0) + 22, width * 0.42
    )
    height = height or row_h * len(rows) + 48
    right_pad = 190
    plot_x = label_w
    plot_w = width - label_w - right_pad
    top = nice_max(max((v for _, v in rows), default=0), 4)
    parts: list[str] = []

    for i, (name, value) in enumerate(rows):
        y = 18 + i * row_h
        parts.append(_text(0, y + bar_h - 4, name, size=21, fill=theme.INK, weight=500))
        w = plot_w * (value / top) if top else 0
        parts.append(_bar_right(plot_x, y, w, bar_h,
                                colors[i] if i < len(colors) else color))
        parts.append(_text(plot_x + w + 12, y + bar_h - 5, value_fmt(value), size=20,
                           fill=theme.INK, weight=600, tabular=True))
        if i < len(notes) and notes[i]:
            offset = plot_x + w + 22 + text_width(value_fmt(value), 20)
            parts.append(_text(offset, y + bar_h - 5, notes[i], size=18,
                               fill=theme.INK_MUTED))

    if target and top:
        tx = plot_x + plot_w * (target / top)
        parts.append(
            f'<line x1="{tx:.1f}" y1="6" x2="{tx:.1f}" y2="{18 + row_h * len(rows) - 12:.1f}" '
            f'stroke="{theme.AXIS}" stroke-width="1"/>'
        )
        parts.append(_text(tx + 8, 16, target_label or "목표", size=17,
                           fill=theme.INK_MUTED))

    return Chart(
        svg=_svg(width, height, "".join(parts)),
        table_head=["항목", "값"],
        table_rows=[[name, value_fmt(value)] for name, value in rows],
    )


# --------------------------------------------------------------------------
# 발산형 가로 막대 — 목표/전기 대비 증감
# --------------------------------------------------------------------------

def _bar_left(x: float, y: float, w: float, h: float, fill: str, radius: float = 4) -> str:
    """오른쪽 기준선에서 왼쪽으로 자라는 막대. 왼쪽 끝만 둥글게."""
    if w <= 0.5:
        return ""
    r = min(radius, h / 2, w)
    return (
        f'<path d="M{x + w:.1f},{y:.1f} L{x + r:.1f},{y:.1f} '
        f'Q{x:.1f},{y:.1f} {x:.1f},{y + r:.1f} L{x:.1f},{y + h - r:.1f} '
        f'Q{x:.1f},{y + h:.1f} {x + r:.1f},{y + h:.1f} L{x + w:.1f},{y + h:.1f} Z" '
        f'fill="{fill}"/>'
    )


def diverging(
    rows: Sequence[tuple[str, float]],
    *,
    width: float = 760,
    value_fmt=lambda v: f"{v:+.1f}%",
    label_w: float = 130,
) -> Chart:
    """0 을 기준으로 좌우로 자라는 막대. 초과는 파랑, 미달은 빨강."""
    row_h, bar_h = 50.0, 22.0
    height = row_h * len(rows) + 40
    plot_x = label_w
    plot_w = width - label_w - 100
    span = nice_max(max((abs(v) for _, v in rows), default=1) or 1, 2)
    mid = plot_x + plot_w / 2
    parts = [
        f'<line x1="{mid:.1f}" y1="8" x2="{mid:.1f}" y2="{height - 26:.1f}" '
        f'stroke="{theme.AXIS}" stroke-width="1"/>'
    ]

    for i, (name, value) in enumerate(rows):
        y = 16 + i * row_h
        w = (plot_w / 2) * (abs(value) / span)
        parts.append(_text(0, y + bar_h - 3, name, size=20, fill=theme.INK, weight=500))
        if value >= 0:
            parts.append(_bar_right(mid, y, w, bar_h, theme.DIVERGE_POS))
            parts.append(_text(mid + w + 12, y + bar_h - 4, value_fmt(value),
                               size=19, fill=theme.INK, weight=600, tabular=True))
        else:
            parts.append(_bar_left(mid - w, y, w, bar_h, theme.DIVERGE_NEG))
            parts.append(_text(mid - w - 12, y + bar_h - 4, value_fmt(value),
                               size=19, fill=theme.INK, weight=600, anchor="end",
                               tabular=True))

    return Chart(
        svg=_svg(width, height, "".join(parts)),
        table_head=["항목", "증감"],
        table_rows=[[name, value_fmt(value)] for name, value in rows],
    )


# --------------------------------------------------------------------------
# 누적 가로 막대 — 구성비 (유입 경로, 광고비 배분)
# --------------------------------------------------------------------------

def stacked(
    parts_in: Sequence[tuple[str, float]],
    *,
    width: float = 900,
    height: float = 56,
    value_fmt=lambda v: f"{v:,.0f}",
) -> Chart:
    """한 줄짜리 누적 막대. 조각 사이는 테두리가 아니라 바탕색 2px 간격으로 나눕니다."""
    total = sum(v for _, v in parts_in) or 1
    gap = 2.0
    inner = width - gap * max(len(parts_in) - 1, 0)
    x = 0.0
    body: list[str] = []
    legend: list[LegendItem] = []

    for i, (name, value) in enumerate(parts_in):
        w = inner * (value / total)
        color = theme.series_color(i)
        first, last = i == 0, i == len(parts_in) - 1
        radius = 6
        if first and last:
            body.append(_bar_right(x, 0, w, height, color, radius))
        elif first:
            body.append(_bar_left(x, 0, w, height, color, radius))
        elif last:
            body.append(_bar_right(x, 0, w, height, color, radius))
        else:
            body.append(f'<rect x="{x:.1f}" y="0" width="{max(w, 0):.1f}" '
                        f'height="{height:.0f}" fill="{color}"/>')
        share = value / total * 100
        text = f"{share:.0f}%"
        # 조각 안에 글자가 들어갈 때만 넣습니다. 안 들어가면 범례가 값을 들고 갑니다.
        if w > text_width(text, 19) + 24:
            body.append(_text(x + w / 2, height / 2 + 7, text, size=19, fill="#ffffff",
                              weight=600, anchor="middle"))
        legend.append(LegendItem(name, color, f"{value_fmt(value)} · {share:.0f}%"))
        x += w + gap

    return Chart(
        svg=_svg(width, height, "".join(body)),
        legend=legend,
        table_head=["구분", "값", "비중"],
        table_rows=[
            [name, value_fmt(value), f"{value / total * 100:.1f}%"]
            for name, value in parts_in
        ],
    )


# --------------------------------------------------------------------------
# 퍼널 — 노출 → 클릭 → 전환
# --------------------------------------------------------------------------

def funnel(
    stages: Sequence[tuple[str, float, float, str]],
    *,
    width: float = 820,
    value_fmt=lambda v: f"{v:,.0f}",
) -> Chart:
    """단계(라벨, 값, 직전 대비 전환율, 단위). 단계는 순서가 있으니 단색 램프를 씁니다."""
    row_h, bar_h = 76.0, 30.0
    height = row_h * len(stages) + 16
    label_w, right = 108.0, 200.0
    plot_w = width - label_w - right
    top = max((v for _, v, _, _ in stages), default=1) or 1
    parts: list[str] = []

    for i, (name, value, rate, unit) in enumerate(stages):
        y = 10 + i * row_h
        color = theme.ORDINAL[min(i, len(theme.ORDINAL) - 1)]
        parts.append(_text(0, y + bar_h - 6, name, size=21, fill=theme.INK, weight=500))
        # 노출과 전환은 자릿수가 서너 개 차이라 마지막 단계가 사라집니다.
        # 최소 폭을 주어 단계가 보이게 하되, 실제 비율은 옆 숫자와 전환율이 말합니다.
        w = max(plot_w * (value / top), 4.0 if value else 0.0)
        parts.append(_bar_right(label_w, y, w, bar_h, color))
        parts.append(_text(label_w + w + 14, y + bar_h - 7,
                           f"{value_fmt(value)}{unit}", size=21, fill=theme.INK,
                           weight=600, tabular=True))
        if i:
            parts.append(_text(label_w, y + bar_h + 26,
                               f"↳ 직전 단계의 {rate:.2f}%", size=18, fill=theme.INK_MUTED))

    return Chart(
        svg=_svg(width, height, "".join(parts)),
        caption="단계별 막대 길이는 최상단 단계 대비 비율입니다.",
        table_head=["단계", "값", "직전 대비"],
        table_rows=[
            [name, f"{value_fmt(value)}{unit}", f"{rate:.2f}%"]
            for name, value, rate, unit in stages
        ],
    )


# --------------------------------------------------------------------------
# 게이지 — 목표 달성률
# --------------------------------------------------------------------------

def meter(
    value: float, target: float, *, width: float = 420, height: float = 18,
    warn_at: float = 0.9, danger_at: float = 0.75,
) -> Chart:
    """하나의 비율을 한계선과 견주는 막대. 트랙은 같은 램프의 밝은 단계입니다."""
    pct = (value / target) if target else 0.0
    fill = theme.SERIES[0]
    if pct < danger_at:
        fill = theme.CRITICAL
    elif pct < warn_at:
        fill = theme.WARNING
    body = [
        _bar_right(0, 0, width, height, theme.RAMP[100], height / 2),
        _bar_right(0, 0, min(width * pct, width), height, fill, height / 2),
    ]
    return Chart(svg=_svg(width, height, "".join(body)))


# --------------------------------------------------------------------------
# 스파크라인 — 지표 타일 안에 들어가는 12점짜리 미니 추이
# --------------------------------------------------------------------------

def sparkline(
    values: Sequence[float], *, width: float = 168, height: float = 40,
    accent: str = theme.SERIES[0],
) -> str:
    """SVG 문자열만 돌려줍니다 (타일 안에 그대로 심습니다)."""
    values = [v for v in values][-12:]
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = width / (len(values) - 1)
    points = [
        (i * step, height - 4 - (v - lo) / span * (height - 10))
        for i, v in enumerate(values)
    ]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}"
                    for i, (x, y) in enumerate(points))
    last_x, last_y = points[-1]
    return _svg(width, height, (
        f'<path d="{path}" fill="none" stroke="{theme.AXIS}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="4" fill="{accent}" '
        f'stroke="{theme.SURFACE}" stroke-width="2"/>'
    ))
