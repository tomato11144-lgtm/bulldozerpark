"""--facts 파일 파서.

검증된 매장 정보를 적은 마크다운을 읽어 카드로 옮길 수 있는 구조로 바꿉니다.
Claude 경로에서는 프롬프트에 원문을 그대로 넣지만, API 키가 없는 오프라인
경로에서도 place 카드를 채울 수 있어야 해서 최소한의 파싱을 여기서 합니다.

기대하는 형식 (느슨합니다):

    ## 1. Sam Stew, Vertis North
    - Google rating: 4.9 (5,000 reviews)
    - Location: Quezon City
    - Price: ₱500-1,000
    - Signature: <<채워주세요>>      <- << >> 는 '아직 안 채움'으로 보고 버립니다
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

HEADING_RE = re.compile(r"^\s{0,3}#{2,3}\s*(?:\d+[.)]\s*)?(.+?)\s*$")
BULLET_RE = re.compile(r"^\s*[-*+]\s*(?:\*\*)?([^:：]{1,40}?)(?:\*\*)?\s*[:：]\s*(.+?)\s*$")
UNFILLED_RE = re.compile(r"<<.*?>>|\{\{.*?\}\}|^[-–—?]+$")

# 다양한 표기를 표준 키로 모읍니다.
KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "rating": ("google rating", "rating", "평점", "구글평점", "구글 평점", "stars"),
    "location": ("address", "location", "area", "주소", "위치", "지역", "saan"),
    "price": ("price", "price level", "price range", "budget", "가격", "가격대", "presyo"),
    "hours": ("hours", "opening hours", "open", "영업시간", "oras"),
    "closed": ("closed", "rest day", "휴무", "sarado"),
    "signature": ("signature", "must order", "must-order", "menu", "대표메뉴", "시그니처"),
    "verdict": ("one-line verdict", "verdict", "one line", "한줄평", "tagline"),
    "body": ("why go", "why", "note", "notes", "추천이유", "설명", "description"),
    "parking": ("parking", "주차"),
    "waiting": ("wait", "wait time", "waiting", "웨이팅", "pila"),
    "reservation": ("reservation", "booking", "예약", "reserba"),
    "phone": ("phone", "contact", "전화", "연락처"),
    "source": ("source", "출처"),
}
# 카드 앞면에 올릴 필드 순서 (locales.META_FIELDS 와 짝을 맞춥니다)
META_KEYS = ("location", "signature", "price", "hours", "closed",
             "parking", "waiting", "reservation")

# 섹션 제목이지만 매장이 아닌 것들
NON_VENUE = ("notes", "note", "writer", "source", "sources", "확인", "참고", "안내")

RATING_RE = re.compile(r"(\d\.\d|\d)\s*(?:/\s*5)?\s*(?:\(|,|\s)\s*([\d,.]+\s*[천kK만]?)")


@dataclass
class Venue:
    name: str
    fields: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> str:
        return self.fields.get(key, "")

    @property
    def rating(self) -> float | None:
        text = self.get("rating")
        match = re.search(r"\d(?:\.\d)?", text)
        return float(match.group()) if match else None

    def meta(self, labels: dict[str, str]) -> dict[str, str]:
        """표준 키 -> 언어별 라벨로 바꾼 meta 딕셔너리."""
        out: dict[str, str] = {}
        for key in META_KEYS:
            value = self.get(key)
            if value and key in labels:
                out[labels[key]] = value
        return out


def _normalise_key(raw: str) -> str | None:
    lowered = raw.strip().lower().rstrip(":").strip()
    for standard, aliases in KEY_ALIASES.items():
        if lowered in aliases:
            return standard
    return None


def _is_unfilled(value: str) -> bool:
    return bool(UNFILLED_RE.search(value.strip())) or not value.strip()


def parse_facts(text: str) -> list[Venue]:
    """마크다운에서 매장 목록을 뽑습니다. 못 알아본 줄은 조용히 넘어갑니다."""
    venues: list[Venue] = []
    current: Venue | None = None

    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#!") or stripped.startswith("# "):
            continue

        heading = HEADING_RE.match(line) if stripped.startswith("#") else None
        if heading:
            name = heading.group(1).strip().strip("*_")
            if any(word in name.lower() for word in NON_VENUE):
                current = None
                continue
            current = Venue(name=name)
            venues.append(current)
            continue

        if current is None:
            continue
        bullet = BULLET_RE.match(line)
        if not bullet:
            continue
        key = _normalise_key(bullet.group(1))
        value = bullet.group(2).strip()
        if key and not _is_unfilled(value):
            current.fields.setdefault(key, value)

    return [v for v in venues if v.fields]


def sort_by_rating(venues: list[Venue]) -> list[Venue]:
    """평점 내림차순. 평점이 없는 곳은 뒤로 보내되 원래 순서를 지킵니다."""
    rated = [v for v in venues if v.rating is not None]
    unrated = [v for v in venues if v.rating is None]
    rated.sort(key=lambda v: v.rating or 0, reverse=True)
    return rated + unrated
