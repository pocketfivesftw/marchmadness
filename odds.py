"""Live odds fallback via The Odds API (the-odds-api.com).

Used when ESPN scoreboard does not include odds (i.e. game is in progress).
Requires ODDS_API_KEY environment variable. Returns None silently if not set.
"""

import os

import requests

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds"


def fetch_live_odds(home_display_name: str, away_display_name: str) -> dict | None:
    api_key = os.environ.get("ODDS_API_KEY", "")
    if not api_key:
        return None
    try:
        resp = requests.get(ODDS_API_URL, params={
            "apiKey": api_key,
            "regions": "us",
            "markets": "h2h,spreads",
            "oddsFormat": "american",
        }, timeout=5)
        resp.raise_for_status()
        events = resp.json()
    except Exception as e:
        print(f"  [Odds API error] {e}")
        return None

    def contains(api_name: str, espn_name: str) -> bool:
        return espn_name.lower() in api_name.lower() or api_name.lower() in espn_name.lower()

    event = next((
        e for e in events
        if contains(e.get("home_team", ""), home_display_name)
        and contains(e.get("away_team", ""), away_display_name)
    ), None)
    if not event:
        return None

    bookmakers = event.get("bookmakers", [])
    if not bookmakers:
        return None
    bm = next((b for b in bookmakers if "draftkings" in b.get("key", "")), bookmakers[0])

    result: dict = {}
    for market in bm.get("markets", []):
        if market["key"] == "h2h":
            for o in market["outcomes"]:
                k = "away_ml" if contains(o["name"], away_display_name) else "home_ml"
                result[k] = str(o["price"])
        elif market["key"] == "spreads":
            for o in market["outcomes"]:
                if not contains(o["name"], away_display_name):  # home team spread
                    result["spread_line"] = str(o["point"])
                    result["spread_odds"] = str(o["price"])

    return result if any(result.values()) else None
