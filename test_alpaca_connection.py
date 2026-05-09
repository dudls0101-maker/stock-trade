"""
Alpaca 페이퍼 계정 연결 테스트.
실행: python test_alpaca_connection.py
"""

from __future__ import annotations
import os
import sys
from pathlib import Path


def load_env():
    """.env 파일을 읽어 환경변수로 주입."""
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("[ERROR] .env 파일이 없습니다. auto_trader/.env 를 만드세요.")
        sys.exit(1)
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")


def main():
    load_env()
    key_id = os.environ.get("ALPACA_API_KEY_ID", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    base_url = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    if not key_id or "여기에" in key_id:
        print("[ERROR] ALPACA_API_KEY_ID 가 .env 에 입력되지 않았습니다.")
        sys.exit(1)
    if not secret or "여기에" in secret:
        print("[ERROR] ALPACA_SECRET_KEY 가 .env 에 입력되지 않았습니다.")
        sys.exit(1)

    print("[1/3] Alpaca 라이브러리 import 중...")
    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        print("[ERROR] alpaca-py 가 설치되어 있지 않습니다.")
        print("  -> pip install alpaca-py")
        sys.exit(1)

    print("[2/3] Alpaca API 연결 시도...")
    client = TradingClient(api_key=key_id, secret_key=secret, paper=True)

    print("[3/3] 계정 정보 조회 중...")
    try:
        account = client.get_account()
    except Exception as e:
        print("[FAIL] 연결 실패: " + str(e))
        print("  - 키 값을 다시 확인하세요 (앞뒤 공백 없이)")
        print("  - Paper 모드로 발급받은 키가 맞는지 확인 (PK로 시작)")
        sys.exit(1)

    print("\n=== 연결 성공! ===")
    print("계정 번호:        " + str(account.account_number))
    print("계정 상태:        " + str(account.status))
    print("페이퍼 자본:      $" + "{:,.2f}".format(float(account.cash)))
    print("포트폴리오 가치:  $" + "{:,.2f}".format(float(account.portfolio_value)))
    print("매수 가능 금액:   $" + "{:,.2f}".format(float(account.buying_power)))
    print("\n시장 상태 조회 중...")

    clock = client.get_clock()
    print("미국 장 현재 상태: " + ("OPEN (개장중)" if clock.is_open else "CLOSED (장 마감)"))
    print("다음 개장:        " + str(clock.next_open))
    print("다음 마감:        " + str(clock.next_close))
    print("\n준비 완료. 이제 자동매매 코드를 만들 수 있습니다.")


if __name__ == "__main__":
    main()
