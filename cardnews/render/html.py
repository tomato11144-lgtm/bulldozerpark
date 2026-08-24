"""카드뉴스 -> HTML.

이미지와 폰트는 로컬 파일 그대로 두고, 렌더 서버가 매핑해 줄 URL 경로만 씁니다.
(base64 로 심으면 문서가 수십 MB 가 되고, file:// 폰트는 크로미움이 CORS 로 막습니다.)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import FONT_DIR, TEMPLATE_DIR, canvas_size
from ..fonts import face_rules, google_fonts_url, missing_report
from ..locales import get_locale
from ..models import CardNews
from ..themes import Theme, get_theme

FONT_URL_PREFIX = "/__fonts"
IMAGE_URL_PREFIX = "/__img"


@dataclass
class RenderDoc:
    """렌더 서버에 넘길 한 벌: HTML 문서 + URL→파일 매핑."""

    html: str                # 전체 카드가 한 페이지에 들어간 문서 (미리보기/요소 캡처용)
    pages: list[str]         # 카드 한 장짜리 문서 (브라우저 CLI 캡처용)
    routes: dict[str, Path]
    width: int
    height: int
    count: int
    missing_fonts: list[str]


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        # 템플릿 파일명이 .html.j2 라 기본 규칙(.html)으로는 걸리지 않습니다.
        # CSS 템플릿(.css.j2)은 이스케이프하면 안 되므로 명시적으로 켜고 끕니다.
        autoescape=select_autoescape(
            enabled_extensions=("html.j2", "xml.j2", "html", "xml"), default=False
        ),
        trim_blocks=False,
        lstrip_blocks=False,
    )
    return env


def prepare_cards(news: CardNews) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    """카드를 템플릿용 dict 로 바꾸고, 이미지 URL 라우팅 표를 만듭니다."""
    cards: list[dict[str, Any]] = []
    routes: dict[str, Path] = {}
    for i, card in enumerate(news.cards, start=1):
        payload = card.__dict__.copy()
        payload["image_url"] = ""
        if card.image:
            path = Path(card.image)
            if path.is_file():
                url = f"{IMAGE_URL_PREFIX}/{i:02d}{path.suffix.lower() or '.jpg'}"
                routes[url] = path
                payload["image_url"] = url
        cards.append(payload)
    return cards, routes


def build_html(
    news: CardNews,
    *,
    theme: Theme | None = None,
    ratio: str = "4:5",
    embed_fonts: bool = False,
) -> RenderDoc:
    """카드뉴스 한 세트를 한 장의 HTML 문서로 만듭니다."""
    theme = theme or get_theme(news.theme)
    locale = get_locale(news.lang)
    width, height = canvas_size(ratio)
    cards, routes = prepare_cards(news)

    families = theme.fonts_for(locale.script)
    missing = missing_report(families)
    # 로컬 TTF 가 하나라도 있으면 그걸 쓰고, 전부 없으면 Google Fonts 로 폴백합니다.
    faces = face_rules(families, None if embed_fonts else FONT_URL_PREFIX)
    font_link = google_fonts_url(families) if not faces else ""

    if faces and not embed_fonts:
        for family in families:
            for path in FONT_DIR.glob(f"{family.replace(' ', '_')}-*.ttf"):
                routes[f"{FONT_URL_PREFIX}/{path.name}"] = path

    env = _env()
    styles = env.get_template("styles.css.j2").render(
        t=theme, width=width, height=height,
        display_font=theme.display_for(locale.script),
        body_font=theme.body_for(locale.script),
        display_weight=theme.display_weight_for(locale.script),
        title_scale=theme.title_scale_for(locale.script),
        script=locale.script,
    )
    template = env.get_template("page.html.j2")

    def render_page(subset: list[dict[str, Any]], offset: int = 0) -> str:
        return template.render(
            news=news,
            cards=subset,
            index_offset=offset,
            total=len(cards),
            handle=news.handle or "",
            styles=styles,
            font_faces=faces,
            font_link=font_link,
            t=theme,
            ui=locale.ui,
        )

    html = render_page(cards)
    pages = [render_page([card], offset=i) for i, card in enumerate(cards)]

    return RenderDoc(
        html=html,
        pages=pages,
        routes=routes,
        width=width,
        height=height,
        count=len(cards),
        missing_fonts=missing,
    )
