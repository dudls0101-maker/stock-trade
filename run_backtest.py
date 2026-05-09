"""Main backtest runner: 24-strategy grid x 5 tickers, with optional stop-loss and min-trades filter."""

from __future__ import annotations
import pandas as pd
from data_loader import load_many
from strategies import standard_grid
from backtester import run_backtest, buy_and_hold_benchmark
from reporter import build_summary_table, best_per_ticker, print_table, save_summary, save_summary_csv

TICKERS = ["AAPL", "MSFT", "GOOGL", "NVDA", "META"]
START_DATE = "2018-01-01"
END_DATE = None
STOP_LOSS_PCT = 0.07
MIN_TRADES = 20


def main():
    print("\n[1/4] Loading data: " + str(TICKERS))
    data = load_many(TICKERS, start=START_DATE, end=END_DATE)

    strategies = standard_grid()
    n_combos = len(strategies) * len(TICKERS)
    sl_str = "-" + str(int(STOP_LOSS_PCT * 100)) + "%" if STOP_LOSS_PCT else "none"
    print("\n[2/4] Backtesting " + str(len(strategies)) + " strategies x " +
          str(len(TICKERS)) + " tickers = " + str(n_combos) + " runs (stop_loss " + sl_str + ")")

    results = []
    for ti, ticker in enumerate(TICKERS, 1):
        df = data[ticker]
        for strat in strategies:
            pos = strat.generate_signals(df)
            res = run_backtest(df, pos, ticker, strat.name, stop_loss_pct=STOP_LOSS_PCT)
            results.append(res)
        print("  - " + ticker + " done (" + str(ti) + "/" + str(len(TICKERS)) + ")")

    print("\n[3/4] Aggregating (min " + str(MIN_TRADES) + " trades for 'best')")
    summary = build_summary_table(results)
    best = best_per_ticker(summary, score_col="sharpe", min_trades=MIN_TRADES)
    benchmarks = {t: buy_and_hold_benchmark(data[t]) for t in TICKERS}

    if best.empty:
        print("  WARNING: no strategy met min trades. Lower MIN_TRADES.")
    else:
        print_table(best, "Best per ticker (Sharpe, min " + str(MIN_TRADES) + " trades)")

    bench_df = pd.DataFrame(benchmarks).T.reset_index().rename(columns={"index": "ticker"})
    print_table(bench_df, "Buy & Hold")

    print("\n[4/4] Saving reports...")
    md_path = save_summary(summary, best, benchmarks, min_trades=MIN_TRADES)
    csv_path = save_summary_csv(summary)
    print("  - " + str(md_path))
    print("  - " + str(csv_path))
    print("\nDone.\n")


if __name__ == "__main__":
    main()
