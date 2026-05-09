"""Smoke tests with synthetic data."""

from __future__ import annotations
import numpy as np
import pandas as pd

from strategies import MACrossStrategy, standard_grid, rsi
from backtester import run_backtest


def make_synthetic_price(n_days=1500, drift=0.0003, vol=0.018, seed=42):
    rng = np.random.default_rng(seed)
    rets = rng.normal(loc=drift, scale=vol, size=n_days)
    closes = 100.0 * np.exp(np.cumsum(rets))
    opens = closes * (1 + rng.normal(0, 0.002, n_days))
    highs = np.maximum(opens, closes) * (1 + np.abs(rng.normal(0, 0.005, n_days)))
    lows = np.minimum(opens, closes) * (1 - np.abs(rng.normal(0, 0.005, n_days)))
    vols = rng.integers(1_000_000, 10_000_000, n_days)
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=n_days, freq="B")
    return pd.DataFrame({"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": vols}, index=dates)


def assert_(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        raise AssertionError(msg)


def test_no_lookahead():
    df = make_synthetic_price(n_days=300)
    pos = MACrossStrategy(fast=5, slow=20).generate_signals(df)
    assert_(pos.iloc[:20].sum() == 0.0, "lookback period position is 0")


def test_zero_position_zero_return():
    df = make_synthetic_price(n_days=500)
    pos = pd.Series(0.0, index=df.index)
    res = run_backtest(df, pos, "T", "ALL_CASH")
    assert_(abs(res.metrics["total_return"]) < 1e-10, "zero pos -> zero ret")


def test_basic_run():
    df = make_synthetic_price(n_days=1500, drift=0.0006)
    s = MACrossStrategy(fast=20, slow=50)
    pos = s.generate_signals(df)
    res = run_backtest(df, pos, "T", s.name)
    print("    " + str(res.summary_row()))
    assert_(res.metrics["num_trades"] > 0, "trades happen")
    assert_(-1 <= res.metrics["max_drawdown"] <= 0, "MDD in [-1, 0]")


def test_stop_loss_fires():
    n = 400
    rng = np.random.default_rng(0)
    closes = np.concatenate([
        100 * (1 + 0.001) ** np.arange(200) + rng.normal(0, 0.5, 200),
        100 * (1 + 0.001) ** 200 * (1 - 0.005) ** np.arange(200) + rng.normal(0, 0.5, 200),
    ])
    df = pd.DataFrame({
        "Open": closes, "High": closes * 1.01, "Low": closes * 0.97, "Close": closes,
        "Volume": np.full(n, 1_000_000),
    }, index=pd.date_range(end=pd.Timestamp.today().normalize(), periods=n, freq="B"))

    s = MACrossStrategy(fast=10, slow=30)
    pos = s.generate_signals(df)
    no_stop = run_backtest(df, pos, "T", s.name, stop_loss_pct=None)
    with_stop = run_backtest(df, pos, "T", s.name, stop_loss_pct=0.02)
    print("    no stop:  trades={} stops={} ret={:.1f}%".format(
        no_stop.metrics["num_trades"], no_stop.metrics.get("num_stop_outs", 0),
        no_stop.metrics["total_return"] * 100))
    print("    -2% stop: trades={} stops={} ret={:.1f}%".format(
        with_stop.metrics["num_trades"], with_stop.metrics.get("num_stop_outs", 0),
        with_stop.metrics["total_return"] * 100))
    assert_(with_stop.metrics["num_stop_outs"] > 0, "tight stop triggers")


def test_rsi_filter_changes_behavior():
    df = make_synthetic_price(n_days=1500)
    pos1 = MACrossStrategy(fast=20, slow=50).generate_signals(df)
    pos2 = MACrossStrategy(fast=20, slow=50, rsi_max=60).generate_signals(df)
    diff = int((pos1 != pos2).sum())
    print("    RSI filter changed " + str(diff) + " signals")
    assert_(pos2.sum() <= pos1.sum(), "RSI filter holding days <= no filter")


def test_ema_runs():
    df = make_synthetic_price(n_days=600)
    s = MACrossStrategy(fast=10, slow=30, ma_type="ema")
    pos = s.generate_signals(df)
    res = run_backtest(df, pos, "T", s.name)
    assert_(res.metrics["num_trades"] >= 0, "EMA mode runs")
    assert_("EMA" in s.name, "name shows EMA: " + s.name)


def test_rsi_function():
    s = pd.Series(np.linspace(100, 200, 100))
    r = rsi(s, period=14)
    val = float(r.iloc[-1])
    assert_(val > 90, "monotone-up RSI > 90 (got " + str(round(val, 1)) + ")")


def test_grid_runs():
    df = make_synthetic_price(n_days=1500)
    grid = standard_grid()
    print("    grid size: " + str(len(grid)))
    for s in grid:
        pos = s.generate_signals(df)
        res = run_backtest(df, pos, "T", s.name, stop_loss_pct=0.07)
        sh = res.metrics["sharpe"]
        ok = isinstance(sh, float) or hasattr(sh, "__float__")
        assert_(ok, s.name + " sharpe computed")
    print("    all " + str(len(grid)) + " grid strategies ran")


def main():
    print("=" * 60)
    for fn in [test_no_lookahead, test_zero_position_zero_return, test_rsi_function,
               test_basic_run, test_ema_runs, test_rsi_filter_changes_behavior,
               test_stop_loss_fires, test_grid_runs]:
        print("\n" + fn.__name__)
        fn()
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
