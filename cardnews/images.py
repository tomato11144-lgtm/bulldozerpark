"""카드에 붙일 사진을 구합니다.

우선순위:
  1. 로컬 폴더(--images) — 파일명에 키워드가 들어간 사진을 우선 매칭
  2. 무료 스톡 API — Unsplash 또는 Pexels (키가 있을 때만)
  3. 그라데이션 폴백 — 테마 색으로 만든 추상 배경 (항상 성공)

내려받은 사진은 .cache/images/ 에 캐싱해 같은 검색어를 두 번 부르지 않습니다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .config import IMAGE_CACHE_DIR, Settings
from .themes import Theme

log = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
TIMEOUT = 30


@dataclass
class ImageResult:
    path: Path
    credit: str = ""       # 출처 표기 문구 (Unsplash 는 표기가 의무입니다)
    source: str = "local"


def _cache_path(key: str, suffix: str = ".jpg") -> Path:
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return IMAGE_CACHE_DIR / f"{digest}{suffix}"


def _download(url: str, target: Path, headers: dict[str, str] | None = None) -> Path | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cardnews/1.0", **(headers or {})})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read()
    except Exception as exc:  # noqa: BLE001
        log.warning("이미지 내려받기 실패 %s: %s", url[:60], exc)
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def _get_json(url: str, headers: dict[str, str]) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cardnews/1.0", **headers})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        log.warning("이미지 검색 실패: %s", exc)
        return None


# --------------------------------------------------------------------------
# 제공자
# --------------------------------------------------------------------------

class LocalProvider:
    """사용자가 준 폴더에서 사진을 고릅니다.

    파일명에 키워드가 들어 있으면 우선 고르고, 없으면 아직 안 쓴 사진을 순서대로 씁니다.
    가게 사진처럼 '진짜' 사진이 있을 때 가장 좋은 결과가 나옵니다.
    """

    source = "local"

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.pool = sorted(
            p for p in self.folder.rglob("*") if p.suffix.lower() in IMAGE_EXTS
        )
        self.used: set[Path] = set()
        if not self.pool:
            log.warning("이미지 폴더에 쓸 사진이 없습니다: %s", self.folder)

    def search(self, query: str, keywords: list[str]) -> ImageResult | None:
        if not self.pool:
            return None
        terms = [t.lower() for t in [*keywords, *query.split()] if t]
        # 1) 키워드가 파일명에 있고 아직 안 쓴 사진
        for path in self.pool:
            name = path.stem.lower()
            if path not in self.used and any(t in name for t in terms):
                self.used.add(path)
                return ImageResult(path=path, source="local")
        # 2) 아직 안 쓴 아무 사진
        for path in self.pool:
            if path not in self.used:
                self.used.add(path)
                return ImageResult(path=path, source="local")
        # 3) 다 썼으면 재사용
        return ImageResult(path=random.choice(self.pool), source="local")


class UnsplashProvider:
    """Unsplash 검색 API. 무료지만 사진가 표기(attribution)가 필수입니다."""

    source = "unsplash"

    def __init__(self, access_key: str):
        self.key = access_key
        self.used: set[str] = set()

    def search(self, query: str, keywords: list[str]) -> ImageResult | None:
        if not query.strip():
            return None
        url = (
            "https://api.unsplash.com/search/photos?"
            + urllib.parse.urlencode(
                {"query": query, "per_page": 8, "orientation": "portrait", "content_filter": "high"}
            )
        )
        data = _get_json(url, {"Authorization": f"Client-ID {self.key}"})
        if not data or not data.get("results"):
            return None
        for photo in data["results"]:
            pid = photo.get("id", "")
            if pid in self.used:
                continue
            self.used.add(pid)
            src = (photo.get("urls") or {}).get("regular")
            if not src:
                continue
            target = _cache_path(f"unsplash:{pid}")
            if not target.is_file() and _download(src, target) is None:
                continue
            user = (photo.get("user") or {}).get("name", "Unsplash")
            return ImageResult(path=target, credit=f"Photo by {user} on Unsplash", source="unsplash")
        return None


class PexelsProvider:
    """Pexels 검색 API. 표기 의무는 없지만 넣어두면 좋습니다."""

    source = "pexels"

    def __init__(self, api_key: str):
        self.key = api_key
        self.used: set[int] = set()

    def search(self, query: str, keywords: list[str]) -> ImageResult | None:
        if not query.strip():
            return None
        url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
            {"query": query, "per_page": 8, "orientation": "portrait"}
        )
        data = _get_json(url, {"Authorization": self.key})
        if not data or not data.get("photos"):
            return None
        for photo in data["photos"]:
            pid = photo.get("id")
            if pid in self.used:
                continue
            self.used.add(pid)
            src = (photo.get("src") or {}).get("large")
            if not src:
                continue
            target = _cache_path(f"pexels:{pid}")
            if not target.is_file() and _download(src, target) is None:
                continue
            return ImageResult(
                path=target,
                credit=f"Photo by {photo.get('photographer', 'Pexels')} on Pexels",
                source="pexels",
            )
        return None


class GradientProvider:
    """항상 성공하는 폴백. 테마 색으로 추상 배경을 그립니다."""

    source = "gradient"

    def __init__(self, theme: Theme, size: tuple[int, int] = (1080, 1350)):
        self.theme = theme
        self.size = size
        self.counter = 0

    def search(self, query: str, keywords: list[str]) -> ImageResult | None:
        try:
            from PIL import Image, ImageDraw, ImageFilter
        except ImportError:
            return None

        self.counter += 1
        seed = f"{self.theme.name}:{query}:{self.counter}"
        target = _cache_path(f"gradient:{seed}", ".png")
        if target.is_file():
            return ImageResult(path=target, source="gradient")

        rng = random.Random(seed)
        w, h = self.size
        base = _hex_rgb(self.theme.bg_alt)
        top = _hex_rgb(self.theme.accent)
        bottom = _hex_rgb(self.theme.accent2)

        img = Image.new("RGB", (w, h), base)
        draw = ImageDraw.Draw(img, "RGBA")
        # 대각선 그라데이션
        for y in range(0, h, 4):
            t = y / h
            color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
            draw.rectangle([0, y, w, y + 4], fill=(*color, 255))
        # 부드러운 원형 블롭 몇 개
        for _ in range(rng.randint(4, 7)):
            r = rng.randint(w // 5, w // 2)
            cx, cy = rng.randint(0, w), rng.randint(0, h)
            tint = rng.choice([top, bottom, base])
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*tint, rng.randint(40, 110)))
        img = img.filter(ImageFilter.GaussianBlur(radius=w // 12))

        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target, "PNG")
        return ImageResult(path=target, source="gradient")


def _hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# --------------------------------------------------------------------------
# 리졸버
# --------------------------------------------------------------------------

class ImageResolver:
    """제공자들을 순서대로 시도하는 얇은 래퍼."""

    def __init__(
        self,
        theme: Theme,
        settings: Settings | None = None,
        *,
        local_dir: str | Path | None = None,
        provider: str = "auto",   # auto | local | unsplash | pexels | gradient | none
        size: tuple[int, int] = (1080, 1350),
    ):
        settings = settings or Settings.from_env()
        self.provider_name = provider
        self.chain: list = []

        if provider == "none":
            return
        if local_dir and provider in ("auto", "local"):
            self.chain.append(LocalProvider(local_dir))
        if provider in ("auto", "unsplash") and settings.unsplash_key:
            self.chain.append(UnsplashProvider(settings.unsplash_key))
        if provider in ("auto", "pexels") and settings.pexels_key:
            self.chain.append(PexelsProvider(settings.pexels_key))
        if provider != "local":
            self.chain.append(GradientProvider(theme, size))

    @property
    def enabled(self) -> bool:
        return bool(self.chain)

    def resolve(self, query: str, keywords: list[str] | None = None) -> ImageResult | None:
        for provider in self.chain:
            try:
                result = provider.search(query, keywords or [])
            except Exception as exc:  # noqa: BLE001 - 한 제공자가 죽어도 다음으로
                log.warning("%s 제공자 오류: %s", provider.source, exc)
                continue
            if result:
                return result
        return None
