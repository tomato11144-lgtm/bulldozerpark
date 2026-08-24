"""명령줄 인터페이스.

    storeboard report shots/ --period 2026-W33        # 캡처 -> 슬라이드까지 한 번에
    storeboard extract shots/ -o report.json          # 캡처 판독만
    storeboard build report.json                      # 데이터 -> 슬라이드
    storeboard sample                                 # 데모 덱 (API 키 없이)
    storeboard template -o report.json                # 손으로 채울 빈 리포트
    storeboard doctor                                 # 실행 환경 점검
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import periods
from .config import DEFAULT_OUT_DIR, Settings
from .models import CHANNELS, INFLOW_PATHS, Report
from .pipeline import FORMATS, build

PROG = "storeboard"
COMMANDS = ("report", "extract", "build", "sample", "template", "channels", "doctor")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="직영 매장 마케팅 성과 + 매출 분석 슬라이드 생성기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "예시\n"
            f"  {PROG} report shots/ --period 2026-W33 --brand 불도저파크\n"
            f"  {PROG} extract shots/매출_주간.png -o report.json\n"
            f"  {PROG} build report.json --format pdf,png\n"
            f"  {PROG} sample\n"
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="자세한 로그")
    sub = parser.add_subparsers(dest="command")

    rep = sub.add_parser("report", help="캡처 -> 판독 -> 슬라이드까지 한 번에")
    rep.add_argument("shots", nargs="+", help="캡처 이미지 또는 폴더")
    _add_meta_args(rep)
    _add_build_args(rep)

    ext = sub.add_parser("extract", help="캡처를 읽어 report.json 만 만들기")
    ext.add_argument("shots", nargs="+", help="캡처 이미지 또는 폴더")
    ext.add_argument("-o", "--out", default="report.json", help="저장 경로 (기본 report.json)")
    _add_meta_args(ext)

    bld = sub.add_parser("build", help="report.json 으로 슬라이드 만들기")
    bld.add_argument("json", help="report.json 경로")
    _add_build_args(bld)

    smp = sub.add_parser("sample", help="데모 데이터로 덱 한 부 만들어 보기")
    _add_build_args(smp)

    tpl = sub.add_parser("template", help="손으로 채우는 빈 report.json")
    tpl.add_argument("-o", "--out", default="report.json")
    tpl.add_argument("--period", default="", help="기준 기간 (예: 2026-W33)")
    tpl.add_argument("--stores", default="", help="매장 이름 쉼표 구분")

    sub.add_parser("channels", help="채널·유입경로 키 목록")
    sub.add_parser("doctor", help="실행 환경 점검 (API 키/브라우저/폰트)")
    return parser


def _add_meta_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--period", default="",
                   help="기준 기간 (2026-W33 / 2026-08). 캡처에 없으면 이 값을 씁니다")
    p.add_argument("--brand", default="", help="브랜드·회사명 (표지와 꼬리말)")
    p.add_argument("--title", default="", help="보고서 제목")
    p.add_argument("--stores", default="", help="매장 이름 쉼표 구분 (표기 통일용)")


def _add_build_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("-o", "--out", help="결과 폴더 (기본: out/<제목-기간>)")
    p.add_argument("--history", type=int, default=8, help="추이에 넣을 기간 수 (기본 8)")
    p.add_argument("--format", default="png,pdf,html",
                   help="내보낼 형식: " + ", ".join(FORMATS) + " (쉼표 구분)")
    p.add_argument("--scale", type=float, default=1.0, help="PNG 해상도 배율 (2 = 3840px)")
    p.add_argument("--offline", action="store_true",
                   help="Claude 를 부르지 않고 규칙 기반 코멘트만 사용")
    p.add_argument("--clean", action="store_true", help="결과 폴더를 비우고 시작")
    if "--period" not in {a.option_strings[0] for a in p._actions if a.option_strings}:
        p.add_argument("--period", default="", help="기준 기간을 바꿔서 다시 뽑기")


def normalize(argv: list[str]) -> list[str]:
    """`storeboard report.json` / `storeboard shots/` 처럼 서브커맨드를 생략한 호출 보정."""
    for i, token in enumerate(argv):
        if token in ("-h", "--help"):
            return argv
        if token.startswith("-"):
            continue
        if token in COMMANDS:
            return argv
        command = "build" if token.endswith(".json") else "report"
        return [*argv[:i], command, *argv[i:]]
    return argv


def _formats(value: str) -> tuple[str, ...]:
    picked = tuple(v.strip() for v in value.split(",") if v.strip() in FORMATS)
    return picked or FORMATS


def _print_result(result) -> None:
    print(f"\n완성했습니다 → {result.out_dir}")
    if result.slides:
        print(f"  슬라이드 {len(result.slides)}장  {result.slides[0].parent}")
    if result.pdf:
        print(f"  PDF        {result.pdf.name}")
    if result.html:
        print(f"  미리보기   {result.html.name}")
    print(f"  데이터     {result.json_path.name} (고친 뒤 build 로 다시 뽑을 수 있습니다)")
    print(f"  텍스트요약 {result.summary_path.name}")
    if result.report.warnings:
        print("\n확인이 필요한 항목")
        for warning in result.report.warnings:
            print(f"  - {warning}")


def cmd_build(args) -> int:
    settings = Settings.from_env()
    result = build(
        args.json,
        out_dir=args.out,
        period=args.period,
        history=args.history,
        formats=_formats(args.format),
        scale=args.scale,
        offline=args.offline,
        settings=settings,
        clean=args.clean,
    )
    _print_result(result)
    return 0


def cmd_sample(args) -> int:
    from .sample import build_sample

    report = build_sample()
    result = build(
        report,
        out_dir=args.out or (DEFAULT_OUT_DIR / "sample"),
        history=args.history,
        formats=_formats(args.format),
        scale=args.scale,
        offline=True,          # 데모는 항상 오프라인 — 키가 있어도 돈을 쓰지 않습니다.
        clean=args.clean,
    )
    _print_result(result)
    print("\n샘플 데이터입니다. 실제 매장 실적이 아닙니다.")
    return 0


def cmd_extract(args, *, save: bool = True) -> Report:
    from .extract import extract_all

    stores = [s.strip() for s in args.stores.split(",") if s.strip()]

    def progress(i: int, total: int, capture) -> None:
        print(f"  [{i}/{total}] {capture.name} 읽는 중…", flush=True)

    print("캡처를 읽습니다.")
    report = extract_all(
        args.shots, period=args.period, stores=stores,
        title=args.title, brand=args.brand, on_progress=progress,
    )
    print(f"  매출 {len(report.sales)}행 · 광고 {len(report.ads)}행 · 유입 {len(report.traffic)}행")
    if save:
        path = report.save_json(args.out)
        print(f"  저장 → {path}")
    if report.warnings:
        print("\n확인이 필요한 항목")
        for warning in report.warnings:
            print(f"  - {warning}")
    return report


def cmd_report(args) -> int:
    # 판독 결과는 파일로 남기지 않고 바로 넘깁니다 —
    # 결과 폴더의 report.json 이 어차피 같은 내용을 들고 있습니다.
    report = cmd_extract(args, save=False)
    result = build(
        report,
        out_dir=args.out,
        period=args.period,
        history=args.history,
        formats=_formats(args.format),
        scale=args.scale,
        offline=args.offline,
        clean=args.clean,
    )
    _print_result(result)
    return 0


TEMPLATE_HELP = [
    "이 파일을 채운 뒤 `storeboard build report.json` 을 실행하세요.",
    "기간 표기: 주간 2026-W33 / 월간 2026-08 / 연간 2026 (전년 자료는 그 해로 적습니다)",
    "금액은 원 단위 정수입니다. 모르는 값은 0 으로 두면 지표에서 빠집니다.",
    f"광고 채널 키: {', '.join(CHANNELS)}",
    f"유입 경로 키: {', '.join(INFLOW_PATHS)}",
]


def cmd_template(args) -> int:
    stores = [s.strip() for s in args.stores.split(",") if s.strip()] or ["매장1", "매장2"]
    period = periods.normalize(args.period) if args.period else "2026-W33"
    data = {
        "_사용법": TEMPLATE_HELP,
        "title": "직영점 주간 마케팅·매출 리포트",
        "brand": "",
        "period": period,
        "stores": stores,
        "goal": {"revenue": 0, "roas": 0, "ad_ratio": 0},
        "sales": [
            {"store": store, "period": p, "revenue": 0, "orders": 0, "customers": 0}
            for store in stores
            for p in (period, periods.prev(period), periods.last_year(period))
        ],
        "ads": [
            {"channel": channel, "period": period, "store": "전체", "spend": 0,
             "impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0}
            for channel in ("naver_sa", "naver_place", "meta", "google_ads")
        ],
        "traffic": [
            {"store": store, "period": period, "views": 0,
             "inflow": {key: 0 for key in ("search", "map", "ad", "blog", "direct")},
             "keywords": [{"term": "", "count": 0}],
             "saves": 0, "calls": 0, "reservations": 0, "directions": 0,
             "reviews": 0, "review_score": 0}
            for store in stores
        ],
        "captures": [],
        "notes": "",
    }
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"빈 리포트를 만들었습니다 → {path}")
    for line in TEMPLATE_HELP:
        print(f"  · {line}")
    return 0


def cmd_channels() -> int:
    print("광고 채널 키\n")
    for key, label in CHANNELS.items():
        print(f"  {key:<14} {label}")
    print("\n네이버 플레이스 유입 경로 키\n")
    for key, label in INFLOW_PATHS.items():
        print(f"  {key:<14} {label}")
    return 0


def cmd_doctor() -> int:
    from .render.browser import _find_chrome, _has_playwright

    settings = Settings.from_env()
    print("storeboard 환경 점검\n")

    key = settings.anthropic_api_key
    print(f"  ANTHROPIC_API_KEY  {'있음 (' + key[:8] + '…)' if key else '없음'}")
    print(f"  모델               {settings.model}")
    if not key:
        print("     → 캡처 판독은 키가 필요합니다. 코멘트는 규칙 기반으로 대체됩니다.")

    chrome = _find_chrome(settings.chromium_path)
    print(f"  Playwright         {'설치됨' if _has_playwright() else '없음'}")
    print(f"  크로미움           {chrome or '못 찾음'}")
    if not chrome and not _has_playwright():
        print("     → pip install playwright && playwright install chromium")
        print("       (PNG·PDF 를 못 만듭니다. HTML 미리보기는 됩니다)")

    try:
        from PIL import Image  # noqa: F401
        print("  Pillow             설치됨")
    except ImportError:
        print("  Pillow             없음 → 캡처 축소·여백 정리를 건너뜁니다")

    try:
        from cardnews.fonts import available_families
        from .render.html import FONT_FAMILIES

        have = available_families()
        missing = [f for f in FONT_FAMILIES if f not in have]
        print(f"  폰트               {'모두 있음' if not missing else '없음: ' + ', '.join(missing)}")
        if missing:
            print("     → python scripts/fetch_fonts.py (없으면 시스템 서체로 렌더링됩니다)")
    except ImportError:
        print("  폰트               확인 불가")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(normalize(argv))
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if args.command == "doctor":
        return cmd_doctor()
    if args.command == "channels":
        return cmd_channels()
    if args.command == "template":
        return cmd_template(args)
    if args.command == "sample":
        return cmd_sample(args)
    if args.command == "extract":
        cmd_extract(args)
        return 0
    if args.command == "report":
        return cmd_report(args)
    if args.command == "build":
        return cmd_build(args)

    parser.print_help()
    return 1
