"""카드뉴스 데이터 모델.

문안 생성기(content.py) -> 이미지 매칭(images.py) -> 렌더러(render/) 로 이어지는
파이프라인 전체가 여기 정의된 구조를 주고받습니다.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .locales import meta_order

# 카드 종류. 렌더러의 템플릿 이름과 1:1로 대응합니다.
CARD_KINDS = (
    "cover",   # 표지 — 후킹 문구 + 대표 이미지
    "intro",   # 도입 — 왜 이 주제인지
    "place",   # 가게 소개 — 순위/상호/한줄평/기본정보
    "menu",    # 메뉴 소개 — 메뉴명/가격/설명
    "tip",     # 꿀팁 — 번호 + 제목 + 본문
    "list",    # 목록 — 제목 + 불릿
    "quote",   # 인용 — 리뷰/평가 한 줄
    "outro",   # 마무리 — 저장 유도 CTA
)

# meta 표시 순서. 지원하는 모든 언어의 라벨을 표준 순서대로 늘어놓은 표라
# 카드가 어떤 언어인지 몰라도 위치 -> 대표메뉴 -> 가격 순으로 정렬됩니다.
META_ORDER = meta_order()


def slugify(text: str) -> str:
    """한글을 살린 파일/디렉터리용 슬러그."""
    text = re.sub(r"[^\w가-힣\s-]", "", text, flags=re.UNICODE).strip()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60] or "cardnews"


@dataclass
class Card:
    """카드 한 장."""

    kind: str = "tip"
    title: str = ""
    subtitle: str = ""
    body: str = ""
    # 이중 언어(en+tl)에서 아래에 한 줄 더 붙는 보조 언어 문구.
    title_alt: str = ""
    subtitle_alt: str = ""
    body_alt: str = ""
    badge: str = ""              # 좌상단 라벨 (예: "BEST 3", "꿀팁 02")
    eyebrow: str = ""            # 제목 위 작은 문구
    bullets: list[str] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)   # 위치/가격대/영업시간 등
    footnote: str = ""           # 하단 작은 글씨 (출처, 주의사항)
    image_query: str = ""        # 스톡 사진 검색어 (영문 권장)
    image_keywords: list[str] = field(default_factory=list)  # 로컬 이미지 매칭용
    image: str | None = None     # 렌더 시점에 채워지는 실제 이미지 경로
    image_credit: str = ""       # 사진 출처 표기 (Unsplash 등에서 요구)
    accent: str = ""             # 테마 accent 색을 카드 단위로 덮어쓰기

    def __post_init__(self) -> None:
        if self.kind not in CARD_KINDS:
            self.kind = "tip"
        # meta 는 표시 순서를 고정해 둡니다.
        if self.meta:
            ordered = {k: self.meta[k] for k in META_ORDER if k in self.meta}
            ordered.update({k: v for k, v in self.meta.items() if k not in ordered})
            self.meta = ordered

    @property
    def wants_image(self) -> bool:
        """이미지를 붙일 가치가 있는 카드인지."""
        return self.kind in ("cover", "place", "menu", "intro", "quote", "outro")


@dataclass
class CardNews:
    """카드뉴스 한 세트."""

    topic: str                                   # 사용자가 준 주제 원문
    title: str = ""                              # 시리즈 제목
    cards: list[Card] = field(default_factory=list)
    caption: str = ""                            # 인스타 본문 캡션
    hashtags: list[str] = field(default_factory=list)
    theme: str = "warm"
    lang: str = "ko"
    handle: str = ""                             # @계정명 (푸터에 표기)
    source: str = ""                             # "claude" | "offline"
    notes: str = ""                              # 생성기가 남긴 메모/주의사항
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        return slugify(self.title or self.topic)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CardNews":
        cards = [Card(**c) for c in data.get("cards", [])]
        payload = {k: v for k, v in data.items() if k != "cards"}
        payload.setdefault("topic", "")
        return cls(cards=cards, **payload)

    @classmethod
    def load_json(cls, path: str | Path) -> "CardNews":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def full_caption(self) -> str:
        """캡션 + 해시태그를 붙인 인스타 업로드용 본문."""
        tags = " ".join(t if t.startswith("#") else f"#{t}" for t in self.hashtags)
        return f"{self.caption.strip()}\n\n{tags}".strip()
