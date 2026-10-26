"""
DerbySignal AI — Expandable Betting Markets

New betting markets can be added here without rewriting bot.py.
"""

from math import exp, factorial


def poisson_probability(expected_goals, goals):
    """Probability of a team scoring an exact number of goals."""
    if expected_goals < 0 or goals < 0:
        return 0.0

    return (
        exp(-expected_goals)
        * (expected_goals ** goals)
        / factorial(goals)
    )


def calculate_markets(home_xg, away_xg, max_goals=10):
    """
    Calculate probabilities for multiple football betting markets.

    Inputs:
        home_xg: expected goals for the home team
        away_xg: expected goals for the away team

    Returns:
        A dictionary of market names and probabilities.
    """
    if home_xg < 0 or away_xg < 0:
        raise ValueError("Expected goals cannot be negative.")

    home_probs = [
        poisson_probability(home_xg, goals)
        for goals in range(max_goals + 1)
    ]

    away_probs = [
        poisson_probability(away_xg, goals)
        for goals in range(max_goals + 1)
    ]

    home_win = 0.0
    draw = 0.0
    away_win = 0.0
    over_15 = 0.0
    over_25 = 0.0
    over_35 = 0.0
    btts_yes = 0.0
    home_clean_sheet = 0.0
    away_clean_sheet = 0.0
    home_scores_2_plus = 0.0
    away_scores_2_plus = 0.0

    correct_scores = []

    for home_goals, home_prob in enumerate(home_probs):
        for away_goals, away_prob in enumerate(away_probs):
            probability = home_prob * away_prob

            if home_goals > away_goals:
                home_win += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away_win += probability

            total_goals = home_goals + away_goals

            if total_goals >= 2:
                over_15 += probability
            if total_goals >= 3:
                over_25 += probability
            if total_goals >= 4:
                over_35 += probability

            if home_goals > 0 and away_goals > 0:
                btts_yes += probability

            if away_goals == 0:
                home_clean_sheet += probability
            if home_goals == 0:
                away_clean_sheet += probability

            if home_goals >= 2:
                home_scores_2_plus += probability
            if away_goals >= 2:
                away_scores_2_plus += probability

            correct_scores.append(
                {
                    "home_score": home_goals,
                    "away_score": away_goals,
                    "probability": probability,
                }
            )

    double_chance_1x = home_win + draw
    double_chance_x2 = draw + away_win
    double_chance_12 = home_win + away_win

    markets = {
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "double_chance_1x": double_chance_1x,
        "double_chance_x2": double_chance_x2,
        "double_chance_12": double_chance_12,
        "over_1_5": over_15,
        "under_1_5": 1.0 - over_15,
        "over_2_5": over_25,
        "under_2_5": 1.0 - over_25,
        "over_3_5": over_35,
        "under_3_5": 1.0 - over_35,
        "btts_yes": btts_yes,
        "btts_no": 1.0 - btts_yes,
        "home_clean_sheet": home_clean_sheet,
        "away_clean_sheet": away_clean_sheet,
        "home_scores_2_plus": home_scores_2_plus,
        "away_scores_2_plus": away_scores_2_plus,
    }

    correct_scores.sort(
        key=lambda item: item["probability"],
        reverse=True,
    )

    markets["top_10_correct_scores"] = correct_scores[:10]

    return markets