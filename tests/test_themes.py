import re

import pytest

from cardnews.themes import THEMES, all_fonts, get_theme, suggest_theme

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


@pytest.mark.parametrize("theme", THEMES.values(), ids=lambda t: t.name)
def test_theme_colours_are_valid_hex(theme):
    for field in ("bg", "bg_alt", "surface", "ink", "ink_sub", "accent", "accent_ink", "accent2"):
        assert HEX.match(getattr(theme, field)), f"{theme.name}.{field}"


def test_unknown_theme_falls_back():
    assert get_theme("nope").name == "warm"
    assert get_theme(None).name == "warm"


@pytest.mark.parametrize(
    "topic,expected",
    [
        ("강남 오마카세 데이트 코스", "mono"),
        ("홍대 포차 야식 안주", "neon"),
        ("서울 TOP 5 신상 카페 랭킹", "pop"),
        ("연남동 브런치 카페 3곳", "mint"),
        ("아무 관련 없는 주제", "warm"),
    ],
)
def test_suggest_theme(topic, expected):
    assert suggest_theme(topic) == expected


def test_all_fonts_covers_every_theme_font():
    fonts = all_fonts()
    for theme in THEMES.values():
        assert theme.display_font in fonts
        assert theme.body_font in fonts
