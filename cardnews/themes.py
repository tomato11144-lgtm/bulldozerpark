"""카드뉴스 디자인 테마.

각 테마는 색 팔레트 + 폰트 조합 + 약간의 장식 규칙을 들고 있습니다.
HTML 렌더러는 이 값을 CSS 변수로, Pillow 렌더러는 직접 색/폰트로 사용합니다.

폰트는 전부 Google Fonts 에 있는 한글 지원 서체라
`python scripts/fetch_fonts.py` 한 번이면 오프라인 렌더링까지 됩니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 폰트 패밀리 -> 내려받아야 할 두께 목록.
# scripts/fetch_fonts.py 가 이 표를 그대로 Google Fonts css2 쿼리로 바꿉니다.
FONT_WEIGHTS: dict[str, list[int]] = {
    "Noto Sans KR": [400, 500, 700, 900],
    "Black Han Sans": [400],
    "Do Hyeon": [400],
    "Jua": [400],
    "Gasoek One": [400],
    "Nanum Myeongjo": [400, 700, 800],
    "Gowun Dodum": [400],
    "Gowun Batang": [400, 700],
    "IBM Plex Sans KR": [400, 600, 700],
    # 라틴 문자용 (영어 · 따갈로그). 따갈로그의 ñ, á 같은 글자까지 커버합니다.
    "Anton": [400],
    "Archivo Black": [400],
    "Alfa Slab One": [400],
    "Bowlby One": [400],
    "Fredoka": [400, 600, 700],
    "Playfair Display": [400, 700, 900],
    "Inter": [400, 500, 700, 900],
    "Work Sans": [400, 600, 700],
}


@dataclass(frozen=True)
class Theme:
    """카드 한 세트에 적용되는 시각 스타일."""

    name: str
    label: str                 # 사람이 읽는 이름
    best_for: str              # 어떤 주제에 어울리는지 (CLI 도움말 & 자동 추천에 사용)

    bg: str                    # 카드 바탕
    bg_alt: str                # 보조 바탕 (그라데이션 끝점)
    surface: str               # 본문 박스 배경
    ink: str                   # 기본 글자색
    ink_sub: str               # 보조 글자색
    accent: str                # 강조색 1 (숫자, 밑줄, 배지)
    accent_ink: str            # accent 위에 올라가는 글자색
    accent2: str               # 강조색 2 (포인트)

    display_font: str          # 제목용 (한글)
    body_font: str             # 본문용 (한글)
    display_weight: int = 400
    title_scale: float = 1.0   # 제목 크기 배율 (서체별 체급 보정)

    # 라틴 문자 언어(영어·따갈로그)에서 쓸 짝. 한글 서체는 라틴 글자가
    # 밋밋하거나 아예 없어서, 같은 인상을 주는 라틴 서체로 갈아끼웁니다.
    latin_display: str = "Anton"
    latin_body: str = "Inter"
    latin_display_weight: int = 400
    latin_title_scale: float = 1.0

    radius: int = 28           # 박스 모서리
    overlay: str = "rgba(0,0,0,0.55)"     # 사진 위 어둡게 덮는 정도
    photo_filter: str = "none"            # 사진 보정 CSS filter
    grain: bool = False                   # 종이 질감 노이즈
    dark: bool = False                    # 어두운 테마 여부 (그림자/보더 계산에 사용)

    # 자동 테마 추천에 쓰이는 키워드
    keywords: tuple[str, ...] = field(default_factory=tuple)

    @property
    def fonts(self) -> list[str]:
        return sorted({self.display_font, self.body_font})

    @property
    def latin_fonts(self) -> list[str]:
        return sorted({self.latin_display, self.latin_body})

    def fonts_for(self, script: str) -> list[str]:
        return self.latin_fonts if script == "latin" else self.fonts

    def display_for(self, script: str) -> str:
        return self.latin_display if script == "latin" else self.display_font

    def body_for(self, script: str) -> str:
        return self.latin_body if script == "latin" else self.body_font

    def display_weight_for(self, script: str) -> int:
        return self.latin_display_weight if script == "latin" else self.display_weight

    def title_scale_for(self, script: str) -> float:
        return self.latin_title_scale if script == "latin" else self.title_scale


THEMES: dict[str, Theme] = {
    "warm": Theme(
        name="warm",
        latin_display="Archivo Black", latin_body="Inter", latin_title_scale=0.86,
        label="따뜻한 우드 크림",
        best_for="한식·백반·국밥·베이커리·동네 맛집 리스트",
        bg="#FFF7EE", bg_alt="#FBE9D4", surface="#FFFFFF",
        ink="#241608", ink_sub="#7A6350",
        accent="#D6532A", accent_ink="#FFFFFF", accent2="#E8A33D",
        display_font="Black Han Sans", body_font="Noto Sans KR",
        title_scale=0.98, radius=30, overlay="rgba(36,22,8,0.52)",
        photo_filter="saturate(1.06) contrast(1.02)", grain=True,
        keywords=("한식", "백반", "국밥", "찌개", "빵", "베이커리", "카페", "동네", "가성비", "노포", "골목식당"),
    ),
    "neon": Theme(
        name="neon",
        latin_display="Anton", latin_body="Inter", latin_title_scale=0.94,
        label="네온 야식",
        best_for="야식·포차·술집·심야식당·안주 추천",
        bg="#0C0A12", bg_alt="#161226", surface="#1C1830",
        ink="#F6F3FF", ink_sub="#A79DC4",
        accent="#FF3D71", accent_ink="#FFFFFF", accent2="#2BE7C4",
        display_font="Black Han Sans", body_font="Noto Sans KR",
        title_scale=1.0, radius=26, overlay="rgba(8,6,14,0.62)",
        photo_filter="saturate(1.15) contrast(1.08)", dark=True,
        keywords=("야식", "포차", "술집", "안주", "이자카야", "맥주", "소주", "와인", "바", "심야", "회식"),
    ),
    "mint": Theme(
        name="mint",
        latin_display="Fredoka", latin_body="Inter", latin_display_weight=700, latin_title_scale=0.92,
        label="상큼 브런치",
        best_for="브런치·디저트·샐러드·비건·카페 신메뉴",
        bg="#F3FBF7", bg_alt="#DDF3E8", surface="#FFFFFF",
        ink="#103124", ink_sub="#5C7D70",
        accent="#12A379", accent_ink="#FFFFFF", accent2="#F5B93C",
        display_font="Jua", body_font="Noto Sans KR",
        title_scale=1.04, radius=34, overlay="rgba(9,42,31,0.46)",
        photo_filter="saturate(1.04) brightness(1.03)",
        keywords=("브런치", "디저트", "샐러드", "비건", "케이크", "베이글", "스무디", "건강", "다이어트", "아침"),
    ),
    "mono": Theme(
        name="mono",
        latin_display="Playfair Display", latin_body="Inter", latin_display_weight=900, latin_title_scale=0.92,
        label="모노 파인다이닝",
        best_for="파인다이닝·오마카세·기념일·미쉐린",
        bg="#0F0F0F", bg_alt="#1A1A1A", surface="#191919",
        ink="#F6F3EE", ink_sub="#9C948A",
        accent="#C7A868", accent_ink="#121212", accent2="#EFE7D8",
        display_font="Nanum Myeongjo", body_font="Noto Sans KR",
        display_weight=800, title_scale=1.0, radius=6,
        overlay="rgba(10,10,10,0.58)", photo_filter="contrast(1.06) saturate(0.92)",
        dark=True,
        keywords=("파인다이닝", "오마카세", "미쉐린", "코스", "기념일", "스시", "한우", "프렌치", "이탈리안", "데이트"),
    ),
    "retro": Theme(
        name="retro",
        latin_display="Alfa Slab One", latin_body="Work Sans", latin_title_scale=0.80,
        label="뉴트로 노포",
        best_for="노포·시장·분식·중식·추억의 맛집",
        bg="#F6EAD2", bg_alt="#EBD8B4", surface="#FFF9EC",
        ink="#2A1A10", ink_sub="#7C6247",
        accent="#B7332A", accent_ink="#FFF3DD", accent2="#1F6B54",
        display_font="Do Hyeon", body_font="Gowun Dodum",
        title_scale=1.06, radius=10, overlay="rgba(42,26,16,0.5)",
        photo_filter="sepia(0.18) saturate(1.05) contrast(1.04)", grain=True,
        keywords=("노포", "시장", "분식", "중식", "짜장", "탕수육", "추억", "옛날", "전통", "골목"),
    ),
    "pop": Theme(
        name="pop",
        latin_display="Bowlby One", latin_body="Inter", latin_title_scale=0.80,
        label="팝 랭킹",
        best_for="TOP N 랭킹·신상 오픈·이벤트·프랜차이즈 신메뉴",
        bg="#FFDE3D", bg_alt="#FFC93C", surface="#FFFFFF",
        ink="#171717", ink_sub="#5B5B5B",
        accent="#FF3B1F", accent_ink="#FFFFFF", accent2="#1B54F0",
        display_font="Gasoek One", body_font="Noto Sans KR",
        title_scale=0.92, radius=24, overlay="rgba(23,23,23,0.5)",
        photo_filter="saturate(1.12) contrast(1.05)",
        keywords=("랭킹", "top", "베스트", "신상", "오픈", "이벤트", "할인", "신메뉴", "인기", "화제"),
    ),
}

DEFAULT_THEME = "warm"


def get_theme(name: str | None) -> Theme:
    """이름으로 테마를 찾습니다. 없으면 기본 테마."""
    if not name:
        return THEMES[DEFAULT_THEME]
    return THEMES.get(name.strip().lower(), THEMES[DEFAULT_THEME])


def suggest_theme(topic: str) -> str:
    """주제 문장에서 키워드를 보고 어울리는 테마를 고릅니다.

    `--theme auto` 일 때 사용합니다. 맞는 키워드가 없으면 기본 테마.
    """
    text = (topic or "").lower()
    best, best_score = DEFAULT_THEME, 0
    for theme in THEMES.values():
        # 긴 키워드일수록 구체적이므로 가중치를 더 줍니다
        # ("브런치 카페" 는 카페(warm)보다 브런치(mint)에 가깝습니다).
        score = sum(len(kw) for kw in theme.keywords if kw.lower() in text)
        if score > best_score:
            best, best_score = theme.name, score
    return best


def theme_names() -> list[str]:
    return list(THEMES)


def all_fonts(script: str = "") -> dict[str, list[int]]:
    """실제 테마들이 쓰는 폰트만 추린 목록.

    script 를 주면 그 계열만("hangul" 또는 "latin"), 안 주면 전부 돌려줍니다.
    """
    used: dict[str, list[int]] = {}
    for theme in THEMES.values():
        families = (
            theme.fonts if script == "hangul"
            else theme.latin_fonts if script == "latin"
            else [*theme.fonts, *theme.latin_fonts]
        )
        for fam in families:
            used[fam] = FONT_WEIGHTS.get(fam, [400])
    return used
