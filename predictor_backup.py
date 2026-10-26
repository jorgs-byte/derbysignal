from math import exp, factorial
import os
import requests

def poisson_probability(expected_goals, goals):
    """Calculate the probability of a team scoring a given number of goals."""
    if expected_goals < 0 or goals < 0:
        return 0.0

    return (
        exp(-expected_goals)
        * expected_goals**goals
        / factorial(goals)
    )


def predict_score(home_xg, away_xg, max_goals=6):
    """Estimate probabilities for possible football scorelines."""

    if not (0.05 <= home_xg <= 8 and 0.05 <= away_xg <= 8):
        raise ValueError("Expected goals must be between 0.05 and 8.")

    scores = []

    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            home_prob = poisson_probability(home_xg, home_goals)
            away_prob = poisson_probability(away_xg, away_goals)

            probability = home_prob * away_prob

            scores.append(
                (home_goals, away_goals, probability)
            )

    return sorted(scores, key=lambda item: item[2], reverse=True)


def main():
    # Demonstration values only; not real match statistics.
    home_xg = 1.5
    away_xg = 1.0

    predictions = predict_score(home_xg, away_xg)

    print("\n⚽ DERBYSIGNAL AI — SCORE PROBABILITIES")
    print(f"Home expected goals: {home_xg}")
    print(f"Away expected goals: {away_xg}")
    print("\nMost likely scorelines:")

    for home, away, probability in predictions[:5]:
        print(f"{home}-{away}: {probability:.2%}")


if __name__ == "__main__":
    main()
def get_available_leagues():
    """Get leagues available through the football API."""
    api_key = os.getenv("FOOTBALL_API_KEY")

    if not api_key:
        return {"error": "Football API key is missing."}

    url = "https://v3.football.api-sports.io/leagues"
    headers = {"x-apisports-key": api_key}

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if data.get("errors"):
            return {"error": str(data["errors"])}

        leagues = []

        for item in data.get("response", []):
            league = item["league"]
            country = item.get("country", {}).get("name", "Unknown")
            leagues.append({
                "id": league["id"],
                "name": league["name"],
                "country": country
            })

        return leagues

    except requests.RequestException as exc:
        return {"error": f"Could not fetch leagues: {exc}"}

def get_upcoming_fixtures(league_id, season=2026):
    """Fetch upcoming fixtures for a selected league."""

    api_key = os.getenv("FOOTBALL_API_KEY")

    if not api_key:
        return {"error": "Football API key is missing."}

    url = "https://v3.football.api-sports.io/fixtures"

    headers = {
        "x-apisports-key": api_key
    }

    params = {
        "league": league_id,
        "season": season,
        "next": 10
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20
        )

        response.raise_for_status()
        data = response.json()

        if data.get("errors"):
            return {"error": str(data["errors"])}

        fixtures = []

        for item in data.get("response", []):
            fixtures.append({
                "id": item["fixture"]["id"],
                "home": item["teams"]["home"]["name"],
                "away": item["teams"]["away"]["name"],
                "date": item["fixture"]["date"],
                "league": item["league"]["name"],
                "country": item["league"].get("country", "")
            })

        return fixtures

    except requests.RequestException as exc:
        return {"error": f"Could not fetch fixtures: {exc}"} 
def get_football_data_fixtures(competition_code="PL"):
    token = os.getenv("FOOTBALL_DATA_TOKEN")

    if not token:
        return {"error": "FOOTBALL_DATA_TOKEN is missing. Check your Codespaces secrets."}

    url = f"https://api.football-data.org/v4/competitions/{competition_code}/matches"

    headers = {"X-Auth-Token": token}
    params = {"status": "SCHEDULED"}

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20
        )

        if response.status_code != 200:
            try:
                details = response.json()
            except ValueError:
                details = response.text

            return {
                "error": f"Football-data.org returned HTTP {response.status_code}: {details}"
            }

        data = response.json()
        matches = data.get("matches", [])

        if not matches:
            return {"error": f"No scheduled matches found for competition {competition_code}."}

        fixtures = []

        for match in matches:
            home_team = match.get("homeTeam", {}).get("name", "Unknown")
            away_team = match.get("awayTeam", {}).get("name", "Unknown")
            match_date = match.get("utcDate", "Date unavailable")

            fixtures.append({
                "home": home_team,
                "away": away_team,
                "date": match_date,
                "league": match.get("competition", {}).get("name", competition_code)
            })

        return fixtures

    except requests.RequestException as error:
        return {"error": f"Could not connect to football-data.org: {error}"}  
