"""데모용 리포트.

API 키도 캡처도 없이 `storeboard sample` 로 슬라이드 모양을 먼저 볼 수 있게
만들어 둔 가짜 데이터입니다. 실제 매장 데이터가 아닙니다.
"""

from __future__ import annotations

import random

from . import periods
from .models import AdPoint, Goal, Report, SalesPoint, TrafficPoint

STORES = ("강남점", "홍대점", "판교점")
BASE_WEEK = "2026-W33"

# 매장별 (기준주 매출, 결제건수, 주간 성장 기울기)
_PROFILE = {
    "강남점": (48_200_000, 1_420, 1.012),
    "홍대점": (31_600_000, 1_180, 0.994),
    "판교점": (26_900_000, 780, 1.021),
}

_ADS = [
    # (채널, 광고비, 노출, 클릭, 전환, 전환매출)
    ("naver_sa", 3_800_000, 412_000, 12_460, 486, 21_900_000),
    ("naver_place", 1_450_000, 268_000, 5_920, 214, 8_200_000),
    ("meta", 2_600_000, 631_000, 9_140, 231, 9_800_000),
    ("google_ads", 1_900_000, 187_000, 4_380, 152, 7_100_000),
    ("kakao", 900_000, 143_000, 2_260, 41, 1_400_000),
]

_INFLOW = {"search": 0.46, "map": 0.21, "ad": 0.18, "blog": 0.09, "direct": 0.06}
_KEYWORDS = [
    ("강남 고깃집", 3_120), ("홍대 술집", 2_480), ("판교 회식", 1_940),
    ("강남역 삼겹살", 1_510), ("홍대 맛집", 1_180), ("판교 점심", 860),
]


def build_sample(period: str = BASE_WEEK, *, weeks: int = 8) -> Report:
    """주간 8주 + 전년 동기 데이터를 갖춘 데모 리포트."""
    rng = random.Random(33)
    keys = periods.series_back(period, weeks)

    sales: list[SalesPoint] = []
    traffic: list[TrafficPoint] = []
    for store, (revenue, orders, slope) in _PROFILE.items():
        for step, key in enumerate(reversed(keys)):        # 최근 -> 과거
            wobble = rng.uniform(0.94, 1.06)
            factor = wobble / (slope ** step)
            sales.append(SalesPoint(
                store=store, period=key,
                revenue=int(revenue * factor),
                orders=int(orders * factor),
                customers=int(orders * factor * 2.3),
            ))
            # 전년 동기 — 올해가 나아 보이도록 살짝 낮게, 매장마다 편차를 둡니다.
            ly = rng.uniform(0.82, 1.04) if store != "홍대점" else rng.uniform(1.0, 1.12)
            sales.append(SalesPoint(
                store=store, period=periods.last_year(key),
                revenue=int(revenue * factor * ly),
                orders=int(orders * factor * ly),
                customers=int(orders * factor * ly * 2.3),
            ))

        share = revenue / sum(v[0] for v in _PROFILE.values())
        for key in keys[-3:]:
            views = int(41_000 * share * rng.uniform(0.9, 1.1))
            traffic.append(TrafficPoint(
                store=store, period=key, views=views,
                inflow={k: int(views * w) for k, w in _INFLOW.items()},
                keywords=[{"term": t, "count": int(c * share)} for t, c in _KEYWORDS[:4]],
                saves=int(views * 0.031), calls=int(views * 0.017),
                reservations=int(views * 0.026), directions=int(views * 0.048),
                reviews=int(views * 0.004), review_score=round(rng.uniform(4.3, 4.8), 1),
            ))

    ads: list[AdPoint] = []
    for key in keys[-4:]:
        drift = 1.0 if key == period else rng.uniform(0.86, 1.02)
        for channel, spend, impr, clicks, conv, rev in _ADS:
            ads.append(AdPoint(
                channel=channel, period=key,
                spend=int(spend * drift), impressions=int(impr * drift),
                clicks=int(clicks * drift), conversions=round(conv * drift),
                revenue=int(rev * drift),
            ))

    return Report(
        title="직영점 주간 마케팅·매출 리포트",
        brand="불도저파크",
        period=period,
        sales=sales,
        ads=ads,
        traffic=traffic,
        goal=Goal(revenue=110_000_000, roas=4.0, ad_ratio=12.0),
        notes="샘플 데이터입니다. 실제 매장 실적이 아닙니다.",
        meta={"source": "sample"},
    )
