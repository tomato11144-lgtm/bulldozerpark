"""오프라인 문안 생성기.

API 키 없이도 카드뉴스 뼈대가 나오도록 하는 규칙 기반 생성기입니다.
주제 문장에서 지역·음식 카테고리·개수를 뽑아내 카드 구성을 짜고,
가게별 사실 정보 자리에는 자리표시자를 넣습니다.

목적은 "Claude 대체"가 아니라 "키 없이도 레이아웃과 파이프라인을 끝까지 확인"입니다.
"""

from __future__ import annotations

import re

from .facts import parse_facts, sort_by_rating
from .locales import META_FIELDS, get_locale
from .models import Card, CardNews

# 한글 음식 키워드 -> (표시용 이름, 영문 스톡 검색어, 추천 해시태그)
FOOD_LEXICON: list[tuple[tuple[str, ...], str, str, tuple[str, ...]]] = [
    (("파스타", "이탈리안", "리조또", "피자"), "파스타", "pasta plate restaurant closeup",
     ("파스타맛집", "이탈리안", "파스타")),
    (("스시", "오마카세", "초밥", "japanese"), "스시", "sushi omakase counter",
     ("스시", "오마카세", "일식")),
    (("한우", "고기", "삼겹살", "구이", "갈비", "정육"), "고깃집", "korean bbq grilled meat",
     ("고기맛집", "삼겹살", "한우")),
    (("국밥", "탕", "찌개", "해장", "곰탕", "설렁탕"), "국밥", "korean soup hot pot bowl",
     ("국밥", "해장", "한식")),
    (("카페", "커피", "라떼", "디저트", "베이커리", "빵", "케이크"), "카페",
     "cafe latte art wooden table", ("카페", "디저트", "커피")),
    (("브런치", "샐러드", "비건", "샌드위치"), "브런치", "brunch plate eggs avocado",
     ("브런치", "브런치카페", "샐러드")),
    (("술", "포차", "이자카야", "안주", "맥주", "와인", "야식"), "술집",
     "izakaya night bar food", ("술집", "안주", "포차")),
    (("중식", "짜장", "짬뽕", "탕수육", "마라"), "중식", "chinese noodles wok",
     ("중식", "짜장면", "탕수육")),
    (("분식", "떡볶이", "김밥", "순대"), "분식", "korean street food tteokbokki",
     ("분식", "떡볶이", "김밥")),
    (("치킨", "닭"), "치킨", "fried chicken korean", ("치킨", "치맥")),
    (("면", "국수", "냉면", "라멘", "우동"), "면요리", "noodle bowl closeup",
     ("면스타그램", "국수", "라멘")),
]

DEFAULT_FOOD = ("맛집", "korean restaurant food table", ("맛집", "맛집추천", "food"))

# 지역 접미사 — "성수동", "강남구", "부산" 같은 표현을 잡습니다.
REGION_RE = re.compile(r"([가-힣]{1,6}(?:동|읍|면|리|구|시|군|역|로|길))")
# 접미사 없이 쓰이는 대표 상권/지역명
BARE_REGIONS = (
    "강남", "홍대", "이태원", "연남", "망원", "성수", "한남", "서촌", "북촌", "을지로",
    "신촌", "건대", "잠실", "판교", "여의도", "종로", "합정", "가로수길", "익선동",
    "해운대", "서면", "전포", "경리단", "송리단", "왕십리", "회기", "노원", "부산", "대구",
    "제주", "속초", "강릉", "전주", "광주", "대전", "인천", "수원", "일산", "분당",
)
# "고르는 법" 류 주제는 가게 나열보다 가이드형 구성이 맞습니다.
GUIDE_HINTS = ("고르는", "고르기", "차이", "방법", "이유", "알아야", "기준", "가이드", "정리", "총정리", "상식")
COUNT_RE = re.compile(r"(?:top|베스트|BEST)?\s*(\d{1,2})\s*(?:곳|개|군데|선|위)?", re.IGNORECASE)


def detect_food(topic: str) -> tuple[str, str, tuple[str, ...]]:
    lowered = topic.lower()
    for keys, label, query, tags in FOOD_LEXICON:
        if any(k in lowered for k in keys):
            return label, query, tags
    return DEFAULT_FOOD


def detect_region(topic: str) -> str:
    match = REGION_RE.search(topic)
    if match:
        return match.group(1)
    for name in BARE_REGIONS:
        if name in topic:
            return name
    return ""


def looks_like_guide(topic: str) -> bool:
    return any(hint in topic for hint in GUIDE_HINTS)


