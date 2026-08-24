#!/usr/bin/env python3
"""Google Places API 로 매장의 **검증된 사실**을 받아 --facts 파일로 만듭니다.

    export GOOGLE_MAPS_API_KEY=...
    python scripts/fetch_places.py "korean bbq" --area "Metro Manila" \
        --top 5 --min-reviews 200 --include "Wolhwa Galbi" -o data/manila-kbbq.md

    cardnews "Manila K-BBQ best 5" --lang en+tl --facts data/manila-kbbq.md

가져오는 것: 상호 · 평점 · 리뷰 수 · 주소 · 영업시간 · 가격대 · 지도 링크.
전부 Places API 가 공식으로 제공하는 사실 데이터입니다.

가져오지 않는 것: **사진**.
Places 사진과 구글 이미지 검색 결과는 매장·사진가·리뷰어의 저작물이고,
Google Maps Platform 약관은 지도 맥락 밖 재사용을 제한합니다. 인스타 카드뉴스
배경으로 쓰면 저작권 문제와 계정 신고 위험이 있습니다. 사진은
  1) 매장 공식 사진(사용 허락 받고)  2) 직접 촬영  3) 무료 스톡  4) 사진 없는 타이포 카드
중에서 고르세요. --images-dir / --images 옵션이 그 경로입니다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

# 필요한 필드만 요청합니다 — Places API 는 필드 마스크에 따라 과금됩니다.
FIELD_MASK = ",".join(
    f"places.{f}" for f in (
        "displayName", "formattedAddress", "shortFormattedAddress",
        "rating", "userRatingCount", "priceLevel",
        "regularOpeningHours.weekdayDescriptions",
        "websiteUri", "googleMapsUri", "primaryTypeDisplayName",
        "businessStatus",
    )
)

PRICE_LABELS = {
    "PRICE_LEVEL_INEXPENSIVE": "₱",
    "PRICE_LEVEL_MODERATE": "₱₱",
    "PRICE_LEVEL_EXPENSIVE": "₱₱₱",
    "PRICE_LEVEL_VERY_EXPENSIVE": "₱₱₱₱",
}


def search(query: str, api_key: str, *, region: str = "", limit: int = 20) -> list[dict]:
    payload: dict = {"textQuery": query, "maxResultCount": min(limit, 20)}
    if region:
        payload["regionCode"] = region
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("places", [])
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"Places API 오류 {exc.code}: {detail}") from exc


def rank(
    places: list[dict], *, top: int, min_reviews: int, include: list[str]
) -> list[dict]:
    """평점 순 정렬. 리뷰가 너무 적은 곳은 빼고, --include 로 지정한 곳은 항상 남깁니다."""
    wanted = [s.lower() for s in include]

    def pinned(place: dict) -> bool:
        name = (place.get("displayName", {}).get("text") or "").lower()
        return any(w in name for w in wanted)

    def usable(place: dict) -> bool:
        if place.get("businessStatus") not in (None, "OPERATIONAL"):
            return False
        return place.get("userRatingCount", 0) >= min_reviews

    seen: set[str] = set()
    unique: list[dict] = []
    for place in places:
        name = place.get("displayName", {}).get("text", "")
        if name and name not in seen:
            seen.add(name)
            unique.append(place)

    pins = [p for p in unique if pinned(p)]
    rest = [p for p in unique if not pinned(p) and usable(p)]
    rest.sort(key=lambda p: (p.get("rating", 0), p.get("userRatingCount", 0)), reverse=True)

    out = pins + [p for p in rest if p not in pins]
    return out[:top]


def to_markdown(places: list[dict], query: str, area: str) -> str:
    today = date.today().isoformat()
    lines = [
        f"# {area or 'Verified'} — {query}",
        "",
        f"Source: Google Places API, pulled {today}.",
        "Ratings and hours drift — re-check anything time-sensitive before posting.",
        "Photos are NOT included here; supply your own via --images-dir.",
        "",
    ]
    for i, place in enumerate(places, start=1):
        name = place.get("displayName", {}).get("text", "?")
        rating = place.get("rating")
        count = place.get("userRatingCount")
        lines.append(f"## {i}. {name}")
        if rating is not None:
            lines.append(f"- Google rating: {rating} ({count:,} reviews, as of {today})")
        addr = place.get("shortFormattedAddress") or place.get("formattedAddress")
        if addr:
            lines.append(f"- Address: {addr}")
        if place.get("priceLevel"):
            lines.append(f"- Price level: {PRICE_LABELS.get(place['priceLevel'], place['priceLevel'])}")
        hours = (place.get("regularOpeningHours") or {}).get("weekdayDescriptions")
        if hours:
            lines.append("- Hours:")
            lines += [f"    - {h}" for h in hours]
        if place.get("websiteUri"):
            lines.append(f"- Website: {place['websiteUri']}")
        if place.get("googleMapsUri"):
            lines.append(f"- Maps: {place['googleMapsUri']}")
        lines.append("- Must-order: <<채워주세요 — Places API 는 메뉴를 주지 않습니다>>")
        lines.append("- One-line verdict: <<채워주세요>>")
        lines.append("")
    lines += [
        "## Notes for the writer",
        "- Only the facts above are verified. Anything marked <<...>> must be filled in by hand.",
        "- Do not state a price per head unless it is written above.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Google Places 로 매장 사실 데이터를 받아 --facts 파일 만들기"
    )
    parser.add_argument("query", help='검색어 (예: "korean bbq unlimited samgyupsal")')
    parser.add_argument("--area", default="", help='지역 (예: "Metro Manila") — 검색어에 붙습니다')
    parser.add_argument("--region", default="", help='ISO 국가 코드 (예: PH)')
    parser.add_argument("--top", type=int, default=5, help="뽑을 매장 수 (기본 5)")
    parser.add_argument("--min-reviews", type=int, default=100,
                        help="리뷰 수 하한 (기본 100). 리뷰 3개짜리 5.0 을 걸러냅니다")
    parser.add_argument("--include", action="append", default=[],
                        help="순위와 무관하게 반드시 포함할 상호 (여러 번 지정 가능)")
    parser.add_argument("-o", "--out", default="places.md", help="출력 파일 (.md)")
    parser.add_argument("--json", help="원본 응답도 이 경로에 저장")
    args = parser.parse_args()

    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        print("GOOGLE_MAPS_API_KEY 가 필요합니다.\n"
              "  https://console.cloud.google.com/ 에서 Places API (New) 를 켜고 키를 만드세요.\n"
              "  export GOOGLE_MAPS_API_KEY=...", file=sys.stderr)
        return 2

    query = f"{args.query} {args.area}".strip()
    print(f"검색: {query!r}")
    places = search(query, api_key, region=args.region)
    # --include 로 지정한 곳은 따로 한 번 더 찾아 확실히 넣습니다.
    for name in args.include:
        places += search(f"{name} {args.area}".strip(), api_key, region=args.region, limit=5)
    print(f"  {len(places)}건 수신")

    ranked = rank(places, top=args.top, min_reviews=args.min_reviews, include=args.include)
    if not ranked:
        print("조건에 맞는 매장이 없습니다. --min-reviews 를 낮춰보세요.", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_markdown(ranked, args.query, args.area), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(
            json.dumps(ranked, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"\n{len(ranked)}곳 저장 -> {out}\n")
    for i, place in enumerate(ranked, start=1):
        name = place.get("displayName", {}).get("text", "?")
        rating = place.get("rating", "-")
        count = place.get("userRatingCount", 0)
        print(f"  {i}. {name}  ★{rating} ({count:,})")
    print("\n<<...>> 로 표시된 대표메뉴·한줄평을 채운 뒤:")
    print(f'  cardnews "<주제>" --lang en+tl --facts {out} --images-dir photos/')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
