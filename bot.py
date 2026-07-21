import os
import csv
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging
import requests
from datetime import date
from groq import Groq

# Load environment variables from the .env file
load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ✅ SECURELY LOAD KEYS FROM .ENV FILE
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    raise ValueError("⚠️ Missing API keys! Please check your Environment Variables.")

ai_client = Groq(api_key=GROQ_API_KEY)

# ==========================================
# MODULE 1: API FETCHERS 
# ==========================================
def fetch_thesportsdb():
    today = date.today().strftime('%Y-%m-%d')
    url = f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={today}&s=Soccer"
    try:
        response = requests.get(url).json()
        events = response.get('events', [])
        if not events: return []
        return [{"home": e['strHomeTeam'], "away": e['strAwayTeam'], "time": e.get('strTime', 'TBD')} for e in events[:5]]
    except Exception as e:
        print(f"API Fetch Error: {e}")
        return []

# ==========================================
# MODULE 2: DATA LOGGING (No Pandas needed!)
# ==========================================
def log_prediction_to_csv(home, away, prediction):
    file_exists = os.path.isfile('paper_trading_log.csv')
    with open('paper_trading_log.csv', 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Date', 'Home Team', 'Away Team', 'AI Prediction', 'Result'])
        writer.writerow([date.today(), home, away, prediction, 'Pending'])

# ==========================================
# MODULE 3: AI ANALYSIS 
# ==========================================
def ask_ai_for_predictions(matches):
    matches_text = "\n".join([f"- {m['home']} vs {m['away']} (Time: {m['time']})" for m in matches])
    
    prompt = f"""
    You are an expert sports betting analyst. I am paper trading (testing with fake money).
    Here are the soccer matches happening today:
    {matches_text}

    Task:
    1. Pick the ONE most predictable match from this list.
    2. Give a clear prediction (e.g., Home Win, Away Win, Over 2.5 Goals).
    3. Provide a brief, 2-sentence explanation for WHY.
    
    IMPORTANT: Do NOT use any markdown formatting. Just plain text.
    """

    try:
        response = ai_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        print("\n--- GROQ API ERROR DEBUG ---")
        print(e)
        return f"AI Error: Check terminal for details."

# ==========================================
# MODULE 4: TELEGRAM COMMANDS 
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Welcome to SportyBot! Type /predict to get AI betting analysis for today\'s matches.')

async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 Fetching live matches and waking up the AI analyst...")
    
    matches = fetch_thesportsdb()
    
    if not matches:
        await update.message.reply_text("No soccer matches found in the database for today.")
        return

    ai_analysis = ask_ai_for_predictions(matches)
    final_message = f"📊 Today's AI Betting Analysis:\n\n{ai_analysis}\n\n(Match logged to CSV)"
    await update.message.reply_text(final_message)

    log_prediction_to_csv(matches[0]['home'], matches[0]['away'], "See Telegram Message")

# ==========================================
# MAIN ENGINE
# ==========================================
def main():
    print("Bot is starting up...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("predict", predict))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()