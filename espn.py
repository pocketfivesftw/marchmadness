"""ESPN scoreboard API fetcher and parser for NCAA Tournament games."""

import requests

SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball"
    "/mens-college-basketball/scoreboard"
)
NCAA_TOURNAMENT_ID = 22


def fetch_games() -> list[dict]:
    """Fetch and parse all in-progress NCAA Tournament games in 2nd half or OT."""
    resp = requests.get(SCOREBOARD_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    games = []
    for event in data.get("events", []):
        game = _parse_game(event)
        if game:
            games.append(game)
    return games


def _parse_game(event: dict) -> dict | None:
    competition = event.get("competitions", [{}])[0]

    # Filter to NCAA Tournament only
    if competition.get("tournamentId") != NCAA_TOURNAMENT_ID:
        return None

    status = competition.get("status", event.get("status", {}))
    status_name = status.get("type", {}).get("name", "")

    if status_name != "STATUS_IN_PROGRESS":
        return None

    period = status.get("period", 1)
    if period < 2:
        return None  # 1st half or halftime

    clock_seconds = status.get("clock", 0.0) or 0.0
    display_clock = status.get("displayClock", "0:00")

    competitors = competition.get("competitors", [])
    if len(competitors) < 2:
        return None

    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

    home_score = int(home.get("score") or 0)
    away_score = int(away.get("score") or 0)
    home_name = home.get("team", {}).get("shortDisplayName", "Home")
    away_name = away.get("team", {}).get("shortDisplayName", "Away")

    # Broadcast channel: prefer the simple string, fall back to broadcasts array
    broadcast = competition.get("broadcast", "")
    if not broadcast:
        names = competition.get("broadcasts", [{}])[0].get("names", [])
        broadcast = names[0] if names else ""

    return {
        "id": event["id"],
        "period": period,
        "clock_seconds": float(clock_seconds),
        "display_clock": display_clock,
        "home_name": home_name,
        "away_name": away_name,
        "home_score": home_score,
        "away_score": away_score,
        "score_diff": abs(home_score - away_score),
        "broadcast": broadcast,
    }