def get_football_data_competitions():
    token = os.getenv("FOOTBALL_DATA_TOKEN")

    if not token:
        return {"error": "FOOTBALL_DATA_TOKEN is missing."}

    url = "https://api.football-data.org/v4/competitions"
    headers = {"X-Auth-Token": token}

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        if response.status_code != 200:
            return {
                "error": f"API error {response.status_code}: {response.text}"
            }

        data = response.json()
        competitions = data.get("competitions", [])

        return [
            {
                "name": competition.get("name", "Unknown"),
                "code": competition.get("code", "N/A"),
                "area": competition.get("area", {}).get("name", "Unknown")
            }
            for competition in competitions
        ]

    except requests.RequestException as error:
        return {"error": f"Connection failed: {error}"}   
def predict_match_score(home_goals, away_goals):
    from math import exp, factorial

    def poisson_probability(goals, expected_goals):
        if expected_goals < 0:
            return 0.0

        return (
            exp(-expected_goals)
            * (expected_goals ** goals)
            / factorial(goals)
        )

    best_score = (0, 0)
    best_probability = 0.0

    for home in range(6):
        for away in range(6):
            probability = (
                poisson_probability(home, home_goals)
                * poisson_probability(away, away_goals)
            )

            if probability > best_probability:
                best_probability = probability
                best_score = (home, away)

    return {
        "home_score": best_score[0],
        "away_score": best_score[1],
        "probability": best_probability,
    }
def get_competition_results(competition_code="PL"):
    """Retrieve recent completed matches from football-data.org."""
    import os
    import requests

    token = os.getenv("FOOTBALL_DATA_TOKEN")

    if not token:
        print("Error: FOOTBALL_DATA_TOKEN is missing.")
        return []

    url = (
        "https://api.football-data.org/v4/"
        f"competitions/{competition_code}/matches"
    )

    headers = {"X-Auth-Token": token}
    params = {"status": "FINISHED"}

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        results = []

        for match in data.get("matches", []):
            home_team = match.get("homeTeam", {}).get("name")
            away_team = match.get("awayTeam", {}).get("name")
            score = match.get("score", {}).get("fullTime", {})

            home_goals = score.get("home")
            away_goals = score.get("away")

            if (
                home_team
                and away_team
                and home_goals is not None
                and away_goals is not None
            ):
                results.append({
                    "home": home_team,
                    "away": away_team,
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "date": match.get("utcDate"),
                })

        return results

    except requests.RequestException as error:
        print(f"Could not retrieve match results: {error}")
        return []   
def calculate_team_strength(competition_code="PL"):
    """Calculate team scoring and conceding averages from completed matches."""

    matches = get_competition_results(competition_code)

    if not matches:
        return {}

    teams = {}

    for match in matches:
        home = match["home"]
        away = match["away"]
        home_goals = match["home_goals"]
        away_goals = match["away_goals"]

        for team in (home, away):
            if team not in teams:
                teams[team] = {
                    "played": 0,
                    "goals_scored": 0,
                    "goals_conceded": 0,
                }

        teams[home]["played"] += 1
        teams[home]["goals_scored"] += home_goals
        teams[home]["goals_conceded"] += away_goals

        teams[away]["played"] += 1
        teams[away]["goals_scored"] += away_goals
        teams[away]["goals_conceded"] += home_goals

    for stats in teams.values():
        played = stats["played"]

        stats["avg_scored"] = round(
            stats["goals_scored"] / played, 2
        )
        stats["avg_conceded"] = round(
            stats["goals_conceded"] / played, 2
        )

    return teams 
def predict_expected_goals(home_team, away_team, competition_code="PL"):
    """
    Estimate expected goals using completed matches.
    Team names are matched without case sensitivity.
    """
    stats = calculate_team_strength(competition_code)
    if not stats:
        raise ValueError(
            f"No team statistics available for competition {competition_code}."
        )
    def normalize(name):
        name = name.lower().strip()
        for suffix in (" fc", " afc", " cf", " sc"):
            name = name.replace(suffix, "")
        return " ".join(name.split())
    def find_team(team_name):
        wanted = normalize(team_name)
        for actual_name, team_stats in stats.items():
            if normalize(actual_name) == wanted:
                return actual_name, team_stats
        return None, None
    actual_home, home_stats = find_team(home_team)
    actual_away, away_stats = find_team(away_team)
    if home_stats is None or away_stats is None:
        missing = []
        if home_stats is None:
            missing.append(home_team)
        if away_stats is None:
            missing.append(away_team)
        available = ", ".join(list(stats.keys())[:15])
        raise ValueError(
            f"Statistics not found for: {', '.join(missing)}. "
            f"Some available teams: {available}"
        )
    home_xg = (
        home_stats["avg_scored"] + away_stats["avg_conceded"]
    ) / 2
    away_xg = (
        away_stats["avg_scored"] + home_stats["avg_conceded"]
    ) / 2
    return round(max(0.1, home_xg), 2), round(max(0.1, away_xg), 2)                   