# 미국주식 자동매매 프로젝트

빅테크 5종목(AAPL, MSFT, GOOGL, NVDA, META)에 대해 이동평균 크로스(추세추종) 전략을 백테스트하고, 향후 Alpaca 페이퍼 트레이딩으로 자동매매까지 확장할 수 있는 프로젝트입니다.

## 1단계: Windows에서 환경 설정

### Python 설치

1. https://www.python.org/downloads/windows/ 에서 **Python 3.11 이상** 다운로드.
2. 설치 시 **반드시 "Add Python to PATH" 체크박스** 켜고 설치.
3. 설치 끝나면 PowerShell이나 명령 프롬프트(cmd)를 열고 확인:

```
python --version
```

`Python 3.11.x` 같은 결과가 나오면 OK.

### 프로젝트 폴더로 이동

```
cd C:\Users\indong\CascadeProjects\auto_trader
```

### 의존 패키지 설치

```
pip install -r requirements.txt
```

설치되는 것: `yfinance`(시세 데이터), `pandas`/`numpy`(데이터 처리), `matplotlib`(차트), `tabulate`(표 출력).

## 2단계: 백테스트 실행

```
python run_backtest.py
```

- 처음 실행하면 yfinance로 5종목 일봉 데이터를 다운로드 (몇 초 ~ 1분).
- 다운로드한 데이터는 `data/` 폴더에 CSV로 캐시됨 → 다음 실행은 즉시.
- 6개 MA 조합 × 5종목 = **30회 백테스트**가 자동 수행됨.
- 결과:
  - 콘솔에 종목별 최적 전략 표 출력
  - `reports/backtest_report.md` 마크다운 리포트
  - `reports/backtest_summary.csv` 엑셀에서 열 수 있는 CSV

## 3단계: 결과 해석

### 핵심 지표

| 지표 | 의미 | 좋은 값 |
| --- | --- | --- |
| `total_return_%` | 전체 누적 수익률 | 매수후보유보다 높으면 가치 있음 |
| `annual_return_%` | 연환산 수익률 (CAGR) | 연 10% 이상이면 양호 |
| `max_drawdown_%` | 자본 최대 낙폭 | 절대값이 작을수록 좋음 (-30% 이내 권장) |
| `sharpe` | 위험조정 수익. (수익률/변동성) | 1.0+ 양호, 2.0+ 우수 |
| `profit_factor` | 총이익/총손실 | 1.5+ 견고 |
| `win_rate_%` | 승률 | 추세추종은 30~50%로 낮은 게 정상 |
| `trades` | 총 거래 수 | 너무 적으면(< 20) 통계 신뢰도 낮음 |

### 주의사항 — 백테스트의 함정

1. **과최적화 (overfitting)**: 한 종목에 너무 잘 맞는 파라미터는 미래엔 안 통할 가능성이 큼. 여러 종목에서 두루 좋은 파라미터를 선호.
2. **백테스트 ≠ 실전**: 슬리피지, 부분체결, 거래정지, 시장 충격 등이 실제로는 추가 비용. 본 백테스터는 5bps(0.05%) 슬리피지만 가정.
3. **승률에 속지 말 것**: 승률 80%여도 한 번 잃을 때 크게 잃으면 손실. 항상 `profit_factor`와 `sharpe`를 같이 보기.
4. **매수후보유와 비교**: 빅테크는 장기 우상향이라 매수후보유를 이기기 정말 어려움. 자동매매의 진짜 가치는 "수익을 더 내는 것"보다 "낙폭(MDD)을 줄이는 것"인 경우가 많음.

## 4단계: 검증 (선택)

코드가 제대로 동작하는지 합성 데이터로 자체 점검:

```
python test_smoke.py
```

전부 PASS가 떠야 정상.

## 다음 단계 (이후 추가 예정)

- [ ] **Alpaca 페이퍼 계정 연동**: 실시간 시세 + 모의 주문
- [ ] **실시간 트레이딩 루프**: 장 중 일정 시간마다 시그널 체크 → 주문
- [ ] **상시 가동 호스팅**: Oracle Cloud Free Tier에 배포
- [ ] **알림 (Telegram/이메일)**: 매수·매도 발생 시 알림
- [ ] **워크포워드 분석**: 과거 일부로 파라미터 찾고, 다른 구간에서 검증

## 폴더 구조

```
auto_trader/
├── README.md              # 이 문서
├── requirements.txt       # 의존 패키지
├── data_loader.py         # yfinance 데이터 로딩 + 캐싱
├── strategies.py          # MA 크로스 전략
├── backtester.py          # 백테스트 엔진
├── reporter.py            # 리포트 생성
├── run_backtest.py        # 메인 실행 스크립트
├── test_smoke.py          # 합성 데이터로 로직 검증
├── data/                  # 시세 캐시 (자동 생성)
└── reports/               # 백테스트 리포트 (자동 생성)
```

## 문제 해결

### `pip` 명령이 인식되지 않는다고 나올 때

Python 설치 시 "Add to PATH" 체크를 안 한 경우입니다. Python을 제거하고 재설치하면서 체크박스를 꼭 키세요. 또는 다음 명령으로 시도:

```
python -m pip install -r requirements.txt
```

### yfinance에서 빈 데이터프레임이 온다고 할 때

- 인터넷 방화벽 또는 회사 프록시 문제. 가정 네트워크에서 시도.
- 종목 코드 확인: `GOOGL` (구글 클래스 A), `META` (페이스북) 정확한지.
- yfinance가 가끔 야후 측 변경으로 일시 장애. 잠시 후 재시도.

### 한글이 깨질 때

PowerShell에서 다음 명령으로 UTF-8 모드 실행:

```
chcp 65001
python run_backtest.py
```
