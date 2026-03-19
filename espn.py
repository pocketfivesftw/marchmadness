"""ESPN scoreboard API fetcher and parser for NCAA Tournament games."""

import requests

SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball"
    "/mens-college-basketball/scoreboard"
)
NCAA_TOURNAMENT_ID = 22


def fetch_games() -> list[dict]:
    """Fetch and parse all in-progress NCAA Tournament games."""
    resp = requests.get(SCOREBOARD_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    games = []
    for event in data.get("events", []):
        game = _parse_game(event)
        if game:
            games.append(game)
    return games


def fetch_upcoming_odds() -> dict[str, dict]:
    """Fetch odds for upcoming (pre-game) NCAA Tournament games, keyed by game id."""
    resp = requests.get(SCOREBOARD_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    result = {}
    for event in data.get("events", []):
        competition = event.get("competitions", [{}])[0]
        if competition.get("tournamentId") != NCAA_TOURNAMENT_ID:
            continue
        status_name = competition.get("status", event.get("status", {})).get("type", {}).get("name", "")
        if status_name != "STATUS_SCHEDULED":
            continue
        competitors = competition.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1] if len(competitors) > 1 else {})
        home_name = home.get("team", {}).get("shortDisplayName", "Home")
        away_name = away.get("team", {}).get("shortDisplayName", "Away")
        odds = _parse_odds(competition, away_name, home_name)
        if odds:
            result[event["id"]] = odds
    return result


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
    home_display_name = home.get("team", {}).get("displayName", home_name)
    away_display_name = away.get("team", {}).get("displayName", away_name)

    def _rank(competitor: dict) -> int | None:
        r = competitor.get("curatedRank", {}).get("current")
        return r if r and r < 99 else None

    home_rank = _rank(home)
    away_rank = _rank(away)

    # Broadcast channel: prefer the simple string, fall back to broadcasts array
    broadcast = competition.get("broadcast", "")
    if not broadcast:
        names = competition.get("broadcasts", [{}])[0].get("names", [])
        broadcast = names[0] if names else ""

    # Odds: already present in scoreboard response, no extra API call needed
    odds = _parse_odds(competition, away_name, home_name)

    return {
        "id": event["id"],
        "period": period,
        "clock_seconds": float(clock_seconds),
        "display_clock": display_clock,
        "home_name": home_name,
        "away_name": away_name,
        "home_display_name": home_display_name,
        "away_display_name": away_display_name,
        "home_score": home_score,
        "away_score": away_score,
        "home_rank": home_rank,
        "away_rank": away_rank,
        "score_diff": abs(home_score - away_score),
        "broadcast": broadcast,
        "odds": odds,
    }


def _parse_odds(competition: dict, away_name: str, home_name: str) -> dict | None:
    odds_list = competition.get("odds", [])
    if not odds_list:
        return None

    # Prefer DraftKings; fall back to first provider
    o = next(
        (x for x in odds_list if "Draft Kings" in x.get("provider", {}).get("name", "")),
        odds_list[0],
    )

    def _s(d: dict, *keys: str) -> str:
        for k in keys:
            if not isinstance(d, dict):
                return ""
            d = d.get(k, {})
        return str(d) if d and not isinstance(d, dict) else ""

    ml = o.get("moneyline", {})
    ps = o.get("pointSpread", {})

    result = {
        "away_ml": _s(ml, "away", "close", "odds"),
        "home_ml": _s(ml, "home", "close", "odds"),
        "spread_line": _s(ps, "home", "close", "line"),
        "spread_odds": _s(ps, "home", "close", "odds"),
    }

    return result if any(result.values()) else None
