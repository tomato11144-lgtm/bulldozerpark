"""HTML -> PNG (크로미움).

렌더 중에는 로컬 HTTP 서버를 잠깐 띄워 문서와 폰트·사진을 서빙합니다.
file:// 로 열면 크로미움이 폰트를 CORS 로 막고, base64 로 심으면 문서가 수십 MB 가 됩니다.

백엔드 선택:
  1. Playwright 가 설치돼 있으면 그것을 씁니다(가장 안정적).
  2. 없으면 크로미움/크롬 실행 파일을 찾아 `--headless --screenshot` 으로 한 장씩 찍습니다.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .html import RenderDoc

log = logging.getLogger(__name__)

MIME = {
    ".ttf": "font/ttf", ".otf": "font/otf", ".woff2": "font/woff2",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".avif": "image/avif",
}

# playwright 가 설치돼 있지 않을 때 찾아볼 실행 파일들
CHROME_CANDIDATES = (
    "/opt/pw-browsers/chromium",
    "chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
)


class RenderError(RuntimeError):
    """렌더링 실패."""


# --------------------------------------------------------------------------
# 정적 서버
# --------------------------------------------------------------------------

class _DeckServer:
    """문서 한 벌을 서빙하는 임시 HTTP 서버.

    /            -> 전체 카드 페이지
    /card/<n>    -> 카드 한 장짜리 페이지 (n 은 1부터)
    /__fonts/... -> 폰트 파일
    /__img/...   -> 사진 파일
    """

    def __init__(self, doc: RenderDoc):
        self.doc = doc
        handler = self._make_handler()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    def __enter__(self) -> "_DeckServer":
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def _make_handler(self):
        doc = self.doc

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: object) -> None:  # 서버 로그 조용히
                pass

            def _send(self, body: bytes, mime: str) -> None:
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802 - stdlib 시그니처
                path = unquote(urlparse(self.path).path)
                if path in ("/", "/index.html"):
                    return self._send(doc.html.encode("utf-8"), "text/html; charset=utf-8")
                if path.startswith("/card/"):
                    try:
                        idx = int(path.rsplit("/", 1)[-1]) - 1
                        return self._send(doc.pages[idx].encode("utf-8"),
                                          "text/html; charset=utf-8")
                    except (ValueError, IndexError):
                        pass
                target = doc.routes.get(path)
                if target and target.is_file():
                    mime = MIME.get(target.suffix.lower(), "application/octet-stream")
                    return self._send(target.read_bytes(), mime)
                self.send_error(404)

        return Handler


# --------------------------------------------------------------------------
# 백엔드
# --------------------------------------------------------------------------

def _find_chrome(explicit: str = "") -> str | None:
    for candidate in filter(None, (explicit, os.getenv("CARDNEWS_CHROMIUM_PATH", ""))):
        if Path(candidate).exists():
            return candidate
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


def _has_playwright() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


def render_png(
    doc: RenderDoc,
    out_paths: list[Path],
    *,
    scale: float = 1.0,
    chromium_path: str = "",
    backend: str = "auto",   # auto | playwright | cli
) -> list[Path]:
    """카드마다 PNG 한 장씩 뽑습니다. out_paths 는 카드 수와 길이가 같아야 합니다."""
    if len(out_paths) != doc.count:
        raise ValueError(f"출력 경로 {len(out_paths)}개 != 카드 {doc.count}장")
    for path in out_paths:
        path.parent.mkdir(parents=True, exist_ok=True)

    if backend in ("auto", "playwright") and _has_playwright():
        try:
            return _render_playwright(doc, out_paths, scale=scale, chromium_path=chromium_path)
        except Exception as exc:  # noqa: BLE001
            if backend == "playwright":
                raise
            log.warning("Playwright 렌더 실패(%s) — 크로미움 CLI 로 재시도합니다.", exc)

    chrome = _find_chrome(chromium_path)
    if not chrome:
        raise RenderError(
            "크로미움을 찾지 못했습니다.\n"
            "  pip install playwright && playwright install chromium\n"
            "또는 CARDNEWS_CHROMIUM_PATH 로 실행 파일 경로를 지정하세요.\n"
            "브라우저 없이 뽑으려면 --renderer pillow 를 쓰세요."
        )
    return _render_cli(doc, out_paths, chrome, scale=scale)


def _render_playwright(
    doc: RenderDoc, out_paths: list[Path], *, scale: float, chromium_path: str
) -> list[Path]:
    from playwright.sync_api import sync_playwright

    exe = _find_chrome(chromium_path)
    with _DeckServer(doc) as server, sync_playwright() as pw:
        launch: dict = {"args": ["--font-render-hinting=none", "--disable-lcd-text"]}
        # 번들 브라우저 버전이 안 맞는 환경(CI 등)을 위해 실행 파일을 직접 지정합니다.
        if exe and not Path(exe).name.startswith("chrome-headless-shell"):
            launch["executable_path"] = exe
        try:
            browser = pw.chromium.launch(**launch)
        except Exception:
            launch.pop("executable_path", None)
            browser = pw.chromium.launch(**launch)

        page = browser.new_page(
            viewport={"width": doc.width, "height": doc.height},
            device_scale_factor=scale,
        )
        page.goto(f"{server.base}/", wait_until="load")
        page.wait_for_timeout(200)
        page.evaluate("() => document.fonts.ready")

        results = []
        for i, out in enumerate(out_paths, start=1):
            page.locator(f"#card-{i}").screenshot(path=str(out), type="png")
            results.append(out)
        browser.close()
    return results


def _render_cli(
    doc: RenderDoc, out_paths: list[Path], chrome: str, *, scale: float
) -> list[Path]:
    """Playwright 없이 크로미움 CLI 로 한 장씩 캡처합니다."""
    results = []
    with _DeckServer(doc) as server, tempfile.TemporaryDirectory() as profile:
        for i, out in enumerate(out_paths, start=1):
            cmd = [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                "--force-color-profile=srgb",
                "--font-render-hinting=none",
                f"--user-data-dir={profile}",
                f"--window-size={doc.width},{doc.height}",
                f"--force-device-scale-factor={scale}",
                "--virtual-time-budget=4000",   # 폰트·이미지 로딩 대기
                f"--screenshot={out}",
                f"{server.base}/card/{i}",
            ]
            proc = subprocess.run(cmd, capture_output=True, timeout=120)
            if not out.is_file():
                raise RenderError(
                    f"{out.name} 캡처 실패\n{proc.stderr.decode('utf-8', 'replace')[-500:]}"
                )
            results.append(out)
    return results
