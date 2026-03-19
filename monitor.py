#!/usr/bin/env python3
"""March Madness close game notification service.

Polls the ESPN API every 30 seconds. When an NCAA Tournament game
is in the 2nd half or OT with 8, 5, 3, or 1 minute(s) remaining and
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

from espn import fetch_games, fetch_upcoming_odds
from odds import fetch_live_odds
from notify import notify

load_dotenv()

CLOSE_GAME_MARGIN = 6       # points
THRESHOLDS = [8, 5, 3, 1]      # minutes remaining to notify at
POLL_INTERVAL = 30          # seconds between API calls

# In-memory dedup: (game_id, period, threshold_minutes)
sent: set[tuple] = set()

# Pre-game odds cache: populated from ESPN scoreboard before games go live
pregame_odds: dict[str, dict] = {}


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
    if game["period"] < 2:
        return
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

        def ranked(name: str, rank: int | None) -> str:
            return f"#{rank} {name}" if rank else name

        away = ranked(game["away_name"], game.get("away_rank"))
        home = ranked(game["home_name"], game.get("home_rank"))
        away_s = game["away_score"]
        home_s = game["home_score"]
        clock = game["display_clock"]
        broadcast = game.get("broadcast", "")

        channel_line = f"\U0001f4fa {broadcast}\n" if broadcast else ""

        live_odds = game.get("odds") or fetch_live_odds(game["home_display_name"], game["away_display_name"])
        open_odds = pregame_odds.get(game["id"])

        def sign(v):
            try:
                return f"+{v}" if float(v) > 0 else str(v)
            except (TypeError, ValueError):
                return str(v) if v is not None else ""

        def fmt_ml(o: dict) -> str:
            if not o.get("away_ml"):
                return ""
            return f"{sign(o['away_ml'])} / {sign(o['home_ml'])}"

        def fmt_spread(o: dict) -> str:
            if not o.get("spread_line"):
                return ""
            return f"{o['spread_line']} ({sign(o['spread_odds'])})"

        odds_lines = []
        ml_live = fmt_ml(live_odds) if live_odds else ""
        ml_open = fmt_ml(open_odds) if open_odds else ""
        if ml_live or ml_open:
            current = ml_live or ml_open
            was = f" (open: {ml_open})" if ml_open and ml_live and ml_open != ml_live else ""
            odds_lines.append(f"ML: {current}{was}")

        sp_live = fmt_spread(live_odds) if live_odds else ""
        sp_open = fmt_spread(open_odds) if open_odds else ""
        if sp_live or sp_open:
            current = sp_live or sp_open
            was = f" (open: {sp_open})" if sp_open and sp_live and sp_open != sp_live else ""
            odds_lines.append(f"Spread: {current}{was}")

        odds_line = "\n".join(odds_lines) + "\n" if odds_lines else ""

        message = (
            f"\U0001f3c0 CLOSE GAME \u2014 March Madness\n"
            f"{away} {away_s}  \u2013  {home} {home_s}\n"
            f"{label}, {clock}\n"
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
            # Cache odds for upcoming games before they go in-progress
            upcoming = fetch_upcoming_odds()
            for game_id, odds in upcoming.items():
                if game_id not in pregame_odds:
                    log(f"Caching open odds for upcoming game {game_id}: {odds}")
                pregame_odds[game_id] = odds

            games = fetch_games()
            if games:
                log(f"{len(games)} in-progress tournament game(s) found")
            for game in games:
                log(f"Open odds cache for {game['away_name']} vs {game['home_name']} (id={game['id']}): {pregame_odds.get(game['id'])}")
                check_and_notify(game)
        except Exception as e:
            log(f"Poll error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
