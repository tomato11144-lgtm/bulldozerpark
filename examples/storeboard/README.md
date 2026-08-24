# storeboard 예시

- `report-template.json` — `storeboard template` 이 만들어 주는 빈 리포트입니다.
  캡처 없이 손으로 채워 쓸 때의 출발점이고, 필드 이름과 기간 표기를 확인하는 용도로도 씁니다.

```bash
# 내 매장 이름으로 새로 만들기
storeboard template -o report.json --period 2026-W33 --stores 강남점,홍대점

# 채운 뒤 슬라이드로
storeboard build report.json
```

캡처에서 자동으로 채우려면 `storeboard report shots/ --period 2026-W33` 을 쓰세요.
자세한 내용은 [../../docs/storeboard.md](../../docs/storeboard.md).
