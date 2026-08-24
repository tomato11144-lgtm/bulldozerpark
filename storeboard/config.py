"""설정 — 경로, 환경변수, 슬라이드 규격."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
FONT_DIR = PROJECT_ROOT / "assets" / "fonts"
TEMPLATE_DIR = PACKAGE_DIR / "render" / "templates"
DEFAULT_OUT_DIR = PROJECT_ROOT / "out"

# 보고용 슬라이드는 16:9 고정. 1920x1080 이면 PPT 삽입·PDF 인쇄 모두 깨지지 않습니다.
SLIDE_W = 1920
SLIDE_H = 1080

DEFAULT_MODEL = "claude-opus-5"

# 캡처를 그대로 모델에 넘기면 토큰이 크게 뜁니다. 긴 변을 이 값으로 줄여 보냅니다.
MAX_IMAGE_EDGE = 1600


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
    chromium_path: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        model = os.getenv("STOREBOARD_MODEL", "").strip()
        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
            model=model or DEFAULT_MODEL,
            chromium_path=(
                os.getenv("STOREBOARD_CHROMIUM_PATH", "").strip()
                or os.getenv("CARDNEWS_CHROMIUM_PATH", "").strip()
            ),
        )

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key)
