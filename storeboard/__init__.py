"""storeboard — 직영 매장 마케팅 성과 + 매출 분석 슬라이드 생성기.

매출표·네이버 유입 리포트·광고 리포트 캡처를 넣으면
보고용 16:9 슬라이드(PNG/PDF/HTML)로 만들어 줍니다.

    from storeboard.pipeline import build
    result = build("report.json")
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
