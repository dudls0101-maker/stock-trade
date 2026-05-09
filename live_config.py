"""
종목별 운영 전략 설정 (시스템 A 대형주 + 시스템 B 중소형주).

자본 분배: A 70% / B 30%
A: 9종목 동일 비중 = 약 7.78% / 종목  (손절 -7%)
B: 3종목 동일 비중 = 10% / 종목       (손절 -10%, 변동성 큼)
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TickerConfig:
    ticker: str
    fast: int
    slow: int
    ma_type: str  # "sma" or "ema"
    rsi_max: float | None
    weight: float
    stop_loss_pct: float
    system: str  # "A" or "B"


# --- 시스템 A: 대형주 (워크포워드 검증 + 보유 종목 분석으로 선정) ---
# 자본 70% 분배, 9종목 동일비중 ≈ 7.78%
A_WEIGHT_EACH = 0.70 / 9  # ≈ 0.0778

SYSTEM_A: list[TickerConfig] = [
    TickerConfig("AAPL",  fast=5,  slow=20,  ma_type="ema", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("MSFT",  fast=10, slow=30,  ma_type="ema", rsi_max=70,   weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("GOOGL", fast=10, slow=50,  ma_type="ema", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("NVDA",  fast=10, slow=30,  ma_type="sma", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("META",  fast=10, slow=50,  ma_type="ema", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    # 보유 종목 추가 (백테스트 Sharpe 0.86+)
    TickerConfig("APP",   fast=10, slow=30,  ma_type="ema", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("LLY",   fast=10, slow=50,  ma_type="sma", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("AVGO",  fast=10, slow=30,  ma_type="ema", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
    TickerConfig("VST",   fast=20, slow=50,  ma_type="sma", rsi_max=None, weight=A_WEIGHT_EACH, stop_loss_pct=0.07, system="A"),
]

# --- 시스템 B: 중소형주 (보유 종목 중 변동성 큰 그룹) ---
# 자본 30% 분배, 3종목 동일비중 = 10%
B_WEIGHT_EACH = 0.30 / 3  # = 0.10

SYSTEM_B: list[TickerConfig] = [
    TickerConfig("RDW",   fast=20, slow=50,  ma_type="sma", rsi_max=None, weight=B_WEIGHT_EACH, stop_loss_pct=0.10, system="B"),
    TickerConfig("LAC",   fast=5,  slow=20,  ma_type="sma", rsi_max=None, weight=B_WEIGHT_EACH, stop_loss_pct=0.10, system="B"),
    TickerConfig("TMDX",  fast=20, slow=50,  ma_type="sma", rsi_max=None, weight=B_WEIGHT_EACH, stop_loss_pct=0.10, system="B"),
]

# 기본 = 둘 다
LIVE_CONFIG: list[TickerConfig] = SYSTEM_A + SYSTEM_B

# 안전장치
MAX_POSITION_PCT = 0.15  # 한 종목 최대 15%
MIN_ORDER_USD = 100.0


def get_configs(system: str = "all") -> list[TickerConfig]:
    """system='A' / 'B' / 'all' 로 필터링."""
    if system == "A":
        return SYSTEM_A
    if system == "B":
        return SYSTEM_B
    return LIVE_CONFIG
