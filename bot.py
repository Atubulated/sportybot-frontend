import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging
import requests
import pandas as pd
from datetime import date
from groq import Groq

# Load environment variables from the .env file
load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ✅ SECURELY LOAD KEYS FROM .ENV FILE
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Safety check to ensure keys are loaded
if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    raise ValueError("⚠️ Missing API keys! Please check your .env file.")

# Initialize the Groq AI Client
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
# MODULE 2: DATA LOGGING 
# ==========================================
def log_prediction_to_csv(home, away, prediction):
    file_exists = os.path.isfile('paper_trading_log.csv')
    data = {
        'Date': [date.today()],
        'Home Team': [home],
        'Away Team': [away],
        'AI Prediction': [prediction],
        'Result': ['Pending'] 
    }
    df = pd.DataFrame(data)
    df.to_csv('paper_trading_log.csv', mode='a', header=not file_exists, index=False)

# ==========================================
# MODULE 3: AI ANALYSIS (The Brain)
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
    
    IMPORTANT: Do NOT use any markdown formatting. Do not use asterisks (*), hashtags (#), or underscores (_). Just plain text.
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
        print("-----------------------------\n")
        return f"AI Error: Check terminal for details."

# ==========================================
# MODULE 4: TELEGRAM COMMANDS 
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Welcome to SportyBot! Type /predict to get AI betting analysis for today\'s matches.')

async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 Fetching live matches and waking up the AI analyst... (This will take ~2 seconds)")
    
    matches = fetch_thesportsdb()
    
    if not matches:
        await update.message.reply_text("No soccer matches found in the database for today. Try again tomorrow!")
        return

    ai_analysis = ask_ai_for_predictions(matches)
    
    final_message = f"📊 Today's AI Betting Analysis:\n\n{ai_analysis}\n\n(Match logged to CSV for paper trading tracking)"
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