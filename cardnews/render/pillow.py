"""브라우저 없이 PNG 를 뽑는 대체 렌더러.

크로미움을 못 쓰는 환경(서버, CI, 사내망)을 위한 백엔드입니다.
HTML 렌더러와 픽셀 단위로 같지는 않지만, 같은 테마 색과 폰트를 써서
같은 톤의 결과가 나오도록 맞췄습니다.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..fonts import resolve_ttf
from ..models import Card, CardNews
from ..themes import Theme, get_theme

PAD = 88
FOOTER_H = 156


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


@dataclass
class _Fonts:
    display: str | None
    body: str | None

    def get(self, kind: str, size: int) -> ImageFont.FreeTypeFont:
        path = self.display if kind == "display" else self.body
        if path:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
        return ImageFont.load_default(size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """한글은 공백이 적어 어절 단위로 자르되, 한 어절이 넘치면 글자 단위로 쪼갭니다."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=font) <= max_w or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
            # 한 어절 자체가 너무 길면 글자 단위로 흘려보냅니다.
            while draw.textlength(current, font=font) > max_w and len(current) > 1:
                cut = len(current)
                while cut > 1 and draw.textlength(current[:cut], font=font) > max_w:
                    cut -= 1
                lines.append(current[:cut])
                current = current[cut:]
        if current:
            lines.append(current)
    return lines


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    xy: tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    max_w: int,
    line_height: float = 1.5,
) -> int:
    """텍스트를 감싸서 그리고, 다음 y 좌표를 돌려줍니다."""
    x, y = xy
    step = int(font.size * line_height)
    for line in _wrap(draw, text, font, max_w):
        draw.text((x, y), line, font=font, fill=fill)
        y += step
    return y


def _cover_fit(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """비율 유지하며 잘라 채우기 (CSS background-size: cover)."""
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    resized = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                         Image.LANCZOS)
    left = (resized.width - tw) // 2
    top = (resized.height - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def _rounded(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width - 1, img.height - 1],
                                          radius=radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def _gradient_bg(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h), _rgb(top))
    draw = ImageDraw.Draw(img)
    c1, c2 = _rgb(top), _rgb(bottom)
    for y in range(h):
        t = y / max(1, h - 1)
        draw.line([(0, y), (w, y)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)))
    return img


