# bulldozerpark — 매장 마케팅 도구 모음

| 도구 | 무엇을 | 문서 |
|---|---|---|
| **cardnews** | 주제 한 줄 → 인스타 카드뉴스 이미지 + 캡션 | 아래 |
| **storeboard** | 매출·유입·광고 리포트 캡처 → 보고용 16:9 슬라이드(PDF·PNG) | [docs/storeboard.md](docs/storeboard.md) |

```bash
cardnews "성수동 파스타 맛집 TOP 5" --handle @bulldozer.eats
storeboard report shots/ --period 2026-W33 --brand 불도저파크
```

---

# storeboard — 매장 마케팅·매출 리포트 슬라이드

주간/월간/작년 **매출표 · 네이버 플레이스 유입 리포트 · 광고 리포트(네이버·구글·메타…)
캡처를 넣으면** 보고 자리에 그대로 띄우는 슬라이드로 정리해 줍니다.

```bash
storeboard sample                                            # 키 없이 모양부터 보기
storeboard report shots/ --period 2026-W33 --brand 불도저파크   # 캡처 → 슬라이드
```

```
out/직영점-주간-마케팅매출-리포트-2026-W33/
├── slides/01_cover.png … 09_appendix.png   ← PPT·메신저에 그대로
├── deck.pdf        ← 보고용 (슬라이드당 한 쪽)
├── deck.html       ← 브라우저 미리보기
├── report.json     ← 판독된 원본. 고쳐서 다시 빌드
└── summary.txt     ← 단톡방에 붙이는 텍스트 요약
```

**슬라이드 구성** — 한 장 = 한 질문. 데이터가 없는 장은 만들지 않습니다.

| # | 슬라이드 | 답하는 질문 |
|---|---|---|
| 1 | 표지 | 누구의 · 언제 실적인가 |
| 2 | 한눈에 | 이번 기간 결론은 (매출 · 전년비 · 객단가 · 광고비율 · ROAS · 목표 달성률) |
| 3 | 매출 추이 | 흐름이 좋아지고 있나 (전년 동기 겹쳐보기) |
| 4 | 매장별 | 어디가 끌고 어디가 빠졌나 |
| 5 | 채널 효율 | 광고비를 어디에 썼고 무엇이 남았나 |
| 6 | 광고 퍼널 | 어느 단계에서 새고 있나 |
| 7 | 네이버 유입 | 찾아온 사람이 행동으로 이어졌나 |
| 8 | 인사이트·액션 | 다음 기간에 무엇을 할 것인가 (담당·기한 포함) |
| 9 | 부록 | 원본 캡처 · 읽지 못한 항목 |

세 가지 원칙을 지킵니다.

- **없는 숫자는 지어내지 않습니다.** 캡처에서 못 읽은 항목은 비워 두고
  "확인 필요"로 부록에 올립니다. 비교 기간 자료가 없으면 0%가 아니라 `—` 입니다.
- **원본은 하나입니다.** `report.json` 만 고치면 모든 슬라이드의 숫자가 함께 바뀝니다
  (지표는 저장하지 않고 빌드할 때마다 다시 계산합니다).
- **API 키가 없어도 끝까지 돕니다.** 캡처 판독만 키가 필요하고,
  손으로 채운 데이터(`storeboard template`)면 코멘트까지 규칙 기반으로 만듭니다.

자세한 사용법 · 지표 정의 · `report.json` 스펙 → **[docs/storeboard.md](docs/storeboard.md)**

---

# cardnews — F&B 인스타그램 카드뉴스 생성기

주제 한 줄을 주면 **문안 · 사진 · 업로드용 카드 이미지 · 인스타 캡션**까지 한 번에 만듭니다.
맛집·카페·식당·주류 콘텐츠에 맞춰 카피 규칙과 디자인 테마를 미리 잡아뒀습니다.

```bash
cardnews "성수동 파스타 맛집 TOP 5" --handle @bulldozer.eats
cardnews "Manila K-BBQ best 5" --lang en+tl --theme neon   # 영어 + 따갈로그 병기
```

