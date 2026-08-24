"""cardnews — F&B 인스타그램 카드뉴스 생성기.

주제 한 줄을 받아 문안을 쓰고, 사진을 붙이고, 업로드용 PNG 와 캡션까지 만듭니다.

    from cardnews import create
    result = create("성수동 파스타 맛집 TOP 5", handle="@bulldozer.eats")
    print(result.out_dir)
"""

from .models import Card, CardNews  # noqa: F401
from .pipeline import Result, create, rebuild, render  # noqa: F401
from .themes import THEMES, get_theme, suggest_theme  # noqa: F401

__version__ = "0.1.0"
__all__ = [
    "Card", "CardNews", "Result",
    "create", "rebuild", "render",
    "THEMES", "get_theme", "suggest_theme",
    "__version__",
]