def detect_count(topic: str, default: int) -> int:
    match = COUNT_RE.search(topic)
    if match:
        value = int(match.group(1))
        if 1 <= value <= 10:
            return value
    return default


def build_offline(
    topic: str,
    *,
    card_count: int = 7,
    mode: str = "placeholder",
    facts: str = "",
    handle: str = "",
) -> CardNews:
    """주제 문장으로 카드뉴스 뼈대를 만듭니다."""
    topic = topic.strip()
    food_label, image_query, food_tags = detect_food(topic)
    region = detect_region(topic)
    place_label = f"{region} {food_label}".strip()

    # cover + intro + place*n + tip + outro 로 카드 수를 맞춥니다.
    venues = sort_by_rating(parse_facts(facts)) if mode == "facts" else []

    fixed = 4  # cover, intro, tip, outro
    if mode == "guide" or (looks_like_guide(topic) and not COUNT_RE.search(topic)):
        place_n = 0
    elif venues:
        place_n = len(venues)
        card_count = min(12, max(card_count, place_n + fixed))
    else:
        # 주제에 "TOP 5" 처럼 개수가 박혀 있으면 그 수를 우선하고 카드 수를 늘립니다.
        place_n = max(1, detect_count(topic, min(3, max(1, card_count - fixed))))
        card_count = min(12, max(card_count, place_n + fixed))
        place_n = min(place_n, card_count - fixed)

    cards: list[Card] = [
        Card(
            kind="cover",
            badge=food_label,
            eyebrow=f"{food_label} 가이드" if region else "오늘의 추천",
            title=_cover_title(topic, region, food_label, place_n),
            subtitle="스와이프해서 확인하세요",
            image_query=image_query,
            image_keywords=[food_label, region] if region else [food_label],
        ),
        Card(
            kind="intro",
            title=f"{place_label or food_label}, 어디로 갈지 고민되죠",
            body=(
                f"검색해도 광고만 나오고, 막상 가면 웨이팅이 길죠. "
                f"{'이 지역' if region else '이 카테고리'}에서 실패 확률을 줄이는 기준부터 정리했습니다."
            ),
            image_query=f"{image_query} ambience",
            image_keywords=[food_label],
        ),
    ]

    ko_labels = {key: get_locale("ko").meta_label(key) for key in META_FIELDS}
    for i in range(1, place_n + 1):
        venue = venues[i - 1] if i <= len(venues) else None
        if venue:
            card = Card(
                kind="place",
                badge=f"{i:02d}",
                title=venue.name,
                subtitle=venue.get("verdict"),
                body=venue.get("body"),
                meta=venue.meta(ko_labels),
                eyebrow=f"구글 {venue.get('rating')}" if venue.get("rating") else "",
                footnote="평점·영업시간은 구글 기준 — 방문 전 다시 확인하세요",
                image_query=f"{image_query} {i}",
                image_keywords=[food_label, f"{i}"],
            )
        else:
            card = Card(
                kind="place",
                badge=f"{i:02d}",
                title=f"{{{{가게명{i}}}}}",
                subtitle=f"{{{{한줄평{i}}}}}",
                body=f"{{{{추천이유{i}}}}}",
                meta={
                    "위치": f"{{{{위치{i}}}}}",
                    "대표메뉴": f"{{{{대표메뉴{i}}}}}",
                    "가격대": f"{{{{가격대{i}}}}}",
                },
                image_query=f"{image_query} {i}",
                image_keywords=[food_label, f"{i}"],
                footnote="방문 전 영업시간 확인",
            )
        cards.append(card)

    cards.append(
        Card(
            kind="tip",
            badge="TIP",
            title=_tip_title(food_label),
            body=_tip_body(food_label),
            image_keywords=[food_label],
        )
    )

    # 남는 자리는 체크리스트/팁 카드를 돌려가며 채웁니다(같은 카드 반복 방지).
    fillers = _filler_cards(food_label, region)
    while len(cards) < card_count - 1 and fillers:
        cards.append(fillers.pop(0))

    cards = cards[: card_count - 1]
    cards.append(
        Card(
            kind="outro",
            title="저장해두고 갈 때 꺼내보세요",
            body="같이 갈 사람 태그하면 약속이 잡힙니다. 다녀오셨다면 후기도 댓글로 남겨주세요.",
            subtitle=handle or "",
            image_query=f"{image_query} table sharing",
        )
    )

    tags = ["맛집", "맛집추천", "맛스타그램", "먹스타그램", *food_tags]
    if region:
        tags = [f"{region}맛집", region, *tags]
    if place_label:
        tags.append(place_label.replace(" ", ""))

    if venues:
        notes_lines = [
            f"--facts 파일의 매장 {len(venues)}곳을 그대로 채웠습니다. 파일에 없는 정보는 넣지 않았습니다.",
            "구글 평점은 계속 바뀝니다. 기준 시점을 함께 적거나 숫자를 빼세요.",
        ]
        missing = [v.name for v in venues if not v.get("signature")]
        if missing:
            notes_lines.append("대표메뉴가 비어 있는 곳: " + ", ".join(missing))
    else:
        notes_lines = ["카드에 남은 {{...}} 자리표시자를 실제 정보로 바꿔주세요."]
    if mode == "guide":
        notes_lines = ["가게를 나열하지 않는 가이드형 구성입니다."]

    return CardNews(
        topic=topic,
        title=(f"{place_label} BEST {place_n}" if place_n and place_label
               else topic or "카드뉴스"),
        cards=cards,
        caption=_caption(topic, place_label, food_label, place_n),
        hashtags=list(dict.fromkeys(tags))[:18],
        handle=handle,
        source="offline",
        notes="\n".join(notes_lines),
        meta={"mode": mode, "region": region, "food": food_label},
    )


