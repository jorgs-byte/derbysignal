import logging
import os
import re

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from predictor import (
    get_football_data_fixtures,
    get_football_data_competitions,
    predict_expected_goals,
    predict_score,
    get_team_analysis,
    get_head_to_head,
    detect_competition,
)

from markets import calculate_markets, format_markets


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_COMPETITION = "PL"

COMPETITION_CODES = {
    "PL", "BL1", "SA", "FL1", "PD", "PPL",
    "DED", "CL", "BSA", "CLI", "EC", "WC",
}


def parse_match(args):
    if not args:
        raise ValueError(
            "Enter two teams, for example:\n"
            "/predict Bayern vs Dortmund"
        )

    parts = list(args)
    competition_code = None

    if parts and parts[0].upper() in COMPETITION_CODES:
        competition_code = parts.pop(0).upper()

    text = " ".join(parts)

    match = re.split(
        r"\s+vs\s+",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )

    if len(match) != 2:
        raise ValueError(
            "Separate the teams with 'vs'.\n"
            "Example: /predict Bayern vs Dortmund"
        )

    home = match[0].strip()
    away = match[1].strip()

    if not home or not away:
        raise ValueError("Please enter both team names.")

    return competition_code, home, away


def get_match_details(args):
    requested_code, home, away = parse_match(args)

    code = detect_competition(
        home,
        away,
        requested_code,
    )

    if not code:
        raise ValueError(
            f"Couldn't identify a competition containing both "
            f"{home} and {away}.\n\n"
            "Try teams from the same competition, such as:\n"
            "/predict BL1 Bayern vs Dortmund\n"
            "/predict SA Inter vs Juventus"
        )

    return code, home, away


def get_xg(home, away, code):
    """Convert the predictor's dictionary into two numbers."""

    result = predict_expected_goals(home, away, code)

    if isinstance(result, dict):
        home_xg = float(result["home_xg"])
        away_xg = float(result["away_xg"])
    elif isinstance(result, (tuple, list)) and len(result) >= 2:
        home_xg = float(result[0])
        away_xg = float(result[1])
    else:
        raise ValueError(
            "The predictor returned an unexpected expected-goals format."
        )

    return home_xg, away_xg


def get_score_rows(home_xg, away_xg):
    """Support both dictionary and tuple score formats."""

    raw_scores = predict_score(home_xg, away_xg, 6)
    rows = []

    for item in raw_scores:
        if isinstance(item, dict):
            hg = item.get("home_goals")
            ag = item.get("away_goals")
            probability = item.get("probability")

            if hg is None or ag is None or probability is None:
                score_text = item.get("score", "")
                score_parts = score_text.split("-")

                if len(score_parts) != 2:
                    continue

                hg, ag = map(int, score_parts)
                probability = item.get("probability", 0)

        else:
            if len(item) < 3:
                continue

            hg, ag, probability = item[0], item[1], item[2]

        rows.append((int(hg), int(ag), float(probability)))

    rows.sort(key=lambda row: row[2], reverse=True)
    return rows


def percentage(value):
    return f"{value:.1%}"


def stat_value(stats, *keys, default=None):
    for key in keys:
        if key in stats and stats[key] is not None:
            return stats[key]
    return default


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = (
        "⚽ Welcome to DerbySignal AI!\n\n"
        "Your football prediction assistant.\n\n"
        "Available commands:\n"
        "/competitions - Available competitions\n"
        "/fixtures [CODE] - Upcoming fixtures\n"
        "/predict Bayern vs Dortmund - Predict a match\n"
        "/analysis Bayern vs Dortmund - Analyse a match\n"
        "/markets Bayern vs Dortmund - Betting markets\n"
        "/help - Show help\n\n"
        "Predictions are statistical estimates, not guarantees."
    )

    await update.message.reply_text(message)


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = (
        "📘 DerbySignal AI Help\n\n"
        "Commands:\n"
        "/competitions\n"
        "/fixtures PL\n"
        "/predict BL1 Bayern vs Dortmund\n"
        "/analysis SA Inter vs Juventus\n"
        "/markets PL Arsenal vs Chelsea\n\n"
        "Put the competition code first when needed.\n"
        "Use 'vs' between the two teams.\n\n"
        "Predictions are estimates, not guarantees."
    )

    await update.message.reply_text(message)


async def competitions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        comps = get_football_data_competitions()

        if not comps:
            await update.message.reply_text(
                "No competitions were returned by the API."
            )
            return

        lines = ["🏆 Available competitions:\n"]

        for comp in comps[:100]:
            code = comp.get("code") or "No code"
            name = comp.get("name") or "Unknown competition"
            lines.append(f"{code} - {name}")

        await update.message.reply_text("\n".join(lines))

    except Exception as exc:
        logger.exception("Competition lookup failed")
        await update.message.reply_text(
            f"Couldn't load competitions: {exc}"
        )


