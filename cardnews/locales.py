"""언어별 설정.

카드에 들어가는 라벨·UI 문구·해시태그·서체 계열을 언어마다 다르게 잡습니다.
한국어 계정과 해외(특히 필리핀) 계정을 같은 도구로 돌리기 위한 계층입니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# meta 필드에서 쓰는 표준 키. 언어별로 표시 라벨만 달라집니다.
META_FIELDS = (
    "location", "signature", "price", "hours",
    "closed", "parking", "waiting", "reservation",
)


@dataclass(frozen=True)
class Locale:
    code: str
    label: str                       # 사람이 읽는 이름
    script: str                      # "hangul" | "latin" — 서체 선택에 사용
    meta: dict[str, str]             # 표준 키 -> 카드에 찍힐 라벨
    ui: dict[str, str]               # 템플릿에 박히는 고정 문구
    hashtags: tuple[str, ...] = ()   # 언제나 붙이는 기본 태그
    alt: str = ""                    # 이중 언어일 때 보조 언어 코드
    note: str = ""                   # 사용자에게 보여줄 설명

    @property
    def bilingual(self) -> bool:
        return bool(self.alt)

    def meta_label(self, key: str) -> str:
        return self.meta.get(key, key)

    def meta_labels(self) -> list[str]:
        return [self.meta[k] for k in META_FIELDS if k in self.meta]


KO = Locale(
    code="ko",
    label="한국어",
    script="hangul",
    meta={
        "location": "위치", "signature": "대표메뉴", "price": "가격대",
        "hours": "영업시간", "closed": "휴무", "parking": "주차",
        "waiting": "웨이팅", "reservation": "예약",
    },
    ui={"swipe": "넘겨보기", "arrow": "→"},
    hashtags=("맛집", "맛집추천", "맛스타그램", "먹스타그램"),
    note="국내 계정 기본값",
)

EN = Locale(
    code="en",
    label="English",
    script="latin",
    meta={
        "location": "LOCATION", "signature": "MUST ORDER", "price": "PRICE",
        "hours": "HOURS", "closed": "CLOSED", "parking": "PARKING",
        "waiting": "WAIT TIME", "reservation": "BOOKING",
    },
    ui={"swipe": "SWIPE", "arrow": "→"},
    hashtags=("foodie", "foodstagram", "wheretoeat"),
    note="영어권 계정",
)

TL = Locale(
    code="tl",
    label="Tagalog / Filipino",
    script="latin",
    meta={
        "location": "SAAN", "signature": "DAPAT I-ORDER", "price": "PRESYO",
        "hours": "ORAS", "closed": "SARADO", "parking": "PARKING",
        "waiting": "PILA", "reservation": "RESERBA",
    },
    ui={"swipe": "SWIPE MO", "arrow": "→"},
    hashtags=("foodiePH", "saanKaKakain", "pinoyfoodie"),
    note="따갈로그 전용",
)

TAGLISH = Locale(
    code="taglish",
    label="Taglish (English + Tagalog 자연 혼용)",
    script="latin",
    meta={
        "location": "SAAN", "signature": "MUST ORDER", "price": "PRESYO",
        "hours": "HOURS", "closed": "SARADO", "parking": "PARKING",
        "waiting": "PILA", "reservation": "BOOKING",
    },
    ui={"swipe": "SWIPE MO", "arrow": "→"},
    hashtags=("foodiePH", "saanKaKakain", "manilaeats"),
    note="마닐라 소셜에서 가장 자연스러운 톤 — 문장 안에서 두 언어를 섞습니다",
)

EN_TL = Locale(
    code="en+tl",
    label="English + Tagalog (두 줄 병기)",
    script="latin",
    meta={
        "location": "LOCATION / SAAN", "signature": "MUST ORDER",
        "price": "PRICE / PRESYO", "hours": "HOURS / ORAS",
        "closed": "CLOSED / SARADO", "parking": "PARKING",
        "waiting": "WAIT / PILA", "reservation": "BOOKING / RESERBA",
    },
    ui={"swipe": "SWIPE", "arrow": "→"},
    hashtags=("foodiePH", "saanKaKakain", "manilaeats"),
    alt="tl",
    note="영어를 주 문구로, 따갈로그를 보조 줄로 병기합니다",
)

LOCALES: dict[str, Locale] = {
    loc.code: loc for loc in (KO, EN, TL, TAGLISH, EN_TL)
}
DEFAULT_LOCALE = "ko"


def get_locale(code: str | None) -> Locale:
    if not code:
        return LOCALES[DEFAULT_LOCALE]
    return LOCALES.get(code.strip().lower(), LOCALES[DEFAULT_LOCALE])


def locale_codes() -> list[str]:
    return list(LOCALES)


# 모든 언어의 meta 라벨을 표준 순서대로 늘어놓은 표.
# models.Card 가 언어를 몰라도 meta 순서를 맞출 수 있게 합니다.
def meta_order() -> tuple[str, ...]:
    order: list[str] = []
    for key in META_FIELDS:
        for loc in LOCALES.values():
            label = loc.meta.get(key)
            if label and label not in order:
                order.append(label)
    return tuple(order)
