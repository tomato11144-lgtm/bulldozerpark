# 폰트

이 폴더에는 렌더링에 쓸 한글 TTF 가 들어갑니다. **파일 자체는 저장소에 커밋하지 않습니다**
(재배포를 피하기 위해 `.gitignore` 처리되어 있습니다).

```bash
python scripts/fetch_fonts.py            # 전체 테마 폰트
python scripts/fetch_fonts.py --theme warm
```

내려받는 서체는 모두 Google Fonts 에 공개된 자유 라이선스(SIL OFL 등) 한글 서체입니다.

| 패밀리 | 쓰임 |
|---|---|
| Noto Sans KR | 본문 (거의 모든 테마) |
| Black Han Sans | `warm` · `neon` 제목 |
| Jua | `mint` 제목 |
| Nanum Myeongjo | `mono` 제목 |
| Do Hyeon · Gowun Dodum | `retro` |
| Gasoek One | `pop` 제목 |

폰트가 없어도 실행은 됩니다 — 크로미움 렌더러는 Google Fonts CDN 으로,
Pillow 렌더러는 시스템 한글 폰트로 대체합니다. 다만 결과가 달라지고
네트워크가 필요해지므로 미리 받아두는 쪽을 권합니다.
