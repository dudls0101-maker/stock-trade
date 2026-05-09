"""
Alpaca 페이퍼 실시간 자동매매 루프.

매 실행마다:
  1) 5종목의 최근 시세 받아옴 (Alpaca 일봉)
  2) 종목별 전략으로 시그널(보유/관망) 계산
  3) 현재 Alpaca 포지션과 비교
  4) 차이를 메우는 매수/매도 주문 (시장가)
  5) 손절가 도달 종목은 강제 청산
  6) 모든 동작을 logs/ 에 기록

사용법:
    python live_trader.py            # dry-run (주문 안 함, 시뮬레이션)
    python live_trader.py --live     # 실제 페이퍼 주문 실행

매일 미국 장 마감 30분 전 즈음에 한 번 실행하면 됨.
(예: 한국 시간 새벽 5시 30분 / 서머타임 시 4시 30분)
"""

from __future__ import annotations
import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from live_config import get_configs, MAX_POSITION_PCT, MIN_ORDER_USD
from strategies import MACrossStrategy
from trade_log import log_line, log_trade
from notifier import notify_signal_changes, notify_error

LOOKBACK_DAYS = 400  # SMA(50/200) 같은 긴 MA를 위해 충분히 가져옴

# 이벤트 수집용 (텔레그램 알림에 사용)
EVENTS_NEW_ENTRY: list[dict] = []
EVENTS_EXIT: list[dict] = []
EVENTS_STOP: list[dict] = []
EVENTS_ERROR: list[str] = []


def load_env() -> tuple[str, str]:
    """
    환경변수 로딩.
    - 로컬 PC: .env 파일에서 읽음
    - GitHub Actions: secrets로 이미 환경변수 설정됨 → .env 없어도 OK
    """
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            # 이미 환경변수에 값이 있으면 (GitHub Actions secrets) 덮어쓰지 않음
            if not os.environ.get(k.strip()):
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

    key = os.environ.get("ALPACA_API_KEY_ID", "")
    sec = os.environ.get("ALPACA_SECRET_KEY", "")
    if not key or not sec:
        log_line("[ERROR] API 키 누락 (.env 또는 환경변수에서 ALPACA_API_KEY_ID, ALPACA_SECRET_KEY 설정 필요)")
        sys.exit(1)
    return key, sec


def fetch_bars(data_client, ticker: str, lookback_days: int) -> pd.DataFrame:
    """Alpaca 시세 클라이언트로 일봉 데이터 가져오기 (무료 IEX 피드 사용)."""
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import DataFeed
    from datetime import timezone
    # 무료 계정은 SIP 데이터 조회 불가 -> IEX 피드 사용 + 최근 데이터는 16분+ 지연 필요
    end = datetime.now(timezone.utc) - timedelta(minutes=20)
    start = end - timedelta(days=int(lookback_days * 1.7))
    req = StockBarsRequest(
        symbol_or_symbols=[ticker],
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )
    bars = data_client.get_stock_bars(req).df
    if bars.empty:
        return pd.DataFrame()
    # 멀티인덱스 (symbol, timestamp) 풀기
    if isinstance(bars.index, pd.MultiIndex):
        bars = bars.xs(ticker, level=0)
    bars = bars.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    })
    bars.index = pd.to_datetime(bars.index).tz_localize(None)
    bars.index.name = "Date"
    return bars[["Open", "High", "Low", "Close", "Volume"]]


def get_current_positions(trade_client) -> dict[str, dict]:
    """현재 보유 포지션 -> {ticker: {qty, avg_entry_price, market_value}}"""
    positions = trade_client.get_all_positions()
    result = {}
    for p in positions:
        result[p.symbol] = {
            "qty": float(p.qty),
            "avg_entry_price": float(p.avg_entry_price),
            "market_value": float(p.market_value),
        }
    return result


def compute_target_signal(df: pd.DataFrame, cfg) -> int:
    """오늘 진입 여부: 1 (보유 권장) 또는 0 (관망 권장)."""
    if len(df) < cfg.slow + 5:
        log_line("  [WARN] " + cfg.ticker + ": 데이터 부족 (" + str(len(df)) + "봉)")
        return 0
    strat = MACrossStrategy(
        fast=cfg.fast, slow=cfg.slow, ma_type=cfg.ma_type,
        rsi_max=cfg.rsi_max,
    )
    pos_series = strat.generate_signals(df)
    return int(pos_series.iloc[-1])  # 가장 최근 시그널


