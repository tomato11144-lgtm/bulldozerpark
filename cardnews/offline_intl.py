"""영어 / 따갈로그 / Taglish 오프라인 문안 생성기.

API 키 없이도 라틴 문자권(특히 필리핀) 카드뉴스 뼈대가 나오게 하는 규칙 기반 생성기입니다.
한국어 경로는 offline.py 에 그대로 있고, 여기는 그 자매 구현입니다.
"""

from __future__ import annotations

import re

from .facts import parse_facts, sort_by_rating
from .locales import META_FIELDS, Locale
from .models import Card, CardNews

# 음식 키워드 -> (표시명, 스톡 사진 검색어, 해시태그, 주문 팁)
FOOD_LEXICON: list[tuple[tuple[str, ...], str, str, tuple[str, ...], str]] = [
    (("k-bbq", "kbbq", "korean bbq", "samgyup", "samgyeopsal", "unli"),
     "K-BBQ", "korean bbq grilled pork belly table",
     ("kbbq", "samgyupsal", "koreanbbq", "unlimitedsamgyupsal"),
     "Start with plain pork belly before the marinated cuts — you taste the meat first, "
     "and the sauces stop competing."),
    (("ramen", "ramyun", "noodle", "pancit", "mami"),
     "ramen", "ramen bowl closeup broth",
     ("ramen", "noodles", "ramenph"),
     "Drink the broth before you add chilli oil. That first sip tells you how long they simmered it."),
    (("sushi", "omakase", "sashimi", "japanese"),
     "Japanese", "sushi omakase counter",
     ("sushi", "omakase", "japanesefood"),
     "Sit at the counter if you can. The pieces reach you at the temperature they were made for."),
    (("cafe", "coffee", "latte", "matcha", "milk tea", "milktea", "dessert", "bakery"),
     "cafe", "cafe latte art wooden table",
     ("cafehopping", "coffee", "dessert"),
     "Ask what the beans are before you order iced. A light roast is wasted under that much ice."),
    (("lechon", "sisig", "adobo", "filipino", "pinoy", "silog", "kamayan"),
     "Filipino", "filipino food lechon rice plate",
     ("filipinofood", "pinoyfood", "lutongbahay"),
     "Order one shared dish more than you think you need — the rice disappears faster than the ulam."),
    (("pasta", "pizza", "italian"),
     "Italian", "pasta plate restaurant closeup",
     ("pasta", "pizza", "italianfood"),
     "If the menu is short, that is a good sign. It usually means they make the sauce that day."),
    (("bar", "cocktail", "craft beer", "speakeasy", "rooftop", "nightlife"),
     "bar", "cocktail bar night counter",
     ("cocktails", "barhopping", "nightlife"),
     "Two people, two drinks, one solid dish to share. Ordering food late is how the night stays civil."),
    (("buffet", "eat all you can", "eat-all-you-can"),
     "buffet", "buffet spread restaurant",
     ("buffet", "eatallyoucan"),
     "Do one slow lap before you take a plate. Deciding on the way is how people fill up on bread."),
    (("seafood", "crab", "shrimp", "grill"),
     "seafood", "grilled seafood platter",
     ("seafood", "seafoodlover"),
     "Ask what came in that morning. A good place will tell you without being asked twice."),
    (("steak", "grill", "meat", "burger"),
     "steak", "steak grilled closeup",
     ("steak", "meatlover", "burger"),
     "Order it one notch rarer than you like. It keeps cooking on the way to the table."),
]
DEFAULT_FOOD = ("food", "restaurant table food spread", ("foodie", "wheretoeat"),
                "Go at opening or an hour before closing. Same kitchen, a quarter of the queue.")

# 마닐라 및 필리핀 주요 상권 — 지역명이 들어가면 카피가 훨씬 구체적으로 나옵니다.
PH_AREAS = (
    "BGC", "Bonifacio Global City", "Makati", "Poblacion", "Salcedo", "Legazpi",
    "Rockwell", "Quezon City", "QC", "Tomas Morato", "Katipunan", "Maginhawa",
    "Cubao", "Eastwood", "Ortigas", "Kapitolyo", "Pasig", "Mandaluyong",
    "Greenhills", "San Juan", "Alabang", "Muntinlupa", "Parañaque", "Paranaque",
    "BF Homes", "Pasay", "Manila", "Malate", "Ermita", "Binondo", "Intramuros",
    "Marikina", "Antipolo", "Caloocan", "Las Piñas", "Taguig",
    "Cebu", "Davao", "Baguio", "Iloilo", "Bacolod", "Tagaytay", "Clark", "Pampanga",
)
GENERIC_AREAS = (
    "Seoul", "Tokyo", "Bangkok", "Singapore", "Hong Kong", "Taipei", "Jakarta",
    "Kuala Lumpur", "Ho Chi Minh", "Hanoi", "Sydney", "London", "New York", "LA",
)

