"""Backtester: bar-by-bar simulation with optional stop-loss."""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass
class BacktestResult:
    ticker: str
    strategy_name: str
    equity_curve: pd.Series
    trades: pd.DataFrame
    metrics: dict

    def summary_row(self) -> dict:
        m = self.metrics
        return {
            "ticker": self.ticker,
            "strategy": self.strategy_name,
            "total_return_%": round(m["total_return"] * 100, 2),
            "annual_return_%": round(m["annual_return"] * 100, 2),
            "max_drawdown_%": round(m["max_drawdown"] * 100, 2),
            "sharpe": round(float(m["sharpe"]), 2),
            "profit_factor": round(float(m["profit_factor"]), 2) if m["profit_factor"] != float("inf") else 999.0,
            "win_rate_%": round(m["win_rate"] * 100, 1),
            "trades": m["num_trades"],
            "stop_outs": m.get("num_stop_outs", 0),
        }


def run_backtest(df, position, ticker, strategy_name, slippage_bps=5.0, stop_loss_pct=None):
    """Simulate trading bar-by-bar. Position series should already be 1-bar shifted."""
    df = df.copy()
    position = position.reindex(df.index).fillna(0.0)
    slip = slippage_bps / 10000.0

    holding = False
    entry_price = None
    entry_date = None
    blocked = False  # block re-entry until signal drops to 0

    equity = 1.0
    equity_history = []
    trade_rows = []
    daily_ret = []
    num_stop_outs = 0

    closes = df["Close"].values
    opens = df["Open"].values
    lows = df["Low"].values
    dates = df.index
    pos_arr = position.values
    prev_close = None

    for i in range(len(df)):
        date = dates[i]
        sig = pos_arr[i]
        op = opens[i]
        cl = closes[i]
        lo = lows[i]
        day_ret = 0.0

        if holding:
            # stop-loss
            if stop_loss_pct is not None:
                stop_price = entry_price * (1.0 - stop_loss_pct)
                if lo <= stop_price:
                    exit_price = stop_price * (1.0 - slip)
                    if prev_close is not None:
                        day_ret = (exit_price / prev_close) - 1.0
                    trade_rows.append({
                        "entry_date": entry_date, "exit_date": date,
                        "entry_price": round(entry_price, 4), "exit_price": round(exit_price, 4),
                        "return_%": round((exit_price / entry_price - 1) * 100, 2),
                        "holding_days": (date - entry_date).days,
                        "exit_reason": "stop_loss",
                    })
                    holding = False
                    entry_price = entry_date = None
                    blocked = True
                    num_stop_outs += 1
                    equity *= (1.0 + day_ret)
                    daily_ret.append(day_ret)
                    equity_history.append(equity)
                    prev_close = cl
                    continue

            # signal exit
            if sig == 0.0:
                exit_price = cl * (1.0 - slip)
                if prev_close is not None:
                    day_ret = (cl / prev_close) - 1.0
                trade_rows.append({
                    "entry_date": entry_date, "exit_date": date,
                    "entry_price": round(entry_price, 4), "exit_price": round(exit_price, 4),
                    "return_%": round((exit_price / entry_price - 1) * 100, 2),
                    "holding_days": (date - entry_date).days,
                    "exit_reason": "signal",
                })
                holding = False
                entry_price = entry_date = None
                equity *= (1.0 + day_ret) * (1.0 - slip)
                daily_ret.append(day_ret - slip)
                equity_history.append(equity)
                prev_close = cl
                continue

            # hold
            if prev_close is not None:
                day_ret = (cl / prev_close) - 1.0
            equity *= (1.0 + day_ret)
            daily_ret.append(day_ret)
            equity_history.append(equity)
            prev_close = cl
            continue

        # not holding
        if blocked and sig == 0.0:
            blocked = False

        if sig == 1.0 and not blocked:
            entry_price = op * (1.0 + slip)
            entry_date = date
            holding = True
            day_ret = (cl / entry_price) - 1.0
            equity *= (1.0 + day_ret)
            daily_ret.append(day_ret)
            equity_history.append(equity)
            prev_close = cl
            continue

        # cash
        daily_ret.append(0.0)
        equity_history.append(equity)
        prev_close = cl

    # close out at end
    if holding:
        last_price = closes[-1] * (1.0 - slip)
        trade_rows.append({
            "entry_date": entry_date, "exit_date": dates[-1],
            "entry_price": round(entry_price, 4), "exit_price": round(last_price, 4),
            "return_%": round((last_price / entry_price - 1) * 100, 2),
            "holding_days": (dates[-1] - entry_date).days,
            "exit_reason": "end_of_data",
        })

    equity_curve = pd.Series(equity_history, index=dates, name="equity")
    strat_ret = pd.Series(daily_ret, index=dates, name="ret")
    trades = pd.DataFrame(trade_rows)
    metrics = _compute_metrics(strat_ret, equity_curve, trades, num_stop_outs)

    return BacktestResult(
        ticker=ticker, strategy_name=strategy_name,
        equity_curve=equity_curve, trades=trades, metrics=metrics,
    )


def _compute_metrics(strat_ret, equity, trades, num_stop_outs=0):
    if len(equity) == 0:
        return _empty_metrics()
    total_return = float(equity.iloc[-1] - 1.0)
    n_days = len(equity)
    n_years = n_days / TRADING_DAYS
    annual_return = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 and (1 + total_return) > 0 else 0.0
    daily_std = strat_ret.std()
    sharpe = (strat_ret.mean() / daily_std) * np.sqrt(TRADING_DAYS) if daily_std > 0 else 0.0
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_drawdown = float(drawdown.min())

    if len(trades) > 0:
        wins = trades[trades["return_%"] > 0]["return_%"]
        losses = trades[trades["return_%"] <= 0]["return_%"]
        win_rate = len(wins) / len(trades)
        gp = float(wins.sum()) if len(wins) > 0 else 0.0
        gl = abs(float(losses.sum())) if len(losses) > 0 else 0.0
        pf = gp / gl if gl > 0 else float("inf")
        nt = len(trades)
    else:
        win_rate = 0.0; pf = 0.0; nt = 0

    return {
        "total_return": total_return, "annual_return": annual_return,
        "max_drawdown": max_drawdown, "sharpe": sharpe,
        "profit_factor": pf, "win_rate": win_rate,
        "num_trades": nt, "num_stop_outs": num_stop_outs,
    }


def _empty_metrics():
    return {"total_return": 0.0, "annual_return": 0.0, "max_drawdown": 0.0,
            "sharpe": 0.0, "profit_factor": 0.0, "win_rate": 0.0,
            "num_trades": 0, "num_stop_outs": 0}


def buy_and_hold_benchmark(df):
    closes = df["Close"]
    total = float(closes.iloc[-1] / closes.iloc[0] - 1)
    n_years = len(closes) / TRADING_DAYS
    annual = (1 + total) ** (1 / n_years) - 1 if n_years > 0 else 0.0
    daily = closes.pct_change().fillna(0.0)
    sharpe = (daily.mean() / daily.std()) * np.sqrt(TRADING_DAYS) if daily.std() > 0 else 0.0
    eq = (1 + daily).cumprod()
    rmax = eq.cummax()
    mdd = float(((eq - rmax) / rmax).min())
    return {
        "total_return_%": round(total * 100, 2),
        "annual_return_%": round(annual * 100, 2),
        "max_drawdown_%": round(mdd * 100, 2),
        "sharpe": round(float(sharpe), 2),
    }
