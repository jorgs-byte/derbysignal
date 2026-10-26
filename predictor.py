import os
import re
import unicodedata
import requests
from math import exp, factorial
from functools import lru_cache
from datetime import datetime, timezone
# ============================================================
# DERBYSIGNAL AI — FOOTBALL PREDICTION ENGINE
# ============================================================
API_URL = "https://api.football-data.org/v4"
TIMEOUT = 20
RECENCY_HALF_LIFE = 60.0
SHRINKAGE_MATCHES = 5.0
MIN_XG = 0.15
MAX_XG = 4.50
MIN_HISTORY_FOR_BACKTEST = 10
COMPETITIONS = {
    "PL": "Premier League",
    "BL1": "Bundesliga",
    "BL2": "2. Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "PD": "La Liga",
    "PPL": "Primeira Liga",
    "DED": "Eredivisie",
    "CL": "UEFA Champions League",
    "EL": "UEFA Europa League",
    "BSA": "Campeonato Brasileiro Série A",
    "CLI": "Copa Libertadores",
    "EC": "European Championship",
    "WC": "FIFA World Cup",
    "ELC": "Championship",
    "FAC": "FA Cup",
}
ALIASES = {
    "arsenal fc": "arsenal",
    "chelsea fc": "chelsea",
    "liverpool fc": "liverpool",
    "man utd": "manchester united",
    "man united": "manchester united",
    "man u": "manchester united",
    "manchester utd": "manchester united",
    "manchester united fc": "manchester united",
    "man city": "manchester city",
    "tottenham": "tottenham hotspur",
    "spurs": "tottenham hotspur",
    "newcastle": "newcastle united",
    "west ham": "west ham united",
    "wolves": "wolverhampton wanderers",
    "brighton": "brighton and hove albion",
    "brighton hove albion": "brighton and hove albion",
    "nottingham forest fc": "nottingham forest",
    "leeds": "leeds united",
    "barca": "barcelona",
    "barcelona fc": "barcelona",
    "atleti": "atletico madrid",
    "atletico": "atletico madrid",
    "atletico de madrid": "atletico madrid",
    "bayern": "bayern munchen",
    "bayern munich": "bayern munchen",
    "fc bayern munchen": "bayern munchen",
    "dortmund": "borussia dortmund",
    "inter": "internazionale milano",
    "inter milan": "internazionale milano",
    "internazionale": "internazionale milano",
    "ac milan": "milan",
    "juve": "juventus",
    "psg": "paris saint germain",
    "paris sg": "paris saint germain",
    "leverkusen": "bayer leverkusen",
    "as roma": "roma",
    "ssc napoli": "napoli",
    "sporting": "sporting cp",
    "sporting lisbon": "sporting cp",
    "sl benfica": "benfica",
    "porto": "fc porto",
    "ajax": "ajax",
    "psv": "psv eindhoven",
    "real": "real madrid",
    "real madrid cf": "real madrid",
    "athletic bilbao": "athletic club",
    "real betis": "real betis",
    "sociedad": "real sociedad",
    "la real": "real sociedad",
    "marseille": "olympique marseille",
    "olympique de marseille": "olympique marseille",
    "lyon": "olympique lyon",
    "monaco": "as monaco",
}
# ============================================================
# TEAM NAME NORMALISATION
# ============================================================
def normalize_team_name(name):
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", str(name).strip().lower())
    name = "".join(
        char for char in name
        if not unicodedata.combining(char)
    )
    name = name.replace("&", " and ")
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    prefixes = (
        "football club ",
        "futbol club ",
        "club de futbol ",
        "club ",
        "fc ",
        "afc ",
        "cf ",
    )
    suffixes = (
        " football club",
        " futbol club",
        " fc",
        " afc",
        " cf",
        " sc",
    )
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
                changed = True
                break
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
                changed = True
                break
    return ALIASES.get(name, name)
def same_team(name_a, name_b):
    a = normalize_team_name(name_a)
    b = normalize_team_name(name_b)
    return bool(a and b and a == b)