```
out/성수동-파스타-BEST-5/
├── 01_cover.png   02_intro.png   03_place.png  …  08_outro.png   ← 그대로 업로드
├── cards.json     ← 문구를 고쳐서 다시 렌더링할 수 있는 원본
├── caption.txt    ← 인스타 본문 + 해시태그
├── credits.txt    ← 사진 출처 (스톡 사진을 썼을 때)
└── preview.html   ← 브라우저로 한눈에 확인
```

---

## 빠른 시작

```bash
git clone https://github.com/tomato11144-lgtm/bulldozerpark.git
cd bulldozerpark

pip install -r requirements.txt
playwright install chromium        # 렌더링용 브라우저 (한 번만)
python scripts/fetch_fonts.py      # 한글 폰트 내려받기 (한 번만)

python -m cardnews doctor          # 환경 점검
python -m cardnews "성수동 파스타 맛집 TOP 5"

python -m storeboard doctor        # 리포트 도구 환경 점검
python -m storeboard sample        # 데모 덱 한 부 만들어 보기
```

`pip install -e .` 를 하면 `python -m cardnews` / `python -m storeboard` 대신
`cardnews`, `storeboard` 명령으로 쓸 수 있습니다.

### API 키 (선택)

`.env.example` 를 `.env` 로 복사해서 채웁니다.

| 키 | 없으면 | 있으면 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 규칙 기반 템플릿으로 뼈대를 만듭니다 (storeboard 는 캡처 판독만 불가) | Claude 가 문안을 쓰고, storeboard 는 캡처를 읽습니다 |
| `UNSPLASH_ACCESS_KEY` 또는 `PEXELS_API_KEY` | 테마 색 그라데이션 배경 | 주제에 맞는 무료 스톡 사진 |

키가 하나도 없어도 끝까지 동작합니다. 키 없이 먼저 돌려보고 결과 형태를 확인한 뒤
채워 넣는 순서를 권합니다.

---

## 사실 관계 — 먼저 읽어주세요

맛집 콘텐츠에서 가장 위험한 건 **없는 가게, 틀린 가격, 지난 영업시간**입니다.
그래서 이 도구는 기본적으로 **가게 이름·주소·가격·영업시간을 지어내지 않습니다.**

네 가지 모드가 있습니다 (`--mode`).

| 모드 | 언제 | 동작 |
|---|---|---|
| `placeholder` **(기본)** | 검증 자료가 아직 없을 때 | 가게 정보 자리에 `{{가게명1}}` 같은 자리표시자를 넣습니다. 카피·팁·구성은 완성해 둡니다 |
| `facts` | 확인된 자료가 있을 때 | `--facts` 로 준 내용**만** 사실로 씁니다. 거기 없는 숫자는 카드에 나오지 않습니다 |
| `guide` | 특정 가게를 안 다룰 때 | 고르는 기준·메뉴 조합·방문 팁으로 채웁니다. 상호가 등장하지 않습니다 |
| `unverified` | 초안만 급할 때 | 널리 알려진 예시를 쓰되 각주에 "정보 확인 필요" 를 붙입니다 |

`--facts` 는 파일 경로나 문자열 둘 다 받습니다. 형식은 자유지만, 아래처럼 쓰면
**API 키가 없어도** 오프라인 생성기가 매장 카드를 그대로 채웁니다.

```markdown
## 1. Sam Stew, Vertis North
- Google rating: 4.9 (5,000 reviews)
- Location: Vertis North, Quezon City
- Price: ₱500-1,000
- Signature: <<대표메뉴>>          ← << >> 는 '아직 안 채움'으로 보고 카드에서 뺍니다
- One-line verdict: Highest rated on this list
```

`## 번호. 상호` 아래에 `- 키: 값` 을 적으면 됩니다. 키는 한글·영어 둘 다 됩니다
(`위치`/`Location`, `가격대`/`Price`, `대표메뉴`/`Signature`, `한줄평`/`One-line verdict`).
매장은 **평점 내림차순**으로 정렬되고, 파일에 없는 정보는 카드에 등장하지 않습니다.
`## Notes for the writer` 같은 섹션은 매장으로 세지 않습니다.

```bash
cardnews "우리 가게 겨울 신메뉴 3종" \
  --facts data/menu.md \
  --images-dir photos/ \
  --handle @bulldozer.eats
```

---

## 실전 워크플로우