async def fixtures(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    code = (
        context.args[0].upper()
        if context.args
        else DEFAULT_COMPETITION
    )

    try:
        matches = get_football_data_fixtures(code)

        if not matches:
            await update.message.reply_text(
                f"No upcoming fixtures were found for {code}."
            )
            return

        lines = [f"📅 Upcoming fixtures ({code}):\n"]

        for match in matches[:15]:
            home = (match.get("homeTeam") or {}).get("name", "Home")
            away = (match.get("awayTeam") or {}).get("name", "Away")
            date = (match.get("utcDate") or "")[:10]
            lines.append(f"{date}: {home} vs {away}")

        await update.message.reply_text("\n".join(lines))

    except Exception as exc:
        logger.exception("Fixture lookup failed")
        await update.message.reply_text(
            f"Couldn't load fixtures for {code}: {exc}"
        )


async def predict(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        code, home, away = get_match_details(context.args)

        home_xg, away_xg = get_xg(home, away, code)
        scores = get_score_rows(home_xg, away_xg)[:5]

        lines = [
            "⚽ DerbySignal AI Prediction",
            f"Competition: {code}",
            f"Match: {home} vs {away}",
            "",
            f"{home} expected goals: {home_xg:.2f}",
            f"{away} expected goals: {away_xg:.2f}",
            "",
            "Top predicted scores:",
        ]

        for hg, ag, probability in scores:
            lines.append(
                f"{hg}-{ag}: {percentage(probability)}"
            )

        lines.extend([
            "",
            "Probabilities are model estimates, not guarantees.",
        ])

        await update.message.reply_text("\n".join(lines))

    except Exception as exc:
        logger.exception("Prediction failed")
        await update.message.reply_text(
            f"Prediction error: {exc}"
        )


async def analysis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        code, home, away = get_match_details(context.args)

        home_stats = get_team_analysis(home, code)
        away_stats = get_team_analysis(away, code)

        if home_stats.get("error") or away_stats.get("error"):
            raise ValueError(
                home_stats.get("error")
                or away_stats.get("error")
            )

        meetings = get_head_to_head(home, away, code)

        home_matches = stat_value(
            home_stats, "matches", "games", default=0
        )
        home_scored = stat_value(
            home_stats, "goals_scored", "goals_for", default=0
        )
        home_conceded = stat_value(
            home_stats, "goals_conceded", "goals_against", default=0
        )
        home_average = stat_value(
            home_stats, "average_scored", "goals_for_per_game", default=0
        )

        away_matches = stat_value(
            away_stats, "matches", "games", default=0
        )
        away_scored = stat_value(
            away_stats, "goals_scored", "goals_for", default=0
        )
        away_conceded = stat_value(
            away_stats, "goals_conceded", "goals_against", default=0
        )
        away_average = stat_value(
            away_stats, "average_scored", "goals_for_per_game", default=0
        )

        lines = [
            "📊 DerbySignal AI Match Analysis",
            f"Competition: {code}",
            f"Match: {home} vs {away}",
            "",
            f"{home}:",
            f"Matches in available data: {home_matches}",
            f"Goals scored: {home_scored}",
            f"Goals conceded: {home_conceded}",
            f"Average scored per match: {float(home_average):.2f}",
            "",
            f"{away}:",
            f"Matches in available data: {away_matches}",
            f"Goals scored: {away_scored}",
            f"Goals conceded: {away_conceded}",
            f"Average scored per match: {float(away_average):.2f}",
            "",
            f"Head-to-head matches found: {len(meetings)}",
            "",
            "Statistics depend on data available from the provider.",
        ]

        await update.message.reply_text("\n".join(lines))

    except Exception as exc:
        logger.exception("Analysis failed")
        await update.message.reply_text(
            f"Analysis error: {exc}"
        )


async def markets(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        code, home, away = get_match_details(context.args)

        home_xg, away_xg = get_xg(home, away, code)

        results = calculate_markets(home_xg, away_xg)
        formatted = format_markets(results)

        message = (
            "📈 DerbySignal AI Markets\n"
            f"Competition: {code}\n"
            f"Match: {home} vs {away}\n\n"
            f"Home expected goals: {home_xg:.2f}\n"
            f"Away expected goals: {away_xg:.2f}\n\n"
            f"{formatted}\n\n"
            "Markets are model estimates, not guarantees."
        )

        for start_index in range(0, len(message), 4000):
            await update.message.reply_text(
                message[start_index:start_index + 4000]
            )

    except Exception as exc:
        logger.exception("Market calculation failed")
        await update.message.reply_text(
            f"Markets error: {exc}"
        )


def main():
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing from your environment secrets."
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("competitions", competitions))
    app.add_handler(CommandHandler("fixtures", fixtures))
    app.add_handler(CommandHandler("predict", predict))
    app.add_handler(CommandHandler("analysis", analysis))
    app.add_handler(CommandHandler("markets", markets))

    logger.info("DerbySignal AI is starting")
    app.run_polling()


if __name__ == "__main__":
    main()