COUNT_RE = re.compile(r"(?:top|best|#)?\s*(\d{1,2})\s*(?:places|spots|picks|best|list)?",
                      re.IGNORECASE)
GUIDE_HINTS = ("how to", "guide", "what to", "why", "explained", "difference",
               "before you", "rules", "mistakes", "101")


def detect_food(topic: str) -> tuple[str, str, tuple[str, ...], str]:
    lowered = topic.lower()
    for keys, label, query, tags, tip in FOOD_LEXICON:
        if any(k in lowered for k in keys):
            return label, query, tags, tip
    return DEFAULT_FOOD


def detect_area(topic: str) -> str:
    for name in (*PH_AREAS, *GENERIC_AREAS):
        if re.search(rf"\b{re.escape(name)}\b", topic, re.IGNORECASE):
            return name
    return ""


def detect_count(topic: str, default: int) -> int:
    match = COUNT_RE.search(topic)
    if match:
        value = int(match.group(1))
        if 1 <= value <= 10:
            return value
    return default


def looks_like_guide(topic: str) -> bool:
    lowered = topic.lower()
    return any(hint in lowered for hint in GUIDE_HINTS)


# --------------------------------------------------------------------------
# 언어별 문구
# --------------------------------------------------------------------------

def _tl(text_en: str, text_tl: str, locale: Locale) -> str:
    """언어에 맞는 문구 하나를 고릅니다 (병기 모드에서는 영어를 주 문구로)."""
    return text_tl if locale.code == "tl" else text_en


def _alt(text_tl: str, locale: Locale) -> str:
    """병기 모드에서만 보조 줄을 남깁니다."""
    return text_tl if locale.bilingual else ""


def build_offline_intl(
    topic: str,
    locale: Locale,
    *,
    card_count: int = 7,
    mode: str = "placeholder",
    facts: str = "",
    handle: str = "",
) -> CardNews:
    topic = topic.strip()
    food, image_query, food_tags, order_tip = detect_food(topic)
    area = detect_area(topic)
    where = area or "the city"
    taglish = locale.code in ("taglish", "tl")

    # --facts 를 줬으면 그 매장들이 목록이 됩니다.
    venues = sort_by_rating(parse_facts(facts)) if mode == "facts" else []

    fixed = 4
    if mode == "guide" or (looks_like_guide(topic) and not COUNT_RE.search(topic)):
        place_n = 0
    elif venues:
        place_n = len(venues)
        card_count = min(12, max(card_count, place_n + fixed))
    else:
        place_n = max(1, detect_count(topic, min(3, max(1, card_count - fixed))))
        card_count = min(12, max(card_count, place_n + fixed))
        place_n = min(place_n, card_count - fixed)

    cards: list[Card] = [
        _cover(topic, area, food, place_n, image_query, locale, taglish),
        _intro(area, food, where, image_query, locale, taglish),
    ]

    labels = {key: locale.meta_label(key) for key in META_FIELDS}
    for i in range(1, place_n + 1):
        venue = venues[i - 1] if i <= len(venues) else None
        if venue:
            card = Card(
                kind="place",
                badge=f"{i:02d}",
                title=venue.name,
                subtitle=venue.get("verdict"),
                body=venue.get("body"),
                meta=venue.meta(labels),
                image_query=f"{image_query} {i}",
                image_keywords=[food.lower(), str(i)],
            )
            if venue.get("rating"):
                card.eyebrow = _tl(f"Google {venue.get('rating')}",
                                   f"Google {venue.get('rating')}", locale)
            card.footnote = _tl(
                "Rating and hours as listed on Google — recheck before you go",
                "Base sa Google ang rating at oras — i-check ulit bago pumunta",
                locale,
            )
        else:
            card = Card(
                kind="place",
                badge=f"{i:02d}",
                title=f"{{{{VENUE {i}}}}}",
                subtitle=f"{{{{ONE LINE VERDICT {i}}}}}",
                body=f"{{{{WHY GO {i}}}}}",
                meta={
                    labels["location"]: f"{{{{LOCATION {i}}}}}",
                    labels["signature"]: f"{{{{MUST ORDER {i}}}}}",
                    labels["price"]: f"{{{{PRICE {i}}}}}",
                },
                footnote=_tl("Check hours before you go",
                             "I-check ang oras bago pumunta", locale),
                image_query=f"{image_query} {i}",
                image_keywords=[food.lower(), str(i)],
            )
        cards.append(card)

    cards.append(
        Card(
            kind="tip",
            badge="TIP 01",
            title=_tl("What to order first", "Ano ang unang i-order", locale),
            title_alt=_alt("Ano ang unang i-order", locale),
            body=order_tip,
            body_alt=_alt("Simple lang: doon ka mag-start, tapos saka mo subukan ang iba.", locale),
        )
    )

    fillers = _fillers(food, where, locale, taglish)
    while len(cards) < card_count - 1 and fillers:
        cards.append(fillers.pop(0))
    cards = cards[: card_count - 1]
    cards.append(_outro(handle, image_query, locale, taglish))

    tags = _hashtags(area, food, food_tags, locale)
    notes = _notes(mode, locale, venues)

    title = (f"{area} {food} BEST {place_n}" if place_n and area
             else f"{food} in {area}" if area
             else topic or "Card news")

    return CardNews(
        topic=topic,
        title=title,
        cards=cards,
        caption=_caption(topic, area, food, place_n, handle, locale, taglish),
        hashtags=tags,
        lang=locale.code,
        handle=handle,
        source="offline",
        notes=notes,
        meta={"mode": mode, "area": area, "food": food, "lang": locale.code},
    )


