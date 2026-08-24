"""캡처 이미지 -> 구조화된 리포트 조각.

    from storeboard.extract import extract_all
    report = extract_all(["shots/매출_주간.png", "shots/네이버유입.png"], period="2026-W33")

캡처 한 장당 한 번 호출합니다. 장마다 경고가 따로 붙어야 어느 캡처의 무엇을
못 읽었는지 보고서 부록에서 바로 알 수 있기 때문입니다.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from . import prompts
from .config import MAX_IMAGE_EDGE, Settings
from .models import Report

log = logging.getLogger(__name__)

SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif")

# 파일명으로 종류를 먼저 짐작합니다 (모델 판단보다 확실하고 공짜입니다).
FILENAME_HINTS = {
    "sales": ("매출", "sales", "revenue", "pos", "정산", "결제"),
    "traffic": ("네이버", "naver", "플레이스", "place", "유입", "traffic", "smartplace"),
    "ads": ("광고", "ads", "ad_", "roas", "구글", "google", "메타", "meta",
            "페이스북", "facebook", "인스타", "gfa", "kakao", "카카오"),
}


class ExtractError(RuntimeError):
    """캡처 판독 실패."""


@dataclass
class Capture:
    path: Path
    kind: str = ""

    @property
    def name(self) -> str:
        return self.path.name


def guess_kind(path: Path) -> str:
    """파일 이름에서 캡처 종류를 짐작합니다. 모르면 빈 문자열."""
    name = path.name.lower()
    # 광고 리포트에 '네이버'가 들어가는 경우가 많아 매출 -> 광고 -> 유입 순으로 봅니다.
    for kind in ("sales", "ads", "traffic"):
        if any(token in name for token in FILENAME_HINTS[kind]):
            return kind
    return ""


def collect(paths: list[str | Path]) -> list[Capture]:
    """파일과 폴더를 섞어 받아 캡처 목록으로 폅니다."""
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found += sorted(p for p in path.rglob("*") if p.suffix.lower() in SUFFIXES)
        elif path.is_file() and path.suffix.lower() in SUFFIXES:
            found.append(path)
        else:
            log.warning("건너뜁니다(이미지가 아님): %s", path)
    return [Capture(path=p, kind=guess_kind(p)) for p in found]


def _image_block(path: Path) -> dict:
    """이미지를 base64 블록으로. 너무 크면 긴 변 기준으로 줄입니다."""
    media_type = mimetypes.guess_type(path.name)[0] or "image/png"
    data = path.read_bytes()
    try:
        from PIL import Image
    except ImportError:
        pass
    else:
        import io

        with Image.open(path) as img:
            if max(img.size) > MAX_IMAGE_EDGE:
                ratio = MAX_IMAGE_EDGE / max(img.size)
                resized = img.convert("RGB").resize(
                    (int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS
                )
                buffer = io.BytesIO()
                resized.save(buffer, format="PNG")
                data, media_type = buffer.getvalue(), "image/png"
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(data).decode("ascii"),
        },
    }


def extract_one(
    capture: Capture,
    *,
    settings: Settings | None = None,
    period: str = "",
    stores: list[str] | None = None,
) -> Report:
    """캡처 한 장을 읽어 리포트 조각으로."""
    settings = settings or Settings.from_env()
    if not settings.has_llm:
        raise ExtractError(
            "ANTHROPIC_API_KEY 가 없어 캡처를 읽을 수 없습니다.\n"
            "  · .env 에 키를 넣거나\n"
            "  · `storeboard template` 로 빈 report.json 을 만들어 손으로 채우세요."
        )
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - 설치 안내
        raise ExtractError("anthropic 패키지가 필요합니다: pip install anthropic") from exc

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.model,
        max_tokens=12000,
        system=prompts.SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                _image_block(capture.path),
                {"type": "text", "text": prompts.user_prompt(
                    filename=capture.name, kind=capture.kind,
                    period=period, stores=stores or [],
                )},
            ],
        }],
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",     # 표 판독은 정확도가 전부입니다.
            "format": {"type": "json_schema", "schema": prompts.schema()},
        },
    )
    if getattr(response, "stop_reason", None) == "refusal":
        raise ExtractError(f"모델이 응답을 거부했습니다: {getattr(response, 'stop_details', None)}")

    text = next((b.text for b in response.content if b.type == "text"), "")
    if not text.strip():
        raise ExtractError(f"{capture.name}: 빈 응답")

    data = json.loads(text)
    return _to_report(data, capture, fallback_period=period)


def _to_report(data: dict, capture: Capture, *, fallback_period: str = "") -> Report:
    """판독 결과를 Report 조각으로. 기간이 빈 행은 기준 기간으로 채웁니다."""
    period = (data.get("period") or "").strip() or fallback_period
    for row in (*data.get("sales", []), *data.get("ads", []), *data.get("traffic", [])):
        if not (row.get("period") or "").strip():
            row["period"] = period
    rows = [*data.get("sales", []), *data.get("ads", []), *data.get("traffic", [])]
    warnings = list(data.get("warnings", []))
    if not period and any(not r.get("period") for r in rows):
        warnings.append(f"{capture.name}: 기간을 읽지 못했습니다 — --period 로 지정하세요.")

    keep = [r for r in rows if r.get("period")]
    report = Report(
        period=period,
        sales=[r for r in data.get("sales", []) if r in keep],
        ads=[r for r in data.get("ads", []) if r in keep],
        traffic=[r for r in data.get("traffic", []) if r in keep],
        captures=[str(capture.path)],
        warnings=[f"{capture.name}: {w}" if not w.startswith(capture.name) else w
                  for w in warnings],
        notes=(data.get("notes") or "").strip(),
        meta={"kind": data.get("kind", capture.kind or "unknown")},
    )
    return report


def extract_all(
    paths: list[str | Path],
    *,
    settings: Settings | None = None,
    period: str = "",
    stores: list[str] | None = None,
    title: str = "",
    brand: str = "",
    on_progress=None,
) -> Report:
    """캡처 여러 장을 읽어 하나의 리포트로 합칩니다."""
    settings = settings or Settings.from_env()
    captures = collect(paths)
    if not captures:
        raise ExtractError("읽을 이미지가 없습니다.")

    merged = Report(period=period, brand=brand)
    if title:
        merged.title = title
    known = list(stores or [])

    for i, capture in enumerate(captures, start=1):
        if on_progress:
            on_progress(i, len(captures), capture)
        try:
            piece = extract_one(capture, settings=settings, period=period, stores=known)
        except Exception as exc:  # noqa: BLE001 - 한 장이 실패해도 나머지는 살립니다
            log.warning("%s 판독 실패: %s", capture.name, exc)
            merged.warnings.append(f"{capture.name}: 판독 실패 ({exc})")
            merged.captures.append(str(capture.path))
            continue
        merged.merge(piece)
        known = merged.detect_stores() or known

    merged.stores = merged.detect_stores()
    merged.period = period or merged.detect_period()
    return merged
