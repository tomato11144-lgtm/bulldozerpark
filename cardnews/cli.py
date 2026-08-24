"""명령줄 인터페이스.

    cardnews "성수동 파스타 맛집 TOP 5"
    cardnews "홍대 야식" --theme neon --cards 8 --handle @bulldozer.eats
    cardnews rebuild out/성수동-파스타-BEST-5/cards.json
    cardnews themes
    cardnews doctor
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import CANVAS_SIZES, DEFAULT_RATIO, Settings
from .content import MODES
from .locales import LOCALES, locale_codes
from .pipeline import create, rebuild
from .themes import THEMES, suggest_theme, theme_names

PROG = "cardnews"


def _read_facts(value: str | None) -> str:
    """--facts 는 파일 경로나 문자열 둘 다 받습니다."""
    if not value:
        return ""
    path = Path(value)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="F&B 인스타그램 카드뉴스 생성기 — 주제 한 줄로 카드 이미지와 캡션까지",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "예시\n"
            f"  {PROG} \"성수동 파스타 맛집 TOP 5\"\n"
            f"  {PROG} \"홍대 심야 안주\" --theme neon --cards 8 --handle @bulldozer.eats\n"
            f"  {PROG} \"우리 가게 신메뉴 소개\" --facts data/menu.md --images-dir photos/\n"
            f"  {PROG} rebuild out/성수동-파스타-BEST-5/cards.json\n"
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="자세한 로그")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="주제로 카드뉴스 만들기 (기본 명령)")
    _add_generate_args(gen)

    reb = sub.add_parser("rebuild", help="cards.json 을 고친 뒤 다시 렌더링")
    reb.add_argument("json", help="cards.json 경로")
    reb.add_argument("-o", "--out", help="결과 폴더 (기본: json 파일이 있는 폴더)")
    reb.add_argument("--theme", choices=theme_names(), help="테마 바꿔서 다시 뽑기")
    reb.add_argument("--lang", choices=locale_codes(), help="언어를 바꿔서 다시 뽑기")
    reb.add_argument("--ratio", choices=list(CANVAS_SIZES), default=DEFAULT_RATIO)
    reb.add_argument("--renderer", choices=["auto", "chromium", "pillow"], default="auto")
    reb.add_argument("--scale", type=float, default=1.0)

    sub.add_parser("themes", help="테마 목록 보기")
    sub.add_parser("langs", help="지원 언어 목록 보기")
    sub.add_parser("doctor", help="실행 환경 점검 (폰트/브라우저/API 키)")
    return parser


COMMANDS = ("generate", "rebuild", "themes", "langs", "doctor")


def normalize(argv: list[str]) -> list[str]:
    """`cardnews "주제"` 처럼 서브커맨드를 생략한 호출에 generate 를 채워 넣습니다."""
    for i, token in enumerate(argv):
        if token in ("-h", "--help"):
            return argv
        if token.startswith("-"):
            continue
        # 첫 위치 인자가 서브커맨드가 아니면 주제로 봅니다.
        return argv if token in COMMANDS else [*argv[:i], "generate", *argv[i:]]
    return argv


def _add_generate_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("topic", nargs="?", help="카드뉴스 주제 (예: \"성수동 파스타 맛집 TOP 5\")")
    p.add_argument("-o", "--out", help="결과 폴더 (기본: out/<제목>)")
    p.add_argument("--theme", default="auto",
                   help="테마: " + ", ".join(theme_names()) + " (기본: auto — 주제 보고 자동 선택)")
    p.add_argument("-n", "--cards", type=int, default=7, help="카드 장수 (3~12, 기본 7)")
    p.add_argument("--ratio", choices=list(CANVAS_SIZES), default=DEFAULT_RATIO,
                   help="캔버스 비율 (기본 4:5)")
    p.add_argument("--handle", default="", help="계정명 (예: @bulldozer.eats)")
    p.add_argument("--lang", default="ko", choices=locale_codes(),
                   help="문안 언어: ko(기본) / en / tl(따갈로그) / taglish / en+tl(병기)")
    p.add_argument("--tone", default="", help="말투 (기본값은 언어에 맞춰 자동)")
    p.add_argument("--audience", default="", help="타깃 독자 (기본값은 언어에 맞춰 자동)")
    p.add_argument("--mode", choices=list(MODES),
                   help="facts=제공 자료만 사용 / placeholder=자리표시자(기본) / "
                        "unverified=예시 허용 / guide=가게 없이 정보형")
    p.add_argument("--facts", help="검증된 가게·메뉴 정보 (파일 경로 또는 문자열)")
    p.add_argument("--extra", default="", help="추가 요청사항 한 줄")
    p.add_argument("--images", default="auto",
                   choices=["auto", "local", "unsplash", "pexels", "gradient", "none"],
                   help="사진 출처 (기본 auto)")
    p.add_argument("--images-dir", help="내 사진 폴더 (가장 좋은 결과가 나옵니다)")
    p.add_argument("--renderer", choices=["auto", "chromium", "pillow"], default="auto",
                   help="렌더 백엔드 (기본 auto — 크로미움 우선, 실패 시 Pillow)")
    p.add_argument("--scale", type=float, default=1.0, help="해상도 배율 (2 로 주면 2160px)")
    p.add_argument("--offline", action="store_true",
                   help="Claude 를 부르지 않고 템플릿 생성기만 사용")
    p.add_argument("--clean", action="store_true", help="결과 폴더를 비우고 시작")


def cmd_themes() -> int:
    print("사용 가능한 테마\n")
    for theme in THEMES.values():
        print(f"  {theme.name:<7} {theme.label}")
        print(f"          {theme.best_for}")
        print(f"          {theme.display_font} / {theme.body_font}\n")
    print("--theme auto (기본) 로 두면 주제 키워드를 보고 알아서 고릅니다.")
    return 0


def cmd_langs() -> int:
    print("지원 언어\n")
    for loc in LOCALES.values():
        print(f"  {loc.code:<8} {loc.label}")
        if loc.note:
            print(f"           {loc.note}")
        print(f"           카드 라벨: {' · '.join(loc.meta_labels()[:3])}\n")
    print("예: cardnews \"Manila K-BBQ best 5\" --lang en+tl --theme neon")
    return 0


def cmd_doctor() -> int:
    from .fonts import available_families
    from .render.chromium import _find_chrome, _has_playwright
    from .themes import all_fonts

    settings = Settings.from_env()
    ok = True
    print("환경 점검\n")

    have = available_families()
    for script, label in (("hangul", "한글"), ("latin", "영어·따갈로그")):
        missing = sorted(set(all_fonts(script)) - have)
        if missing:
            ok = False
            print(f"  [!] {label} 폰트 {len(missing)}개 없음: {', '.join(missing)}")
            print(f"      -> python scripts/fetch_fonts.py --script {script}")
        else:
            print(f"  [o] {label} 폰트 준비됨")

    if _has_playwright():
        print("  [o] Playwright 설치됨")
    elif _find_chrome(settings.chromium_path):
        print(f"  [o] 크로미움 발견: {_find_chrome(settings.chromium_path)}")
    else:
        ok = False
        print("  [!] 크로미움을 못 찾았습니다 -> pip install playwright && playwright install chromium")
        print("      (그대로 두면 --renderer pillow 로 자동 대체됩니다)")

    try:
        import PIL  # noqa: F401
        print("  [o] Pillow 설치됨 (대체 렌더러 사용 가능)")
    except ImportError:
        ok = False
        print("  [!] Pillow 없음 -> pip install Pillow")

    if settings.has_llm:
        print(f"  [o] ANTHROPIC_API_KEY 설정됨 (모델 {settings.model})")
    else:
        print("  [-] ANTHROPIC_API_KEY 없음 — 오프라인 템플릿 생성기로 동작합니다")

    provider = settings.stock_provider
    if provider:
        print(f"  [o] 스톡 사진: {provider}")
    else:
        print("  [-] 스톡 사진 키 없음 — 그라데이션 배경 또는 --images-dir 를 쓰세요")

    print("\n" + ("모두 정상입니다." if ok else "위 [!] 항목을 먼저 처리하세요."))
    return 0 if ok else 1


def cmd_generate(args: argparse.Namespace) -> int:
    if not args.topic:
        print("주제를 입력하세요. 예: cardnews \"성수동 파스타 맛집 TOP 5\"", file=sys.stderr)
        return 2

    theme = args.theme
    if theme in ("auto", None, ""):
        theme = suggest_theme(args.topic)
        print(f"테마 자동 선택: {theme} ({THEMES[theme].label})")

    result = create(
        args.topic,
        out_dir=args.out,
        theme=theme,
        card_count=args.cards,
        ratio=args.ratio,
        tone=args.tone,
        audience=args.audience,
        mode=args.mode,
        facts=_read_facts(args.facts),
        handle=args.handle,
        extra=args.extra,
        lang=args.lang,
        images=args.images,
        images_dir=args.images_dir,
        renderer=args.renderer,
        scale=args.scale,
        offline=args.offline,
        clean=args.clean,
    )

    print(f"\n완료 — {len(result.images)}장")
    print(f"  폴더    {result.out_dir}")
    print(f"  미리보기 {result.preview_path}")
    print(f"  캡션    {result.caption_path}")
    if result.credits:
        print(f"  사진출처 {result.out_dir / 'credits.txt'}")
    if result.news.notes:
        print("\n확인할 것:")
        for line in result.news.notes.splitlines():
            print(f"  · {line}")
        print(f"\n  {result.json_path} 를 고친 뒤")
        print(f"  {PROG} rebuild {result.json_path} 로 다시 뽑으면 됩니다.")
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    result = rebuild(
        args.json, out_dir=args.out, ratio=args.ratio,
        renderer=args.renderer, scale=args.scale, theme=args.theme,
        lang=args.lang,
    )
    print(f"다시 렌더 완료 — {len(result.images)}장 -> {result.out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize(list(sys.argv[1:] if argv is None else argv)))
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if args.command == "themes":
        return cmd_themes()
    if args.command == "langs":
        return cmd_langs()
    if args.command == "doctor":
        return cmd_doctor()
    if args.command == "rebuild":
        return cmd_rebuild(args)
    return cmd_generate(args)


if __name__ == "__main__":
    raise SystemExit(main())
