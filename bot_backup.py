import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from predictor import (
    get_available_leagues,
    get_upcoming_fixtures, get_football_data_fixtures, get_football_data_competitions
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ Welcome to DerbySignal AI!\n\n"
        "Your football analysis assistant.\n\n"
        "Commands:\n"
        "/leagues - Available leagues\n"
        "/fixtures LEAGUE_ID - Upcoming matches\n"
        "/predict HOME_GOALS AWAY_GOALS - Demo score model\n"
        "/analysis - Match analysis help\n"
        "/markets - Supported market ideas\n"
        "/help - Show commands"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def leagues(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌍 Loading football leagues...")

    result = get_available_leagues()

    if isinstance(result, dict) and "error" in result:
        await update.message.reply_text(str(result["error"]))
        return

    if not result:
        await update.message.reply_text("No leagues were returned by the API.")
        return

    lines = ["🌍 AVAILABLE LEAGUES\n"]

    for league in result[:40]:
        if isinstance(league, dict):
            lines.append(
                f"ID: {league.get('id', '?')} | "
                f"{league.get('name', 'Unknown')} | "
                f"{league.get('country', 'Unknown')}"
            )

    message = "\n".join(lines)

    for start_index in range(0, len(message), 3500):
        await update.message.reply_text(message[start_index:start_index + 3500])


async def fixtures(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Please provide a competition code.\n\n"
            "Examples:\n"
            "/fixtures PL - English Premier League\n"
            "/fixtures PD - Spanish La Liga\n"
            "/fixtures BL1 - German Bundesliga\n"
            "/fixtures SA - Italian Serie A\n"
            "/fixtures FL1 - French Ligue 1"
        )
        return

    competition_code = context.args[0].upper()

    await update.message.reply_text(
        f"Fetching scheduled matches for {competition_code}..."
    )

    result = get_football_data_fixtures(competition_code)

    if isinstance(result, dict) and "error" in result:
        await update.message.reply_text(
            f"Could not fetch matches:\n{result['error']}"
        )
        return

    if not result:
        await update.message.reply_text(
            "No scheduled matches were found."
        )
        return

    message = f"⚽ Upcoming Matches — {competition_code}\n\n"

    for match in result[:10]:
        message += (
            f"🏆 {match['league']}\n"
            f"🏠 {match['home']} vs {match['away']}\n"
            f"📅 {match['date']}\n\n"
        )

    await update.message.reply_text(message)


async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ Score prediction is not connected to real match statistics yet.\n\n"
        "The current predictor uses demo expected-goal values, so it should "
        "not be treated as a reliable match prediction."
    )


async def analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 MATCH ANALYSIS\n\n"
        "Send the home team, away team, league and match date. "
        "We can then work on connecting team form, goals, home advantage "
        "and other available statistics."
    )


async def markets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ MARKET OPTIONS TO DEVELOP\n\n"
        "• Match result (1X2)\n"
        "• Double chance\n"
        "• Over/under goals\n"
        "• Both teams to score\n"
        "• Correct score\n"
        "• Draw no bet\n"
        "• Half-time result\n"
        "• Half-time/full-time\n\n"
        "These are planned analysis options, not live odds or guaranteed picks."
    )


def main():
 async def competitions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌍 Loading available competitions...")

    result = get_football_data_competitions()

    if isinstance(result, dict) and "error" in result:
        await update.message.reply_text(
            f"Could not load competitions:\n{result['error']}"
        )
        return

    if not result:
        await update.message.reply_text("No competitions were returned.")
        return

    message = "🌍 AVAILABLE COMPETITIONS\n\n"

    for competition in result:
        message += (
            f"🏆 {competition['name']}\n"
            f"🌐 Country/Region: {competition['area']}\n"
            f"🔑 Code: {competition['code']}\n\n"
        )

    for start in range(0, len(message), 3500):
        await update.message.reply_text(message[start:start + 3500])   
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing. Add it in Codespaces Secrets."
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("leagues", leagues))
    app.add_handler(CommandHandler("fixtures", fixtures))
    app.add_handler(CommandHandler("predict", predict))
    app.add_handler(CommandHandler("analysis", analysis))
    app.add_handler(CommandHandler("markets", markets))
    app.add_handler(CommandHandler("competitions", competitions))
    
    print("DerbySignal AI is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()