def place_market_order(trade_client, ticker: str, qty: float, side: str,
                       reason: str, strategy_name: str, mode: str,
                       est_price: float):
    """시장가 매수/매도 주문 (notional 대신 fractional qty 사용)."""
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    side_enum = OrderSide.BUY if side == "buy" else OrderSide.SELL
    qty_rounded = round(qty, 6)  # Alpaca fractional shares 지원

    if mode == "dry":
        order_id = "DRYRUN"
        log_line("  [DRY] " + side.upper() + " " + ticker + " qty=" + str(qty_rounded)
                 + " est=$" + "{:.2f}".format(est_price * qty_rounded)
                 + " reason=" + reason)
    else:
        req = MarketOrderRequest(
            symbol=ticker,
            qty=qty_rounded,
            side=side_enum,
            time_in_force=TimeInForce.DAY,
        )
        order = trade_client.submit_order(req)
        order_id = str(order.id)
        log_line("  [LIVE] " + side.upper() + " " + ticker + " qty=" + str(qty_rounded)
                 + " est=$" + "{:.2f}".format(est_price * qty_rounded)
                 + " order_id=" + order_id + " reason=" + reason)

    log_trade(ticker, side, qty_rounded, est_price, order_id, strategy_name, reason, mode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true",
                        help="실제 주문 실행 (지정 안 하면 dry-run)")
    parser.add_argument("--system", default="all", choices=["C", "A", "B", "all"],
                        help="C=인덱스 코어(SPY/QQQ), A=대형주, B=중소형주, all=전부 (기본)")
    args = parser.parse_args()
    mode = "live" if args.live else "dry"
    configs = get_configs(args.system)

    log_line("=" * 60)
    log_line("Live Trader 시작 (mode=" + mode + ", system=" + args.system
             + ", " + str(len(configs)) + " 종목)")

    load_env()
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient

    trade_client = TradingClient(
        api_key=os.environ["ALPACA_API_KEY_ID"],
        secret_key=os.environ["ALPACA_SECRET_KEY"],
        paper=True,
    )
    data_client = StockHistoricalDataClient(
        api_key=os.environ["ALPACA_API_KEY_ID"],
        secret_key=os.environ["ALPACA_SECRET_KEY"],
    )

    account = trade_client.get_account()
    portfolio_value = float(account.portfolio_value)
    cash = float(account.cash)
    log_line("계정: 자본 $" + "{:,.2f}".format(portfolio_value)
             + " / 현금 $" + "{:,.2f}".format(cash))

    clock = trade_client.get_clock()
    log_line("시장: " + ("OPEN" if clock.is_open else "CLOSED")
             + " (다음 개장 " + str(clock.next_open) + ")")

    if not clock.is_open and mode == "live":
        log_line("[INFO] 장 마감 중. 주문은 다음 개장 시 처리됩니다.")

    positions = get_current_positions(trade_client)
    log_line("현재 보유 종목: " + (str(list(positions.keys())) if positions else "없음"))

    log_line("\n--- 종목별 결정 ---")
    for cfg in configs:
        log_line("\n[" + cfg.ticker + " | system " + cfg.system + "] strategy=" + cfg.ma_type.upper()
                 + "(" + str(cfg.fast) + "/" + str(cfg.slow) + ")"
                 + (" RSI<" + str(int(cfg.rsi_max)) if cfg.rsi_max else "")
                 + " stop=-" + str(int(cfg.stop_loss_pct * 100)) + "%")

        try:
            df = fetch_bars(data_client, cfg.ticker, LOOKBACK_DAYS)
        except Exception as e:
            log_line("  [ERROR] 시세 조회 실패: " + str(e))
            EVENTS_ERROR.append(cfg.ticker + " price fetch failed: " + str(e)[:60])
            continue

        if df.empty:
            log_line("  [WARN] 시세 데이터 없음")
            EVENTS_ERROR.append(cfg.ticker + " no price data")
            continue

        last_price = float(df["Close"].iloc[-1])
        log_line("  최근 종가: $" + "{:.2f}".format(last_price)
                 + " (" + str(df.index[-1].date()) + ")")

        target_signal = compute_target_signal(df, cfg)
        log_line("  시그널: " + ("BUY/HOLD" if target_signal == 1 else "EXIT/CASH"))

        current = positions.get(cfg.ticker)
        currently_holding = current is not None and current["qty"] > 0

        # 손절 체크 (보유 중일 때만)
        if currently_holding:
            entry = current["avg_entry_price"]
            stop_price = entry * (1.0 - cfg.stop_loss_pct)
            log_line("  보유: qty=" + str(current["qty"])
                     + " avg=$" + "{:.2f}".format(entry)
                     + " stop=$" + "{:.2f}".format(stop_price))
            if last_price <= stop_price:
                log_line("  >> 손절 발동! 청산 진행")
                place_market_order(
                    trade_client, cfg.ticker, current["qty"], "sell",
                    reason="stop_loss", strategy_name=cfg.ma_type.upper()
                    + "(" + str(cfg.fast) + "/" + str(cfg.slow) + ")",
                    mode=mode, est_price=last_price,
                )
                EVENTS_STOP.append({
                    "ticker": cfg.ticker, "price": last_price,
                    "system": cfg.system, "stop_pct": int(cfg.stop_loss_pct * 100),
                })
                continue

        # 시그널 vs 현재 포지션 reconcile
        if target_signal == 1 and not currently_holding:
            # 신규 매수
            target_value = portfolio_value * cfg.weight
            target_value = min(target_value, portfolio_value * MAX_POSITION_PCT)
            qty = target_value / last_price
            if target_value < MIN_ORDER_USD:
                log_line("  [SKIP] 주문 금액 너무 작음 ($" + str(round(target_value, 2)) + ")")
                continue
            log_line("  >> 신규 진입")
            place_market_order(
                trade_client, cfg.ticker, qty, "buy",
                reason="signal_entry", strategy_name=cfg.ma_type.upper()
                + "(" + str(cfg.fast) + "/" + str(cfg.slow) + ")",
                mode=mode, est_price=last_price,
            )
            EVENTS_NEW_ENTRY.append({
                "ticker": cfg.ticker, "price": last_price, "system": cfg.system,
            })
        elif target_signal == 0 and currently_holding:
            # 청산
            log_line("  >> 시그널 종료, 청산")
            place_market_order(
                trade_client, cfg.ticker, current["qty"], "sell",
                reason="signal_exit", strategy_name=cfg.ma_type.upper()
                + "(" + str(cfg.fast) + "/" + str(cfg.slow) + ")",
                mode=mode, est_price=last_price,
            )
            EVENTS_EXIT.append({
                "ticker": cfg.ticker, "price": last_price, "system": cfg.system,
            })
        elif target_signal == 1 and currently_holding:
            log_line("  유지 (보유 계속)")
        else:
            log_line("  유지 (관망)")

    log_line("\n" + "=" * 60)
    log_line("완료. mode=" + mode)

    # --- 텔레그램 알림 발송 (시그널 변경 / 사고 있을 때만) ---
    date_str = datetime.now().strftime("%Y-%m-%d (%a)")
    total_buy = len(EVENTS_NEW_ENTRY)
    total_exit_count = len(EVENTS_EXIT) + len(EVENTS_STOP)

    if EVENTS_NEW_ENTRY or EVENTS_EXIT or EVENTS_STOP:
        sent = notify_signal_changes(
            date_str,
            new_entries=EVENTS_NEW_ENTRY,
            exits=EVENTS_EXIT,
            stops=EVENTS_STOP,
            total_buy=total_buy,
            total_exit=total_exit_count,
        )
        log_line("[Telegram] signal alert " + ("sent" if sent else "skipped (no token)"))

    if EVENTS_ERROR:
        sent = notify_error(date_str, EVENTS_ERROR)
        log_line("[Telegram] error alert " + ("sent" if sent else "skipped (no token)"))

    if not (EVENTS_NEW_ENTRY or EVENTS_EXIT or EVENTS_STOP or EVENTS_ERROR):
        log_line("[Telegram] no changes, no alert sent")


if __name__ == "__main__":
    main()
