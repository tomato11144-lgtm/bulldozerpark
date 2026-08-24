"""설정 로딩 — 경로, 환경변수, 캔버스 규격."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
FONT_DIR = PROJECT_ROOT / "assets" / "fonts"
TEMPLATE_DIR = PACKAGE_DIR / "render" / "templates"
CACHE_DIR = PROJECT_ROOT / ".cache"
IMAGE_CACHE_DIR = CACHE_DIR / "images"
DEFAULT_OUT_DIR = PROJECT_ROOT / "out"

# 인스타그램 규격. 카드뉴스는 4:5(세로)가 피드 점유율이 가장 큽니다.
CANVAS_SIZES: dict[str, tuple[int, int]] = {
    "4:5": (1080, 1350),   # 기본 — 피드 세로형
    "1:1": (1080, 1080),   # 정사각
    "9:16": (1080, 1920),  # 스토리/릴스 커버
}
DEFAULT_RATIO = "4:5"

DEFAULT_MODEL = "claude-opus-5"


def _load_dotenv(path: Path) -> None:
    """의존성 없이 .env 를 읽어 os.environ 에 채웁니다(기존 값은 유지)."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class Settings:
    """런타임 설정 한 묶음."""

    anthropic_api_key: str = ""
    model: str = DEFAULT_MODEL
    unsplash_key: str = ""
    pexels_key: str = ""
    chromium_path: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
            model=os.getenv("CARDNEWS_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            unsplash_key=os.getenv("UNSPLASH_ACCESS_KEY", "").strip(),
            pexels_key=os.getenv("PEXELS_API_KEY", "").strip(),
            chromium_path=os.getenv("CARDNEWS_CHROMIUM_PATH", "").strip(),
        )

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def stock_provider(self) -> str:
        """사용 가능한 스톡 사진 제공자 이름."""
        if self.unsplash_key:
            return "unsplash"
        if self.pexels_key:
            return "pexels"
        return ""


def canvas_size(ratio: str) -> tuple[int, int]:
    return CANVAS_SIZES.get(ratio, CANVAS_SIZES[DEFAULT_RATIO])
