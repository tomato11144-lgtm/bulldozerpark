"""숫자 표기. 보고서 안에서 같은 값이 늘 같은 모양으로 보이게 합니다."""

from __future__ import annotations

EOK = 100_000_000
MAN = 10_000


def _trim(text: str) -> str:
    return text.rstrip("0").rstrip(".") if "." in text else text


def won(value: float | int) -> str:
    """원 단위 그대로. 표 안에서 씁니다."""
    return f"{int(round(value)):,}원"


def won_compact(value: float | int, *, unit: bool = True) -> str:
    """억/만 단위로 줄인 표기. 큰 숫자를 눈으로 비교할 때 씁니다."""
    v = int(round(value))
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= EOK:
        return f"{sign}{_trim(f'{v / EOK:.2f}')}억"
    if v >= MAN:
        return f"{sign}{v / MAN:,.0f}만"
    return f"{sign}{v:,}" + ("원" if unit else "")


def num(value: float | int, digits: int = 0) -> str:
    """천 단위 콤마."""
    if digits:
        return f"{value:,.{digits}f}"
    return f"{int(round(value)):,}"


def pct(value: float, digits: int = 1) -> str:
    """이미 퍼센트 값인 숫자에 % 를 붙입니다 (12.3 -> 12.3%)."""
    return f"{value:,.{digits}f}%"


def signed_pct(value: float, digits: int = 1) -> str:
    """증감률. 부호를 항상 붙이되, 반올림해서 0 이면 부호를 뗍니다(-0.0% 방지)."""
    if round(value, digits) == 0:
        return f"{0:.{digits}f}%"
    return f"{value:+,.{digits}f}%"


def multiple(value: float, digits: int = 2) -> str:
    """ROAS 처럼 배수로 읽는 값."""
    return f"{value:,.{digits}f}x"


def roas_pct(value: float) -> str:
    """네이버·구글 리포트가 쓰는 % 표기의 ROAS (2.5x -> 250%)."""
    return f"{value * 100:,.0f}%"
