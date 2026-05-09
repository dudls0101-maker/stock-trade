"""
사용자 보유 종목 백테스트.
APP, AVGO, LAC, LLY, RDW, TEM, VST, TMDX
- 짧은 히스토리 종목은 자동으로 가능한 전략만 돌림
- 현재 시그널 (BUY/HOLD or EXIT/CASH) 표시
- reports/holdings_report.md 생성
"""

from __future__ import annotations
import pandas as pd
from pathlib import Path
from tabulate import tabulate

from data_loader import load_ohlcv
from strategies import standard_grid, MACrossStrategy
from backtester import run_backtest, buy_and_hold_benchmark
from reporter import REPORTS_DIR

HOLDINGS = ["APP", "AVGO", "LAC", "LLY", "RDW", "TEM", "VST", "TMDX"]
START_DATE = "2018-01-01"
STOP_LOSS_PCT = 0.10  # 보유 종목엔 좀 더 넓게 (-10%) — 변동성 큰 종목 포함
MIN_TRADES = 15  # 약간 완화 (짧은 히스토리 종목 위해)


def main():
    print("\n[1/4] 보유 종목 데이터 로딩")
    data = {}
    for ticker in HOLDINGS:
        try:
            df = load_ohlcv(ticker, start=START_DATE)
            data[ticker] = df
            print("  - " + ticker + ": " + str(len(df)) + " bars (" 
                  + str(df.index[0].date()) + " ~ " + str(df.index[-1].date()) + ")")
        except Exception as e:
            print("  - " + ticker + ": FAILED (" + str(e) + ")")

    if not data:
        print("데이터 로딩 실패")
        return

    print("\n[2/4] 백테스트 실행")
    grid = standard_grid()
    all_results = []
    for ticker, df in data.items():
        # 데이터가 너무 짧으면 슬로우 MA 200 같은 건 못 돌림
        valid_strategies = [s for s in grid if len(df) > s.slow + 30]
        skipped = len(grid) - len(valid_strategies)
        if skipped > 0:
            print("  - " + ticker + ": " + str(len(valid_strategies)) + "/" 
                  + str(len(grid)) + " 전략 (히스토리 부족으로 " + str(skipped) + "개 스킵)")
        for strat in valid_strategies:
            pos = strat.generate_signals(df)
            res = run_backtest(df, pos, ticker, strat.name, stop_loss_pct=STOP_LOSS_PCT)
            all_results.append(res)

    print("\n[3/4] 종목별 최적 전략 + 현재 시그널")
    summary_rows = [r.summary_row() for r in all_results]
    summary_df = pd.DataFrame(summary_rows)

    # 종목별 최적 (Sharpe 기준, 최소 거래 필터)
    filtered = summary_df[summary_df["trades"] >= MIN_TRADES]
    if filtered.empty:
        print("  WARNING: 최소 거래 만족 전략 없음. MIN_TRADES 낮춰보세요.")
        best_df = pd.DataFrame()
    else:
        idx = filtered.groupby("ticker")["sharpe"].idxmax()
        best_df = filtered.loc[idx].sort_values("sharpe", ascending=False).reset_index(drop=True)
        print(tabulate(best_df, headers="keys", tablefmt="github", showindex=False))

    # 매수후보유 비교
    print("\n  매수후보유 벤치마크:")
    bh = {t: buy_and_hold_benchmark(d) for t, d in data.items()}
    bh_df = pd.DataFrame(bh).T.reset_index().rename(columns={"index": "ticker"})
    print(tabulate(bh_df, headers="keys", tablefmt="github", showindex=False))

    # 현재 시그널 — 종목별 최적 전략으로 오늘 BUY/SELL 판단
    print("\n  현재 시그널 (각 종목의 최적 전략 기준):")
    current_signals = []
    if not best_df.empty:
        for _, row in best_df.iterrows():
            ticker = row["ticker"]
            strat_name = row["strategy"]
            # strategy_name 파싱: "EMA(10/30)+RSI<70" 같은 형태
            ma_type = "ema" if "EMA" in strat_name else "sma"
            paren = strat_name[strat_name.index("(") + 1:strat_name.index(")")]
            fast, slow = [int(x) for x in paren.split("/")]
            rsi_max = None
            if "RSI<" in strat_name:
                rsi_max = int(strat_name.split("RSI<")[1])
            strat = MACrossStrategy(fast=fast, slow=slow, ma_type=ma_type, rsi_max=rsi_max)
            pos = strat.generate_signals(data[ticker])
            sig = int(pos.iloc[-1])
            last_price = float(data[ticker]["Close"].iloc[-1])
            current_signals.append({
                "ticker": ticker,
                "strategy": strat_name,
                "current_price": round(last_price, 2),
                "signal": "BUY/HOLD" if sig == 1 else "EXIT/CASH",
            })
        sig_df = pd.DataFrame(current_signals)
        print(tabulate(sig_df, headers="keys", tablefmt="github", showindex=False))

    print("\n[4/4] 리포트 저장")
    out = REPORTS_DIR / "holdings_report.md"
    parts = ["# 보유 종목 백테스트 리포트\n"]
    parts.append("## 1. 종목별 최적 전략 (Sharpe, 최소 " + str(MIN_TRADES) + " 거래, 손절 -" + str(int(STOP_LOSS_PCT*100)) + "%)\n")
    if best_df.empty:
        parts.append("_조건 만족 전략 없음._\n")
    else:
        parts.append(tabulate(best_df, headers="keys", tablefmt="github", showindex=False))
    parts.append("\n\n## 2. 매수후보유 벤치마크\n")
    parts.append(tabulate(bh_df, headers="keys", tablefmt="github", showindex=False))
    if current_signals:
        parts.append("\n\n## 3. 현재 시그널\n")
        parts.append(tabulate(sig_df, headers="keys", tablefmt="github", showindex=False))
    parts.append("\n\n## 4. 전체 결과\n")
    parts.append(tabulate(summary_df, headers="keys", tablefmt="github", showindex=False))
    out.write_text("\n".join(parts), encoding="utf-8")
    print("  - 리포트: " + str(out))
    print("\n완료.\n")


if __name__ == "__main__":
    main()