def _team_names(team):
    if not team:
        return []
    return [
        value
        for value in (
            team.get("name"),
            team.get("shortName"),
            team.get("tla"),
        )
        if value
    ]
def _team_matches_query(query, team):
    wanted = normalize_team_name(query)
    if not wanted:
        return False
    names = [
        normalize_team_name(name)
        for name in _team_names(team)
    ]
    if wanted in names:
        return True
    # Permit partial matching only when it is sufficiently specific.
    possible = [
        name for name in names
        if name and len(name) >= 5 and len(wanted) >= 5
    ]
    return any(
        wanted in name or name in wanted
        for name in possible
    )
# ============================================================
# FOOTBALL API CONNECTION
# ============================================================
def get_headers():
    token = (
        os.getenv("FOOTBALL_DATA_TOKEN")
        or os.getenv("FOOTBALL_API_KEY")
        or os.getenv("FOOTBALL API KEY")
    )
    if not token:
        raise RuntimeError(
            "Football API key is missing. "
            "Check your workspace secrets."
        )
    return {"X-Auth-Token": token}
def api_get(endpoint, params=None):
    url = f"{API_URL}{endpoint}"
    try:
        response = requests.get(
            url,
            headers=get_headers(),
            params=params,
            timeout=TIMEOUT,
        )
        if response.status_code == 401:
            raise RuntimeError(
                "Football API rejected the key. Check your secret."
            )
        if response.status_code == 403:
            raise RuntimeError(
                "Your API plan does not allow this competition, "
                "season, or endpoint."
            )
        if response.status_code == 429:
            raise RuntimeError(
                "Football API request limit reached. Try again later."
            )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout as exc:
        raise RuntimeError("Football API request timed out.") from exc
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Could not connect to the Football API. "
            "Check your internet connection."
        ) from exc
    except requests.exceptions.HTTPError as exc:
        try:
            message = response.json().get(
                "message",
                "Football API request failed.",
            )
        except Exception:
            message = "Football API request failed."
        raise RuntimeError(message) from exc
def get_football_data_competitions():
    data = api_get("/competitions")
    return [
        {
            "code": item.get("code"),
            "name": item.get("name") or item.get("code"),
            "id": item.get("id"),
            "area": (item.get("area") or {}).get("name", ""),
        }
        for item in data.get("competitions", [])
        if item.get("code")
    ]
def get_competition_name(code):
    return COMPETITIONS.get(code, code or "Unknown competition")
def get_football_data_fixtures(competition_code="PL"):
    code = (competition_code or "PL").strip().upper()
    data = api_get(
        f"/competitions/{code}/matches",
        params={
            "status": "SCHEDULED",
            "limit": 100,
        },
    )
    return data.get("matches", [])
@lru_cache(maxsize=64)
def get_competition_results(competition_code, limit=100):
    """
    Retrieve finished matches for a competition.
    Results are cached to reduce repeated API requests.
    """
    code = (competition_code or "PL").strip().upper()
    limit = max(1, min(int(limit), 500))
    data = api_get(
        f"/competitions/{code}/matches",
        params={
            "status": "FINISHED",
            "limit": limit,
        },
    )
    matches = [
        match
        for match in data.get("matches", [])
        if _valid_match(match)
    ]
    matches.sort(
        key=lambda match: match.get("utcDate", ""),
        reverse=True,
    )
    return tuple(matches)
def clear_results_cache():
    get_competition_results.cache_clear()
    _team_list.cache_clear()
# ============================================================
# TEAM SEARCH
# ============================================================
@lru_cache(maxsize=64)
def _team_list(competition_code):
    try:
        data = api_get(
            f"/competitions/{competition_code}/teams"
        )
        return tuple(data.get("teams", []))
    except Exception:
        return tuple()