가장 자주 쓰게 될 흐름입니다.

```bash
# 1. 뼈대부터 뽑습니다 (자리표시자가 들어갑니다)
cardnews "연남동 혼밥 맛집 5곳" --handle @bulldozer.eats

# 2. preview.html 을 열어 구성이 마음에 드는지 봅니다
open out/연남동-맛집-BEST-5/preview.html

# 3. cards.json 의 {{가게명1}} 같은 자리를 실제 정보로 채웁니다
$EDITOR out/연남동-맛집-BEST-5/cards.json

# 4. 고친 내용으로 다시 렌더링합니다 (테마도 바꿔볼 수 있습니다)
cardnews rebuild out/연남동-맛집-BEST-5/cards.json --theme mint
```

`cards.json` 은 카드 순서를 바꾸거나, 카드를 지우거나, 사진 경로(`image`)를
직접 지정하는 데도 씁니다.

---

## 언어

`--lang` 으로 문안 언어를 바꿉니다. 카드 라벨(위치/대표메뉴/가격대), 하단 UI 문구,
해시태그, 서체가 언어에 맞춰 함께 바뀝니다.

| 값 | 결과 | 언제 |
|---|---|---|
| `ko` (기본) | 한국어 | 국내 계정 |
| `en` | 영어 | 영어권 계정 |
| `tl` | 따갈로그 | 필리핀 현지 계정 |
| `taglish` | 영어·따갈로그 자연 혼용 | 마닐라 소셜에서 가장 자연스러운 톤 |
| `en+tl` | 두 줄 병기 | 영어를 주 문구, 따갈로그를 보조 줄로 |

```bash
cardnews "Manila K-BBQ best 5" --lang en+tl --theme neon --handle @your.account
cardnews "Best unli samgyup in BGC" --lang taglish --theme pop
```

`en+tl` 은 카드마다 영어 문구 아래에 강조색 따갈로그 한 줄이 붙습니다. 직역이 아니라
같은 내용을 현지 톤으로 다시 쓴 문장입니다. `cardnews langs` 로 목록을 볼 수 있습니다.

서체는 언어에 따라 자동으로 갈아끼웁니다 — 한글은 Black Han Sans·Jua 계열,
라틴 문자는 Anton·Archivo Black 계열이라 따갈로그의 `ñ`, `á` 까지 깨지지 않습니다.

```bash
python scripts/fetch_fonts.py --script latin    # 영어·따갈로그용만
python scripts/fetch_fonts.py --script hangul   # 한글용만
```

## 테마

`cardnews themes` 로 확인할 수 있습니다. 기본값 `--theme auto` 는 주제 키워드를 보고 고릅니다.

| 이름 | 분위기 | 어울리는 주제 |
|---|---|---|
| `warm` | 따뜻한 우드 크림 | 한식·백반·국밥·베이커리·동네 맛집 |
| `neon` | 어두운 네온 | 야식·포차·술집·심야식당 |
| `mint` | 상큼한 민트 | 브런치·디저트·샐러드·비건 |
| `mono` | 검정 + 골드 세리프 | 파인다이닝·오마카세·기념일 |
| `retro` | 뉴트로 종이 질감 | 노포·시장·분식·중식 |
| `pop` | 강한 원색 | TOP N 랭킹·신상 오픈·이벤트 |

---

## 자주 쓰는 옵션

```
cardnews "<주제>" [옵션]

  -n, --cards N        카드 장수 (3~12, 기본 7)
      --theme NAME     테마 (기본 auto)
      --ratio 4:5      4:5(기본) | 1:1 | 9:16
      --handle @name   카드 하단에 들어갈 계정명
      --lang CODE      ko(기본) | en | tl | taglish | en+tl
      --facts PATH     검증된 가게·메뉴 정보 (파일 또는 문자열)
      --mode MODE      placeholder | facts | guide | unverified
      --images-dir DIR 내 사진 폴더 (결과 품질 차이가 가장 큽니다)
      --images SOURCE  auto | local | unsplash | pexels | gradient | none
      --scale 2        2배 해상도로 출력 (2160×2700)
      --renderer NAME  auto | chromium | pillow
      --offline        Claude 를 부르지 않고 템플릿 생성기만 사용
  -o, --out DIR        결과 폴더 지정
```

