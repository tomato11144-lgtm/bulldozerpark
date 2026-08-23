# cardnews — F&B 인스타그램 카드뉴스 생성기

주제 한 줄을 주면 **문안 · 사진 · 업로드용 카드 이미지 · 인스타 캡션**까지 한 번에 만듭니다.
맛집·카페·식당·주류 콘텐츠에 맞춰 카피 규칙과 디자인 테마를 미리 잡아뒀습니다.

```bash
cardnews "성수동 파스타 맛집 TOP 5" --handle @bulldozer.eats
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
```

`pip install -e .` 를 하면 `python -m cardnews` 대신 `cardnews` 명령으로 쓸 수 있습니다.

### API 키 (선택)

`.env.example` 를 `.env` 로 복사해서 채웁니다.

| 키 | 없으면 | 있으면 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 규칙 기반 템플릿으로 뼈대를 만듭니다 | Claude 가 주제에 맞는 문안을 씁니다 |
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

`--facts` 는 파일 경로나 문자열 둘 다 받습니다. 형식은 자유입니다
(`examples/facts-sample.md` 참고).

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
      --facts PATH     검증된 가게·메뉴 정보 (파일 또는 문자열)
      --mode MODE      placeholder | facts | guide | unverified
      --images-dir DIR 내 사진 폴더 (결과 품질 차이가 가장 큽니다)
      --images SOURCE  auto | local | unsplash | pexels | gradient | none
      --scale 2        2배 해상도로 출력 (2160×2700)
      --renderer NAME  auto | chromium | pillow
      --offline        Claude 를 부르지 않고 템플릿 생성기만 사용
  -o, --out DIR        결과 폴더 지정
```

부가 명령: `cardnews themes`, `cardnews doctor`, `cardnews rebuild <cards.json>`

---

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

---

## 프로젝트 구조

```
cardnews/
├── cli.py           명령줄 인터페이스
├── pipeline.py      주제 → 결과 폴더까지의 전체 흐름
├── content.py       Claude 로 문안 생성 (+ 실패 시 폴백)
├── offline.py       API 키 없이 도는 규칙 기반 생성기
├── prompts.py       F&B 카피 프롬프트 + 구조화 출력 스키마
├── themes.py        테마 6종 (색 · 폰트 · 장식)
├── images.py        사진 소스 (로컬 / Unsplash / Pexels / 그라데이션)
├── models.py        Card, CardNews 데이터 모델
├── fonts.py         폰트 로딩
└── render/
    ├── html.py      카드 → HTML
    ├── chromium.py  HTML → PNG (기본)
    ├── pillow.py    PNG 직접 그리기 (대체)
    └── templates/   Jinja2 템플릿 + CSS
```

테스트: `python -m pytest tests -q`

---

## 라이선스

MIT. 생성된 카드 이미지의 저작권은 사용자에게 있습니다.
스톡 사진을 썼다면 `credits.txt` 의 출처 표기를 지켜주세요 (Unsplash 는 표기가 의무입니다).
