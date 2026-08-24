"""주제 -> 결과 폴더까지 한 번에.

    from cardnews.pipeline import create
    result = create("성수동 파스타 맛집 TOP 5")

결과 폴더 구성:
    01_cover.png ... 08_outro.png   업로드용 이미지
    cards.json                       카드 데이터 (고쳐서 다시 렌더 가능)
    caption.txt                      인스타 본문 + 해시태그
    credits.txt                      사진 출처 (있을 때만)
    preview.html                     브라우저로 넘겨보는 미리보기
"""

from __future__ import annotations

import html
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .config import DEFAULT_OUT_DIR, Settings, canvas_size
from .content import DEFAULT_AUDIENCE, DEFAULT_TONE, generate
from .images import ImageResolver
from .models import CardNews
from .render.html import build_html
from .themes import get_theme, suggest_theme

log = logging.getLogger(__name__)


@dataclass
class Result:
    news: CardNews
    out_dir: Path
    images: list[Path] = field(default_factory=list)
    credits: list[str] = field(default_factory=list)
    renderer: str = "chromium"

    @property
    def caption_path(self) -> Path:
        return self.out_dir / "caption.txt"

    @property
    def json_path(self) -> Path:
        return self.out_dir / "cards.json"

    @property
    def preview_path(self) -> Path:
        return self.out_dir / "preview.html"


def _card_filename(index: int, kind: str) -> str:
    return f"{index:02d}_{kind}.png"


# 실제 상호가 적힌 카드에 스톡/그라데이션 사진이 붙으면, 보는 사람은 그 가게의
# 사진으로 읽습니다. 그건 사실이 아니므로 각주로 분명히 밝힙니다.
ILLUSTRATIVE_SOURCES = ("unsplash", "pexels", "gradient")
ILLUSTRATIVE_NOTE = {
    "ko": "이미지는 이해를 돕기 위한 예시입니다",
    "en": "Photo is illustrative, not the venue",
    "tl": "Larawan ay halimbawa lang, hindi sa mismong resto",
    "taglish": "Photo is illustrative lang, hindi actual sa resto",
    "en+tl": "Photo is illustrative, not the venue",
}


def _mark_illustrative(card, source: str, lang: str) -> None:
    """상호가 있는 카드 + 남의 사진 -> 각주 추가. 자리표시자 카드는 건너뜁니다."""
    if card.kind not in ("place", "menu") or source not in ILLUSTRATIVE_SOURCES:
        return
    if not card.title or "{{" in card.title:
        return
    note = ILLUSTRATIVE_NOTE.get(lang, ILLUSTRATIVE_NOTE["en"])
    if note in card.footnote:
        return
    card.footnote = f"{card.footnote} · {note}".strip(" ·")


def attach_images(
    news: CardNews,
    *,
    settings: Settings | None = None,
    local_dir: str | Path | None = None,
    provider: str = "auto",
    ratio: str = "4:5",
) -> list[str]:
    """카드마다 사진을 붙이고, 출처 문구 목록을 돌려줍니다."""
    theme = get_theme(news.theme)
    resolver = ImageResolver(
        theme, settings, local_dir=local_dir, provider=provider, size=canvas_size(ratio)
    )
    credits: list[str] = []
    if not resolver.enabled:
        return credits

    for card in news.cards:
        if card.image:            # 이미 지정돼 있으면 존중합니다.
            continue
        if not card.wants_image:
            continue
        result = resolver.resolve(card.image_query, card.image_keywords)
        if not result:
            continue
        card.image = str(result.path)
        card.image_credit = result.credit
        _mark_illustrative(card, result.source, news.lang)
        if result.credit and result.credit not in credits:
            credits.append(result.credit)
    return credits


