"""
Telegram notification module.
- Sends only signal changes and operational errors.
- NEVER sends P&L info, account value, or anything emotional.
- Silently no-ops if TELEGRAM_BOT_TOKEN/CHAT_ID not set.
"""

from __future__ import annotations
import json
import os
import urllib.request
import urllib.error


SYSTEM_NAMES = {
    "C": "INDEX CORE",
    "A": "BIG TECH",
    "B": "SMALL CAP",
}

DIVIDER = "━━━━━━━━━━━━━━━━━━━"


def _send_raw(message: str) -> bool:
    """Low-level Telegram send. Returns True on success."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False

    url = "https://api.telegram.org/bot" + token + "/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False


def _format_event_block(events: list[dict], event_type: str = "entry") -> str:
    """
    Format events grouped by system inside <pre>.
    Tickers prefixed with ▸ to stand out visually.
    """
    if not events:
        return ""

    by_system: dict[str, list[dict]] = {"C": [], "A": [], "B": []}
    for e in events:
        sys = e.get("system", "?")
        by_system.setdefault(sys, []).append(e)

    blocks = []
    for sys in ["C", "A", "B"]:
        items = by_system.get(sys, [])
        if not items:
            continue
        block_lines = ["━ [" + sys + "] " + SYSTEM_NAMES.get(sys, sys)]
        for e in items:
            ticker = e["ticker"].ljust(6)
            price = "${:>9,.2f}".format(e["price"])
            extra = ""
            if event_type == "stop":
                extra = "  (-" + str(int(e.get("stop_pct", 7))) + "%)"
            block_lines.append("  ▸ " + ticker + " " + price + extra)
        blocks.append("\n".join(block_lines))

    return "<pre>" + "\n\n".join(blocks) + "</pre>"


def notify_signal_changes(date_str: str,
                          new_entries: list[dict],
                          exits: list[dict],
                          stops: list[dict],
                          total_buy: int,
                          total_exit: int) -> bool:
    """Send signal change summary."""
    if not (new_entries or exits or stops):
        return False

    parts = []
    parts.append(DIVIDER)
    parts.append("🤖 <b>AUTO TRADER UPDATE</b>")
    parts.append(DIVIDER)
    parts.append(date_str)
    parts.append("<i>가격은 마지막 종가 (체결가는 다음 개장가)</i>")
    parts.append("")

    if new_entries:
        parts.append("🟢 <b>NEW ENTRIES (" + str(len(new_entries)) + ")</b>")
        parts.append(_format_event_block(new_entries, "entry"))
        parts.append("")

    if exits:
        parts.append("🔴 <b>EXITS (" + str(len(exits)) + ")</b>")
        parts.append(_format_event_block(exits, "exit"))
        parts.append("")

    if stops:
        parts.append("⛔ <b>STOP LOSS (" + str(len(stops)) + ")</b>")
        parts.append(_format_event_block(stops, "stop"))
        parts.append("")

    parts.append(DIVIDER)
    parts.append("Active <b>" + str(total_buy) + "</b>  ·  Out <b>" + str(total_exit) + "</b>")

    return _send_raw("\n".join(parts))


def notify_error(date_str: str, error_summary: list[str]) -> bool:
    """Send operational error summary."""
    if not error_summary:
        return False

    parts = []
    parts.append(DIVIDER)
    parts.append("⚠️ <b>AUTO TRADER ERRORS</b>")
    parts.append(DIVIDER)
    parts.append(date_str)
    parts.append("")
    parts.append("<pre>")
    for err in error_summary:
        parts.append("▸ " + err)
    parts.append("</pre>")
    parts.append("<i>Will retry next scheduled run.</i>")

    return _send_raw("\n".join(parts))


def notify_test() -> bool:
    """Send a test message with sample buy/exit/stop."""
    sample_entries = [
        {"ticker": "SPY",   "price": 737.54, "system": "C"},
        {"ticker": "QQQ",   "price": 711.12, "system": "C"},
        {"ticker": "AAPL",  "price": 293.15, "system": "A"},
        {"ticker": "MSFT",  "price": 414.96, "system": "A"},
        {"ticker": "GOOGL", "price": 400.67, "system": "A"},
        {"ticker": "RDW",   "price": 11.06,  "system": "B"},
        {"ticker": "LAC",   "price": 5.57,   "system": "B"},
    ]
    sample_exits = [
        {"ticker": "META", "price": 609.54, "system": "A"},
    ]
    sample_stops = [
        {"ticker": "TMDX", "price": 60.30, "system": "B", "stop_pct": 10},
    ]

    return notify_signal_changes(
        "TEST 2026-05-09 (Sat)",
        new_entries=sample_entries,
        exits=sample_exits,
        stops=sample_stops,
        total_buy=7,
        total_exit=2,
    )


def _load_env_file():
    """Load .env file into os.environ for standalone testing."""
    from pathlib import Path
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("No .env file found")
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if not os.environ.get(k.strip()):
            os.environ[k.strip()] = v.strip().strip('"').strip("'")


if __name__ == "__main__":
    _load_env_file()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    print("TOKEN  : " + (token[:10] + "..." if token else "(empty)"))
    print("CHAT_ID: " + (chat_id if chat_id else "(empty)"))
    if not token or not chat_id:
        print("\nERROR: .env 파일에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 추가 필요")
    else:
        print("\nSending test message (sample buy/exit/stop)...")
        ok = notify_test()
        print("Sent OK!" if ok else "Failed (check token validity)")
