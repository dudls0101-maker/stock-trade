"""Strategy module: MA Cross + EMA + optional RSI filter. 1-bar shift to prevent look-ahead."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
import numpy as np
import pandas as pd

MAType = Literal["sma", "ema"]


def _moving_average(series: pd.Series, period: int, kind: MAType) -> pd.Series:
    if kind == "sma":
        return series.rolling(period, min_periods=period).mean()
    elif kind == "ema":
        return series.ewm(span=period, adjust=False, min_periods=period).mean()
    raise ValueError("unknown ma_type: " + str(kind))


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI; handles flat-loss edge case (returns 100 when no losses)."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    out = 100.0 - (100.0 / (1.0 + rs))
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
    return out


@dataclass
class MACrossStrategy:
    fast: int
    slow: int
    ma_type: MAType = "sma"
    rsi_max: float | None = None
    rsi_period: int = 14

    def __post_init__(self) -> None:
        if self.fast >= self.slow:
            raise ValueError("fast must be less than slow")

    @property
    def name(self) -> str:
        suffix = ""
        if self.rsi_max is not None:
            suffix = "+RSI<" + str(int(self.rsi_max))
        return self.ma_type.upper() + "(" + str(self.fast) + "/" + str(self.slow) + ")" + suffix

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["Close"]
        fast_ma = _moving_average(close, self.fast, self.ma_type)
        slow_ma = _moving_average(close, self.slow, self.ma_type)
        in_uptrend = fast_ma > slow_ma

        if self.rsi_max is None:
            position = in_uptrend.astype(float)
        else:
            r = rsi(close, self.rsi_period)
            position = pd.Series(0.0, index=close.index)
            holding = False
            in_uptrend_arr = in_uptrend.values
            r_arr = r.values
            for i in range(len(close)):
                trend_up = bool(in_uptrend_arr[i])
                rsi_val = r_arr[i] if not np.isnan(r_arr[i]) else 50.0
                if not trend_up:
                    holding = False
                else:
                    if not holding and rsi_val < self.rsi_max:
                        holding = True
                position.iloc[i] = 1.0 if holding else 0.0

        position = position.shift(1).fillna(0.0)
        position.name = "position"
        return position


def standard_grid() -> list[MACrossStrategy]:
    """SMA/EMA x 6 MA combos x with/without RSI filter = 24 strategies."""
    combos = [(5, 20), (10, 30), (10, 50), (20, 50), (20, 100), (50, 200)]
    out: list[MACrossStrategy] = []
    for f, s in combos:
        for ma in ("sma", "ema"):
            out.append(MACrossStrategy(fast=f, slow=s, ma_type=ma))
            out.append(MACrossStrategy(fast=f, slow=s, ma_type=ma, rsi_max=70))
    return out
