"""데이터 모델.

캡처 추출(extract.py) -> 지표 계산(metrics.py) -> 슬라이드 구성(deck.py)
-> 렌더러(render/) 가 여기 정의된 구조만 주고받습니다.

report.json 이 사람이 직접 고치는 원본입니다. 캡처가 흐리거나 항목이
빠졌을 때는 여기 값을 손으로 채워 넣고 다시 빌드하면 됩니다.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import periods

# 광고 채널 표준 키. 캡처에 적힌 이름이 뭐든 이 키로 모읍니다.
CHANNELS: dict[str, str] = {
    "naver_sa": "네이버 검색광고",
    "naver_gfa": "네이버 GFA",
    "naver_place": "네이버 플레이스광고",
    "google_ads": "구글 검색광고",
    "google_pmax": "구글 P-Max",
    "youtube": "유튜브",
    "meta": "메타(인스타·페북)",
    "kakao": "카카오",
    "baemin": "배달의민족",
    "coupang_eats": "쿠팡이츠",
    "influencer": "인플루언서",
    "other": "기타",
}

# 네이버 플레이스 유입 경로 표준 키.
INFLOW_PATHS: dict[str, str] = {
    "search": "플레이스 검색",
    "map": "지도 탐색",
    "ad": "광고",
    "blog": "블로그·리뷰",
    "sns": "SNS",
    "direct": "즐겨찾기·직접",
    "other": "기타",
}


def channel_label(key: str) -> str:
    return CHANNELS.get(key, key)


def inflow_label(key: str) -> str:
    return INFLOW_PATHS.get(key, key)


def slugify(text: str) -> str:
    """한글을 살린 파일/디렉터리용 슬러그."""
    text = re.sub(r"[^\w가-힣\s-]", "", text or "", flags=re.UNICODE).strip()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60] or "report"


def _int(value: Any) -> int:
    """'1,234,000원' / '1.2만' / None 을 정수로. 못 읽으면 0."""
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(round(value))
    text = str(value).strip().replace(",", "").replace("원", "")
    mult = 1
    for suffix, factor in (("억", 100_000_000), ("만", 10_000), ("천", 1_000)):
        if text.endswith(suffix):
            text, mult = text[: -len(suffix)], factor
            break
    try:
        return int(round(float(text) * mult))
    except ValueError:
        return 0


def _float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


ALL_STORES = "전체"


@dataclass
class SalesPoint:
    """매장 하나의 한 기간 매출."""

    store: str = ALL_STORES
    period: str = ""                  # 2026-W33 / 2026-08 / 2026
    revenue: int = 0                  # 매출액(원)
    orders: int = 0                   # 결제 건수
    customers: int = 0                # 방문 고객수 (없으면 orders 로 대체 계산)
    note: str = ""

    def __post_init__(self) -> None:
        self.store = (self.store or ALL_STORES).strip()
        self.period = periods.normalize(self.period) if self.period else ""
        self.revenue, self.orders, self.customers = (
            _int(self.revenue), _int(self.orders), _int(self.customers)
        )

    @property
    def grain(self) -> str:
        return periods.grain_of(self.period)

    @property
    def ticket(self) -> int:
        """객단가. 고객수가 없으면 결제 건수로 나눕니다."""
        base = self.customers or self.orders
        return int(round(self.revenue / base)) if base else 0


@dataclass
class AdPoint:
    """채널 하나의 한 기간 광고 성과."""

    channel: str = "other"
    period: str = ""
    store: str = ALL_STORES
    spend: int = 0                    # 광고비(원, VAT 포함 기준을 권장)
    impressions: int = 0
    clicks: int = 0
    conversions: float = 0.0          # 전환수 (예약·주문·전화 등 채널 정의대로)
    revenue: int = 0                  # 채널 리포트가 집계한 전환 매출
    note: str = ""

    def __post_init__(self) -> None:
        self.channel = (self.channel or "other").strip()
        self.store = (self.store or ALL_STORES).strip()
        self.period = periods.normalize(self.period) if self.period else ""
        self.spend, self.impressions, self.clicks, self.revenue = (
            _int(self.spend), _int(self.impressions), _int(self.clicks), _int(self.revenue)
        )
        self.conversions = _float(self.conversions)

    @property
    def label(self) -> str:
        return channel_label(self.channel)


@dataclass
class TrafficPoint:
    """네이버 플레이스 유입 리포트 한 기간."""

    store: str = ALL_STORES
    period: str = ""
    views: int = 0                              # 플레이스 조회수
    inflow: dict[str, int] = field(default_factory=dict)   # 유입 경로별 (INFLOW_PATHS 키)
    keywords: list[dict[str, Any]] = field(default_factory=list)  # [{term, count}]
    saves: int = 0                              # 저장(즐겨찾기)
    calls: int = 0                              # 전화 문의
    reservations: int = 0                       # 예약·주문
    directions: int = 0                         # 길찾기
    reviews: int = 0                            # 신규 리뷰 수
    review_score: float = 0.0
    note: str = ""

    def __post_init__(self) -> None:
        self.store = (self.store or ALL_STORES).strip()
        self.period = periods.normalize(self.period) if self.period else ""
        self.views, self.saves, self.calls, self.reservations, self.directions, self.reviews = (
            _int(self.views), _int(self.saves), _int(self.calls),
            _int(self.reservations), _int(self.directions), _int(self.reviews),
        )
        self.review_score = _float(self.review_score)
        self.inflow = {str(k): _int(v) for k, v in (self.inflow or {}).items() if _int(v)}
        self.keywords = [
            {"term": str(k.get("term", "")).strip(), "count": _int(k.get("count"))}
            for k in (self.keywords or [])
            if str(k.get("term", "")).strip()
        ]

    @property
    def actions(self) -> int:
        """유입이 실제 행동으로 이어진 횟수 (예약+전화+길찾기)."""
        return self.reservations + self.calls + self.directions


@dataclass
class Goal:
    """목표치. 있으면 달성률 게이지가 슬라이드에 붙습니다."""

    revenue: int = 0
    roas: float = 0.0
    ad_ratio: float = 0.0          # 매출 대비 광고비 상한(%)

    def __post_init__(self) -> None:
        self.revenue = _int(self.revenue)
        self.roas = _float(self.roas)
        self.ad_ratio = _float(self.ad_ratio)


@dataclass
class Report:
    """보고서 한 부의 원본 데이터."""

    title: str = "매장 마케팅·매출 리포트"
    period: str = ""                       # 이 보고서의 기준 기간
    brand: str = ""                        # 브랜드/회사명 (표지·푸터)
    stores: list[str] = field(default_factory=list)
    sales: list[SalesPoint] = field(default_factory=list)
    ads: list[AdPoint] = field(default_factory=list)
    traffic: list[TrafficPoint] = field(default_factory=list)
    goal: Goal = field(default_factory=Goal)
    captures: list[str] = field(default_factory=list)   # 원본 캡처 경로 (부록 슬라이드)
    warnings: list[str] = field(default_factory=list)   # 캡처에서 못 읽은 항목
    notes: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.period:
            self.period = periods.normalize(self.period)
        self.sales = [s if isinstance(s, SalesPoint) else SalesPoint(**s) for s in self.sales]
        self.ads = [a if isinstance(a, AdPoint) else AdPoint(**a) for a in self.ads]
        self.traffic = [
            t if isinstance(t, TrafficPoint) else TrafficPoint(**t) for t in self.traffic
        ]
        if isinstance(self.goal, dict):
            self.goal = Goal(**self.goal)
        if not self.stores:
            self.stores = self.detect_stores()
        if not self.period:
            self.period = self.detect_period()

    # ---------------------------------------------------------------- 조회
    def detect_stores(self) -> list[str]:
        """데이터에 등장한 매장 이름을 등장 순서대로."""
        seen: list[str] = []
        for row in (*self.sales, *self.traffic, *self.ads):
            if row.store and row.store != ALL_STORES and row.store not in seen:
                seen.append(row.store)
        return seen

    def detect_period(self) -> str:
        """기준 기간을 못 받았으면 매출 데이터 중 가장 최근 기간으로."""
        candidates = [s.period for s in self.sales if s.period]
        weekly = [p for p in candidates if periods.grain_of(p) == periods.WEEKLY]
        pool = weekly or candidates
        return max(pool, key=periods.start_date) if pool else ""

    @property
    def grain(self) -> str:
        return periods.grain_of(self.period) if self.period else periods.WEEKLY

    @property
    def slug(self) -> str:
        return slugify(f"{self.title}-{self.period}")

    def sales_for(self, period: str, store: str | None = None) -> list[SalesPoint]:
        rows = [s for s in self.sales if s.period == period]
        if store is not None:
            rows = [s for s in rows if s.store == store]
        return rows

    def ads_for(self, period: str) -> list[AdPoint]:
        return [a for a in self.ads if a.period == period]

    def traffic_for(self, period: str, store: str | None = None) -> list[TrafficPoint]:
        rows = [t for t in self.traffic if t.period == period]
        if store is not None:
            rows = [t for t in rows if t.store == store]
        return rows

    def has_store_split(self) -> bool:
        """매장별로 나뉜 매출이 있는지 (없으면 매장 비교 슬라이드를 건너뜁니다)."""
        return len({s.store for s in self.sales if s.store != ALL_STORES}) >= 2

    # ---------------------------------------------------------------- 직렬화
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json() + "\n", encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Report":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})

    @classmethod
    def load_json(cls, path: str | Path) -> "Report":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def merge(self, other: "Report") -> "Report":
        """캡처 여러 장에서 나온 조각들을 하나로 합칩니다(같은 키는 나중 값이 이김)."""
        pairs = (
            (self.sales, other.sales, lambda r: (r.store, r.period)),
            (self.ads, other.ads, lambda r: (r.channel, r.period, r.store)),
            (self.traffic, other.traffic, lambda r: (r.store, r.period)),
        )
        for target, incoming, key in pairs:
            index = {key(row): i for i, row in enumerate(target)}
            for row in incoming:
                if (pos := index.get(key(row))) is not None:
                    target[pos] = row
                else:
                    index[key(row)] = len(target)
                    target.append(row)

        self.title = other.title or self.title
        self.brand = other.brand or self.brand
        self.captures += [c for c in other.captures if c not in self.captures]
        self.warnings += [w for w in other.warnings if w not in self.warnings]
        self.notes = "\n".join(filter(None, [self.notes, other.notes]))
        self.stores = self.detect_stores()
        self.period = self.period or self.detect_period()
        return self
