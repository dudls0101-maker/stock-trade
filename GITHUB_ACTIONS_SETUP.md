# GitHub Actions로 자동매매 셋업

이 가이드를 따라하면 PC를 끄고 자도 매일 자동으로 live_trader가 돌아갑니다.

## 0단계 — Git 설치 (이미 있으면 패스)

PowerShell에서 확인:
```
git --version
```

없으면 https://git-scm.com/download/win 에서 설치. 설치 시 기본값 OK.

## 1단계 — GitHub 계정 + Private Repo 생성

1. https://github.com 접속, 계정 없으면 가입
2. 우측 상단 `+` → **New repository**
3. 설정:
   - Repository name: `auto-trader` (원하는 이름)
   - **Private** 반드시 선택 (코드 노출 방지)
   - 나머지 빈칸으로 두고 **Create repository**

## 2단계 — Secrets 등록 (API 키 안전 저장)

1. 방금 만든 repo 페이지에서 **Settings** 탭
2. 좌측 메뉴: **Secrets and variables → Actions**
3. **New repository secret** 클릭, 두 개 등록:

   | Name | Value |
   |---|---|
   | `ALPACA_API_KEY_ID` | (PK로 시작하는 키 붙여넣기) |
   | `ALPACA_SECRET_KEY` | (Secret Key 붙여넣기) |

4. 저장 후엔 GitHub UI에서도 절대 볼 수 없음 (보안). 나중에 바꾸려면 새로 등록.

## 3단계 — 로컬 코드를 GitHub에 push

PowerShell에서:

```
cd C:\Users\indong\CascadeProjects\auto_trader
git init
git branch -M main
git add .
git commit -m "Initial auto trader"
git remote add origin https://github.com/<본인_GitHub_ID>/auto-trader.git
git push -u origin main
```

처음 push할 때 GitHub 로그인 창 뜨면 본인 계정으로 인증.

**주의**: `.gitignore`에 `.env`가 있어서 API 키 파일은 GitHub에 안 올라감. 안전.

## 4단계 — Actions 활성화 + 첫 실행 테스트

1. GitHub repo 페이지 → **Actions** 탭
2. 처음이면 "Workflows aren't being run on this forked repository" 같은 메시지 → **I understand my workflows, go ahead and enable them** 클릭
3. 좌측 목록에 **Daily Live Trade** 보임 → 클릭
4. 우측 **Run workflow** 버튼 클릭 (수동 트리거)
5. 약 30초~2분 기다리면 노란색 → 초록색 ✅로 바뀜

성공하면 셋업 완료. 매일 21:05 UTC (한국 시간 새벽 6:05)에 자동 실행됨.

## 5단계 — 결과 확인

**실시간 로그**:
- Actions 탭 → 가장 최근 run 클릭 → `trade` job 펼치기 → 각 step 로그 확인

**거래 로그 다운로드**:
- 같은 run 페이지 하단 **Artifacts** 섹션
- `trade-logs-XXXX` 클릭 → ZIP 파일 다운로드
- 안에 logs/ 폴더 있음 (run_YYYYMMDD.log, trades.csv)

**Alpaca 대시보드에서 직접 확인**:
- https://app.alpaca.markets/paper → Orders / Positions

## 스케줄 변경하려면

`.github/workflows/daily_trade.yml` 파일에서 `cron: "5 21 * * 1-5"` 부분 수정.
- 첫 숫자: 분 (0-59)
- 둘째 숫자: 시 (0-23, **UTC 기준**)
- 셋째: 일
- 넷째: 월
- 다섯째: 요일 (1-5 = 월~금)

UTC 시간 변환:
- 한국 시간 = UTC + 9
- 미국 동부 ET (서머타임 EDT) = UTC - 4
- 미국 동부 ET (표준 EST) = UTC - 5

미국 장 마감(4 PM ET) 직후가 좋음:
- EDT 시즌 (3월~11월): 20:05 UTC
- EST 시즌 (11월~3월): 21:05 UTC
- 둘 다 커버하려면 21:05 UTC가 무난 (현재 설정)

## 정지/일시중단

**일시 정지 (다음부턴 안 돌게)**:
- Actions 탭 → Daily Live Trade → 우측 ⋯ → **Disable workflow**

**완전 삭제**:
- `.github/workflows/daily_trade.yml` 파일 삭제 후 push

## 비용 / 한도

- Private repo: 월 2,000분 무료. 우리 작업 1회 ~2분 × 22 영업일 = ~45분/월. **한참 남음**.
- Public repo로 만들면 무제한 (단 코드는 공개되니 키 보안만 잘하면 OK)

## 코드 수정 후 자동 반영

전략 바꾸거나 종목 추가했을 때:
```
cd C:\Users\indong\CascadeProjects\auto_trader
git add .
git commit -m "전략 수정"
git push
```

다음 스케줄 실행부터 새 코드로 돌아감.

## 트러블슈팅

**Run failed (빨간 X)**:
- 해당 run 클릭 → 에러 메시지 확인
- 흔한 원인: API 키 오타, requirements.txt 누락 패키지

**시그널은 잘 나오는데 주문이 큐에 안 들어감**:
- Alpaca 대시보드에서 페이퍼 모드 활성 확인
- API 키가 페이퍼용인지 확인 (PK로 시작)

**한 번도 자동 실행이 안 됨**:
- GitHub Actions cron은 첫 등록 후 24시간까지 지연될 수 있음
- 수동 트리거 (Run workflow 버튼)로 일단 한 번 돌려보면 됨
