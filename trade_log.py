"""
거래/실행 로그 기록.
- logs/trades.csv: 모든 매수/매도 1줄씩
- logs/run_YYYYMMDD.log: 실행별 상세 로그
"""

from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

TRADES_CSV = LOGS_DIR / "trades.csv"
TRADES_HEADER = [
    "timestamp", "ticker", "action", "qty", "price",
    "order_id", "strategy", "reason", "mode",
]


def get_run_log_path() -> Path:
    today = datetime.now().strftime("%Y%m%d")
    return LOGS_DIR / ("run_" + today + ".log")


def log_line(msg: str) -> None:
    """콘솔과 일별 로그 파일에 동시 기록."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = "[" + timestamp + "] " + msg
    print(line)
    with open(get_run_log_path(), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_trade(ticker: str, action: str, qty: float, price: float,
              order_id: str, strategy: str, reason: str, mode: str) -> None:
    """trades.csv 한 줄 추가."""
    is_new = not TRADES_CSV.exists()
    with open(TRADES_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(TRADES_HEADER)
        w.writerow([
            datetime.now().isoformat(timespec="seconds"),
            ticker, action, qty, round(price, 4),
            order_id, strategy, reason, mode,
        ])
