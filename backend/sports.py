import requests
from datetime import datetime, timedelta
from backend.db import get_teams, add_team, remove_team

SPORTS_DB_BASE = "https://www.thesportsdb.com/api/v1/json/3"

SPORT_EMOJIS = {
    "Football": "⚽",
    "Soccer": "⚽",
    "Tennis": "🎾",
    "Basketball": "🏀",
    "Rugby": "🏉",
    "default": "🏆",
}


def _get(endpoint, params=None):
    try:
        r = requests.get(f"{SPORTS_DB_BASE}/{endpoint}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[Sports API] Error: {e}")
        return {}


def search_team(query: str):
    data = _get("searchteams.php", {"t": query})
    teams = data.get("teams") or []
    return [
        {
            "name": t.get("strTeam"),
            "sport": t.get("strSport"),
            "external_id": t.get("idTeam"),
            "badge_url": t.get("strTeamBadge", ""),
            "country": t.get("strCountry", ""),
            "league": t.get("strLeague", ""),
        }
        for t in teams[:10]
    ]


def _parse_event(event: dict, team_name: str, sport: str) -> dict:
    date_str = event.get("dateEvent", "")
    time_str = event.get("strTime", "")
    home = event.get("strHomeTeam", "")
    away = event.get("strAwayTeam", "")
    emoji = SPORT_EMOJIS.get(sport, SPORT_EMOJIS["default"])

    # Format readable date
    display_date = date_str
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        DAYS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        MONTHS_FR = ["jan", "fév", "mars", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"]
        display_date = f"{DAYS_FR[dt.weekday()]} {dt.day} {MONTHS_FR[dt.month - 1]}"
    except Exception:
        pass

    display_time = ""
    if time_str:
        try:
            t = datetime.strptime(time_str[:5], "%H:%M")
            display_time = t.strftime("%Hh%M")
        except Exception:
            display_time = time_str[:5]

    return {
        "id": event.get("idEvent"),
        "name": event.get("strEvent", f"{home} vs {away}"),
        "home_team": home,
        "away_team": away,
        "sport": sport,
        "emoji": emoji,
        "league": event.get("strLeague", ""),
        "date_raw": date_str,
        "date_display": display_date,
        "time_display": display_time,
        "home_badge": event.get("strHomeTeamBadge", ""),
        "away_badge": event.get("strAwayTeamBadge", ""),
        "thumb": event.get("strThumb", ""),
        "tracked_team": team_name,
    }


def get_team_upcoming(external_id: str, team_name: str, sport: str):
    data = _get("eventsnext.php", {"id": external_id})
    events = data.get("events") or []
    return [_parse_event(e, team_name, sport) for e in events]


def get_team_last(external_id: str, team_name: str, sport: str):
    data = _get("eventslast.php", {"id": external_id})
    events = data.get("events") or []
    return [_parse_event(e, team_name, sport) for e in events]


def get_all_upcoming():
    teams = get_teams()
    all_events = []
    seen_ids = set()

    for team in teams:
        events = get_team_upcoming(team["external_id"], team["name"], team["sport"])
        for event in events:
            if event["id"] not in seen_ids:
                seen_ids.add(event["id"])
                all_events.append(event)

    all_events.sort(key=lambda e: e.get("date_raw", ""))
    return all_events


def get_all_recent():
    teams = get_teams()
    all_events = []
    seen_ids = set()

    for team in teams:
        events = get_team_last(team["external_id"], team["name"], team["sport"])
        for event in events:
            if event["id"] not in seen_ids:
                seen_ids.add(event["id"])
                all_events.append(event)

    all_events.sort(key=lambda e: e.get("date_raw", ""), reverse=True)
    return all_events[:10]
