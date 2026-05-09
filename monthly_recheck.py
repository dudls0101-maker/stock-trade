"""
월간 전략 재검토 스크립트.

매월 1회 실행:
  1) 12종목 전체 백테스트 재실행 (최신 데이터 반영)
  2) 종목별 현재 최적 전략 재계산
  3) live_config.py에 적힌 현재 전략과 비교
  4) 차이 발견 시 변경 추천 리포트 생성
  5) 자동 반영은 안 함 — 인동님이 검토 후 직접 결정

사용법:
    python monthly_recheck.py

출력:
  - reports/monthly_recheck_YYYYMMDD.md (변경 추천 리포트)
  - logs/strategy_changes.log (이력 누적)
  - 콘솔에 핵심 변경사항 요약
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import pandas as pd
from tabulate import tabulate

from data_loader import load_ohlcv
from strategies import standard_grid, MACrossStrategy
from backtester import run_backtest, buy_and_hold_benchmark
from live_config import LIVE_CONFIG

REPORTS_DIR = Path(__file__).parent / "reports"
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

START_DATE = "2018-01-01"
MIN_TRADES = 15  # 보유종목 짧은 히스토리 고려해서 약간 완화


def parse_strategy_name(name: str) -> dict:
    """'EMA(10/30)+RSI<70' -> {ma_type, fast, slow, rsi_max}"""
    ma_type = "ema" if name.startswith("EMA") else "sma"
    paren = name[name.index("(") + 1:name.index(")")]
    fast, slow = [int(x) for x in paren.split("/")]
    rsi_max = None
    if "RSI<" in name:
        rsi_max = int(name.split("RSI<")[1])
    return {"ma_type": ma_type, "fast": fast, "slow": slow, "rsi_max": rsi_max}


def current_config_for(ticker: str):
    for cfg in LIVE_CONFIG:
        if cfg.ticker == ticker:
            return cfg
    return None


def main():
    today = datetime.now().strftime("%Y%m%d")
    print("=" * 60)
    print("Monthly Recheck — " + today)
    print("=" * 60)

    print("\n[1/4] 12종목 데이터 로딩")
    data = {}
    for cfg in LIVE_CONFIG:
        try:
            df = load_ohlcv(cfg.ticker, start=START_DATE)
            data[cfg.ticker] = df
            print("  - " + cfg.ticker + ": " + str(len(df)) + " bars")
        except Exception as e:
            print("  - " + cfg.ticker + ": FAIL (" + str(e) + ")")

    print("\n[2/4] 종목별 24개 전략 백테스트")
    grid = standard_grid()
    rows = []
    for cfg in LIVE_CONFIG:
        if cfg.ticker not in data:
            continue
        df = data[cfg.ticker]
        for strat in grid:
            if len(df) < strat.slow + 30:
                continue
            pos = strat.generate_signals(df)
            res = run_backtest(df, pos, cfg.ticker, strat.name, stop_loss_pct=cfg.stop_loss_pct)
            row = res.summary_row()
            row["system"] = cfg.system
            rows.append(row)
    summary = pd.DataFrame(rows)

    print("\n[3/4] 변경사항 감지")
    changes = []
    for cfg in LIVE_CONFIG:
        if cfg.ticker not in data:
            continue
        # 현재 전략명 만들기
        cur_name = cfg.ma_type.upper() + "(" + str(cfg.fast) + "/" + str(cfg.slow) + ")"
        if cfg.rsi_max is not None:
            cur_name += "+RSI<" + str(int(cfg.rsi_max))

        ticker_results = summary[summary["ticker"] == cfg.ticker]
        ticker_results = ticker_results[ticker_results["trades"] >= MIN_TRADES]
        if ticker_results.empty:
            changes.append({
                "ticker": cfg.ticker, "system": cfg.system,
                "current": cur_name, "recommended": "(데이터 부족)",
                "current_sharpe": "-", "recommended_sharpe": "-",
                "verdict": "데이터 부족",
            })
            continue

        # 현재 전략의 최신 결과
        cur_row = ticker_results[ticker_results["strategy"] == cur_name]
        cur_sharpe = float(cur_row.iloc[0]["sharpe"]) if not cur_row.empty else None

        # 새 최적 전략
        best_row = ticker_results.loc[ticker_results["sharpe"].idxmax()]
        best_name = best_row["strategy"]
        best_sharpe = float(best_row["sharpe"])

        # 판정
        verdict = "유지"
        if cur_sharpe is None:
            verdict = "현재 전략 데이터 부족"
        elif best_name != cur_name:
            improvement = best_sharpe - cur_sharpe
            if improvement > 0.3:
                verdict = "★ 변경 강력 추천 (Sharpe +" + "{:.2f}".format(improvement) + ")"
            elif improvement > 0.15:
                verdict = "변경 고려 (Sharpe +" + "{:.2f}".format(improvement) + ")"
            else:
                verdict = "차이 미미, 유지 권장"
        if cur_sharpe is not None and cur_sharpe < 0.3:
            verdict = "⚠ 현재 전략 부진 (Sharpe " + "{:.2f}".format(cur_sharpe) + ") — 검토 필요"

        changes.append({
            "ticker": cfg.ticker, "system": cfg.system,
            "current": cur_name, "recommended": best_name,
            "current_sharpe": "{:.2f}".format(cur_sharpe) if cur_sharpe is not None else "-",
            "recommended_sharpe": "{:.2f}".format(best_sharpe),
            "verdict": verdict,
        })

    changes_df = pd.DataFrame(changes)
    print("\n=== 변경 추천 ===")
    print(tabulate(changes_df, headers="keys", tablefmt="github", showindex=False))

    # 큰 변경 요약
    big_changes = changes_df[changes_df["verdict"].str.contains("★", na=False)]
    warnings = changes_df[changes_df["verdict"].str.contains("⚠", na=False)]
    print("\n--- 요약 ---")
    print("강력 변경 추천: " + str(len(big_changes)) + "건")
    print("경고 (현재 전략 부진): " + str(len(warnings)) + "건")
    if len(big_changes) == 0 and len(warnings) == 0:
        print("→ 모든 전략 정상 작동 중. live_config.py 수정 불필요.")
    else:
        print("→ 아래 리포트 검토 후 필요 시 live_config.py 수정.")

    print("\n[4/4] 리포트 저장")
    report_path = REPORTS_DIR / ("monthly_recheck_" + today + ".md")
    md = ["# 월간 전략 재검토 — " + datetime.now().strftime("%Y-%m-%d") + "\n"]
    md.append("## 요약\n")
    md.append("- 강력 변경 추천: **" + str(len(big_changes)) + "건**\n")
    md.append("- 경고 (현재 부진): **" + str(len(warnings)) + "건**\n")
    md.append("\n## 종목별 검토\n")
    md.append(tabulate(changes_df, headers="keys", tablefmt="github", showindex=False))
    md.append("\n\n## 판정 기준\n")
    md.append("- ★ 변경 강력 추천: 새 전략의 Sharpe가 현재보다 0.30 이상 높음\n")
    md.append("- 변경 고려: Sharpe 차이 0.15~0.30\n")
    md.append("- 차이 미미: 0.15 미만 → 유지 권장 (노이즈일 수 있음)\n")
    md.append("- ⚠ 현재 전략 부진: Sharpe < 0.3 → 검토 필요\n")
    md.append("\n## 적용 방법 (수동)\n")
    md.append("변경하려는 종목이 있으면 `live_config.py` 열어서 해당 줄 직접 수정.\n")
    md.append("예: AAPL의 fast=5, slow=20, ma_type='ema' → fast=10, slow=30, ma_type='sma'\n")
    report_path.write_text("\n".join(md), encoding="utf-8")
    print("  - 리포트: " + str(report_path))

    # 변경 이력 누적 로그
    log_path = LOGS_DIR / "strategy_changes.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n[" + datetime.now().isoformat(timespec="seconds") + "] Monthly Recheck\n")
        for c in changes:
            if "★" in c["verdict"] or "⚠" in c["verdict"]:
                f.write("  " + c["ticker"] + " (" + c["system"] + "): "
                        + c["current"] + " → " + c["recommended"]
                        + " | " + c["verdict"] + "\n")
    print("  - 로그: " + str(log_path))
    print("\n완료.\n")


if __name__ == "__main__":
    main()
