"""Report generation: filter best strategies by min trade count for statistical reliability."""

from __future__ import annotations
from pathlib import Path
import pandas as pd
from tabulate import tabulate
from backtester import BacktestResult

REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

DEFAULT_MIN_TRADES = 20


def build_summary_table(results: list[BacktestResult]) -> pd.DataFrame:
    return pd.DataFrame([r.summary_row() for r in results])


def best_per_ticker(summary, score_col="sharpe", min_trades=DEFAULT_MIN_TRADES):
    """Pick best strategy per ticker, requiring at least min_trades for reliability."""
    filtered = summary[summary["trades"] >= min_trades].copy()
    if filtered.empty:
        return filtered
    idx = filtered.groupby("ticker")[score_col].idxmax()
    return filtered.loc[idx].sort_values(score_col, ascending=False).reset_index(drop=True)


def print_table(df, title=""):
    if title:
        print("\n=== " + title + " ===")
    print(tabulate(df, headers="keys", tablefmt="github", showindex=False))


def save_summary(summary, best, benchmarks, min_trades=DEFAULT_MIN_TRADES):
    out_path = REPORTS_DIR / "backtest_report.md"
    bench_df = pd.DataFrame(benchmarks).T.reset_index().rename(columns={"index": "ticker"})

    parts = []
    parts.append("# Backtest Report\n")
    parts.append("## 1. Best Strategy per Ticker (Sharpe, min " + str(min_trades) + " trades)\n")
    if best.empty:
        parts.append("_No strategy met the minimum trade count threshold._\n")
    else:
        parts.append(tabulate(best, headers="keys", tablefmt="github", showindex=False))
    parts.append("\n\n## 2. Buy & Hold Benchmark\n")
    parts.append(tabulate(bench_df, headers="keys", tablefmt="github", showindex=False))
    parts.append("\n\n## 3. All Strategy Results (no filter)\n")
    parts.append(tabulate(summary, headers="keys", tablefmt="github", showindex=False))
    parts.append("\n\n## Metric Notes\n")
    parts.append("- total_return_%: cumulative return over the full period\n")
    parts.append("- annual_return_%: CAGR\n")
    parts.append("- max_drawdown_%: largest peak-to-trough decline (smaller absolute is better)\n")
    parts.append("- sharpe: risk-adjusted return; >1 good, >2 excellent\n")
    parts.append("- profit_factor: gross profit / gross loss; >1.5 robust\n")
    parts.append("- win_rate_%: percent of winning trades; trend-following is OK with 30-50%\n")
    parts.append("- trades: total number of round-trip trades\n")
    parts.append("- stop_outs: trades closed by stop-loss\n")
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path


def save_summary_csv(summary):
    out_path = REPORTS_DIR / "backtest_summary.csv"
    summary.to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path
