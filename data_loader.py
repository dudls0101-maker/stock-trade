"""
시세 데이터 로더
================
yfinance에서 미국 주식 일봉 데이터를 가져오고, 로컬 CSV로 캐싱합니다.
같은 데이터를 다시 받지 않아 빠르고, 인터넷 없이도 백테스트 가능.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

# 이 파일이 위치한 폴더 기준으로 data/ 디렉토리 사용
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def load_ohlcv(
    ticker: str,
    start: str = "2015-01-01",
    end: str | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """
    한 종목의 OHLCV 일봉 데이터를 가져옵니다.

    Parameters
    ----------
    ticker : str
        종목 코드 (예: "AAPL")
    start : str
        시작일 (YYYY-MM-DD)
    end : str | None
        종료일. None이면 오늘.
    refresh : bool
        True면 캐시 무시하고 새로 다운로드.

    Returns
    -------
    pd.DataFrame
        index: 날짜, columns: Open, High, Low, Close, Volume
    """
    if end is None:
        end = datetime.utcnow().strftime("%Y-%m-%d")

    cache_file = DATA_DIR / f"{ticker}_{start}_{end}.csv"

    if cache_file.exists() and not refresh:
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        return df

    print(f"[{ticker}] yfinance에서 다운로드 중... ({start} ~ {end})")
    df = yf.download(
        ticker,
        start=start,
        end=end,
        progress=False,
        auto_adjust=True,  # 분할/배당 조정된 가격 사용
    )

    if df.empty:
        raise ValueError(f"{ticker} 데이터를 가져올 수 없습니다. 종목 코드를 확인하세요.")

    # yfinance가 가끔 멀티인덱스 컬럼을 반환하는 경우 평탄화
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 필요한 컬럼만
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index.name = "Date"

    df.to_csv(cache_file)
    print(f"[{ticker}] {len(df)}개 데이터 캐시 완료 -> {cache_file.name}")
    return df


def load_many(
    tickers: list[str],
    start: str = "2015-01-01",
    end: str | None = None,
    refresh: bool = False,
) -> dict[str, pd.DataFrame]:
    """여러 종목을 한 번에 로드하여 딕셔너리로 반환."""
    return {t: load_ohlcv(t, start=start, end=end, refresh=refresh) for t in tickers}


if __name__ == "__main__":
    # 단독 실행 시 빅테크 5종목 받아오기
    BIG_TECH = ["AAPL", "MSFT", "GOOGL", "NVDA", "META"]
    data = load_many(BIG_TECH, start="2018-01-01")
    for t, df in data.items():
        print(f"\n=== {t} ===")
        print(df.tail(3))