def _cover(topic, area, food, count, image_query, locale, taglish) -> Card:
    if count >= 2 and area:
        title = f"{area}\n{food} TOP {count}"
    elif area:
        title = f"Where to eat\n{food} in {area}"
    else:
        title = topic[:40] or f"{food} guide"
    return Card(
        kind="cover",
        badge=food.upper(),
        eyebrow=_tl(f"{food} guide" if area else "Editor's pick",
                    f"Gabay sa {food}" if area else "Pili ng editor", locale),
        title=title,
        subtitle=_tl("Saved lists beat search results",
                     "Mas okay ang naka-save kaysa maghanap sa search", locale),
        subtitle_alt=_alt("I-save mo muna, pag-usapan niyo mamaya", locale),
        image_query=image_query,
        image_keywords=[food.lower(), area.lower()] if area else [food.lower()],
    )


def _intro(area, food, where, image_query, locale, taglish) -> Card:
    return Card(
        kind="intro",
        title=_tl(f"Too many {food} spots, too little time",
                  f"Ang dami nang {food} spots, kulang ang oras", locale),
        title_alt=_alt(f"Ang dami nang {food} spots, kulang ang oras", locale),
        body=_tl(
            f"Search {food.lower()} in {where} and you get sponsored posts. "
            "This list starts from what actually matters: what to order, when to go, "
            "and what it costs you.",
            f"Kapag hinanap mo ang {food.lower()} sa {where}, puro sponsored ang lumalabas. "
            "Dito, ang mahalaga muna: ano ang i-order, kailan pumunta, magkano.",
            locale,
        ),
        body_alt=_alt("Walang paligoy-ligoy — kung saan sulit, yun ang nandito.", locale),
        image_query=f"{image_query} interior",
        image_keywords=[food.lower()],
    )


