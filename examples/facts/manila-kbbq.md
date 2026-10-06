# Metro Manila — K-BBQ (작성 중인 초안)
#
# 이 파일은 --facts 로 넘기면 여기 적힌 내용만 사실로 사용됩니다.
#   cardnews "Manila K-BBQ best 5" --lang en+tl --facts examples/facts/manila-kbbq.md
#
# 지금 상태: 1번만 공개 자료로 확인했고, 2~5번은 비어 있습니다.
# 구글 평점 순 목록은 scripts/fetch_places.py 로 받아 채우세요:
#   export GOOGLE_MAPS_API_KEY=...
#   python scripts/fetch_places.py "unlimited korean bbq samgyupsal" \
#       --area "Metro Manila" --region PH --top 5 --min-reviews 200 \
#       --include "Wolhwa Galbi" -o examples/facts/manila-kbbq.md

## 1. Wolhwa Galbi Unlimited Premium Korean BBQ — Tomas Morato
- Address: 114 Scout Lozano St, Laging Handa, Quezon City 1103
- Phone: +63 927 994 5369
- Hours: Sun-Thu 11:00-02:00 / Fri-Sat 11:00-03:00
- Price: unlimited premium set ₱599 per head (solo diner surcharge ₱200)
- Signature: dry-aged samgyupsal, 9 selected cuts
- Note: Hi-Seoul certified brand; branches also at SM MAAX Pasay,
  GH O-Square2 San Juan, Ayala Fairview Terraces
- Source: Tripadvisor listing + Quezon City government opening announcement,
  checked 2026-08-24
- 확인 필요: 구글 평점 / 리뷰 수, 현재 가격(프로모션 종료 여부)

## 2. <<상호>>
- Google rating: <<평점>> (<<리뷰 수>> reviews)
- Address: <<주소>>
- Price: <<1인 가격>>
- Signature: <<대표메뉴>>
- One-line verdict: <<한줄평>>

## 3. <<상호>>
## 4. <<상호>>
## 5. <<상호>>

## Notes for the writer
- 여기 적히지 않은 가격·영업시간·메뉴는 카드에 등장하지 않습니다.
- 평점은 계속 바뀝니다. 카드에 숫자를 넣을 거면 "2026년 8월 기준"을 함께 적으세요.
- 사진은 이 파일로 들어오지 않습니다. --images-dir 로 직접 준비한 사진을 넘기세요.
