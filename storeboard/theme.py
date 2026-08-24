"""색·간격 토큰 한 곳.

값은 검증된 데이터 시각화 기본 팔레트를 그대로 씁니다
(카테고리 8슬롯의 '순서'가 색각 이상 구분을 보장하는 장치라 임의로 섞지 않습니다).
보고용 덱은 인쇄·PPT 삽입이 목적이라 슬라이드 안쪽은 라이트 한 가지로 고정합니다.
"""

from __future__ import annotations

# 면
SURFACE = "#fcfcfb"          # 카드/차트 바탕
PLANE = "#f9f9f7"            # 슬라이드 바탕
PANEL = "#ffffff"

# 글자
INK = "#0b0b0b"
INK_SUB = "#52514e"
INK_MUTED = "#898781"

# 차트 크롬
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BORDER = "rgba(11,11,11,0.10)"

# 카테고리 8슬롯 — 이 순서를 지켜서 씁니다.
SERIES = (
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
)

# 단일 색조(파랑) 순서형 램프. 라이트 배경에서는 250 단계보다 밝아지지 않습니다.
RAMP = {
    100: "#cde2fb", 150: "#b7d3f6", 200: "#9ec5f4", 250: "#86b6ef",
    300: "#6da7ec", 350: "#5598e7", 400: "#3987e5", 450: "#2a78d6",
    500: "#256abf", 550: "#1c5cab", 600: "#184f95", 650: "#104281", 700: "#0d366b",
}
ORDINAL = (RAMP[250], RAMP[400], RAMP[550], RAMP[700])   # 퍼널 등 순서가 있는 단계

# 상태색 — 좋다/나쁘다를 '뜻할 때만' 씁니다. 계열색으로 돌려쓰지 않습니다.
GOOD = "#0ca30c"
WARNING = "#fab219"
SERIOUS = "#ec835a"
CRITICAL = "#d03b3b"
GOOD_TEXT = "#006300"        # 라이트 배경에서 글자로 쓸 수 있는 초록

# 발산형(목표 대비 초과/미달)
DIVERGE_POS = SERIES[0]      # 파랑 = 초과
DIVERGE_NEG = SERIES[7]      # 빨강 = 미달
DIVERGE_MID = "#f0efec"

FONT_STACK = (
    '"Pretendard", "Noto Sans KR", system-ui, -apple-system, '
    '"Apple SD Gothic Neo", "Malgun Gothic", sans-serif'
)


def series_color(index: int) -> str:
    """8슬롯을 넘어가면 색을 새로 만들지 않고 마지막 슬롯을 반복하지 않도록,
    호출부에서 '기타'로 접어야 합니다. 여기서는 방어적으로 잘라 씁니다."""
    return SERIES[min(index, len(SERIES) - 1)]


def delta_color(direction: str, *, up_is_good: bool = True) -> str:
    """증감 방향 -> 글자색. 방향이 좋은지 나쁜지는 지표마다 다릅니다."""
    if direction == "flat":
        return INK_MUTED
    good = (direction == "up") == up_is_good
    return GOOD_TEXT if good else CRITICAL
