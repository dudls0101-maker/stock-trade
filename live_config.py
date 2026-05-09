"""
Trading config: System C (index core) + A (large cap) + B (small cap).

Capital allocation: C 50% / A 35% / B 15%

C: 2 tickers (SPY, QQQ) at 25% each   (stop -7%, index diversification)
A: 9 tickers equal-weight ~3.89% each (stop -7%, big tech bets)
B: 3 tickers equal-weight 5% each     (stop -10%, small cap volatility)
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TickerConfig:
    ticker: str
    fast: int
    slow: int
    ma_type: str
    rsi_max: float | None
    weight: float
    stop_loss_pct: float
    system: str


# System C: index core (50%, 2 tickers)
SYSTEM_C: list[TickerConfig] = [
    TickerConfig("SPY", fast=50, slow=200, ma_type="sma", rsi_max=None, weight=0.25, stop_loss_pct=0.07, system="C"),
    TickerConfig("QQQ", fast=20, slow=50,  ma_type="sma", rsi_max=None, weight=0.25, stop_loss_pct=0.07, system="C"),
]

# System A: big tech bets (35%, 9 tickers)
A_WEIGHT_EACH = 0.35 / 9

SYSTEM_A: list[TickerConfig] = [
    TickerConfig("AAPL",  fast=5,  slow=20, ma_type="ema", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("MSFT",  fast=10, slow=30, ma_type="ema", rsi_max=70,   weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("GOOGL", fast=10, slow=50, ma_type="ema", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("NVDA",  fast=10, slow=30, ma_type="sma", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("META",  fast=10, slow=50, ma_type="ema", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("APP",   fast=10, slow=30, ma_type="ema", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("LLY",   fast=10, slow=50, ma_type="sma", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("AVGO",  fast=10, slow=30, ma_type="ema", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("VST",   fast=20, slow=50, ma_type="sma", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
]

# System B: small cap (15%, 3 tickers)
B_WEIGHT_EACH = 0.15 / 3

SYSTEM_B: list[TickerConfig] = [
    TickerConfig("RDW",  fast=20, slow=50, ma_type="sma", rsi_max=None, weight=B_WEIGHT_EACH, stop_loss_pct=0.10, system="B"),
    TickerConfig("LAC",  fast=5,  slow=20, ma_type="sma", rsi_max=None, weight=B_WEIGHT_EACH, stop_loss_pct=0.10, system="B"),
    TickerConfig("TMDX", fast=20, slow=50, ma_type="sma", rsi_max=None, weight=B_WEIGHT_EACH, stop_loss_pct=0.10, system="B"),
]

LIVE_CONFIG: list[TickerConfig] = SYSTEM_C + SYSTEM_A + SYSTEM_B

MAX_POSITION_PCT = 0.30
MIN_ORDER_USD = 100.0


def get_configs(system: str = "all") -> list[TickerConfig]:
    if system == "C":
        return SYSTEM_C
    if system == "A":
        return SYSTEM_A
    if system == "B":
        return SYSTEM_B
    return LIVE_CONFIG
