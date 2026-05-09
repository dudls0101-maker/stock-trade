"""
워크포워드 분석 (Walk-Forward Analysis)
======================================
과거 데이터를 train/test로 분할:
  - Train 구간: 모든 전략을 백테스트, 종목별 최적 전략 선정
  - Test 구간: train에서 뽑힌 전략을 그대로 적용해 미래(에 해당하는 구간) 성과 측정

목적:
  과거 데이터 전체로 "최적"을 뽑으면 과최적화 위험. 일부 데이터(train)로 결정한 전략이
  나머지 데이터(test)에서도 통하면, 미래에도 통할 가능성이 더 높다.

판정:
  - in-sample sharpe >> out-of-sample sharpe -> 과최적화 의심
  - in/out 모두 양호 -> 견고
  - in/out 모두 부진 -> 전략 자체가 별로

사용법:
    python walk_forward.py
"""

from __future__ import annotations

import pandas as pd

from data_loader import load_many
from strategies import standard_grid
from backtester import run_backtest, buy_and_hold_benchmark
from reporter import build_summary_table, best_per_ticker, REPORTS_DIR
from tabulate import tabulate

TICKERS = ["AAPL", "MSFT", "GOOGL", "NVDA", "META"]
START_DATE = "2018-01-01"
END_DATE = None
TRAIN_FRACTION = 0.6  # train 60%, test 40%
STOP_LOSS_PCT: float | None = 0.07
MIN_TRADES_TRAIN = 12  # train 구간은 짧으므로 기준 약간 완화


def split_data(df: pd.DataFrame, train_frac: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = len(df)
    cut = int(n * train_frac)
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()


def backtest_grid(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """단일 구간에서 전략 그리드 전체 백테스트 후 summary 반환."""
    results = []
    for strat in standard_grid():
        pos = strat.generate_signals(df)
        res = run_backtest(
            df, pos, ticker, strat.name, stop_loss_pct=STOP_LOSS_PCT
        )
        results.append(res)
    return build_summary_table(results)


def main() -> None:
    print(f"\n[1/3] 데이터 로딩")
    data = load_many(TICKERS, start=START_DATE, end=END_DATE)

    print(f"\n[2/3] 종목별 워크포워드 분석 (train {int(TRAIN_FRACTION*100)}% / test {int((1-TRAIN_FRACTION)*100)}%)")
    rows = []
    for ticker in TICKERS:
        df = data[ticker]
        train_df, test_df = split_data(df, TRAIN_FRACTION)

        train_period = f"{train_df.index[0].date()} ~ {train_df.index[-1].date()}"
        test_period = f"{test_df.index[0].date()} ~ {test_df.index[-1].date()}"

        # train 구간에서 최적 전략 찾기
        train_summary = backtest_grid(train_df, ticker)
        train_best = best_per_ticker(
            train_summary, score_col="sharpe", min_trades=MIN_TRADES_TRAIN
        )
        if train_best.empty:
            print(f"  - {ticker}: train에서 최소 거래 만족 전략 없음. 스킵.")
            continue

        best_strategy_name = train_best.iloc[0]["strategy"]
        train_sharpe = train_best.iloc[0]["sharpe"]
        train_ret = train_best.iloc[0]["total_return_%"]
        train_mdd = train_best.iloc[0]["max_drawdown_%"]
        train_trades = train_best.iloc[0]["trades"]

        # 같은 전략을 test 구간에 적용
        test_full = backtest_grid(test_df, ticker)
        test_row = test_full[test_full["strategy"] == best_strategy_name]
        if test_row.empty:
            continue
        test_row = test_row.iloc[0]

        # test 구간 buy & hold 벤치마크
        bh_test = buy_and_hold_benchmark(test_df)

        rows.append({
            "ticker": ticker,
            "best_strategy": best_strategy_name,
            "train_period": train_period,
            "test_period": test_period,
            "in_sample_sharpe": train_sharpe,
            "out_of_sample_sharpe": test_row["sharpe"],
            "in_sample_return_%": train_ret,
            "out_of_sample_return_%": test_row["total_return_%"],
            "test_buyhold_return_%": bh_test["total_return_%"],
            "out_of_sample_mdd_%": test_row["max_drawdown_%"],
            "out_of_sample_trades": int(test_row["trades"]),
            "verdict": _verdict(train_sharpe, test_row["sharpe"]),
        })

        print(f"  - {ticker}: {best_strategy_name}  "
              f"IS샤프 {train_sharpe:.2f} -> OOS샤프 {test_row['sharpe']:.2f}  "
              f"({_verdict(train_sharpe, test_row['sharpe'])})")

    if not rows:
        print("\n분석 가능한 종목이 없습니다.")
        return

    result_df = pd.DataFrame(rows)

    print("\n=== 워크포워드 결과 ===")
    print(tabulate(result_df, headers="keys", tablefmt="github", showindex=False))

    out_path = REPORTS_DIR / "walk_forward_report.md"
    md = []
    md.append("# 워크포워드 분석 리포트\n")
    md.append(
        f"- Train: 데이터의 첫 {int(TRAIN_FRACTION*100)}% (전략 선정 구간, in-sample)\n"
        f"- Test: 마지막 {int((1-TRAIN_FRACTION)*100)}% (실전 시뮬레이션 구간, out-of-sample)\n\n"
        "Train에서 가장 좋았던 전략을 그대로 Test 구간에 적용해, 미래에도 통할지 검증.\n\n"
    )
    md.append(tabulate(result_df, headers="keys", tablefmt="github", showindex=False))
    md.append(
        "\n\n## 판정 가이드\n"
        "- **GOOD**: in-sample / out-of-sample 둘 다 양호 (Sharpe > 0.5).\n"
        "- **MIXED**: out-of-sample이 in-sample보다 크게 떨어짐 -> 과최적화 의심.\n"
        "- **POOR**: out-of-sample도 부진 -> 전략 자체가 종목과 안 맞음.\n"
        "\n## 해석 팁\n"
        "- out_of_sample 결과가 buy & hold보다 낫고, MDD가 작으면 실전 후보로 적합.\n"
        "- out_of_sample이 음수 수익이면 모의투자에서 진짜 검증 필요.\n"
    )
    out_path.write_text("\n".join(md), encoding="utf-8")
    print(f"\n[3/3] 리포트 저장: {out_path}\n")


def _verdict(is_sharpe: float, oos_sharpe: float) -> str:
    if is_sharpe > 0.5 and oos_sharpe > 0.5:
        return "GOOD"
    if is_sharpe > 0.5 and oos_sharpe < 0.2:
        return "MIXED (overfit?)"
    if oos_sharpe <= 0:
        return "POOR"
    return "MARGINAL"


if __name__ == "__main__":
    main()