def _filler_cards(food: str, region: str) -> list[Card]:
    """가이드형 구성에서 본문을 채우는 카드 후보들."""
    where = region or "이 동네"
    return [
        Card(
            kind="list",
            badge="체크",
            title="가기 전에 확인할 것",
            bullets=[
                "브레이크 타임 있는지",
                "포장·예약 가능한지",
                "주차 또는 근처 공영주차장",
                "1인 방문 가능한지",
            ],
        ),
        Card(
            kind="list",
            badge="기준",
            title=f"{food} 고를 때 보는 세 가지",
            bullets=[
                "재방문 후기가 있는가",
                "메뉴 수가 지나치게 많지 않은가",
                "점심 시간대에 회전이 도는가",
            ],
        ),
        Card(
            kind="tip",
            badge="TIP 02",
            title="둘이 가면 이렇게 시키세요",
            body=f"{food}은 대표 메뉴 하나에 사이드 하나가 기본입니다. "
                 "처음이라면 시그니처부터 시켜보고 다음에 확장하세요.",
        ),
        Card(
            kind="quote",
            body=f"{where}에서 실패를 줄이는 가장 쉬운 방법은 "
                 "점심에 붐비는 집을 저녁에 가보는 것입니다",
            footnote="에디터 노트",
        ),
        Card(
            kind="list",
            badge="주의",
            title="이런 곳은 한 번 더 생각해보세요",
            bullets=[
                "사진과 실물 차이가 크다는 후기가 반복될 때",
                "리뷰가 특정 기간에 몰려 있을 때",
                "메뉴판에 가격이 없을 때",
            ],
        ),
    ]


def _cover_title(topic: str, region: str, food: str, count: int) -> str:
    if count >= 2 and region:
        return f"{region}\n{food} {count}곳"
    if region:
        return f"{region}\n{food} 고르는 법"
    return topic[:20] or f"{food} 고르는 법"


def _tip_title(food: str) -> str:
    return {
        "카페": "붐비기 전에 가는 시간",
        "국밥": "국물부터 한 숟갈",
        "고깃집": "굽기는 직원분께 맡기세요",
        "술집": "안주는 2개부터",
    }.get(food, "웨이팅 피하는 방법")


def _tip_body(food: str) -> str:
    return {
        "카페": "주말이라면 오픈 직후 30분, 평일이라면 오후 2시 전후가 가장 한산합니다.",
        "국밥": "양념을 넣기 전에 국물 맛을 먼저 봐야 그 집 육수 실력이 보입니다.",
        "고깃집": "불판 관리를 해주는 곳이라면 맡기는 편이 굽기 실패가 없습니다.",
        "술집": "둘이라면 마른안주 하나, 따뜻한 안주 하나로 시작하면 실패가 적습니다.",
    }.get(food, "점심은 11시 30분 이전, 저녁은 5시 30분 이전에 들어가면 대기가 짧습니다.")


def _caption(topic: str, place_label: str, food: str, count: int) -> str:
    head = f"{place_label or food} 정리했습니다." if count else f"{food} 고르는 기준을 정리했습니다."
    return (
        f"{head}\n"
        f"주제: {topic}\n"
        "카드 넘기면서 보시고, 가실 곳 하나 정해지면 저장해두세요.\n"
        "직접 다녀온 곳 있으면 댓글로 알려주세요. 다음 편에 반영합니다."
    )
