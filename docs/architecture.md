# 구조 메모

유지보수할 때 참고할 내용입니다. 사용법은 [README](../README.md) 를 보세요.

## 데이터 흐름

```
주제 문자열
   │
   ▼
content.generate()            ── ANTHROPIC_API_KEY 있음 → Claude 구조화 출력
   │                          ── 없음/실패      → offline.build_offline()
   ▼
CardNews (models.py)          카드 리스트 + 캡션 + 해시태그
   │
   ▼
pipeline.attach_images()      카드마다 Card.image 채우기
   │                          로컬 폴더 → 스톡 API → 그라데이션 순
   ▼
pipeline.render()
   ├─ render/html.py          CardNews → HTML 문서 (+ 폰트/이미지 URL 라우팅 표)
   │     └─ render/chromium.py  임시 HTTP 서버 + 크로미움 스크린샷 → PNG
   └─ render/pillow.py        브라우저 없이 PNG 직접 그리기
   │
   ▼
pipeline.write_sidecars()     cards.json / caption.txt / credits.txt / preview.html
```

## 설계상 정해둔 것

**문안 생성은 항상 결과를 냅니다.** API 키가 없어도, 호출이 실패해도
`offline.py` 가 같은 모양의 `CardNews` 를 만듭니다. 파이프라인 뒷단은
문안이 어디서 왔는지 몰라도 됩니다 (`CardNews.source` 로 구분만 가능).

**사실은 지어내지 않습니다.** 프롬프트의 모드 규칙(`prompts.MODE_RULES`)이
가게 이름·가격·영업시간 생성을 막습니다. 검증 자료는 `--facts` 로만 들어옵니다.
이 규칙을 완화하려면 `unverified` 모드를 쓰되 각주 표기가 함께 따라갑니다.

**디자인은 CSS 한 곳에만 있습니다.** 테마를 추가할 때 건드릴 파일은
`themes.py` 하나입니다. HTML 렌더러는 테마 값을 CSS 변수로 받고,
Pillow 렌더러는 같은 값을 직접 읽습니다.

**렌더링 중 외부 네트워크를 쓰지 않습니다.** 폰트와 사진은 로컬 파일이고,
크로미움에는 임시 HTTP 서버(127.0.0.1, 임의 포트)로만 노출합니다.
`file://` 로 열면 크로미움이 폰트를 CORS 로 막고, base64 로 심으면
문서가 수십 MB 가 되기 때문입니다.

## 카드 종류를 추가하려면

1. `models.CARD_KINDS` 에 이름 추가
2. `render/templates/card.html.j2` 에 분기 추가
3. `render/pillow.py` 의 `render_card` 에 분기 추가 (없으면 기본 레이아웃으로 그려집니다)
4. `prompts.KIND_GUIDE` 에 어떤 필드를 채워야 하는지 한 줄 추가
5. `prompts.CARD_SCHEMA` 의 `kind` enum 에 추가

## 테마를 추가하려면

`themes.THEMES` 에 항목 하나를 더합니다. 새 폰트를 쓴다면
`FONT_WEIGHTS` 에 패밀리와 두께를 등록한 뒤 `python scripts/fetch_fonts.py` 를 다시 실행합니다.
Google Fonts 에 있는 한글 서체여야 합니다 (오프라인 렌더링과 Pillow 백엔드가 TTF 를 요구합니다).

## 테스트

- `test_models.py` — 직렬화, 슬러그, meta 정렬
- `test_themes.py` — 색 유효성, 테마 자동 선택
- `test_offline.py` — 주제 파싱(지역/음식/개수), 카드 구성 규칙
- `test_content.py` — Claude 요청 모양과 응답 파싱 (가짜 클라이언트, 실제 호출 없음)
- `test_render.py` — HTML 생성, 이스케이프, 이미지 라우팅, 두 렌더러, rebuild

크로미움이 없는 환경에서는 해당 테스트만 skip 됩니다.
