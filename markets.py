from math import exp, factorial


def _number(value, name):
    """Convert expected goals into a valid number."""
    if isinstance(value, dict):
        for key in ("xg", "expected_goals", "home_xg", "away_xg"):
            if key in value:
                return _number(value[key], name)
        raise ValueError(f"Cannot read {name} from the supplied data.")

    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number.")

    if result < 0:
        raise ValueError(f"{name} cannot be negative.")

    return result


def _poisson(mean, maximum=10):
    """Calculate Poisson probabilities for goal counts."""
    if mean == 0:
        return [1.0] + [0.0] * maximum

    values = [
        exp(-mean) * (mean ** goals) / factorial(goals)
        for goals in range(maximum + 1)
    ]

    total = sum(values)
    return [value / total for value in values]


def calculate_markets(home_xg, away_xg):
    """Calculate football goal-market probabilities."""

    home_xg = _number(home_xg, "Home xG")
    away_xg = _number(away_xg, "Away xG")

    maximum = 10
    home_dist = _poisson(home_xg, maximum)
    away_dist = _poisson(away_xg, maximum)

    grid = {
        (home, away): home_dist[home] * away_dist[away]
        for home in range(maximum + 1)
        for away in range(maximum + 1)
    }

    def probability(condition):
        return sum(
            p for (home, away), p in grid.items()
            if condition(home, away)
        )

    home_win = probability(lambda h, a: h > a)
    draw = probability(lambda h, a: h == a)
    away_win = probability(lambda h, a: h < a)
    btts = probability(lambda h, a: h > 0 and a > 0)

    result = {
        "1X2": {
            "Home Win": home_win,
            "Draw": draw,
            "Away Win": away_win,
        },
        "Double Chance": {
            "1X": home_win + draw,
            "X2": draw + away_win,
            "12": home_win + away_win,
        },
        "Draw No Bet": {
            "Home": home_win / (home_win + away_win)
            if home_win + away_win else 0,
            "Away": away_win / (home_win + away_win)
            if home_win + away_win else 0,
        },
        "Over/Under Goals": {},
        "BTTS": {
            "Yes": btts,
            "No": 1 - btts,
        },
        "Team Goals": {
            "Home": {},
            "Away": {},
        },
        "Clean Sheet": {
            "Home": probability(lambda h, a: a == 0),
            "Away": probability(lambda h, a: h == 0),
        },
        "Win to Nil": {
            "Home": probability(lambda h, a: h > a and a == 0),
            "Away": probability(lambda h, a: a > h and h == 0),
        },
        "Goal Ranges": {},
        "Odd/Even Goals": {},
        "Winning Margin": {},
        "Half-Time Result": {},
        "Half-Time Over/Under": {},
        "Half-Time/Full-Time": {},
        "Correct Scores": [],
    }

    # Total match goals.
    for line in (0.5, 1.5, 2.5, 3.5, 4.5, 5.5):
        over = probability(
            lambda h, a, line=line: h + a > line
        )
        result["Over/Under Goals"][str(line)] = {
            "Over": over,
            "Under": 1 - over,
        }

    # Individual team goals.
    for side, distribution in (
        ("Home", home_dist),
        ("Away", away_dist),
    ):
        for line in (0.5, 1.5, 2.5, 3.5):
            over = sum(
                p for goals, p in enumerate(distribution)
                if goals > line
            )
            result["Team Goals"][side][str(line)] = {
                "Over": over,
                "Under": 1 - over,
            }

    # Total goal ranges.
    ranges = (
        ("0-1", lambda total: total <= 1),
        ("2-3", lambda total: 2 <= total <= 3),
        ("4-5", lambda total: 4 <= total <= 5),
        ("6+", lambda total: total >= 6),
    )

    for label, condition in ranges:
        result["Goal Ranges"][label] = probability(
            lambda h, a, condition=condition: condition(h + a)
        )

    even = probability(lambda h, a: (h + a) % 2 == 0)
    result["Odd/Even Goals"] = {
        "Odd": 1 - even,
        "Even": even,
    }

    # Winning margins.
    result["Winning Margin"] = {
        "Home by 1": probability(lambda h, a: h - a == 1),
        "Home by 2": probability(lambda h, a: h - a == 2),
        "Home by 3+": probability(lambda h, a: h - a >= 3),
        "Draw": draw,
        "Away by 1": probability(lambda h, a: a - h == 1),
        "Away by 2": probability(lambda h, a: a - h == 2),
        "Away by 3+": probability(lambda h, a: a - h >= 3),
    }

    # Approximate half-time model.
    half_home = _poisson(home_xg / 2, maximum)
    half_away = _poisson(away_xg / 2, maximum)

    half_grid = {
        (h, a): half_home[h] * half_away[a]
        for h in range(maximum + 1)
        for a in range(maximum + 1)
    }

    def half_probability(condition):
        return sum(
            p for (h, a), p in half_grid.items()
            if condition(h, a)
        )

    result["Half-Time Result"] = {
        "Home": half_probability(lambda h, a: h > a),
        "Draw": half_probability(lambda h, a: h == a),
        "Away": half_probability(lambda h, a: h < a),
    }

    for line in (0.5, 1.5, 2.5):
        over = half_probability(
            lambda h, a, line=line: h + a > line
        )
        result["Half-Time Over/Under"][str(line)] = {
            "Over": over,
            "Under": 1 - over,
        }

    # Half-time/full-time combinations.
    combinations = {}

    for hh in range(maximum + 1):
        for ha in range(maximum + 1):
            ht_probability = half_home[hh] * half_away[ha]

            ht = (
                "1" if hh > ha
                else "X" if hh == ha
                else "2"
            )

            for sh in range(maximum + 1):
                for sa in range(maximum + 1):
                    second_probability = half_home[sh] * half_away[sa]
                    full_home = hh + sh
                    full_away = ha + sa

                    ft = (
                        "1" if full_home > full_away
                        else "X" if full_home == full_away
                        else "2"
                    )

                    key = f"{ht}/{ft}"
                    combinations[key] = (
                        combinations.get(key, 0)
                        + ht_probability * second_probability
                    )

    result["Half-Time/Full-Time"] = combinations

    # Ten most likely correct scores.
    result["Correct Scores"] = sorted(
        [
            {
                "score": f"{h}-{a}",
                "probability": p,
            }
            for (h, a), p in grid.items()
        ],
        key=lambda item: item["probability"],
        reverse=True,
    )[:10]

    # Compatibility with older bot integrations.
    result["home_win"] = home_win
    result["draw"] = draw
    result["away_win"] = away_win
    result["btts_yes"] = btts

    return result


def format_markets(markets):
    """Format market probabilities safely for Telegram."""

    lines = []
    ignored = {"home_win", "draw", "away_win", "btts_yes"}

    def add_values(values, indent=2):
        for key, value in values.items():
            if isinstance(value, dict):
                lines.append(" " * indent + f"{key}:")
                add_values(value, indent + 2)

            elif isinstance(value, (int, float)):
                lines.append(
                    " " * indent + f"{key}: {value * 100:.1f}%"
                )

            else:
                lines.append(" " * indent + f"{key}: {value}")

    for section, values in markets.items():
        if section in ignored:
            continue

        lines.append(f"\n{section.upper()}")

        if isinstance(values, list):
            for item in values:
                lines.append(
                    f"  {item['score']}: "
                    f"{item['probability'] * 100:.1f}%"
                )

        elif isinstance(values, dict):
            add_values(values)

    return "\n".join(lines)