def render(
    news: CardNews,
    out_dir: str | Path,
    *,
    ratio: str = "4:5",
    renderer: str = "auto",     # auto | chromium | pillow
    scale: float = 1.0,
    chromium_path: str = "",
) -> list[Path]:
    """카드뉴스를 PNG 로 뽑습니다."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    theme = get_theme(news.theme)
    paths = [
        out_dir / _card_filename(i, card.kind)
        for i, card in enumerate(news.cards, start=1)
    ]

    if renderer == "pillow":
        from .render.pillow import render_png as pillow_render
        return pillow_render(news, paths, theme=theme, size=canvas_size(ratio))

    from .render.chromium import render_png as chromium_render

    doc = build_html(news, theme=theme, ratio=ratio)
    if doc.missing_fonts:
        log.warning(
            "폰트가 없어 기본 서체로 대체됩니다: %s — `python scripts/fetch_fonts.py` 를 실행하세요.",
            ", ".join(doc.missing_fonts),
        )
    try:
        return chromium_render(doc, paths, scale=scale, chromium_path=chromium_path)
    except Exception as exc:  # noqa: BLE001
        if renderer == "chromium":
            raise
        log.warning("크로미움 렌더 실패(%s) — Pillow 렌더러로 대체합니다.", exc)
        from .render.pillow import render_png as pillow_render
        return pillow_render(news, paths, theme=theme, size=canvas_size(ratio))


def write_sidecars(
    news: CardNews, out_dir: Path, images: list[Path], credits: list[str]
) -> None:
    """캡션·데이터·출처·미리보기 파일을 씁니다."""
    news.save_json(out_dir / "cards.json")
    (out_dir / "caption.txt").write_text(news.full_caption() + "\n", encoding="utf-8")
    if credits:
        (out_dir / "credits.txt").write_text(
            "이 카드뉴스에 쓰인 사진 출처\n\n" + "\n".join(f"- {c}" for c in credits) + "\n",
            encoding="utf-8",
        )
    (out_dir / "preview.html").write_text(
        _preview_html(news, images, credits), encoding="utf-8"
    )


def _preview_html(news: CardNews, images: list[Path], credits: list[str]) -> str:
    """결과를 한눈에 보는 컨택트 시트. 이미지 파일만 참조하므로 어디서 열어도 됩니다."""
    esc = html.escape
    thumbs = "\n".join(
        f'<figure><img src="{esc(p.name)}" alt="card {i}"><figcaption>{i:02d} · '
        f'{esc(news.cards[i - 1].kind)}</figcaption></figure>'
        for i, p in enumerate(images, start=1)
    )
    warn = ""
    if news.notes:
        warn = f'<div class="notes"><strong>확인할 것</strong><p>{esc(news.notes)}</p></div>'
    credit_html = ""
    if credits:
        credit_html = "<h2>사진 출처</h2><ul>" + "".join(
            f"<li>{esc(c)}</li>" for c in credits) + "</ul>"
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(news.title)} — 미리보기</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
         margin: 0; padding: 40px; background: #12121a; color: #ececf1; }}
  h1 {{ font-size: 28px; margin: 0 0 6px; }}
  .meta {{ color: #9a9aa8; font-size: 14px; margin-bottom: 28px; }}
  .sheet {{ display: grid; gap: 20px; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }}
  figure {{ margin: 0; }}
  img {{ width: 100%; border-radius: 12px; display: block; box-shadow: 0 8px 24px rgba(0,0,0,.4); }}
  figcaption {{ font-size: 12px; color: #8b8b99; margin-top: 8px; letter-spacing: .04em; }}
  .notes {{ background: #2a2216; border-left: 4px solid #e0a33c; padding: 16px 20px;
            border-radius: 8px; margin-bottom: 28px; }}
  .notes p {{ margin: 8px 0 0; white-space: pre-wrap; color: #e8d9bd; }}
  pre {{ background: #1c1c26; padding: 20px; border-radius: 12px; white-space: pre-wrap;
         line-height: 1.7; font-size: 14px; }}
  h2 {{ font-size: 18px; margin-top: 36px; }}
  ul {{ color: #9a9aa8; font-size: 14px; }}
</style></head>
<body>
<h1>{esc(news.title)}</h1>
<div class="meta">{esc(news.topic)} · 테마 {esc(news.theme)} · {len(images)}장 · 생성 {esc(news.source)}</div>
{warn}
<div class="sheet">{thumbs}</div>
<h2>인스타 캡션</h2>
<pre>{esc(news.full_caption())}</pre>
{credit_html}
</body></html>
"""


def create(
    topic: str,
    *,
    out_dir: str | Path | None = None,
    theme: str = "auto",
    card_count: int = 7,
    ratio: str = "4:5",
    tone: str = DEFAULT_TONE,
    audience: str = DEFAULT_AUDIENCE,
    mode: str | None = None,
    facts: str = "",
    handle: str = "",
    extra: str = "",
    lang: str = "ko",
    images: str = "auto",
    images_dir: str | Path | None = None,
    renderer: str = "auto",
    scale: float = 1.0,
    offline: bool = False,
    settings: Settings | None = None,
    clean: bool = False,
) -> Result:
    """주제 하나로 카드뉴스 한 세트를 만들어 폴더에 떨궈 놓습니다."""
    settings = settings or Settings.from_env()
    theme_name = suggest_theme(topic) if theme in ("auto", "", None) else theme

    news = generate(
        topic,
        settings=settings,
        card_count=card_count,
        tone=tone,
        audience=audience,
        mode=mode,
        facts=facts,
        handle=handle,
        extra=extra,
        theme=theme_name,
        lang=lang,
        offline=offline,
    )

    credits = attach_images(
        news, settings=settings, local_dir=images_dir, provider=images, ratio=ratio
    )

    target = Path(out_dir) if out_dir else DEFAULT_OUT_DIR / news.slug
    if clean and target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    paths = render(
        news, target, ratio=ratio, renderer=renderer, scale=scale,
        chromium_path=settings.chromium_path,
    )
    write_sidecars(news, target, paths, credits)
    return Result(news=news, out_dir=target, images=paths, credits=credits,
                  renderer=renderer)


def rebuild(
    json_path: str | Path,
    *,
    out_dir: str | Path | None = None,
    ratio: str = "4:5",
    renderer: str = "auto",
    scale: float = 1.0,
    theme: str | None = None,
    lang: str | None = None,
    settings: Settings | None = None,
) -> Result:
    """cards.json 을 고친 뒤 다시 렌더링합니다(자리표시자를 채운 다음 쓰는 경로)."""
    settings = settings or Settings.from_env()
    json_path = Path(json_path)
    news = CardNews.load_json(json_path)
    if theme:
        news.theme = theme
    if lang:
        news.lang = lang
    target = Path(out_dir) if out_dir else json_path.parent
    target.mkdir(parents=True, exist_ok=True)
    paths = render(news, target, ratio=ratio, renderer=renderer, scale=scale,
                   chromium_path=settings.chromium_path)
    credits = [c.image_credit for c in news.cards if c.image_credit]
    write_sidecars(news, target, paths, list(dict.fromkeys(credits)))
    return Result(news=news, out_dir=target, images=paths, credits=credits,
                  renderer=renderer)
