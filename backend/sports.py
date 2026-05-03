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
    "Motorsport": "🏎️",
    "Cyclisme": "🚴",
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


def _is_live(external_id: str) -> bool:
    return bool(external_id) and not external_id.startswith("nolive_")


def get_team_upcoming(external_id: str, team_name: str, sport: str, tracking_type: str = "team"):
    if not _is_live(external_id):
        return []
    if tracking_type == "league":
        data = _get("eventsnextleague.php", {"id": external_id})
    else:
        data = _get("eventsnext.php", {"id": external_id})
    events = (data.get("events") or [])[:15]
    return [_parse_event(e, team_name, sport) for e in events]


def get_team_last(external_id: str, team_name: str, sport: str, tracking_type: str = "team"):
    if not _is_live(external_id):
        return []
    if tracking_type == "league":
        data = _get("eventspastleague.php", {"id": external_id})
    else:
        data = _get("eventslast.php", {"id": external_id})
    events = (data.get("events") or [])[:10]
    return [_parse_event(e, team_name, sport) for e in events]


def get_all_upcoming():
    teams = get_teams()
    all_events = []
    seen_ids = set()

    for team in teams:
        events = get_team_upcoming(
            team["external_id"], team["name"], team["sport"],
            team.get("tracking_type", "team"),
        )
        for event in events:
            if event["id"] not in seen_ids:
                seen_ids.add(event["id"])
                all_events.append(event)

    all_events.sort(key=lambda e: e.get("date_raw", ""))
    return all_events


def get_all_upcoming_for_month(month: str):
    """Fetch all events for a given month (format: YYYY-MM) across all teams."""
    from datetime import datetime
    teams = get_teams()
    all_events = []
    seen_ids = set()

    year, m = map(int, month.split("-"))
    month_start = f"{year}-{m:02d}-01"
    if m == 12:
        month_end = f"{year+1}-01-01"
    else:
        month_end = f"{year}-{m+1:02d}-01"

    for team in teams:
        if not _is_live(team["external_id"]):
            continue
        tracking_type = team.get("tracking_type", "team")
        if tracking_type == "league":
            data = _get("eventsnextleague.php", {"id": team["external_id"]})
        else:
            data = _get("eventsnext.php", {"id": team["external_id"]})
        events = data.get("events") or []
        for e in events:
            date = e.get("dateEvent", "")
            if month_start <= date < month_end:
                parsed = _parse_event(e, team["name"], team["sport"])
                if parsed["id"] not in seen_ids:
                    seen_ids.add(parsed["id"])
                    all_events.append(parsed)

    all_events.sort(key=lambda e: e.get("date_raw", ""))
    return all_events


def get_all_recent():
    teams = get_teams()
    all_events = []
    seen_ids = set()

    for team in teams:
        events = get_team_last(
            team["external_id"], team["name"], team["sport"],
            team.get("tracking_type", "team"),
        )
        for event in events:
            if event["id"] not in seen_ids:
                seen_ids.add(event["id"])
                all_events.append(event)

    all_events.sort(key=lambda e: e.get("date_raw", ""), reverse=True)
    return all_events[:10]