def _fillers(food, where, locale, taglish) -> list[Card]:
    return [
        Card(
            kind="list",
            badge="CHECK",
            title=_tl("Check before you go", "I-check bago umalis", locale),
            title_alt=_alt("I-check bago umalis", locale),
            bullets=[
                _tl("Do they take reservations", "May reservation ba", locale),
                _tl("Parking, or the nearest paid lot", "Parking, o saan ang pinakamalapit", locale),
                _tl("Card or cash only", "Card ba o cash lang", locale),
                _tl("Service charge on top", "May service charge pa ba", locale),
            ],
        ),
        Card(
            kind="list",
            badge="HOW TO PICK",
            title=_tl(f"Three signs of a good {food} place",
                      f"Tatlong senyales ng magandang {food} place", locale),
            title_alt=_alt(f"Tatlong senyales ng magandang {food} place", locale),
            bullets=[
                _tl("Repeat customers, not first-timers, in the reviews",
                    "Balik-balik ang customers, hindi puro first time", locale),
                _tl("A short menu they actually cook well",
                    "Maikling menu na talagang magaling nilang lutuin", locale),
                _tl("Full at lunch on a weekday",
                    "Puno tuwing lunch kahit weekday", locale),
            ],
        ),
        Card(
            kind="tip",
            badge="TIP 02",
            title=_tl("Going as a pair", "Kung dalawa kayo", locale),
            title_alt=_alt("Kung dalawa kayo", locale),
            body=_tl(
                "One signature dish, one side, one drink each. Add the second main only "
                "after the first one lands — it is the cheapest way to avoid ordering wrong.",
                "Isang signature, isang side, tig-isang inumin. Saka lang mag-add ng "
                "pangalawa pagdating ng una — para hindi sayang.",
                locale,
            ),
            body_alt=_alt("Wag mag-order lahat agad. Hintayin muna ang una.", locale),
        ),
        Card(
            kind="quote",
            body=_tl(
                f"The easiest way to eat well in {where} is to go where people go twice",
                f"Ang pinakamadaling paraan sa {where}: doon ka pumunta kung saan bumabalik ang tao",
                locale,
            ),
            footnote=_tl("Editor's note", "Tala ng editor", locale),
        ),
        Card(
            kind="list",
            badge="RED FLAGS",
            title=_tl("Think twice if you see this", "Mag-isip muna kung ganito", locale),
            title_alt=_alt("Mag-isip muna kung ganito", locale),
            bullets=[
                _tl("Reviews all posted in the same week", "Sabay-sabay ang petsa ng reviews", locale),
                _tl("No prices anywhere on the menu", "Walang presyo sa menu", locale),
                _tl("Photos that look nothing like the plate", "Malayo ang litrato sa totoong plato", locale),
            ],
        ),
    ]


def _outro(handle, image_query, locale, taglish) -> Card:
    return Card(
        kind="outro",
        title=_tl("Save this before you forget", "I-save mo na bago mo makalimutan", locale),
        title_alt=_alt("I-save mo na bago mo makalimutan", locale),
        body=_tl(
            "Tag the person you keep saying 'let's eat out' to. "
            "Been to one of these? Tell us in the comments and we will fold it into the next list.",
            "I-tag mo yung palagi mong sinasabihan ng 'kain tayo'. "
            "Nakapunta ka na? Comment mo para masama sa susunod.",
            locale,
        ),
        body_alt=_alt("Tag mo na siya, wag na mag-isip pa.", locale),
        subtitle=handle or _tl("SAVE THIS", "I-SAVE MO", locale),
        image_query=f"{image_query} friends sharing",
    )


def _hashtags(area, food, food_tags, locale) -> list[str]:
    tags: list[str] = []
    if area:
        squashed = area.replace(" ", "")
        tags += [f"{squashed}Eats", f"{squashed}Food", squashed]
    tags += [t for t in food_tags]
    tags += list(locale.hashtags)
    tags += ["foodie", "wheretoeat", "foodrecommendation"]
    if area and food:
        tags.append(f"{area.replace(' ', '')}{food.replace(' ', '').replace('-', '')}")
    seen, out = set(), []
    for tag in tags:
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            out.append(tag)
    return out[:18]


def _notes(mode: str, locale: Locale, venues: list | None = None) -> str:
    if mode == "guide":
        return "Guide-style set — no venues are named, so nothing needs verifying."
    if venues:
        missing = [v.name for v in venues if not v.get("signature")]
        lines = [
            f"{len(venues)} venues filled from your --facts file. "
            "Nothing outside that file was added.",
            "Google ratings drift — say when they were checked, or drop the numbers.",
        ]
        if missing:
            lines.append("No must-order dish supplied for: " + ", ".join(missing))
        return "\n".join(lines)
    return (
        "Replace every {{...}} placeholder with real, checked information before posting. "
        "Venue names, prices and hours were deliberately left blank so nothing is invented."
    )


def _caption(topic, area, food, count, handle, locale, taglish) -> str:
    head = (f"{count} {food} spots in {area} worth the trip." if count and area
            else f"{food} in {area}." if area
            else f"How to pick a {food.lower()} place without wasting a night.")
    if locale.code == "tl":
        head = (f"{count} {food} spots sa {area} na sulit puntahan." if count and area
                else f"{food} sa {area}." if area
                else f"Paano pumili ng {food.lower()} place na hindi sayang.")
        return (
            f"{head}\n"
            "Swipe mo lahat, tapos i-save yung isa na papuntahan niyo.\n"
            "May napuntahan ka na dito? Comment mo — isasama namin sa susunod.\n"
            f"{handle}".strip()
        )
    return (
        f"{head}\n"
        "Swipe through, then save the one you are actually going to.\n"
        "Been to any of these? Drop it in the comments and we will add it to the next round.\n"
        f"{handle}".strip()
    )
