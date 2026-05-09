"""
Auto Trader Dashboard (Streamlit).
실행: streamlit run dashboard.py
"""

from __future__ import annotations
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from live_config import get_configs, SYSTEM_A, SYSTEM_B, MAX_POSITION_PCT, MIN_ORDER_USD
from data_loader import load_ohlcv
from strategies import MACrossStrategy
from backtester import run_backtest, buy_and_hold_benchmark


# ==========================================================
# Setup
# ==========================================================
st.set_page_config(page_title="Auto Trader Dashboard", layout="wide")

ENV_FILE = ROOT / ".env"


def load_env():
    if not ENV_FILE.exists():
        return None, None
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")
    return os.environ.get("ALPACA_API_KEY_ID"), os.environ.get("ALPACA_SECRET_KEY")


@st.cache_data(ttl=300)  # 5분 캐시
def get_alpaca_account():
    key, sec = load_env()
    if not key or not sec:
        return None
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(api_key=key, secret_key=sec, paper=True)
        acc = client.get_account()
        clock = client.get_clock()
        positions = client.get_all_positions()
        return {
            "portfolio_value": float(acc.portfolio_value),
            "cash": float(acc.cash),
            "buying_power": float(acc.buying_power),
            "status": str(acc.status),
            "is_open": clock.is_open,
            "next_open": str(clock.next_open),
            "positions": [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "avg_entry": float(p.avg_entry_price),
                    "current_price": float(p.current_price),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl),
                    "unrealized_plpc": float(p.unrealized_plpc) * 100,
                }
                for p in positions
            ],
        }
    except Exception as e:
        return {"error": str(e)}


@st.cache_data(ttl=600)  # 10분 캐시 (yfinance)
def fetch_data(ticker: str, start="2018-01-01"):
    return load_ohlcv(ticker, start=start)


def compute_signal_and_equity(cfg):
    """주어진 cfg로 백테스트 + 현재 시그널 계산."""
    df = fetch_data(cfg.ticker)
    if len(df) < cfg.slow + 10:
        return None
    strat = MACrossStrategy(
        fast=cfg.fast, slow=cfg.slow, ma_type=cfg.ma_type, rsi_max=cfg.rsi_max,
    )
    pos = strat.generate_signals(df)
    res = run_backtest(df, pos, cfg.ticker, strat.name, stop_loss_pct=cfg.stop_loss_pct)
    bh = buy_and_hold_benchmark(df)
    current_signal = int(pos.iloc[-1])
    last_price = float(df["Close"].iloc[-1])
    return {
        "df": df,
        "result": res,
        "bh": bh,
        "current_signal": current_signal,
        "last_price": last_price,
        "strategy_name": strat.name,
    }


# ==========================================================
# UI
# ==========================================================
st.title("Auto Trader Dashboard")
st.caption("Alpaca paper trading | system A: 대형주 9 + system B: 중소형주 3")

# Sidebar
with st.sidebar:
    st.header("설정")
    selected_system = st.radio(
        "시스템 선택",
        ["all", "A", "B"],
        format_func=lambda x: {
            "all": "전체 (A+B)",
            "A": "A: 대형주",
            "B": "B: 중소형주",
        }[x],
    )
    st.divider()
    if st.button("Alpaca 새로고침", use_container_width=True):
        get_alpaca_account.clear()
        st.rerun()
    st.caption("시세/계좌 데이터는 5~10분 캐시됨.")

# 메트릭 카드
acc = get_alpaca_account()
col1, col2, col3, col4 = st.columns(4)
if acc and "error" not in acc:
    col1.metric("Portfolio Value", "$" + "{:,.2f}".format(acc["portfolio_value"]))
    col2.metric("Cash", "$" + "{:,.2f}".format(acc["cash"]))
    col3.metric("Buying Power", "$" + "{:,.2f}".format(acc["buying_power"]))
    col4.metric("Market", "OPEN" if acc["is_open"] else "CLOSED")
