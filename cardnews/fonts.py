"""폰트 로딩.

- HTML 렌더러: TTF 를 base64 data URI 로 @font-face 에 심어 네트워크 없이 렌더링합니다.
- Pillow 렌더러: TTF 경로를 그대로 사용합니다.

폰트 파일이 없으면 HTML 은 Google Fonts CDN 링크로, Pillow 는 시스템 폰트로 폴백합니다.
`python scripts/fetch_fonts.py` 로 미리 받아두는 쪽을 권장합니다.
"""

from __future__ import annotations

import base64
import functools
from pathlib import Path

from .config import FONT_DIR
from .themes import FONT_WEIGHTS


def font_filename(family: str, weight: int) -> str:
    return f"{family.replace(' ', '_')}-{weight}.ttf"


def font_path(family: str, weight: int) -> Path | None:
    """정확한 두께가 없으면 같은 패밀리의 가장 가까운 두께로 대체합니다."""
    exact = FONT_DIR / font_filename(family, weight)
    if exact.is_file():
        return exact
    candidates = sorted(
        (p for p in FONT_DIR.glob(f"{family.replace(' ', '_')}-*.ttf")),
        key=lambda p: abs(int(p.stem.rsplit("-", 1)[-1] or 400) - weight),
    )
    return candidates[0] if candidates else None


def available_families() -> set[str]:
    if not FONT_DIR.is_dir():
        return set()
    return {p.stem.rsplit("-", 1)[0].replace("_", " ") for p in FONT_DIR.glob("*.ttf")}


@functools.lru_cache(maxsize=64)
def _data_uri(path_str: str) -> str:
    data = base64.b64encode(Path(path_str).read_bytes()).decode("ascii")
    return f"data:font/ttf;base64,{data}"


def face_rules(families: list[str], url_prefix: str | None = None) -> str:
    """@font-face 규칙 문자열. 로컬 TTF 가 있는 패밀리만 만들어 냅니다.

    url_prefix 를 주면 그 경로 아래에서 폰트를 불러오는 URL 을 씁니다
    (렌더링용 로컬 HTTP 서버). 주지 않으면 base64 data URI 로 파일에 심습니다 —
    문서 하나로 완결되지만 용량이 커집니다.
    """
    rules: list[str] = []
    for family in families:
        for weight in FONT_WEIGHTS.get(family, [400]):
            path = font_path(family, weight)
            if path is None:
                continue
            src = (f"{url_prefix.rstrip('/')}/{path.name}" if url_prefix
                   else _data_uri(str(path)))
            rules.append(
                "@font-face{"
                f"font-family:'{family}';font-style:normal;font-weight:{weight};"
                f"font-display:block;src:url('{src}') format('truetype');"
                "}"
            )
    return "\n".join(rules)


def google_fonts_url(families: list[str]) -> str:
    """로컬 폰트가 없을 때 쓸 Google Fonts CSS URL."""
    parts = []
    for family in sorted(families):
        weights = FONT_WEIGHTS.get(family, [400])
        name = family.replace(" ", "+")
        if len(weights) > 1:
            parts.append(f"family={name}:wght@{';'.join(str(w) for w in weights)}")
        else:
            parts.append(f"family={name}")
    return "https://fonts.googleapis.com/css2?" + "&".join(parts) + "&display=block"


# Pillow 폴백용 시스템 폰트 후보 (한글 지원 우선)
_SYSTEM_FALLBACKS = (
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "C:/Windows/Fonts/malgun.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def resolve_ttf(family: str, weight: int = 400) -> str | None:
    """Pillow 가 열 수 있는 TTF 경로. 없으면 시스템 폰트, 그것도 없으면 None."""
    path = font_path(family, weight)
    if path:
        return str(path)
    for candidate in _SYSTEM_FALLBACKS:
        if Path(candidate).is_file():
            return candidate
    return None


def missing_report(families: list[str]) -> list[str]:
    """아직 내려받지 않은 폰트 패밀리 목록."""
    have = available_families()
    return [f for f in families if f not in have]
