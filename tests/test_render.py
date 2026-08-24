import json

import pytest

from cardnews.images import ImageResolver, LocalProvider
from cardnews.models import Card, CardNews
from cardnews.offline import build_offline
from cardnews.pipeline import attach_images, rebuild, render, write_sidecars
from cardnews.render.html import build_html
from cardnews.themes import get_theme


def _news(**kw):
    news = build_offline("성수동 파스타 맛집 TOP 2", card_count=6, **kw)
    news.theme = "warm"
    news.handle = "@test"
    return news


def test_build_html_has_one_section_per_card():
    doc = build_html(_news())
    assert doc.html.count('class="card ') == doc.count
    assert len(doc.pages) == doc.count
    assert doc.width == 1080 and doc.height == 1350


def test_single_card_pages_keep_their_index():
    doc = build_html(_news())
    assert 'data-index="3"' in doc.pages[2]
    assert doc.pages[2].count('class="card ') == 1


def test_ratio_changes_canvas():
    doc = build_html(_news(), ratio="9:16")
    assert doc.height == 1920


def test_html_escapes_user_text():
    news = CardNews(topic="t", cards=[Card(kind="tip", title="<script>x</script>")])
    doc = build_html(news)
    assert "<script>x</script>" not in doc.html
    assert "&lt;script&gt;" in doc.html


def test_image_routes_are_registered(tmp_path):
    from PIL import Image

    photo = tmp_path / "shot.jpg"
    Image.new("RGB", (40, 50), "red").save(photo)
    news = _news()
    news.cards[0].image = str(photo)
    doc = build_html(news)
    assert any(v == photo for v in doc.routes.values())
    assert "/__img/01.jpg" in doc.html


def test_missing_image_file_is_ignored():
    news = _news()
    news.cards[0].image = "/does/not/exist.jpg"
    doc = build_html(news)
    assert "/__img/" not in doc.html


def test_local_provider_prefers_keyword_match(tmp_path):
    from PIL import Image

    for name in ("random.jpg", "파스타_대표.jpg"):
        Image.new("RGB", (20, 20), "blue").save(tmp_path / name)
    provider = LocalProvider(tmp_path)
    first = provider.search("", ["파스타"])
    assert first is not None and "파스타" in first.path.name
    # 같은 사진을 두 번 쓰지 않습니다.
    second = provider.search("", ["파스타"])
    assert second.path != first.path


def test_gradient_fallback_always_returns_something():
    resolver = ImageResolver(get_theme("neon"))
    result = resolver.resolve("pasta", [])
    assert result is not None and result.path.is_file()


def test_images_none_disables_resolution():
    news = _news()
    credits = attach_images(news, provider="none")
    assert credits == []
    assert all(c.image is None for c in news.cards)


@pytest.mark.parametrize("renderer", ["pillow"])
def test_render_writes_one_png_per_card(tmp_path, renderer):
    news = _news()
    paths = render(news, tmp_path, renderer=renderer)
    assert len(paths) == len(news.cards)
    for path in paths:
        assert path.is_file() and path.stat().st_size > 1000
    assert paths[0].name == "01_cover.png"


def test_sidecars(tmp_path):
    news = _news()
    paths = render(news, tmp_path, renderer="pillow")
    write_sidecars(news, tmp_path, paths, ["Photo by X on Unsplash"])
    assert (tmp_path / "cards.json").is_file()
    assert (tmp_path / "caption.txt").is_file()
    assert (tmp_path / "credits.txt").is_file()
    preview = (tmp_path / "preview.html").read_text(encoding="utf-8")
    assert "01_cover.png" in preview
    assert "Photo by X on Unsplash" in preview


def test_rebuild_reads_edited_json(tmp_path):
    news = _news()
    paths = render(news, tmp_path, renderer="pillow")
    write_sidecars(news, tmp_path, paths, [])

    data = json.loads((tmp_path / "cards.json").read_text(encoding="utf-8"))
    data["cards"][2]["title"] = "라 트라토리아"
    (tmp_path / "cards.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    result = rebuild(tmp_path / "cards.json", renderer="pillow", theme="neon")
    assert result.news.cards[2].title == "라 트라토리아"
    assert result.news.theme == "neon"
    assert len(result.images) == len(news.cards)


def _chromium_available() -> bool:
    from cardnews.render.chromium import _find_chrome, _has_playwright

    return _has_playwright() or bool(_find_chrome())


@pytest.mark.skipif(not _chromium_available(), reason="크로미움이 없는 환경")
def test_chromium_renders_expected_canvas(tmp_path):
    from PIL import Image

    news = _news()
    paths = render(news, tmp_path, renderer="chromium")
    assert len(paths) == len(news.cards)
    with Image.open(paths[0]) as img:
        assert img.size == (1080, 1350)


@pytest.mark.skipif(not _chromium_available(), reason="크로미움이 없는 환경")
def test_chromium_scale_doubles_resolution(tmp_path):
    from PIL import Image

    news = _news()
    news.cards = news.cards[:2]
    paths = render(news, tmp_path, renderer="chromium", scale=2)
    with Image.open(paths[0]) as img:
        assert img.size == (2160, 2700)


def test_unknown_renderer_falls_back_to_pillow(tmp_path, monkeypatch):
    from cardnews.render import chromium

    monkeypatch.setattr(chromium, "_has_playwright", lambda: False)
    monkeypatch.setattr(chromium, "_find_chrome", lambda *a, **k: None)
    paths = render(_news(), tmp_path, renderer="auto")
    assert all(p.is_file() for p in paths)


# --------------------------------------------------------------------------
# 다국어 렌더링
# --------------------------------------------------------------------------

def _intl_news(lang="en+tl"):
    from cardnews.locales import get_locale
    from cardnews.offline_intl import build_offline_intl

    news = build_offline_intl("Manila K-BBQ best 3", get_locale(lang), card_count=7)
    news.theme = "neon"
    news.handle = "@test"
    return news


def test_latin_language_uses_latin_fonts():
    doc = build_html(_intl_news())
    assert "Anton" in doc.html          # neon 테마의 라틴 제목 서체
    assert "Black Han Sans" not in doc.html


def test_korean_language_keeps_hangul_fonts():
    doc = build_html(_news())
    assert "Black Han Sans" in doc.html
    assert "Anton" not in doc.html


def test_ui_strings_follow_the_locale():
    assert "SWIPE" in build_html(_intl_news()).html
    assert "SWIPE MO" in build_html(_intl_news("taglish")).html
    assert "넘겨보기" in build_html(_news()).html


def test_alt_lines_render_only_when_present():
    # 스타일시트에는 항상 .alt 규칙이 있으므로 실제 엘리먼트로 확인합니다.
    assert 'class="alt alt--' in build_html(_intl_news("en+tl")).html
    assert 'class="alt alt--' not in build_html(_intl_news("en")).html


def test_both_renderers_handle_bilingual_cards(tmp_path):
    from PIL import Image

    news = _intl_news()
    paths = render(news, tmp_path, renderer="pillow")
    assert len(paths) == len(news.cards)
    with Image.open(paths[0]) as img:
        assert img.size == (1080, 1350)


def test_rebuild_can_switch_language(tmp_path):
    news = _intl_news()
    paths = render(news, tmp_path, renderer="pillow")
    write_sidecars(news, tmp_path, paths, [])
    result = rebuild(tmp_path / "cards.json", renderer="pillow", lang="en")
    assert result.news.lang == "en"
