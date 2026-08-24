import pytest

from cardnews.locales import LOCALES, META_FIELDS, get_locale, meta_order
from cardnews.models import Card
from cardnews.offline_intl import (
    build_offline_intl, detect_area, detect_count, detect_food, looks_like_guide,
)
from cardnews.themes import THEMES, all_fonts


@pytest.mark.parametrize("loc", LOCALES.values(), ids=lambda l: l.code)
def test_every_locale_labels_every_meta_field(loc):
    assert set(loc.meta) == set(META_FIELDS)
    assert loc.ui.get("swipe") and loc.ui.get("arrow")
    assert loc.script in ("hangul", "latin")


def test_unknown_language_falls_back_to_korean():
    assert get_locale("klingon").code == "ko"
    assert get_locale(None).code == "ko"


def test_only_en_tl_is_bilingual():
    assert get_locale("en+tl").bilingual
    assert not get_locale("taglish").bilingual
    assert not get_locale("ko").bilingual


def test_meta_order_covers_all_locales():
    order = meta_order()
    for loc in LOCALES.values():
        for label in loc.meta.values():
            assert label in order


def test_card_meta_sorts_by_locale_labels():
    card = Card(kind="place", meta={"PRESYO": "P800", "SAAN": "BGC", "PILA": "20 min"})
    assert list(card.meta) == ["SAAN", "PRESYO", "PILA"]


@pytest.mark.parametrize("theme", THEMES.values(), ids=lambda t: t.name)
def test_themes_have_a_latin_pair(theme):
    assert theme.latin_display and theme.latin_body
    assert theme.fonts_for("latin") == theme.latin_fonts
    assert theme.fonts_for("hangul") == theme.fonts
    assert theme.display_for("latin") != theme.display_for("hangul")


def test_all_fonts_can_be_filtered_by_script():
    latin, hangul = all_fonts("latin"), all_fonts("hangul")
    assert not set(latin) & set(hangul)
    assert set(all_fonts()) == set(latin) | set(hangul)


@pytest.mark.parametrize(
    "topic,expected",
    [
        ("Manila K-BBQ best 5", "Manila"),
        ("Best unli samgyup in BGC", "BGC"),
        ("Where to eat in Quezon City", "Quezon City"),
        ("Great noodles somewhere", ""),
    ],
)
def test_detect_area(topic, expected):
    assert detect_area(topic) == expected


def test_detect_food_recognises_local_kbbq_terms():
    for topic in ("Manila K-BBQ best 5", "unli samgyupsal in QC", "korean bbq Makati"):
        label, query, tags, tip = detect_food(topic)
        assert label == "K-BBQ"
        assert "samgyupsal" in tags


def test_detect_count_and_guide_hints():
    assert detect_count("Manila K-BBQ best 5", 3) == 5
    assert detect_count("Manila K-BBQ", 3) == 3
    assert looks_like_guide("How to pick a K-BBQ place")
    assert not looks_like_guide("Manila K-BBQ best 5")


def test_intl_structure_and_placeholders():
    news = build_offline_intl("Manila K-BBQ best 5", get_locale("en+tl"), card_count=7)
    assert news.cards[0].kind == "cover"
    assert news.cards[-1].kind == "outro"
    assert sum(1 for c in news.cards if c.kind == "place") == 5
    assert any("{{" in c.title for c in news.cards)
    assert "placeholder" in news.notes


def test_intl_uses_localised_meta_labels():
    news = build_offline_intl("Manila K-BBQ best 3", get_locale("tl"), card_count=7)
    place = next(c for c in news.cards if c.kind == "place")
    assert "SAAN" in place.meta and "PRESYO" in place.meta


def test_bilingual_mode_fills_alt_lines_and_others_do_not():
    bi = build_offline_intl("Manila K-BBQ best 3", get_locale("en+tl"), card_count=8)
    assert any(c.title_alt or c.body_alt or c.subtitle_alt for c in bi.cards)

    mono = build_offline_intl("Manila K-BBQ best 3", get_locale("en"), card_count=8)
    assert not any(c.title_alt or c.body_alt or c.subtitle_alt for c in mono.cards)


def test_tagalog_locale_writes_tagalog_primary():
    news = build_offline_intl("Manila K-BBQ best 3", get_locale("tl"), card_count=7)
    joined = " ".join(c.title + c.body for c in news.cards)
    assert "I-check" in joined or "Ang dami" in joined


def test_area_and_food_reach_the_hashtags():
    news = build_offline_intl("Manila K-BBQ best 5", get_locale("en"), card_count=7)
    lowered = [t.lower() for t in news.hashtags]
    assert "manilaeats" in lowered
    assert "samgyupsal" in lowered
    assert len(news.hashtags) == len(set(lowered))