def find_team_in_competition(team_name, competition_code):
    if not team_name or not competition_code:
        return None
    code = competition_code.strip().upper()
    teams = list(_team_list(code))
    wanted = normalize_team_name(team_name)
    exact = [
        team for team in teams
        if any(
            normalize_team_name(name) == wanted
            for name in _team_names(team)
        )
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None
    possible = [
        team for team in teams
        if _team_matches_query(team_name, team)
    ]
    return possible[0] if len(possible) == 1 else None
def _find_team_in_matches(team_name, matches):
    found = {}
    for match in matches:
        for side in ("homeTeam", "awayTeam"):
            team = match.get(side) or {}
            if not team.get("name"):
                continue
            if _team_matches_query(team_name, team):
                key = team.get("id") or team["name"]
                found[key] = team
    return next(iter(found.values())) if len(found) == 1 else None
def detect_competition(
    home_team,
    away_team,
    competition_code=None,
):
    if not home_team or not away_team:
        return None
    if competition_code:
        code = competition_code.strip().upper()
        try:
            matches = list(get_competition_results(code, 100))
        except Exception:
            matches = []
        home = _find_team_in_matches(home_team, matches)
        away = _find_team_in_matches(away_team, matches)
        if home and away:
            return code
        home = find_team_in_competition(home_team, code)
        away = find_team_in_competition(away_team, code)
        return code if home and away else None
    preferred = [
        "PL", "BL1", "SA", "FL1", "PD",
        "PPL", "DED", "CL", "BSA", "CLI",
    ]
    try:
        competitions = get_football_data_competitions()
    except Exception:
        competitions = []
    codes = list(dict.fromkeys(
        preferred + [
            item["code"]
            for item in competitions
            if item.get("code")
        ]
    ))
    for code in codes:
        try:
            matches = list(get_competition_results(code, 100))
        except Exception:
            continue
        if (
            _find_team_in_matches(home_team, matches)
            and _find_team_in_matches(away_team, matches)
        ):
            return code
    return None
# ============================================================
# DATE AND MATCH HELPERS
# ============================================================
def _parse_date(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None
def _valid_match(match):
    score = (
        (match.get("score") or {}).get("fullTime") or {}
    )
    home = score.get("home")
    away = score.get("away")
    return (
        isinstance(home, (int, float))
        and not isinstance(home, bool)
        and isinstance(away, (int, float))
        and not isinstance(away, bool)
        and home >= 0
        and away >= 0
    )
def _match_weight(match, index=0, reference_date=None):
    match_date = _parse_date(match.get("utcDate", ""))
    if isinstance(reference_date, str):
        reference_date = _parse_date(reference_date)
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)
    if match_date is None:
        return 0.5 ** (max(0, index) / 8.0)
    age_days = max(
        0.0,
        (reference_date - match_date).total_seconds() / 86400.0,
    )
    return 0.5 ** (age_days / RECENCY_HALF_LIFE)
def _weighted_average(rows, fallback):
    total_weight = sum(weight for _, weight in rows)
    if total_weight <= 0:
        return fallback
    return sum(
        value * weight for value, weight in rows
    ) / total_weight
def _blend_with_prior(observed_average, sample_weight, prior_average):
    denominator = sample_weight + SHRINKAGE_MATCHES
    if denominator <= 0:
        return prior_average
    return (
        observed_average * sample_weight
        + prior_average * SHRINKAGE_MATCHES
    ) / denominator
# ============================================================
# POISSON SCORE MODEL
# ============================================================
def poisson_probability(goals, expected_goals):
    goals = int(goals)
    xg = max(0.0, float(expected_goals))
    if xg == 0:
        return 1.0 if goals == 0 else 0.0
    return exp(-xg) * (xg ** goals) / factorial(goals)
def predict_score(home_xg, away_xg, max_goals=7):
    """
    Return sorted (home_goals, away_goals, probability) tuples.
    Probabilities are normalised within the selected score grid.
    """
    home_xg = min(MAX_XG, max(MIN_XG, float(home_xg)))
    away_xg = min(MAX_XG, max(MIN_XG, float(away_xg)))
    max_goals = max(1, min(int(max_goals), 12))
    scores = []
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            probability = (
                poisson_probability(home_goals, home_xg)
                * poisson_probability(away_goals, away_xg)
            )
            scores.append(
                (home_goals, away_goals, probability)
            )
    total = sum(item[2] for item in scores)
    if total <= 0:
        return []
    scores = [
        (home, away, probability / total)
        for home, away, probability in scores
    ]
    scores.sort(key=lambda item: item[2], reverse=True)
    return scores
def predict_match_score(home_xg, away_xg, max_goals=7):
    scores = predict_score(home_xg, away_xg, max_goals)
    return scores[0] if scores else None
def calculate_1x2_probabilities(home_xg, away_xg, max_goals=10):
    """
    Calculate home-win, draw and away-win probabilities.
    The three probabilities sum to 100%.
    """
    scores = predict_score(
        home_xg,
        away_xg,
        max_goals=max_goals,
    )
    home_win = sum(p for h, a, p in scores if h > a)
    draw = sum(p for h, a, p in scores if h == a)
    away_win = sum(p for h, a, p in scores if h < a)
    total = home_win + draw + away_win
    if total <= 0:
        return {
            "home_win": 0.0,
            "draw": 0.0,
            "away_win": 0.0,
        }
    return {
        "home_win": home_win / total,
        "draw": draw / total,
        "away_win": away_win / total,
    }
# ============================================================
# TEAM STATISTICS
# ============================================================
def _team_records(team_name, matches, reference_date=None):
    records = {
        "home": [],
        "away": [],
        "all": [],
    }
    for index, match in enumerate(matches):
        if not _valid_match(match):
            continue
        home = match.get("homeTeam") or {}
        away = match.get("awayTeam") or {}
        score = (
            (match.get("score") or {}).get("fullTime") or {}
        )
        home_goals = float(score["home"])
        away_goals = float(score["away"])
        weight = _match_weight(
            match,
            index,
            reference_date,
        )
        is_home = _team_matches_query(team_name, home)
        is_away = _team_matches_query(team_name, away)
        # Avoid counting an ambiguous match twice.
        if is_home and not is_away:
            row = {
                "goals_for": home_goals,
                "goals_against": away_goals,
                "weight": weight,
            }
            records["home"].append(row)
            records["all"].append(row)
        elif is_away and not is_home:
            row = {
                "goals_for": away_goals,
                "goals_against": home_goals,
                "weight": weight,
            }
            records["away"].append(row)
            records["all"].append(row)
    return records
def _summarize_records(records):
    total_weight = sum(row["weight"] for row in records)
    if total_weight <= 0:
        return None
    return {
        "games": len(records),
        "sample_weight": total_weight,
        "goals_for_per_game": sum(
            row["goals_for"] * row["weight"]
            for row in records
        ) / total_weight,
        "goals_against_per_game": sum(
            row["goals_against"] * row["weight"]
            for row in records
        ) / total_weight,
    }
def calculate_team_strength(team_name, competition_code="PL"):
    code = (competition_code or "PL").strip().upper()
    matches = list(get_competition_results(code, 100))
    records = _team_records(team_name, matches)
    summary = _summarize_records(records["all"])
    if not summary:
        return None
    home_stats = _summarize_records(records["home"])
    away_stats = _summarize_records(records["away"])
    return {
        "team": team_name,
        "competition": code,
        "games": summary["games"],
        "home_games": len(records["home"]),
        "away_games": len(records["away"]),
        "goals_for_per_game": summary["goals_for_per_game"],
        "goals_against_per_game": summary["goals_against_per_game"],
        "home_goals_for_per_game": (
            home_stats["goals_for_per_game"] if home_stats else None
        ),
        "home_goals_against_per_game": (
            home_stats["goals_against_per_game"] if home_stats else None
        ),
        "away_goals_for_per_game": (
            away_stats["goals_for_per_game"] if away_stats else None
        ),
        "away_goals_against_per_game": (
            away_stats["goals_against_per_game"] if away_stats else None
        ),
    }
def get_team_analysis(team_name, competition_code="PL"):
    code = (competition_code or "PL").strip().upper()
    matches = list(get_competition_results(code, 100))
    records = _team_records(team_name, matches)
    all_stats = _summarize_records(records["all"])
    home_stats = _summarize_records(records["home"])
    away_stats = _summarize_records(records["away"])
    if not all_stats:
        return {
            "team": team_name,
            "competition": code,
            "error": (
                f"No finished-match statistics found for {team_name} "
                f"in {code}. Check the competition and API access."
            ),
        }
    team_matches = [
        match for match in matches
        if _valid_match(match)
        and (
            _team_matches_query(
                team_name,
                match.get("homeTeam") or {},
            )
            or _team_matches_query(
                team_name,
                match.get("awayTeam") or {},
            )
        )
    ][:5]
    recent_stats = _summarize_records(
        _team_records(team_name, team_matches)["all"]
    )
    return {
        "team": team_name,
        "competition": code,
        "played": all_stats["games"],
        "form": f"Recent matches: {len(team_matches)}",
        "avg_scored": all_stats["goals_for_per_game"],
        "avg_conceded": all_stats["goals_against_per_game"],
        "home_avg_scored": (
            home_stats["goals_for_per_game"] if home_stats else 0.0
        ),
        "home_avg_conceded": (
            home_stats["goals_against_per_game"] if home_stats else 0.0
        ),
        "away_avg_scored": (
            away_stats["goals_for_per_game"] if away_stats else 0.0
        ),
        "away_avg_conceded": (
            away_stats["goals_against_per_game"] if away_stats else 0.0
        ),
        "recent_avg_scored": (
            recent_stats["goals_for_per_game"]
            if recent_stats
            else all_stats["goals_for_per_game"]
        ),
        "recent_avg_conceded": (
            recent_stats["goals_against_per_game"]
            if recent_stats
            else all_stats["goals_against_per_game"]
        ),
        "home_games": len(records["home"]),
        "away_games": len(records["away"]),
    }
# ============================================================
# EXPECTED GOALS MODEL
# ============================================================
def _competition_averages(matches, reference_date=None):
    home_rows = []
    away_rows = []
    for index, match in enumerate(matches):
        if not _valid_match(match):
            continue
        score = (
            (match.get("score") or {}).get("fullTime") or {}
        )
        weight = _match_weight(
            match,
            index,
            reference_date,
        )
        home_rows.append((float(score["home"]), weight))
        away_rows.append((float(score["away"]), weight))
    return (
        max(0.2, _weighted_average(home_rows, 1.35)),
        max(0.2, _weighted_average(away_rows, 1.10)),
    )
def _expected_goals_from_history(
    home_team,
    away_team,
    historical_matches,
    reference_date=None,
):
    """
    Estimate expected goals using only the supplied match history.
    reference_date is important for backtesting: it prevents matches
    after the tested match from receiving weight or entering the model.
    """
    matches = [
        match for match in historical_matches
        if _valid_match(match)
    ]
    if reference_date is not None:
        if isinstance(reference_date, str):
            reference_date = _parse_date(reference_date)
        matches = [
            match for match in matches
            if (
                _parse_date(match.get("utcDate", "")) is not None
                and _parse_date(match.get("utcDate", "")) < reference_date
            )
        ]
    if not matches:
        return None
    home_records = _team_records(
        home_team,
        matches,
        reference_date,
    )
    away_records = _team_records(
        away_team,
        matches,
        reference_date,
    )
    home_all = _summarize_records(home_records["all"])
    away_all = _summarize_records(away_records["all"])
    if not home_all or not away_all:
        return None
    league_home, league_away = _competition_averages(
        matches,
        reference_date,
    )
    home_venue = _summarize_records(home_records["home"])
    away_venue = _summarize_records(away_records["away"])
    home_attack = (
        home_venue["goals_for_per_game"]
        if home_venue
        else home_all["goals_for_per_game"]
    )
    home_defence = (
        home_venue["goals_against_per_game"]
        if home_venue
        else home_all["goals_against_per_game"]
    )
    away_attack = (
        away_venue["goals_for_per_game"]
        if away_venue
        else away_all["goals_for_per_game"]
    )
    away_defence = (
        away_venue["goals_against_per_game"]
        if away_venue
        else away_all["goals_against_per_game"]
    )
    home_weight = (
        home_venue["sample_weight"]
        if home_venue
        else home_all["sample_weight"]
    )
    away_weight = (
        away_venue["sample_weight"]
        if away_venue
        else away_all["sample_weight"]
    )
    home_attack = _blend_with_prior(
        home_attack,
        home_weight,
        league_home,
    )
    home_defence = _blend_with_prior(
        home_defence,
        home_weight,
        league_away,
    )
    away_attack = _blend_with_prior(
        away_attack,
        away_weight,
        league_away,
    )
    away_defence = _blend_with_prior(
        away_defence,
        away_weight,
        league_home,
    )
    home_attack_strength = min(
        1.50,
        max(0.65, home_attack / max(league_home, 0.2)),
    )
    home_defence_strength = min(
        1.50,
        max(0.65, home_defence / max(league_away, 0.2)),
    )
    away_attack_strength = min(
        1.50,
        max(0.65, away_attack / max(league_away, 0.2)),
    )
    away_defence_strength = min(
        1.50,
        max(0.65, away_defence / max(league_home, 0.2)),
    )
    home_xg = (
        league_home
        * (home_attack_strength ** 0.65)
        * (away_defence_strength ** 0.35)
    )
    away_xg = (
        league_away
        * (away_attack_strength ** 0.65)
        * (home_defence_strength ** 0.35)
    )
    return (
        round(min(3.50, max(0.25, home_xg)), 2),
        round(min(3.50, max(0.25, away_xg)), 2),
    )
def predict_expected_goals(
    home_team,
    away_team,
    competition_code="PL",
):
    if not home_team or not away_team:
        raise ValueError(
            "Enter both the home and away team names."
        )
    code = (
        competition_code.strip().upper()
        if competition_code
        else None
    )
    if not code:
        code = detect_competition(home_team, away_team)
    if not code:
        raise ValueError(
            f"Could not identify a competition for {home_team} "
            f"and {away_team}. Supply a competition code."
        )
    matches = list(get_competition_results(code, 100))
    if not matches:
        raise ValueError(
            f"No finished-match data is available for {code}."
        )
    home_found = _find_team_in_matches(home_team, matches)
    away_found = _find_team_in_matches(away_team, matches)
    # If team names are absent from the recent finished matches,
    # try the competition's team list.
    home_found = (
        home_found or find_team_in_competition(home_team, code)
    )
    away_found = (
        away_found or find_team_in_competition(away_team, code)
    )
    if not home_found or not away_found:
        raise ValueError(
            f"Could not match both teams in {code}. "
            "Check the team names, competition code and API access."
        )
    expected = _expected_goals_from_history(
        home_found.get("name", home_team),
        away_found.get("name", away_team),
        matches,
    )
    if not expected:
        raise ValueError(
            f"Insufficient finished-match statistics for "
            f"{home_team} and {away_team} in {code}."
        )
    return {
        "home_xg": expected[0],
        "away_xg": expected[1],
        "competition": code,
        "home_team": home_found.get("name", home_team),
        "away_team": away_found.get("name", away_team),
    }
# ============================================================
# HISTORICAL BACKTESTING
# ============================================================
def backtest_competition(
    competition_code="PL",
    limit=100,
    min_history=MIN_HISTORY_FOR_BACKTEST,
):
    """
    Backtest historical matches.
    Only matches earlier than each tested match are used to estimate
    its expected goals. The API's available history limits the result.
    Returns outcome accuracy, exact-score accuracy, Brier score,
    and average total-goals error.
    """
    code = (competition_code or "PL").strip().upper()
    matches = list(
        get_competition_results(code, limit)
    )
    matches = [
        match for match in matches
        if (
            _valid_match(match)
            and _parse_date(match.get("utcDate", "")) is not None
        )
    ]
    matches.sort(
        key=lambda match: match.get("utcDate", "")
    )
    tested = 0
    outcome_correct = 0
    score_correct = 0
    total_goal_error = 0.0
    brier_sum = 0.0
    skipped = 0
    for index, match in enumerate(matches):
        match_date = _parse_date(match.get("utcDate", ""))
        # Exclude the tested match and every later match.
        history = [
            previous for previous in matches[:index]
            if (
                _parse_date(previous.get("utcDate", "")) is not None
                and _parse_date(previous.get("utcDate", "")) < match_date
            )
        ]
        if len(history) < int(min_history):
            skipped += 1
            continue
        home = (match.get("homeTeam") or {}).get("name")
        away = (match.get("awayTeam") or {}).get("name")
        score = (
            (match.get("score") or {}).get("fullTime") or {}
        )
        actual_home = score.get("home")
        actual_away = score.get("away")
        if not home or not away:
            skipped += 1
            continue
        expected = _expected_goals_from_history(
            home,
            away,
            history,
            reference_date=match_date,
        )
        if not expected:
            skipped += 1
            continue
        home_xg, away_xg = expected
        scores = predict_score(home_xg, away_xg, max_goals=10)
        if not scores:
            skipped += 1
            continue
        predicted_home, predicted_away, _ = scores[0]
        actual_result = (
            "H" if actual_home > actual_away
            else "A" if actual_home < actual_away
            else "D"
        )
        probabilities = calculate_1x2_probabilities(
            home_xg,
            away_xg,
            max_goals=10,
        )
        predicted_result = max(
            [
                ("H", probabilities["home_win"]),
                ("D", probabilities["draw"]),
                ("A", probabilities["away_win"]),
            ],
            key=lambda item: item[1],
        )[0]
        if predicted_result == actual_result:
            outcome_correct += 1
        if (
            predicted_home == actual_home
            and predicted_away == actual_away
        ):
            score_correct += 1
        # Multiclass Brier score for the 1X2 probabilities.
        actual_vector = {
            "H": 1.0 if actual_result == "H" else 0.0,
            "D": 1.0 if actual_result == "D" else 0.0,
            "A": 1.0 if actual_result == "A" else 0.0,
        }
        brier_sum += sum(
            (
                probabilities[key] - actual_vector[key]
            ) ** 2
            for key in ("H", "D", "A")
        )
        total_goal_error += abs(
            (home_xg + away_xg) - (actual_home + actual_away)
        )
        tested += 1
    if tested == 0:
        return {
            "competition": code,
            "matches_tested": 0,
            "matches_skipped": skipped,
            "message": (
                "Not enough historical data to backtest this "
                "competition. Try a larger limit if your API plan "
                "allows it."
            ),
        }
    return {
        "competition": code,
        "matches_tested": tested,
        "matches_skipped": skipped,
        "outcome_accuracy": round(
            100 * outcome_correct / tested,
            2,
        ),
        "exact_score_accuracy": round(
            100 * score_correct / tested,
            2,
        ),
        "average_total_goals_error": round(
            total_goal_error / tested,
            3,
        ),
        "brier_score_1x2": round(
            brier_sum / tested,
            4,
        ),
    }
# ============================================================
# HEAD-TO-HEAD
# ============================================================
def get_head_to_head(
    home_team,
    away_team,
    competition_code="PL",
    limit=100,
):
    matches = list(
        get_competition_results(
            competition_code,
            limit,
        )
    )
    results = []
    for match in matches:
        home = match.get("homeTeam") or {}
        away = match.get("awayTeam") or {}
        direct_order = (
            _team_matches_query(home_team, home)
            and _team_matches_query(away_team, away)
        )
        reverse_order = (
            _team_matches_query(away_team, home)
            and _team_matches_query(home_team, away)
        )
        if not (direct_order or reverse_order):
            continue
        score = (
            (match.get("score") or {}).get("fullTime") or {}
        )
        results.append({
            "date": match.get("utcDate", ""),
            "home_team": home.get("name", ""),
            "away_team": away.get("name", ""),
            "home_goals": score.get("home"),
            "away_goals": score.get("away"),
        })
    return results