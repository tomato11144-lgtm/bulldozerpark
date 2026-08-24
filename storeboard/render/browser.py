"""HTML -> PNG / PDF (크로미움).

렌더 중에는 로컬 HTTP 서버를 잠깐 띄워 문서와 폰트·캡처를 서빙합니다.
서버와 실행 파일 탐색은 카드뉴스 렌더러의 것을 그대로 씁니다 — 같은 저장소 안에서
브라우저 배선을 두 벌 들고 있을 이유가 없습니다.

백엔드 선택:
  1. Playwright 가 설치돼 있으면 그것을 씁니다(가장 안정적).
  2. 없으면 크로미움/크롬 실행 파일을 찾아 CLI 로 한 장씩 찍습니다.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from cardnews.render.chromium import (  # noqa: F401 - 재사용 (서버·탐색 로직 공유)
    RenderError,
    _DeckServer,
    _find_chrome,
    _has_playwright,
)

from .html import RenderDoc

log = logging.getLogger(__name__)

# 폰트·이미지가 다 뜬 뒤에 찍도록 주는 여유(ms).
SETTLE_MS = 250

# 크로미움 CLI 로 뷰포트를 정확히 슬라이드 높이에 맞춰 찍으면 맨 아래 몇십 px 이
# 칠해지지 않고 나옵니다(꼬리말이 통째로 사라집니다). 창을 넉넉히 잡아 찍고
# 원래 크기로 잘라 냅니다.
CLI_VIEWPORT_PAD = 200


def _launch(pw, chromium_path: str):
    exe = _find_chrome(chromium_path)
    launch: dict = {"args": ["--font-render-hinting=none", "--disable-lcd-text"]}
    if exe and not Path(exe).name.startswith("chrome-headless-shell"):
        launch["executable_path"] = exe
    try:
        return pw.chromium.launch(**launch)
    except Exception:                       # 번들 브라우저 버전이 안 맞는 환경(CI 등)
        launch.pop("executable_path", None)
        return pw.chromium.launch(**launch)


def render_png(
    doc: RenderDoc,
    out_paths: list[Path],
    *,
    scale: float = 1.0,
    chromium_path: str = "",
) -> list[Path]:
    """슬라이드마다 PNG 한 장. out_paths 는 슬라이드 수와 길이가 같아야 합니다."""
    if len(out_paths) != doc.count:
        raise ValueError(f"출력 경로 {len(out_paths)}개 != 슬라이드 {doc.count}장")
    for path in out_paths:
        path.parent.mkdir(parents=True, exist_ok=True)

    if _has_playwright():
        try:
            return _png_playwright(doc, out_paths, scale=scale, chromium_path=chromium_path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Playwright 렌더 실패(%s) — 크로미움 CLI 로 재시도합니다.", exc)

    chrome = _find_chrome(chromium_path)
    if not chrome:
        raise RenderError(
            "크로미움을 찾지 못했습니다.\n"
            "  pip install playwright && playwright install chromium\n"
            "또는 STOREBOARD_CHROMIUM_PATH 로 실행 파일 경로를 지정하세요."
        )
    return _png_cli(doc, out_paths, chrome, scale=scale)


def _png_playwright(
    doc: RenderDoc, out_paths: list[Path], *, scale: float, chromium_path: str
) -> list[Path]:
    from playwright.sync_api import sync_playwright

    with _DeckServer(doc) as server, sync_playwright() as pw:
        browser = _launch(pw, chromium_path)
        page = browser.new_page(
            viewport={"width": doc.width, "height": doc.height},
            device_scale_factor=scale,
        )
        page.goto(f"{server.base}/", wait_until="load")
        page.wait_for_timeout(SETTLE_MS)
        page.evaluate("() => document.fonts.ready")

        results = []
        for i, out in enumerate(out_paths, start=1):
            page.locator(f"#card-{i}").screenshot(path=str(out), type="png")
            results.append(out)
        browser.close()
    return results


def _png_cli(
    doc: RenderDoc, out_paths: list[Path], chrome: str, *, scale: float
) -> list[Path]:
    results = []
    with _DeckServer(doc) as server, tempfile.TemporaryDirectory() as profile:
        for i, out in enumerate(out_paths, start=1):
            cmd = [
                chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                "--hide-scrollbars", "--force-color-profile=srgb",
                "--font-render-hinting=none",
                f"--user-data-dir={profile}",
                f"--window-size={doc.width},{doc.height + CLI_VIEWPORT_PAD}",
                f"--force-device-scale-factor={scale}",
                "--virtual-time-budget=4000",
                f"--screenshot={out}",
                f"{server.base}/card/{i}",
            ]
            proc = subprocess.run(cmd, capture_output=True, timeout=180)
            if not out.is_file():
                raise RenderError(
                    f"{out.name} 캡처 실패\n{proc.stderr.decode('utf-8', 'replace')[-500:]}"
                )
            _crop(out, int(doc.width * scale), int(doc.height * scale))
            results.append(out)
    return results


def _crop(path: Path, width: int, height: int) -> None:
    """여유를 두고 찍은 이미지를 슬라이드 크기로 잘라 냅니다."""
    try:
        from PIL import Image
    except ImportError:      # Pillow 가 없으면 여백이 붙은 채로 둡니다(내용은 온전합니다).
        log.warning("Pillow 가 없어 캡처 여백을 자르지 못했습니다: %s", path.name)
        return
    with Image.open(path) as img:
        if img.size == (width, height):
            return
        img.crop((0, 0, width, height)).save(path)


def render_pdf(doc: RenderDoc, out_path: Path, *, chromium_path: str = "") -> Path:
    """덱 전체를 슬라이드당 한 쪽인 PDF 로. 보고 자리에 그대로 띄우는 파일입니다."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if _has_playwright():
        try:
            return _pdf_playwright(doc, out_path, chromium_path=chromium_path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Playwright PDF 실패(%s) — 크로미움 CLI 로 재시도합니다.", exc)

    chrome = _find_chrome(chromium_path)
    if not chrome:
        raise RenderError("크로미움을 찾지 못해 PDF 를 만들 수 없습니다.")
    with _DeckServer(doc) as server, tempfile.TemporaryDirectory() as profile:
        cmd = [
            chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--no-pdf-header-footer", "--force-color-profile=srgb",
            f"--user-data-dir={profile}",
            "--virtual-time-budget=8000",
            f"--print-to-pdf={out_path}",
            f"{server.base}/",
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=300)
        if not out_path.is_file():
            raise RenderError(
                f"PDF 생성 실패\n{proc.stderr.decode('utf-8', 'replace')[-500:]}"
            )
    return out_path


def _pdf_playwright(doc: RenderDoc, out_path: Path, *, chromium_path: str) -> Path:
    from playwright.sync_api import sync_playwright

    with _DeckServer(doc) as server, sync_playwright() as pw:
        browser = _launch(pw, chromium_path)
        page = browser.new_page(viewport={"width": doc.width, "height": doc.height})
        page.goto(f"{server.base}/", wait_until="load")
        page.wait_for_timeout(SETTLE_MS)
        page.evaluate("() => document.fonts.ready")
        page.pdf(
            path=str(out_path),
            width=f"{doc.width}px",
            height=f"{doc.height}px",
            print_background=True,
            prefer_css_page_size=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()
    return out_path
