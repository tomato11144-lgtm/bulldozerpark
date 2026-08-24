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


# --------------------------------------------------------------------------
# --facts 파싱 (API 키 없이도 매장이 채워지는지)
# --------------------------------------------------------------------------

FACTS = """
# Metro Manila K-BBQ

## 1. Sam Stew, Vertis North
- Google rating: 4.9 (5,000 reviews)
- Location: Vertis North, Quezon City
- Price: P500-1,000
- Signature: <<대표메뉴>>
- One-line verdict: Highest rated here

## 2. Sariwon Korean Barbecue
- 평점: 4.8 (2,700 reviews)
- 위치: Makati City
- 가격대: P500-3,000

## Notes for the writer
- 이 섹션은 매장이 아닙니다
"""


def test_parse_facts_reads_venues_and_skips_note_sections():
    from cardnews.facts import parse_facts

    venues = parse_facts(FACTS)
    assert [v.name for v in venues] == ["Sam Stew, Vertis North", "Sariwon Korean Barbecue"]


def test_parse_facts_accepts_korean_and_english_keys():
    from cardnews.facts import parse_facts

    sariwon = parse_facts(FACTS)[1]
    assert sariwon.get("location") == "Makati City"
    assert sariwon.get("price") == "P500-3,000"
    assert sariwon.rating == 4.8


def test_unfilled_placeholders_are_dropped():
    from cardnews.facts import parse_facts

    sam = parse_facts(FACTS)[0]
    assert not sam.get("signature")        # <<대표메뉴>> 는 버려야 합니다
    assert sam.get("verdict") == "Highest rated here"


def test_sort_by_rating_puts_unrated_last():
    from cardnews.facts import Venue, sort_by_rating

    ordered = sort_by_rating([
        Venue("low", {"rating": "4.5"}),
        Venue("none", {"location": "x"}),
        Venue("high", {"rating": "4.9"}),
    ])
    assert [v.name for v in ordered] == ["high", "low", "none"]


def test_offline_fills_place_cards_from_facts():
    from cardnews.locales import get_locale
    from cardnews.offline_intl import build_offline_intl

    news = build_offline_intl(
        "Manila K-BBQ best 5", get_locale("en+tl"),
        card_count=7, mode="facts", facts=FACTS,
    )
    places = [c for c in news.cards if c.kind == "place"]
    assert [c.title for c in places] == ["Sam Stew, Vertis North", "Sariwon Korean Barbecue"]
    assert "4.9" in places[0].eyebrow
    assert places[0].meta["LOCATION / SAAN"] == "Vertis North, Quezon City"
    # 파일에 없는 정보는 카드에도 없어야 합니다.
    assert "MUST ORDER" not in places[0].meta
    assert not any("{{" in c.title for c in places)


def test_korean_offline_also_fills_from_facts():
    from cardnews.offline import build_offline

    news = build_offline("마닐라 K-BBQ TOP 5", card_count=7, mode="facts", facts=FACTS)
    places = [c for c in news.cards if c.kind == "place"]
    assert places[0].title == "Sam Stew, Vertis North"
    assert places[0].meta["위치"] == "Vertis North, Quezon City"
    assert "구글 평점" in news.notes or "구글" in news.notes


def test_facts_notes_flag_missing_signatures():
    from cardnews.locales import get_locale
    from cardnews.offline_intl import build_offline_intl

    news = build_offline_intl(
        "Manila K-BBQ", get_locale("en"), card_count=7, mode="facts", facts=FACTS
    )
    assert "Sam Stew" in news.notes            # 대표메뉴가 비었다고 알려줘야 합니다
    assert "2 venues filled" in news.notes


def test_facts_ignored_outside_facts_mode():
    from cardnews.locales import get_locale
    from cardnews.offline_intl import build_offline_intl

    news = build_offline_intl(
        "Manila K-BBQ best 5", get_locale("en"),
        card_count=7, mode="placeholder", facts=FACTS,
    )
    assert all("{{" in c.title for c in news.cards if c.kind == "place")


def test_taglish_is_not_just_english_with_a_swipe_label():
    """taglish 모드가 영어 문구를 그대로 쓰던 회귀를 막습니다."""
    from cardnews.locales import get_locale
    from cardnews.offline_intl import build_offline_intl

    def titles(code):
        news = build_offline_intl("Manila K-BBQ best 3", get_locale(code), card_count=8)
        return [c.title for c in news.cards]

    english, taglish = titles("en"), titles("taglish")
    # 표지 제목은 지역+음식이라 언어와 무관하게 같습니다. 나머지는 달라야 합니다.
    differing = sum(1 for a, b in zip(english, taglish) if a != b)
    assert differing >= 3, f"taglish 가 영어와 거의 같습니다 ({differing}개만 다름)"


def test_each_language_has_its_own_register():
    from cardnews.locales import get_locale
    from cardnews.offline_intl import build_offline_intl

    def body(code):
        news = build_offline_intl("Manila K-BBQ best 3", get_locale(code), card_count=8)
        return " ".join(c.title + c.body + c.subtitle for c in news.cards)

    en, tl, tg = body("en"), body("tl"), body("taglish")
    assert en != tl and tl != tg and en != tg
    # 따갈로그·Taglish 는 필리핀어 단서가 있어야 합니다.
    for text in (tl, tg):
        assert any(word in text for word in ("Ang ", "mo ", "ka ", "ng ", "sa "))


def test_taglish_caption_is_filipino():
    from cardnews.locales import get_locale
    from cardnews.offline_intl import build_offline_intl

    news = build_offline_intl("Manila K-BBQ best 3", get_locale("taglish"), card_count=7)
    assert "Swipe mo lahat" in news.caption
