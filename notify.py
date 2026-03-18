"""Slack and Telegram notification senders."""

import os
import requests


def send_slack(message: str) -> None:
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        return
    try:
        requests.post(url, json={"text": message}, timeout=5)
    except Exception as e:
        print(f"  [Slack error] {e}")


def send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=5)
    except Exception as e:
        print(f"  [Telegram error] {e}")


def notify(message: str) -> None:
    """Send to all configured channels."""
    send_slack(message)
    send_telegram(message)
