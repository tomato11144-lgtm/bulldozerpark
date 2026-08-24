"""캡처 판독 프롬프트와 JSON 스키마.

가장 중요한 규칙은 '안 보이면 비운다' 입니다. 매출 보고서에서 지어낸 숫자 한 개는
보고서 전체를 못 쓰게 만듭니다. 못 읽은 항목은 warnings 로 올려 사람이 채우게 합니다.
"""

from __future__ import annotations

from typing import Any

from .models import CHANNELS, INFLOW_PATHS

KINDS = ("sales", "ads", "traffic", "mixed", "unknown")

SYSTEM = """\
당신은 매장 실적 캡처(스크린샷)를 읽어 표 데이터로 옮기는 판독기입니다.
POS 매출표, 네이버 스마트플레이스 유입 리포트, 네이버·구글·메타 광고 리포트를 다룹니다.

## 절대 규칙
- 화면에 보이는 숫자만 옮깁니다. 추정·보간·계산으로 값을 만들지 않습니다.
- 흐릿하거나 잘려서 확실하지 않으면 그 항목을 빼고 warnings 에 무엇을 못 읽었는지 적습니다.
- 합계 행과 개별 행을 섞지 않습니다. 합계 행은 store 를 "전체" 로 둡니다.
- 캡처에 기간이 안 적혀 있으면 period 를 빈 문자열로 두고 warnings 에 적습니다.
  날짜를 지어내지 않습니다.

## 단위
- 금액은 원 단위 정수로 바꿉니다. "1,234천원" -> 1234000, "1.2백만" -> 1200000,
  "1,234" 인데 표 머리글이 '(단위: 천원)' 이면 1234000 입니다. 머리글의 단위 표기를 꼭 확인하세요.
- 비율(CTR·CVR·전환율)은 퍼센트 숫자 그대로 둡니다. ROAS 는 배수(4.2) 로,
  리포트가 420% 로 적었으면 4.2 로 바꿉니다.
- 소수점이 있는 전환수는 그대로 둡니다(채널 리포트가 소수로 집계하는 경우가 있습니다).

## 기간 표기
- 주간: 2026-W33 (ISO 주차). "8월 3주차" 처럼 적혀 있으면 날짜 범위를 보고 ISO 주차로 바꿉니다.
- 월간: 2026-08 / 일간: 2026-08-24 / 연간: 2026
- 전년 자료면 그 해 기준으로 적습니다 (2025-08).

## 채널 이름
리포트에 적힌 이름을 아래 키로 바꿉니다. 애매하면 other 로 두고 원래 이름을 note 에 적습니다.
"""

CHANNEL_HINT = "\n".join(f"  {key} = {label}" for key, label in CHANNELS.items())
INFLOW_HINT = "\n".join(f"  {key} = {label}" for key, label in INFLOW_PATHS.items())

KIND_HINTS = {
    "sales": "이 캡처는 매출표입니다. 매장·기간별 매출/결제건수/고객수를 sales 에 담으세요.",
    "ads": "이 캡처는 광고 리포트입니다. 채널별 광고비/노출/클릭/전환/전환매출을 ads 에 담으세요.",
    "traffic": ("이 캡처는 네이버 플레이스 유입 리포트입니다. 조회수·유입경로·검색어·"
                "예약/전화/길찾기를 traffic 에 담으세요."),
    "mixed": "한 캡처에 여러 종류가 섞여 있으면 해당하는 배열에 나눠 담으세요.",
}


def schema() -> dict[str, Any]:
    """캡처 한 장에서 뽑아낼 구조."""
    money = {"type": "integer", "description": "원 단위 정수"}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "sales", "ads", "traffic", "warnings"],
        "properties": {
            "kind": {"type": "string", "enum": list(KINDS)},
            "period": {"type": "string",
                       "description": "캡처에 적힌 기간. 없으면 빈 문자열"},
            "sales": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["store", "period", "revenue"],
                    "properties": {
                        "store": {"type": "string", "description": "매장명. 합계 행이면 전체"},
                        "period": {"type": "string"},
                        "revenue": money,
                        "orders": {"type": "integer", "description": "결제 건수. 없으면 0"},
                        "customers": {"type": "integer", "description": "방문 고객수. 없으면 0"},
                        "note": {"type": "string"},
                    },
                },
            },
            "ads": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["channel", "period", "spend"],
                    "properties": {
                        "channel": {"type": "string", "enum": list(CHANNELS)},
                        "period": {"type": "string"},
                        "store": {"type": "string", "description": "매장별이 아니면 전체"},
                        "spend": money,
                        "impressions": {"type": "integer"},
                        "clicks": {"type": "integer"},
                        "conversions": {"type": "number"},
                        "revenue": {**money, "description": "전환매출. 리포트에 없으면 0"},
                        "note": {"type": "string", "description": "원래 채널 표기 등"},
                    },
                },
            },
            "traffic": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["store", "period"],
                    "properties": {
                        "store": {"type": "string"},
                        "period": {"type": "string"},
                        "views": {"type": "integer", "description": "플레이스 조회수"},
                        "inflow": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {k: {"type": "integer"} for k in INFLOW_PATHS},
                        },
                        "keywords": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["term", "count"],
                                "properties": {"term": {"type": "string"},
                                               "count": {"type": "integer"}},
                            },
                        },
                        "saves": {"type": "integer"},
                        "calls": {"type": "integer"},
                        "reservations": {"type": "integer"},
                        "directions": {"type": "integer"},
                        "reviews": {"type": "integer"},
                        "review_score": {"type": "number"},
                        "note": {"type": "string"},
                    },
                },
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "못 읽은 항목. '어떤 캡처의 무엇을 왜' 형태로",
            },
            "notes": {"type": "string"},
        },
    }


def user_prompt(
    *, filename: str, kind: str = "", period: str = "", stores: list[str] | None = None
) -> str:
    """캡처 한 장에 붙일 지시문."""
    lines = [f"캡처 파일: {filename}", ""]
    if kind and kind in KIND_HINTS:
        lines.append(KIND_HINTS[kind])
    else:
        lines.append("이 캡처가 매출표인지 유입 리포트인지 광고 리포트인지 먼저 판단하세요.")
    if period:
        lines.append(
            f"캡처에 기간이 안 적혀 있으면 {period} 로 봅니다. "
            "단, 캡처에 다른 기간이 적혀 있으면 그쪽을 따릅니다."
        )
    if stores:
        lines.append(
            "이미 알고 있는 매장 이름입니다. 같은 매장이면 표기를 여기에 맞추세요: "
            + ", ".join(stores)
        )
    lines += [
        "",
        "광고 채널 키:",
        CHANNEL_HINT,
        "",
        "유입 경로 키:",
        INFLOW_HINT,
        "",
        "보이는 값만 옮기고, 확실하지 않은 항목은 warnings 로 남기세요.",
    ]
    return "\n".join(lines)