부가 명령: `cardnews themes`, `cardnews langs`, `cardnews doctor`,
`cardnews rebuild <cards.json>`

`rebuild` 는 `--lang` 도 받습니다. 한국어로 뽑은 세트를 그대로 영어판으로 다시
렌더링할 수 있습니다 (문구는 `cards.json` 에서 직접 고쳐야 합니다).

---

## 실제 매장 데이터 가져오기 (Google Places)

구글 평점 순으로 매장을 뽑아 `--facts` 파일을 만듭니다. 상호·평점·리뷰 수·주소·
영업시간·가격대만 가져옵니다 — 전부 Places API 가 공식으로 주는 사실 데이터입니다.

```bash
export GOOGLE_MAPS_API_KEY=...        # Places API (New) 활성화 필요
python scripts/fetch_places.py "unlimited korean bbq samgyupsal" \
    --area "Metro Manila" --region PH \
    --top 5 --min-reviews 200 --include "Wolhwa Galbi" \
    -o data/manila-kbbq.md

cardnews "Manila K-BBQ best 5" --lang en+tl --facts data/manila-kbbq.md
```

`--min-reviews` 는 리뷰 3개짜리 별 5.0 이 1위로 올라오는 걸 막습니다.
`--include` 로 지정한 상호는 순위와 무관하게 항상 포함됩니다.
메뉴·한줄평은 API 가 주지 않으므로 `<<...>>` 로 비워둡니다 — 직접 채우세요.

### 사진은 왜 안 가져오나

구글 이미지 검색 결과도, Places API 의 매장 사진도 **매장·사진가·리뷰어의
저작물**입니다. Google Maps Platform 약관은 지도 맥락 밖 재사용을 제한하고,
남의 사진에 우리 계정 로고를 얹어 올리면 저작권 문제와 계정 신고 위험이 있습니다.
그래서 이 도구는 사진을 자동으로 긁어오지 않습니다.

쓸 수 있는 사진은 네 가지입니다.

| 방법 | 명령 | 비고 |
|---|---|---|
| 직접 촬영 / 매장 제공 | `--images-dir photos/` | 가장 좋습니다 |
| 매장 공식 계정 사진 | `--images-dir photos/` | 사용 허락을 받고 저장해서 쓰세요 |
| 무료 스톡 (일반 K-BBQ 사진) | `--images unsplash` | 특정 매장 사진이 아닙니다 |
| 사진 없이 타이포만 | `--images none` | 상호가 크게 들어가 오히려 깔끔합니다 |

실제 상호가 적힌 카드에 스톡·그라데이션 이미지가 붙으면, 도구가 각주에
"Photo is illustrative, not the venue" 를 자동으로 넣습니다. 보는 사람이 그 매장의
사진으로 오해하지 않게 하기 위한 장치이니 지우지 마세요.

## 내 사진 쓰기

스톡 사진보다 실제 가게 사진이 반응이 훨씬 좋습니다.

```bash
cardnews "우리 가게 시그니처 메뉴" --images-dir photos/
```

파일명에 키워드를 넣으면 해당 카드에 우선 매칭됩니다
(`파스타_대표메뉴.jpg` → `파스타` 키워드 카드). 자세한 규칙은 `examples/images/README.md`.

---

## 파이썬에서 쓰기

```python
from cardnews import create

result = create(
    "성수동 파스타 맛집 TOP 5",
    handle="@bulldozer.eats",
    theme="warm",
    card_count=8,
    images_dir="photos/",
)

print(result.out_dir)          # 결과 폴더
print(result.news.full_caption())
for path in result.images:
    print(path)
```

카드 데이터를 직접 만들어 렌더링만 할 수도 있습니다.

```python
from cardnews import Card, CardNews, render

news = CardNews(
    topic="신메뉴 소개",
    title="겨울 신메뉴",
    theme="mono",
    handle="@bulldozer.eats",
    cards=[
        Card(kind="cover", badge="NEW", title="겨울 한정\n메뉴 3종"),
        Card(kind="menu", title="트러플 크림 파스타", subtitle="19,000원",
             body="생크림 대신 우유로 잡은 가벼운 소스에 트러플 오일을 마지막에 둘렀습니다.",
             image="photos/pasta.jpg"),
        Card(kind="outro", title="이번 주말에 만나요", subtitle="저장하기"),
    ],
)
render(news, "out/신메뉴")
```

