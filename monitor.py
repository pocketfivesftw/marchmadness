#!/usr/bin/env python3
"""March Madness close game notification service.

Polls the ESPN API every 30 seconds. When an NCAA Tournament game
is in the 2nd half or OT with 5, 3, or 1 minute(s) remaining and
the score difference is 6 points or fewer, sends an alert to Slack
and/or Telegram.

Environment variables (can be set in a .env file):
  SLACK_WEBHOOK_URL     - Slack incoming webhook URL
  TELEGRAM_BOT_TOKEN    - Telegram bot token
  TELEGRAM_CHAT_ID      - Telegram chat/channel ID
"""

import sys
import time
from datetime import datetime

# Disable stdout buffering so logs appear immediately in Railway
sys.stdout.reconfigure(line_buffering=True)

from dotenv import load_dotenv

from espn import fetch_games
from notify import notify

load_dotenv()

CLOSE_GAME_MARGIN = 6       # points
THRESHOLDS = [19, 16, 11, 8, 5, 3, 1]      # minutes remaining to notify at
POLL_INTERVAL = 30          # seconds between API calls

# In-memory dedup: (game_id, period, threshold_minutes)
sent: set[tuple] = set()


def period_label(period: int) -> str:
    if period == 1:
        return "1st half"
    if period == 2:
        return "2nd half"
    if period == 3:
        return "OT"
    return f"{period - 2}OT"


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def check_and_notify(game: dict) -> None:
    if game["score_diff"] > CLOSE_GAME_MARGIN:
        return

    minutes_left = game["clock_seconds"] / 60.0
    label = period_label(game["period"])

    for threshold in sorted(THRESHOLDS):
        key = (game["id"], game["period"], threshold)
        if key in sent or minutes_left > threshold:
            continue

        sent.add(key)
        # Mark larger thresholds as already handled so we don't spam on startup
        for t in THRESHOLDS:
            if t > threshold:
                sent.add((game["id"], game["period"], t))

        away = game["away_name"]
        home = game["home_name"]
        away_s = game["away_score"]
        home_s = game["home_score"]
        clock = game["display_clock"]
        broadcast = game.get("broadcast", "")

        channel_line = f"Watch on {broadcast}\n" if broadcast else ""

        odds = game.get("odds")
        if odds:
            ml = f"ML: {away} {odds['away_ml']} / {home} {odds['home_ml']}" if odds.get("away_ml") else ""
            spread = f"Spread: {odds['spread_line']} ({odds['spread_odds']})" if odds.get("spread_line") else ""
            parts = [p for p in [ml, spread] if p]
            odds_line = "  |  ".join(parts) + "\n" if parts else ""
        else:
            odds_line = ""

        message = (
            f"\U0001f3c0 CLOSE GAME \u2014 March Madness\n"
            f"{away} {away_s}  \u2013  {home} {home_s}\n"
            f"{clock} left in {label}\n"
            f"{odds_line}"
            f"{channel_line}"
        ).rstrip()
        log(f"ALERT: {away} {away_s} - {home} {home_s} | {clock} in {label}" + (f" | {broadcast}" if broadcast else ""))
        notify(message)


def run() -> None:
    log("March Madness notifier started. Polling ESPN every 30s...")
    notify("\U0001f3c0 March Madness notifier started. Watching for close games...")
    while True:
        try:
            games = fetch_games()
            if games:
                log(f"{len(games)} in-progress tournament game(s) found")
            for game in games:
                check_and_notify(game)
        except Exception as e:
            log(f"Poll error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
