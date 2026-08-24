"""report.json -> 결과 폴더까지 한 번에.

    from storeboard.pipeline import build
    result = build("report.json")

결과 폴더 구성:
    slides/01_cover.png ...     PPT·메신저에 그대로 올리는 장면 이미지
    deck.pdf                    보고 자리에서 띄우는 파일 (슬라이드당 한 쪽)
    deck.html                   브라우저로 넘겨보는 미리보기 (파일 하나로 완결)
    report.json                 정규화된 원본 데이터 (고쳐서 다시 빌드 가능)
    summary.txt                 메신저에 붙여 넣는 텍스트 요약
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import fmt, periods
from .config import DEFAULT_OUT_DIR, Settings
from .deck import Deck, build_deck
from .insights import Insights, build_insights
from .metrics import Summary, summarize
from .models import Report
from .render.html import build_html

log = logging.getLogger(__name__)

FORMATS = ("png", "pdf", "html")


@dataclass
class Result:
    report: Report
    summary: Summary
    insights: Insights
    deck: Deck
    out_dir: Path
    slides: list[Path] = field(default_factory=list)
    pdf: Path | None = None
    html: Path | None = None

    @property
    def json_path(self) -> Path:
        return self.out_dir / "report.json"

    @property
    def summary_path(self) -> Path:
        return self.out_dir / "summary.txt"


def _slide_name(index: int, kind: str) -> str:
    return f"{index:02d}_{kind}.png"


def _standalone_html(doc, out_dir: Path) -> Path:
    """폰트·캡처를 옆에 복사하고 상대경로로 바꾼 미리보기 문서."""
    assets = out_dir / "assets"
    html = doc.html
    if doc.routes:
        assets.mkdir(parents=True, exist_ok=True)
        for url, path in doc.routes.items():
            shutil.copyfile(path, assets / path.name)
            html = html.replace(url, f"assets/{path.name}")
    path = out_dir / "deck.html"
    path.write_text(html, encoding="utf-8")
    return path


def text_summary(report: Report, summary: Summary, insights: Insights) -> str:
    """메신저에 그대로 붙여 넣는 요약."""
    lines = [
        f"[{report.brand or '직영점'}] {periods.label(summary.period)} 실적",
        f"· 매출 {fmt.won_compact(summary.revenue)}원"
        + (f" ({summary.prev.label} {fmt.signed_pct(summary.prev.pct)})"
           if summary.prev.available else ""),
    ]
    if summary.yoy.available:
        lines.append(f"· 전년 동기 대비 {fmt.signed_pct(summary.yoy.pct)}")
    if summary.spend:
        lines.append(
            f"· 광고비 {fmt.won_compact(summary.spend)}원 "
            f"(매출 대비 {fmt.pct(summary.ad_ratio)}, ROAS {fmt.multiple(summary.blended_roas)})"
        )
    if summary.traffic.has_data:
        lines.append(
            f"· 플레이스 조회 {fmt.num(summary.traffic.views)}회 → "
            f"행동 {fmt.num(summary.traffic.actions)}회 ({fmt.pct(summary.traffic.action_rate)})"
        )
    for row in summary.stores:
        lines.append(
            f"  - {row.store} {fmt.won_compact(row.revenue)}원"
            + (f" {fmt.signed_pct(row.prev.pct)}" if row.prev.available else "")
        )
    if insights.actions:
        lines.append("\n다음 액션")
        lines += [f"  {i}. {a.text} ({a.owner}·{a.due})"
                  for i, a in enumerate(insights.actions, start=1)]
    if report.warnings:
        lines.append("\n확인 필요")
        lines += [f"  - {w}" for w in report.warnings]
    return "\n".join(lines) + "\n"


def build(
    source: str | Path | Report,
    *,
    out_dir: str | Path | None = None,
    period: str = "",
    history: int = 8,
    formats: tuple[str, ...] = FORMATS,
    scale: float = 1.0,
    offline: bool = False,
    settings: Settings | None = None,
    clean: bool = False,
) -> Result:
    """리포트 하나로 슬라이드 한 부를 만들어 폴더에 떨궈 놓습니다."""
    settings = settings or Settings.from_env()
    report = source if isinstance(source, Report) else Report.load_json(source)
    if period:
        report.period = periods.normalize(period)
    if not report.period:
        raise ValueError("기준 기간을 알 수 없습니다 — report.json 의 period 를 채워 주세요.")

    summary = summarize(report, report.period)
    insights = build_insights(report, summary, settings=settings, offline=offline)
    deck = build_deck(report, summary, insights, history=history)

    target = Path(out_dir) if out_dir else DEFAULT_OUT_DIR / report.slug
    if clean and target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    doc = build_html(deck)
    if doc.missing_fonts:
        log.info(
            "폰트가 없어 시스템 서체로 대체됩니다: %s — `python scripts/fetch_fonts.py` 를 실행하세요.",
            ", ".join(doc.missing_fonts),
        )

    result = Result(report=report, summary=summary, insights=insights, deck=deck,
                    out_dir=target)

    if "png" in formats or "pdf" in formats:
        from .render.browser import render_pdf, render_png

        if "png" in formats:
            slide_dir = target / "slides"
            paths = [
                slide_dir / _slide_name(i, slide.kind)
                for i, slide in enumerate(deck.slides, start=1)
            ]
            result.slides = render_png(doc, paths, scale=scale,
                                       chromium_path=settings.chromium_path)
        if "pdf" in formats:
            result.pdf = render_pdf(doc, target / "deck.pdf",
                                    chromium_path=settings.chromium_path)

    if "html" in formats:
        result.html = _standalone_html(doc, target)

    report.save_json(result.json_path)
    result.summary_path.write_text(text_summary(report, summary, insights), encoding="utf-8")
    return result