elif acc and "error" in acc:
    st.error("Alpaca 연결 실패: " + acc["error"])
else:
    st.warning(".env 파일에 API 키 설정 필요")

# Tabs
tab_signals, tab_positions, tab_backtest, tab_actions = st.tabs([
    "오늘의 시그널", "Alpaca 보유 현황", "백테스트", "실행 버튼"
])

# ----------------------- TAB 1: 시그널 -----------------------
with tab_signals:
    st.subheader("종목별 현재 시그널")
    configs = get_configs(selected_system)

    rows = []
    progress = st.progress(0.0)
    for i, cfg in enumerate(configs):
        try:
            r = compute_signal_and_equity(cfg)
            if r is None:
                continue
            rows.append({
                "system": cfg.system,
                "ticker": cfg.ticker,
                "strategy": r["strategy_name"],
                "stop_loss": "-" + str(int(cfg.stop_loss_pct * 100)) + "%",
                "weight": "{:.1%}".format(cfg.weight),
                "last_price": "$" + "{:.2f}".format(r["last_price"]),
                "signal": "BUY/HOLD" if r["current_signal"] == 1 else "EXIT/CASH",
                "bt_sharpe": r["result"].metrics["sharpe"],
                "bt_return%": "{:.0f}%".format(r["result"].metrics["total_return"] * 100),
                "bt_mdd%": "{:.0f}%".format(r["result"].metrics["max_drawdown"] * 100),
                "bh_return%": "{:.0f}%".format(r["bh"]["total_return_%"]),
            })
        except Exception as e:
            rows.append({
                "system": cfg.system, "ticker": cfg.ticker, "strategy": "ERROR",
                "stop_loss": "-", "weight": "-", "last_price": "-", "signal": "-",
                "bt_sharpe": 0, "bt_return%": str(e)[:30], "bt_mdd%": "-", "bh_return%": "-",
            })
        progress.progress((i + 1) / len(configs))
    progress.empty()

    df_signals = pd.DataFrame(rows)
    # 색깔 입히기
    def color_signal(val):
        if val == "BUY/HOLD":
            return "background-color: #d4edda; color: #155724"
        if val == "EXIT/CASH":
            return "background-color: #f8d7da; color: #721c24"
        return ""
    styled = df_signals.style.map(color_signal, subset=["signal"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    buy = (df_signals["signal"] == "BUY/HOLD").sum()
    exit_ = (df_signals["signal"] == "EXIT/CASH").sum()
    st.caption("BUY/HOLD: " + str(buy) + " | EXIT/CASH: " + str(exit_))

# ----------------------- TAB 2: Alpaca 포지션 -----------------------
with tab_positions:
    st.subheader("현재 보유 포지션")
    if acc and "positions" in acc:
        if not acc["positions"]:
            st.info("보유 포지션 없음. dry-run으로 시그널 확인 후 --live 모드로 실행하면 매수.")
        else:
            pos_df = pd.DataFrame(acc["positions"])
            pos_df.columns = ["종목", "수량", "평단가", "현재가", "평가금액", "평가손익($)", "평가손익(%)"]
            pos_df["평단가"] = pos_df["평단가"].map(lambda x: "${:,.2f}".format(x))
            pos_df["현재가"] = pos_df["현재가"].map(lambda x: "${:,.2f}".format(x))
            pos_df["평가금액"] = pos_df["평가금액"].map(lambda x: "${:,.2f}".format(x))
            pos_df["평가손익($)"] = pos_df["평가손익($)"].map(lambda x: "${:+,.2f}".format(x))
            pos_df["평가손익(%)"] = pos_df["평가손익(%)"].map(lambda x: "{:+.2f}%".format(x))
            st.dataframe(pos_df, use_container_width=True, hide_index=True)
    else:
        st.warning("Alpaca 연결 안 됨")

    # 거래 로그
    st.subheader("최근 거래 로그")
    trades_csv = ROOT / "logs" / "trades.csv"
    if trades_csv.exists():
        trades_df = pd.read_csv(trades_csv)
        st.dataframe(trades_df.tail(20), use_container_width=True, hide_index=True)
    else:
        st.info("거래 기록 없음. live_trader.py --live 실행 시 기록됨.")

# ----------------------- TAB 3: 백테스트 시각화 -----------------------
with tab_backtest:
    st.subheader("종목별 자본곡선 (전략 vs 매수후보유)")
    configs = get_configs(selected_system)
    selected_ticker = st.selectbox(
        "종목 선택", [c.ticker for c in configs],
        format_func=lambda t: t + " (sys " + next(c.system for c in configs if c.ticker == t) + ")",
    )
    cfg = next(c for c in configs if c.ticker == selected_ticker)
    try:
        r = compute_signal_and_equity(cfg)
        if r:
            equity = r["result"].equity_curve
            df = r["df"]
            bh_curve = (df["Close"] / df["Close"].iloc[0])
            chart_df = pd.DataFrame({
                "전략 자본곡선": equity,
                "매수후보유": bh_curve,
            }).dropna()
            st.line_chart(chart_df)

            colA, colB, colC, colD = st.columns(4)
            colA.metric("전략 수익률", "{:.0f}%".format(r["result"].metrics["total_return"] * 100))
            colB.metric("Sharpe", "{:.2f}".format(r["result"].metrics["sharpe"]))
            colC.metric("MDD", "{:.0f}%".format(r["result"].metrics["max_drawdown"] * 100))
            colD.metric("거래 수", str(r["result"].metrics["num_trades"]))

            # 거래 내역
            if not r["result"].trades.empty:
                st.subheader("거래 내역")
                st.dataframe(r["result"].trades, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error("백테스트 오류: " + str(e))

# ----------------------- TAB 4: 실행 버튼 -----------------------
with tab_actions:
    st.subheader("스크립트 실행")
    st.warning("⚠️ '실제 주문' 버튼은 Alpaca 페이퍼 계정에 진짜 주문을 넣어요. (페이퍼니까 가짜 돈)")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("백테스트 재실행", use_container_width=True):
            with st.spinner("백테스트 실행 중..."):
                result = subprocess.run(
                    [sys.executable, "run_backtest.py"], cwd=ROOT,
                    capture_output=True, text=True, timeout=300,
                )
                st.code(result.stdout[-2000:] + (result.stderr[-1000:] if result.stderr else ""))

    with col2:
        if st.button("Live Trader (Dry-run)", use_container_width=True):
            with st.spinner("Dry-run 실행 중..."):
                result = subprocess.run(
                    [sys.executable, "live_trader.py", "--system", selected_system],
                    cwd=ROOT, capture_output=True, text=True, timeout=120,
                )
                st.code(result.stdout[-3000:] + (result.stderr[-1000:] if result.stderr else ""))

    with col3:
        confirm = st.checkbox("실제 주문 활성화 (필수 체크)")
        if st.button("실제 페이퍼 주문 실행", use_container_width=True, disabled=not confirm):
            with st.spinner("주문 실행 중..."):
                result = subprocess.run(
                    [sys.executable, "live_trader.py", "--live", "--system", selected_system],
                    cwd=ROOT, capture_output=True, text=True, timeout=120,
                )
                st.code(result.stdout[-3000:] + (result.stderr[-1000:] if result.stderr else ""))
                get_alpaca_account.clear()

    st.divider()
    st.subheader("리포트 보기")
    reports_dir = ROOT / "reports"
    if reports_dir.exists():
        for fname in ["backtest_report.md", "walk_forward_report.md", "holdings_report.md"]:
            fp = reports_dir / fname
            if fp.exists():
                with st.expander("📄 " + fname):
                    st.markdown(fp.read_text(encoding="utf-8"))
