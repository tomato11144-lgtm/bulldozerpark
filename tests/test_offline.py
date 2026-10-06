import pytest

from cardnews.offline import build_offline, detect_count, detect_food, detect_region


@pytest.mark.parametrize(
    "topic,region",
    [("성수동 파스타", "성수동"), ("강남 오마카세", "강남"), ("맛있는 국밥", "")],
)
def test_detect_region(topic, region):
    assert detect_region(topic) == region


def test_detect_food():
    label, query, tags = detect_food("성수동 파스타 맛집")
    assert label == "파스타"
    assert "pasta" in query
    assert tags


def test_detect_count():
    assert detect_count("성수동 맛집 TOP 5", 3) == 5
    assert detect_count("성수동 맛집", 3) == 3


def test_structure_starts_with_cover_and_ends_with_outro():
    news = build_offline("성수동 파스타 맛집 TOP 3", card_count=7)
    assert news.cards[0].kind == "cover"
    assert news.cards[-1].kind == "outro"


def test_topic_count_wins_over_card_count():
    news = build_offline("성수동 파스타 맛집 TOP 5", card_count=6)
    assert sum(1 for c in news.cards if c.kind == "place") == 5


def test_guide_topics_skip_place_cards():
    news = build_offline("국밥 고르는 법", card_count=6)
    assert not [c for c in news.cards if c.kind == "place"]


def test_filler_cards_are_not_duplicated():
    news = build_offline("와인 안주 페어링 총정리", card_count=9)
    titles = [c.title for c in news.cards]
    assert len(titles) == len(set(titles))


def test_placeholders_present_and_flagged():
    news = build_offline("성수동 파스타 맛집 TOP 2", card_count=7)
    assert any("{{" in c.title for c in news.cards)
    assert "자리표시자" in news.notes


def test_card_count_is_respected_within_bounds():
    news = build_offline("국밥 고르는 법", card_count=5)
    assert len(news.cards) == 5
