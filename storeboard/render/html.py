"""Deck -> HTML 문서.

캡처 이미지와 폰트는 파일 그대로 두고, 렌더 서버가 매핑할 URL 만 문서에 씁니다
(base64 로 심으면 문서가 수십 MB 가 되고, file:// 폰트는 크로미움이 CORS 로 막습니다).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import theme
from ..config import SLIDE_H, SLIDE_W, TEMPLATE_DIR
from ..deck import Deck

FONT_URL_PREFIX = "/__fonts"
IMAGE_URL_PREFIX = "/__img"

# 상태색이 색만으로 뜻을 나르지 않도록 부호를 함께 답니다.
TONE_MARKS = {"good": "▲", "warn": "!", "critical": "▼", "info": "●"}

# 보고서 본문 서체. 로컬 TTF -> Google Fonts -> 시스템 순으로 폴백합니다.
FONT_FAMILIES = ["Noto Sans KR"]


@dataclass
class RenderDoc:
    """렌더 서버에 넘길 한 벌: HTML 문서 + URL→파일 매핑.

    필드 이름은 cardnews 쪽 렌더 서버와 맞춰 두었습니다 (같은 서버를 씁니다).
    """

    html: str = ""                       # 전체 슬라이드가 들어간 문서 (PDF·미리보기용)
    pages: list[str] = field(default_factory=list)   # 슬라이드 한 장짜리 문서
    routes: dict[str, Path] = field(default_factory=dict)
    width: int = SLIDE_W
    height: int = SLIDE_H
    count: int = 0
    missing_fonts: list[str] = field(default_factory=list)


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        # 템플릿 파일명이 .html.j2 라 기본 규칙(.html)으로는 걸리지 않습니다.
        # CSS 템플릿은 이스케이프하면 안 되므로 확장자로 갈라 둡니다.
        autoescape=select_autoescape(enabled_extensions=("html.j2",), default=False),
    )


def _prepare(deck: Deck) -> tuple[Deck, dict[str, Path]]:
    """캡처 경로를 URL 로 바꾸고 라우팅 표를 만듭니다. 원본 덱은 건드리지 않습니다."""
    deck = copy.deepcopy(deck)
    routes: dict[str, Path] = {}
    seq = 0
    for slide in deck.slides:
        for block in slide.blocks:
            if block.kind != "images" or not block.images:
                continue
            prepared = []
            for raw in block.images:
                path = Path(str(raw))
                if not path.is_file():
                    continue
                seq += 1
                url = f"{IMAGE_URL_PREFIX}/{seq:02d}{path.suffix.lower() or '.png'}"
                routes[url] = path
                prepared.append({"url": url, "name": path.name})
            block.images = prepared
    return deck, routes


def _fonts(routes: dict[str, Path], *, embed: bool) -> tuple[str, str, list[str]]:
    """(@font-face 규칙, Google Fonts 링크, 없는 패밀리)."""
    try:
        from cardnews.fonts import face_rules, google_fonts_url, missing_report
    except ImportError:               # 폰트 도우미가 없어도 시스템 서체로 렌더됩니다.
        return "", "", FONT_FAMILIES

    from ..config import FONT_DIR

    faces = face_rules(FONT_FAMILIES, None if embed else FONT_URL_PREFIX)
    if faces and not embed:
        for family in FONT_FAMILIES:
            for path in FONT_DIR.glob(f"{family.replace(' ', '_')}-*.ttf"):
                routes[f"{FONT_URL_PREFIX}/{path.name}"] = path
    link = google_fonts_url(FONT_FAMILIES) if not faces else ""
    return faces, link, missing_report(FONT_FAMILIES)


def build_html(deck: Deck, *, embed_fonts: bool = False) -> RenderDoc:
    """덱 한 부를 문서 한 장으로. 슬라이드 낱장 문서도 같이 만듭니다."""
    prepared, routes = _prepare(deck)
    faces, link, missing = _fonts(routes, embed=embed_fonts)

    env = _env()
    styles = env.get_template("styles.css.j2").render(
        t=theme, width=SLIDE_W, height=SLIDE_H
    )
    template = env.get_template("deck.html.j2")

    def render(slides, offset: int = 0) -> str:
        return template.render(
            deck=prepared, slides=slides, total=len(prepared.slides),
            index_offset=offset, styles=styles, font_faces=faces, font_link=link,
            t=theme, marks=TONE_MARKS,
        )

    return RenderDoc(
        html=render(prepared.slides),
        pages=[render([slide], offset=i) for i, slide in enumerate(prepared.slides)],
        routes=routes,
        width=SLIDE_W,
        height=SLIDE_H,
        count=len(prepared.slides),
        missing_fonts=missing,
    )
