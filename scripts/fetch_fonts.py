#!/usr/bin/env python3
"""테마가 쓰는 한글 폰트를 Google Fonts 에서 assets/fonts/ 로 내려받습니다.

    python scripts/fetch_fonts.py              # 전체 테마 폰트
    python scripts/fetch_fonts.py --theme warm # 특정 테마만
    python scripts/fetch_fonts.py --force      # 이미 있어도 다시 받기

폰트를 받아두면 렌더링 시 네트워크가 필요 없고, Pillow 백엔드도 한글이 깨지지 않습니다.
받은 파일은 .gitignore 되어 있습니다(라이선스상 재배포하지 않기 위함).
전부 SIL Open Font License 또는 그에 준하는 자유 라이선스 서체입니다.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cardnews.config import FONT_DIR  # noqa: E402
from cardnews.fonts import font_filename  # noqa: E402
from cardnews.themes import FONT_WEIGHTS, THEMES, all_fonts  # noqa: E402

CSS_ENDPOINT = "https://fonts.googleapis.com/css2"
# 구형 User-Agent 를 보내면 woff2 대신 ttf URL 을 돌려줍니다 (Pillow 는 ttf 만 읽습니다).
LEGACY_UA = "Mozilla/4.0"

FACE_RE = re.compile(
    r"font-family:\s*'([^']+)'.*?font-weight:\s*(\d+).*?src:\s*url\((https://[^)]+\.ttf)\)",
    re.DOTALL,
)


def _get(url: str, headers: dict[str, str] | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"Accept": "*/*", **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def css_query(families: dict[str, list[int]]) -> str:
    parts = []
    for family in sorted(families):
        weights = sorted(set(families[family]))
        name = family.replace(" ", "+")
        parts.append(f"family={name}:wght@{';'.join(map(str, weights))}"
                     if len(weights) > 1 else f"family={name}")
    return f"{CSS_ENDPOINT}?" + "&".join(parts)


def fetch(families: dict[str, list[int]], force: bool = False) -> int:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    url = css_query(families)
    print(f"[1/2] 폰트 목록 조회: {url}")
    css = _get(url, {"User-Agent": LEGACY_UA}).decode("utf-8")

    faces = FACE_RE.findall(css)
    if not faces:
        print("!! Google Fonts 응답에서 ttf URL 을 찾지 못했습니다. 네트워크/차단 여부를 확인하세요.")
        return 1

    # 같은 (패밀리, 두께) 가 subset 별로 여러 번 나옵니다 — 마지막(전체 커버리지) 하나만 씁니다.
    unique: dict[tuple[str, int], str] = {}
    for family, weight, ttf_url in faces:
        unique[(family, int(weight))] = ttf_url

    print(f"[2/2] {len(unique)}개 파일 내려받는 중…")
    saved = 0
    for (family, weight), ttf_url in sorted(unique.items()):
        target = FONT_DIR / font_filename(family, weight)
        if target.is_file() and not force:
            print(f"  · 건너뜀 (이미 있음) {target.name}")
            continue
        try:
            target.write_bytes(_get(ttf_url))
        except Exception as exc:  # noqa: BLE001 - 개별 실패는 넘어가고 계속
            print(f"  ! 실패 {target.name}: {exc}")
            continue
        saved += 1
        print(f"  ✓ {target.name} ({target.stat().st_size // 1024} KB)")

    print(f"\n완료 — {saved}개 저장, 위치: {FONT_DIR}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="카드뉴스 테마용 한글 폰트 다운로드")
    parser.add_argument("--theme", help="특정 테마의 폰트만 받기", choices=sorted(THEMES))
    parser.add_argument("--force", action="store_true", help="이미 있어도 다시 받기")
    args = parser.parse_args()

    if args.theme:
        theme = THEMES[args.theme]
        families = {f: FONT_WEIGHTS.get(f, [400]) for f in theme.fonts}
    else:
        families = all_fonts()

    return fetch(families, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
