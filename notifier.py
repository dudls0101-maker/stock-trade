"""
Telegram notification module.
- Sends only signal changes and operational errors.
- NEVER sends P&L info, account value, or anything emotional.
- Silently no-ops if TELEGRAM_BOT_TOKEN/CHAT_ID not set.

Setup:
1. Create new bot via @BotFather, get TOKEN
2. Send /start to your bot, get chat_id from
   https://api.telegram.org/bot<TOKEN>/getUpdates
3. Set environment variables:
     TELEGRAM_BOT_TOKEN=<token>
     TELEGRAM_CHAT_ID=<chat_id>
   (Or add to .env locally / GitHub Secrets for Actions)
"""

from __future__ import annotations
import json
import os
import urllib.request
import urllib.error
from typing import Optional


def _send_raw(message: str) -> bool:
    """Low-level Telegram send. Returns True on success."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False  # silently skip if not configured

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


def notify_signal_changes(date_str: str,
                          new_entries: list[dict],
                          exits: list[dict],
                          stops: list[dict],
                          total_buy: int,
                          total_exit: int) -> bool:
    """
    Send signal change summary.
    Each event dict: {"ticker": str, "price": float, "system": str}
    Only sends if there are any changes (entries/exits/stops > 0).
    """
    if not (new_entries or exits or stops):
        return False  # nothing to report

    lines = ["<b>Auto Trader Signal Update</b>", date_str, ""]

    if new_entries:
        lines.append("<b>New entries (" + str(len(new_entries)) + "):</b>")
        for e in new_entries:
            lines.append("  - " + e["ticker"] + " BUY @ $" + "{:.2f}".format(e["price"])
                         + " (" + e["system"] + ")")
        lines.append("")

    if exits:
        lines.append("<b>Exits (" + str(len(exits)) + "):</b>")
        for e in exits:
            lines.append("  - " + e["ticker"] + " SELL @ $" + "{:.2f}".format(e["price"])
                         + " (signal exit)")
        lines.append("")

    if stops:
        lines.append("<b>Stop loss (" + str(len(stops)) + "):</b>")
        for e in stops:
            lines.append("  - " + e["ticker"] + " STOP @ $" + "{:.2f}".format(e["price"])
                         + " (-" + str(int(e.get("stop_pct", 7))) + "%)")
        lines.append("")

    lines.append("Active: " + str(total_buy) + "/" + str(total_buy + total_exit) + " | Exits: " + str(total_exit))

    return _send_raw("\n".join(lines))


def notify_error(date_str: str, error_summary: list[str]) -> bool:
    """Send operational error summary."""
    if not error_summary:
        return False

    lines = ["<b>Auto Trader Errors</b>", date_str, ""]
    for err in error_summary:
        lines.append("  - " + err)
    lines.append("")
    lines.append("Will retry next scheduled run.")

    return _send_raw("\n".join(lines))


def notify_test() -> bool:
    """Send a test message to verify setup."""
    return _send_raw(
        "<b>Auto Trader connected</b>\n\n"
        "Notifications will arrive only when:\n"
        "  - signals change (BUY/EXIT/STOP)\n"
        "  - operational errors occur\n\n"
        "P&L info is never sent."
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
    # Test from CLI: python notifier.py
    _load_env_file()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    print("TOKEN  : " + (token[:10] + "..." if token else "(empty)"))
    print("CHAT_ID: " + (chat_id if chat_id else "(empty)"))
    if not token or not chat_id:
        print("\nERROR: .env 파일에 다음 두 줄 추가 필요:")
        print("  TELEGRAM_BOT_TOKEN=your_token_here")
        print("  TELEGRAM_CHAT_ID=your_chat_id_here")
    else:
        print("\nSending test message...")
        ok = notify_test()
        print("Sent OK!" if ok else "Failed (Telegram API rejected - token may be invalid)")
