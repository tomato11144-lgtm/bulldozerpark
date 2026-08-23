from cardnews.models import Card, CardNews, slugify


def test_slugify_keeps_korean():
    assert slugify("성수동 파스타 맛집 TOP 5!") == "성수동-파스타-맛집-TOP-5"


def test_unknown_kind_falls_back_to_tip():
    assert Card(kind="nope").kind == "tip"


def test_meta_order_is_normalised():
    card = Card(kind="place", meta={"가격대": "2만원", "위치": "성수동", "기타": "x"})
    assert list(card.meta) == ["위치", "가격대", "기타"]


def test_json_roundtrip(tmp_path):
    news = CardNews(
        topic="성수동 파스타",
        title="성수동 파스타 BEST 3",
        cards=[Card(kind="cover", title="표지"), Card(kind="place", title="가게")],
        hashtags=["맛집", "#성수동"],
    )
    path = news.save_json(tmp_path / "cards.json")
    loaded = CardNews.load_json(path)
    assert loaded.title == news.title
    assert [c.kind for c in loaded.cards] == ["cover", "place"]


def test_full_caption_normalises_hashtags():
    news = CardNews(topic="t", caption="본문", hashtags=["맛집", "#성수동"])
    assert news.full_caption().endswith("#맛집 #성수동")


def test_wants_image():
    assert Card(kind="cover").wants_image
    assert not Card(kind="tip").wants_image