---

## 렌더링 방식

기본은 **크로미움**입니다. HTML/CSS 로 카드를 그린 뒤 스크린샷을 찍습니다
(폰트 커닝, 그림자, 그라데이션이 정확합니다). 렌더링 중에만 로컬 HTTP 서버가 잠깐 뜨고
바깥으로 나가는 요청은 없습니다.

브라우저를 못 쓰는 환경에서는 **Pillow** 백엔드가 같은 테마 색·폰트로 대신 그립니다.
`--renderer pillow` 로 강제할 수 있고, `auto`(기본)에서는 크로미움 실패 시 자동 전환됩니다.

폰트는 전부 Google Fonts 의 자유 라이선스 한글 서체입니다.
`scripts/fetch_fonts.py` 로 `assets/fonts/` 에 받아두면 렌더링에 네트워크가 필요 없습니다
(폰트 파일은 재배포하지 않으려고 `.gitignore` 되어 있습니다).

---

## 문제 해결

| 증상 | 해결 |
|---|---|
| 글자가 네모(□)로 나옴 | `python scripts/fetch_fonts.py` |
| `크로미움을 찾지 못했습니다` | `playwright install chromium` 또는 `--renderer pillow` |
| 사진이 전부 그라데이션 | 스톡 API 키가 없습니다. `--images-dir` 로 내 사진을 주세요 |
| 문안이 밋밋함 | `ANTHROPIC_API_KEY` 를 설정하면 Claude 가 씁니다 |
| 가게 정보가 `{{...}}` 로 나옴 | 의도된 동작입니다. 위의 "사실 관계" 항목을 보세요 |
| 카드 수가 요청과 다름 | 주제에 `TOP 5` 처럼 개수가 있으면 그쪽을 우선합니다 |
| 따갈로그 글자가 깨짐 | `python scripts/fetch_fonts.py --script latin` |

---

## 프로젝트 구조

```
cardnews/
├── cli.py           명령줄 인터페이스
├── pipeline.py      주제 → 결과 폴더까지의 전체 흐름
├── content.py       Claude 로 문안 생성 (+ 실패 시 폴백)
├── offline.py       API 키 없이 도는 규칙 기반 생성기
├── prompts.py       F&B 카피 프롬프트 + 구조화 출력 스키마
├── themes.py        테마 6종 (색 · 폰트 · 장식, 한글/라틴 서체 짝)
├── locales.py       언어팩 (라벨 · UI 문구 · 해시태그 · 문자 계열)
├── offline_intl.py  영어/따갈로그/Taglish 규칙 기반 생성기
├── images.py        사진 소스 (로컬 / Unsplash / Pexels / 그라데이션)
├── models.py        Card, CardNews 데이터 모델
├── fonts.py         폰트 로딩
└── render/
    ├── html.py      카드 → HTML
    ├── chromium.py  HTML → PNG (기본)
    ├── pillow.py    PNG 직접 그리기 (대체)
    └── templates/   Jinja2 템플릿 + CSS

storeboard/          매출·마케팅 리포트 슬라이드 (docs/storeboard.md 참고)
├── cli.py           report / extract / build / sample / template / doctor
├── pipeline.py      report.json → 슬라이드 · PDF · 요약
├── extract.py       캡처 이미지 → 구조화 데이터 (Claude 비전)
├── periods.py       기간 표기 한 가지 규칙 (WoW / YoY 계산의 근거)
├── metrics.py       파생 지표 (증감 · ROAS · CPA · 행동 전환율)
├── insights.py      코멘트·액션 (규칙 기반 + Claude)
├── charts.py        인라인 SVG 차트
├── deck.py          지표 → 슬라이드 구성
└── render/          덱 → HTML → PNG · PDF
```

테스트: `python -m pytest tests -q`

---

## 라이선스

MIT. 생성된 카드 이미지의 저작권은 사용자에게 있습니다.
스톡 사진을 썼다면 `credits.txt` 의 출처 표기를 지켜주세요 (Unsplash 는 표기가 의무입니다).
