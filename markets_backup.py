from math import exp, factorial


def poisson_probability(expected_goals, goals):
    if expected_goals < 0 or goals < 0:
        return 0.0

    return (
        exp(-expected_goals)
        * expected_goals ** goals
        / factorial(goals)
    )


def calculate_markets(home_xg, away_xg, max_goals=12):
    if home_xg < 0 or away_xg < 0:
        raise ValueError("Expected goals cannot be negative.")

    home_probs = [
        poisson_probability(home_xg, g)
        for g in range(max_goals + 1)
    ]

    away_probs = [
        poisson_probability(away_xg, g)
        for g in range(max_goals + 1)
    ]

    home_win = 0.0
    draw = 0.0
    away_win = 0.0
    over_probs = {line: 0.0 for line in (1.5, 2.5, 3.5, 4.5, 5.5)}
    btts_yes = 0.0
    home_scores = {line: 0.0 for line in (0.5, 1.5, 2.5)}
    away_scores = {line: 0.0 for line in (0.5, 1.5, 2.5)}
    correct_scores = []

    home_clean_sheet = away_probs[0]
    away_clean_sheet = home_probs[0]

    for hg, hp in enumerate(home_probs):
        for ag, ap in enumerate(away_probs):
            p = hp * ap
            total = hg + ag

            if hg > ag:
                home_win += p
            elif hg == ag:
                draw += p
            else:
                away_win += p

            for line in over_probs:
                if total > line:
                    over_probs[line] += p

            if hg > 0 and ag > 0:
                btts_yes += p

            for line in home_scores:
                if hg > line:
                    home_scores[line] += p
                if ag > line:
                    away_scores[line] += p

            correct_scores.append({
                "home_score": hg,
                "away_score": ag,
                "probability": p,
            })

    total_probability = home_win + draw + away_win

    if total_probability > 0:
        home_win /= total_probability
        draw /= total_probability
        away_win /= total_probability

    markets = {
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "double_chance_1x": home_win + draw,
        "double_chance_x2": draw + away_win,
        "double_chance_12": home_win + away_win,
        "btts_yes": btts_yes,
        "btts_no": 1.0 - btts_yes,
        "home_clean_sheet": home_clean_sheet,
        "home_no_clean_sheet": 1.0 - home_clean_sheet,
        "away_clean_sheet": away_clean_sheet,
        "away_no_clean_sheet": 1.0 - away_clean_sheet,
    }

    for line, probability in over_probs.items():
        key = str(line).replace(".", "_")
        markets[f"over_{key}"] = probability
        markets[f"under_{key}"] = 1.0 - probability

    for line, probability in home_scores.items():
        key = str(line).replace(".", "_")
        markets[f"home_over_{key}_goals"] = probability
        markets[f"home_under_{key}_goals"] = 1.0 - probability

    for line, probability in away_scores.items():
        key = str(line).replace(".", "_")
        markets[f"away_over_{key}_goals"] = probability
        markets[f"away_under_{key}_goals"] = 1.0 - probability

    # Draw No Bet probabilities conditional on a decisive result.
    decisive_probability = home_win + away_win

    if decisive_probability > 0:
        markets["home_draw_no_bet"] = home_win / decisive_probability
        markets["away_draw_no_bet"] = away_win / decisive_probability
    else:
        markets["home_draw_no_bet"] = 0.0
        markets["away_draw_no_bet"] = 0.0

    correct_scores.sort(
        key=lambda item: item["probability"],
        reverse=True,
    )

    markets["top_10_correct_scores"] = correct_scores[:10]

    return markets