def _pill(
    draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int],
    font: ImageFont.FreeTypeFont, bg: tuple[int, int, int], fg: tuple[int, int, int],
) -> int:
    x, y = xy
    tw = draw.textlength(text, font=font)
    h = int(font.size * 2.0)
    draw.rounded_rectangle([x, y, x + tw + 44, y + h], radius=h // 2, fill=bg)
    draw.text((x + 22, y + h // 2), text, font=font, fill=fg, anchor="lm")
    return y + h


class PillowRenderer:
    """카드 한 장씩 PNG 로 그립니다."""

    def __init__(self, theme: Theme, size: tuple[int, int] = (1080, 1350)):
        self.t = theme
        self.size = size
        self.fonts = _Fonts(
            display=resolve_ttf(theme.display_font, theme.display_weight),
            body=resolve_ttf(theme.body_font, 400),
        )

    # -- 헬퍼 ------------------------------------------------------------
    @property
    def ink(self) -> tuple[int, int, int]:
        return _rgb(self.t.ink)

    @property
    def sub(self) -> tuple[int, int, int]:
        return _rgb(self.t.ink_sub)

    @property
    def accent(self) -> tuple[int, int, int]:
        return _rgb(self.t.accent)

    def _photo(self, card: Card, size: tuple[int, int]) -> Image.Image | None:
        if not card.image:
            return None
        path = Path(card.image)
        if not path.is_file():
            return None
        try:
            with Image.open(path) as src:
                return _cover_fit(src.convert("RGB"), size)
        except Exception:  # noqa: BLE001 - 깨진 파일은 그냥 배경 없이
            return None

    # -- 본체 ------------------------------------------------------------
    def render_card(self, card: Card, index: int, total: int, handle: str) -> Image.Image:
        w, h = self.size
        max_w = w - PAD * 2
        on_photo = card.kind in ("cover", "quote", "outro") and card.image

        img = _gradient_bg(self.size, self.t.bg, self.t.bg_alt)
        photo = self._photo(card, self.size)

        if on_photo and photo:
            img = photo
            scrim = Image.new("RGBA", self.size, (0, 0, 0, 0))
            sd = ImageDraw.Draw(scrim)
            for y in range(h):
                t = y / max(1, h - 1)
                alpha = int(60 + 175 * (t ** 1.6))
                sd.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")
        elif card.kind == "intro" and photo:
            top = _cover_fit(photo, (w, int(h * 0.46)))
            img.paste(top, (0, 0))

        draw = ImageDraw.Draw(img)
        text_col = (255, 255, 255) if on_photo else self.ink
        sub_col = (235, 235, 235) if on_photo else self.sub

        f_badge = self.fonts.get("body", 26)
        f_title = self.fonts.get("display", int(96 * self.t.title_scale))
        f_title_md = self.fonts.get("display", int(72 * self.t.title_scale))
        f_title_sm = self.fonts.get("display", int(58 * self.t.title_scale))
        f_body = self.fonts.get("body", 34)
        f_sub = self.fonts.get("body", 33)
        f_meta_k = self.fonts.get("body", 26)
        f_meta_v = self.fonts.get("body", 31)
        f_foot = self.fonts.get("body", 25)

        y = PAD
        if card.badge and card.kind != "place":
            y = _pill(draw, card.badge, (PAD, y), f_badge, self.accent, _rgb(self.t.accent_ink)) + 30

        if card.kind in ("cover", "outro"):
            # 아래쪽 정렬 — 필요한 높이를 먼저 재고 시작점을 잡습니다.
            block: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int], float]] = []
            if card.eyebrow:
                block.append((card.eyebrow, self.fonts.get("body", 30), _rgb(self.t.accent2), 1.5))
            block.append((card.title, f_title if card.kind == "cover" else f_title_md,
                          text_col, 1.1))
            if card.subtitle and card.kind == "cover":
                block.append((card.subtitle, f_sub, sub_col, 1.5))
            if card.body:
                block.append((card.body, f_body, sub_col, 1.65))
            if card.subtitle and card.kind == "outro":
                block.append((card.subtitle, f_sub, _rgb(self.t.accent2), 1.5))

            height = sum(
                len(_wrap(draw, text, font, max_w)) * int(font.size * lh) + 20
                for text, font, _, lh in block
            )
            y = h - FOOTER_H - height - 20
            for text, font, colour, lh in block:
                y = _draw_text_block(draw, text, xy=(PAD, y), font=font, fill=colour,
                                     max_w=max_w, line_height=lh) + 20

        elif card.kind == "place":
            rank_font = self.fonts.get("display", 112)
            rank_w = 0
            if card.badge:
                draw.text((PAD, y - 8), card.badge, font=rank_font, fill=self.accent)
                rank_w = int(draw.textlength(card.badge, font=rank_font)) + 28
            ty = _draw_text_block(draw, card.title, xy=(PAD + rank_w, y), font=f_title_sm,
                                  fill=text_col, max_w=max_w - rank_w, line_height=1.15)
            if card.subtitle:
                ty = _draw_text_block(draw, card.subtitle, xy=(PAD + rank_w, ty + 10),
                                      font=f_sub, fill=sub_col, max_w=max_w - rank_w)
            y = max(ty, y + int(rank_font.size * 1.05)) + 34

            if photo:
                frame = _rounded(_cover_fit(photo, (max_w, 470)), self.t.radius)
                img.paste(frame, (PAD, y), frame)
                draw = ImageDraw.Draw(img)
                y += 470 + 32

            if card.body:
                y = _draw_text_block(draw, card.body, xy=(PAD, y), font=f_body,
                                     fill=text_col, max_w=max_w, line_height=1.6) + 22

            if card.meta:
                line_col = (*self.sub, 90)
                for key, value in card.meta.items():
                    draw.line([(PAD, y), (w - PAD, y)], fill=self.sub, width=2)
                    y += 16
                    draw.text((PAD, y + 4), key, font=f_meta_k, fill=self.sub)
                    _draw_text_block(draw, value, xy=(PAD + 168, y), font=f_meta_v,
                                     fill=text_col, max_w=max_w - 168)
                    y += 52
                draw.line([(PAD, y), (w - PAD, y)], fill=self.sub, width=2)

        elif card.kind == "list":
            y = _draw_text_block(draw, card.title, xy=(PAD, y), font=f_title_md,
                                 fill=text_col, max_w=max_w, line_height=1.15) + 34
            if card.body:
                y = _draw_text_block(draw, card.body, xy=(PAD, y), font=f_body,
                                     fill=sub_col, max_w=max_w) + 20
            f_item = self.fonts.get("body", 36)
            f_num = self.fonts.get("body", 28)
            for i, item in enumerate(card.bullets, start=1):
                draw.ellipse([PAD, y, PAD + 58, y + 58], fill=self.accent)
                draw.text((PAD + 29, y + 29), str(i), font=f_num,
                          fill=_rgb(self.t.accent_ink), anchor="mm")
                end = _draw_text_block(draw, item, xy=(PAD + 82, y + 4), font=f_item,
                                       fill=text_col, max_w=max_w - 82, line_height=1.45)
                y = max(end, y + 58) + 26

        elif card.kind == "quote":
            f_quote = self.fonts.get("display", int(60 * self.t.title_scale))
            body = card.body or card.title
            lines = _wrap(draw, body, f_quote, max_w)
            height = len(lines) * int(f_quote.size * 1.36)
            y = (h - height) // 2 - 40
            draw.text((PAD, y - 130), "“", font=self.fonts.get("display", 170),
                      fill=self.accent)
            y = _draw_text_block(draw, body, xy=(PAD, y), font=f_quote, fill=text_col,
                                 max_w=max_w, line_height=1.36)
            if card.footnote:
                _draw_text_block(draw, f"— {card.footnote}", xy=(PAD, y + 26),
                                 font=f_foot, fill=sub_col, max_w=max_w)

        else:  # intro, menu, tip
            if card.kind == "intro":
                y = max(y, int(h * 0.46) + 56)
            elif card.kind == "menu" and photo:
                frame = _rounded(_cover_fit(photo, (max_w, 540)), self.t.radius)
                img.paste(frame, (PAD, y), frame)
                draw = ImageDraw.Draw(img)
                y += 540 + 36
            elif card.kind == "tip":
                y = int(h * 0.36)

            if card.eyebrow:
                y = _draw_text_block(draw, card.eyebrow, xy=(PAD, y),
                                     font=self.fonts.get("body", 30),
                                     fill=_rgb(self.t.accent2), max_w=max_w) + 12
            y = _draw_text_block(draw, card.title, xy=(PAD, y), font=f_title_md,
                                 fill=text_col, max_w=max_w, line_height=1.15) + 12
            if card.subtitle:
                y = _draw_text_block(draw, card.subtitle, xy=(PAD, y),
                                     font=self.fonts.get("display", 52),
                                     fill=self.accent, max_w=max_w) + 8
            draw.rounded_rectangle([PAD, y + 12, PAD + 120, y + 20], radius=4, fill=self.accent)
            y += 46
            if card.body:
                y = _draw_text_block(draw, card.body, xy=(PAD, y), font=f_body,
                                     fill=text_col, max_w=max_w, line_height=1.66)

        # 각주 + 푸터
        if card.footnote and card.kind != "quote":
            _draw_text_block(draw, card.footnote, xy=(PAD, h - FOOTER_H - 34),
                             font=f_foot, fill=sub_col, max_w=max_w)
        foot_col = (255, 255, 255, 180) if on_photo else self.sub
        if handle:
            draw.text((PAD, h - 60), handle, font=f_foot, fill=foot_col[:3])
        draw.text((w - PAD, h - 60), f"{index:02d} / {total:02d}",
                  font=self.fonts.get("body", 25), fill=foot_col[:3], anchor="ra")

        if self.t.grain:
            img = img.filter(ImageFilter.SMOOTH)
        return img


def render_png(
    news: CardNews,
    out_paths: list[Path],
    *,
    theme: Theme | None = None,
    size: tuple[int, int] = (1080, 1350),
) -> list[Path]:
    theme = theme or get_theme(news.theme)
    renderer = PillowRenderer(theme, size)
    total = len(news.cards)
    results = []
    for i, (card, out) in enumerate(zip(news.cards, out_paths), start=1):
        out.parent.mkdir(parents=True, exist_ok=True)
        renderer.render_card(card, i, total, news.handle).save(out, "PNG")
        results.append(out)
    return results
