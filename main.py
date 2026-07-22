import os
import json
import asyncio
import time
import re
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import os
import json

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI
from supabase import create_client, Client
import requests

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

# ==========================================
# 1. CONFIGURATION
# ==========================================
app = FastAPI(title="SportyBot Pro AI", version="13.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sportybot-frontend.vercel.app",  # Your deployed Vercel frontend
        "http://localhost:3000",                  # Local Next.js development
        "http://127.0.0.1:3000"                   # Local Next.js development
    ],
    allow_credentials=True, 
    allow_methods=["*"],
    allow_headers=["*"],
)
client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY"),
    timeout=300.0  # Increased to 5 minutes
)

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
CACHE_FILE = "odds_cache.json"

# ==========================================
# 2. CACHING & DATA FETCHER
# ==========================================
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=4)

def fetch_advanced_markets(start_date: date = None, end_date: date = None):
    if start_date is None: start_date = date.today()
    if end_date is None: end_date = start_date
    
    all_matches = []
    current_date = start_date
    cache = load_cache()
    today_str = date.today().strftime('%Y-%m-%d')
    
    if cache.get('last_updated', '') != today_str:
        cache = {'last_updated': today_str}
        save_cache(cache)

    headers = {"x-apisports-key": API_FOOTBALL_KEY, "User-Agent": "SportyBot-Pro/1.0"}
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        fixtures_url = f"https://v3.football.api-sports.io/fixtures?date={date_str}&status=NS"
        
        try:
            res = requests.get(fixtures_url, headers=headers, timeout=15)
            if res.status_code != 200:
                current_date += timedelta(days=1)
                continue
            
            data = res.json().get('response', [])
            print(f"📅 {date_str}: Found {len(data)} fixtures")
            
            for fixture in data[:20]:
                fixture_id = str(fixture['fixture']['id'])
                home = fixture['teams']['home']['name']
                away = fixture['teams']['away']['name']
                league = fixture['league']['name']
                match_date = fixture['fixture']['date']
                
                if fixture_id in cache:
                    market_str = cache[fixture_id]
                else:
                    time.sleep(0.6)
                    odds_url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"
                    odds_res = requests.get(odds_url, headers=headers, timeout=15)
                    
                    if odds_res.status_code == 429: break
                        
                    if odds_res.status_code == 200:
                        odds_data = odds_res.json().get('response', [])
                        if odds_data and odds_data[0].get('bookmakers'):
                            bookmaker = odds_data[0]['bookmakers'][0]
                            markets = {m['name']: m['values'] for m in bookmaker['bets']}
                            
                            market_str = ""
                            if 'Match Winner' in markets:
                                mw = {v['value']: v['odd'] for v in markets['Match Winner']}
                                market_str += f"1X2 -> Home: {mw.get('Home', 'N/A')}, Draw: {mw.get('Draw', 'N/A')}, Away: {mw.get('Away', 'N/A')} | "
                            
                            dc_home_draw = next((v['odd'] for v in markets.get('Home or Draw', []) if v['value'] == 'Home or Draw'), 'N/A')
                            dc_away_draw = next((v['odd'] for v in markets.get('Away or Draw', []) if v['value'] == 'Away or Draw'), 'N/A')
                            if dc_home_draw != 'N/A' or dc_away_draw != 'N/A':
                                market_str += f"Double Chance -> Home/Draw: {dc_home_draw}, Away/Draw: {dc_away_draw} | "
                            
                            if 'Goals Over/Under' in markets:
                                totals = {v['value']: v['odd'] for v in markets['Goals Over/Under']}
                                over_15 = totals.get('Over 1.5', 'N/A')
                                over_25 = totals.get('Over 2.5', 'N/A')
                                if over_15 != 'N/A' or over_25 != 'N/A':
                                    market_str += f"Totals -> Over 1.5: {over_15}, Over 2.5: {over_25} | "
                            
                            if 'Asian Handicap' in markets:
                                ah = {v['value']: v['odd'] for v in markets['Asian Handicap']}
                                safe_hcaps = [k for k in ah.keys() if '+1.5' in k or '+2.5' in k or '-1.5' in k]
                                if safe_hcaps:
                                    ah_str = ", ".join([f"{k}: {ah[k]}" for k in safe_hcaps[:2]])
                                    market_str += f"Asian Handicap -> {ah_str} | "
                            
                            if market_str: cache[fixture_id] = market_str
                            else: continue
                        else: continue
                    else: continue

                if market_str:
                    all_matches.append({
                        "match_name": f"{home} vs {away}",
                        "league": league,
                        "match_date": match_date,
                        "available_markets": market_str.strip(" | ")
                    })
        except Exception as e:
            print(f"❌ Error: {e}")
        current_date += timedelta(days=1)
    
    save_cache(cache)
    if not all_matches: raise HTTPException(status_code=404, detail="No matches found")
    return all_matches

# ==========================================
# 3. STRICT AI ENGINE & VALIDATION
# ==========================================
async def analyze_match_with_risk_profile(match: dict, risk_profile: str):
    print(f" Analyzing ({risk_profile.upper()}): {match['match_name']}...")
    
    if risk_profile == "safe":
        risk_instruction = "PRIORITIZE maximum safety. Focus on Double Chance (1.15-1.50) or Asian Handicaps (+1.5, +2.5). Target confidence: 85%+"
        min_confidence = 85; max_odds = 1.80
    elif risk_profile == "balanced":
        risk_instruction = "Balance safety with value. Target confidence: 75%+"
        min_confidence = 75; max_odds = 2.50
    else:
        risk_instruction = "Seek high-value. Target confidence: 65%+"
        min_confidence = 65; max_odds = 4.00
    
    prompt = f"""
    You are an elite quantitative sports bettor.
    Match: {match['match_name']} ({match['league']})
    
    AVAILABLE MARKETS & ODDS (COPY EXACTLY):
    {match['available_markets']}

    {risk_instruction}

    CRITICAL RULES:
    1. You MUST select a market EXACTLY as it appears in the AVAILABLE MARKETS list (e.g., "1X2 - Home", "Double Chance - Home/Draw", "Totals - Over 1.5").
    2. DO NOT invent markets. DO NOT add team names to the market name.
    3. Respond in JSON ONLY:
    {{"selected_market": "Exact string from list", "estimated_odds": 1.45, "confidence": 85, "reasoning": "1 sentence", "risk_check": "APPROVED"}}
    """
    
    try:
        res = await client.chat.completions.create(
            model="meta/llama-3.3-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2 if risk_profile == "safe" else 0.4,
            max_tokens=250, stream=False
        )
        content = res.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        result = json.loads(content)
        
        selected = result.get('selected_market', '')
        available = match['available_markets']
        
        core_market = selected.split(' - ')[-1] if ' - ' in selected else selected
        if core_market not in available and selected not in available:
            print(f"   ❌ VALIDATION FAILED: AI invented market '{selected}'")
            return None
            
        if result.get('confidence', 0) < min_confidence or result.get('estimated_odds', 0) > max_odds:
            return None
        if "DOWNGRADED" in result.get('risk_check', ''):
            return None
            
        print(f"   ✅ APPROVED: {result['selected_market']} @ {result['estimated_odds']} ({result['confidence']}%)")
        return result
    except Exception as e:
        print(f"   ❌ AI Error: {e}")
        return None

# ==========================================
# NEW: BACKGROUND DAILY ANALYSIS
# ==========================================
@app.get("/api/daily-analysis")
async def run_daily_analysis():
    """Fetches all fixtures, analyzes them, saves to Supabase with status 'ANALYZED'"""
    print("🔄 Starting Daily Analysis...")
    
    today = date.today()
    matches = fetch_advanced_markets(today, today)
    print(f"📊 Found {len(matches)} matches to analyze")
    
    analyzed_count = 0
    for match in matches:
        analysis = await analyze_match_with_risk_profile(match, "safe")
        
        if analysis:
            try:
                supabase.table("predictions").insert({
                    "match_name": match['match_name'],
                    "league": match['league'],
                    "match_date": match.get('match_date'),
                    "selected_market": analysis['selected_market'],
                    "estimated_odds": analysis['estimated_odds'],
                    "confidence": analysis['confidence'],
                    "reasoning": analysis.get('reasoning', ''),
                    "risk_profile": "safe",
                    "model_used": "Llama-3.3-70B-Safe",
                    "status": "ANALYZED",  # Pre-analyzed, not in a slip yet
                    "slip_id": None
                }).execute()
                analyzed_count += 1
            except Exception as e:
                print(f"Supabase Save Error: {e}")
    
    return {"message": f"Analyzed {analyzed_count} matches out of {len(matches)}"}

# ==========================================
# NEW: GET ANALYZED MATCHES
# ==========================================
@app.get("/api/analyzed-matches")
def get_analyzed_matches():
    """Returns all matches analyzed for today with status 'ANALYZED'"""
    try:
        today = date.today().strftime('%Y-%m-%d')
        response = supabase.table("predictions").select("*").eq("status", "ANALYZED").gte("match_date", today).execute()
        return response.data
    except Exception as e:
        return {"error": str(e)}

# ==========================================
# UPDATED: BUILD SLIP FROM SELECTED MATCHES
# ==========================================
class SlipRequest(BaseModel):
    selected_matches: list[str]  # List of match IDs from Supabase
    target_odds: float = 10.0
    risk_profile: str = "safe"

@app.post("/api/build-slip-from-selection")
async def build_slip_from_selection(request: SlipRequest):
    """Builds a slip from pre-analyzed matches selected by user"""
    print(f"\n--- BUILDING SLIP FROM {len(request.selected_matches)} SELECTED MATCHES ---")
    
    # Fetch the selected matches from Supabase
    response = supabase.table("predictions").select("*").in_("id", request.selected_matches).execute()
    selected_picks = response.data
    
    if not selected_picks:
        raise HTTPException(status_code=404, detail="No valid matches selected")
    
    # Sort by confidence (for safe) or value (for aggressive)
    if request.risk_profile == "safe":
        selected_picks.sort(key=lambda x: x['confidence'], reverse=True)
    else:
        selected_picks.sort(key=lambda x: x['estimated_odds'] * x['confidence'] / 100, reverse=True)
    
    # Build accumulator
    accumulator = []
    total_odds = 1.0
    slip_id = f"SLIP-{datetime.now().strftime('%Y%m%d-%H%M')}"
    
    for pick in selected_picks:
        if total_odds >= request.target_odds * 0.9: break
        accumulator.append(pick)
        total_odds *= pick['estimated_odds']
        
        # Update status from ANALYZED to PENDING (now part of a slip)
        supabase.table("predictions").update({
            "slip_id": slip_id,
            "status": "PENDING",
            "risk_profile": request.risk_profile,
            "target_odds": request.target_odds
        }).eq("id", pick['id']).execute()

    return {
        "slip_id": slip_id, 
        "target_odds": request.target_odds, 
        "actual_odds": round(total_odds, 2),
        "risk_profile": request.risk_profile, 
        "number_of_legs": len(accumulator), 
        "picks": accumulator
    }

# ==========================================
# 4. OUTCOME TRACKING (THE RECORD KEEPER)
# ==========================================
def evaluate_bet(market: str, home_score: int, away_score: int) -> str:
    """Evaluates if a specific market won, lost, or was voided based on the final score."""
    market_lower = market.lower()
    
    # 1X2 Markets
    if "1x2" in market_lower or "match winner" in market_lower:
        if "home" in market_lower and "draw" not in market_lower and "away" not in market_lower:
            return "WON" if home_score > away_score else "LOST"
        if "away" in market_lower and "draw" not in market_lower and "home" not in market_lower:
            return "WON" if away_score > home_score else "LOST"
        if "draw" in market_lower and "home" not in market_lower and "away" not in market_lower:
            return "WON" if home_score == away_score else "LOST"
            
    # Double Chance
    if "double chance" in market_lower or "home or draw" in market_lower:
        if "home" in market_lower and "draw" in market_lower:
            return "WON" if home_score >= away_score else "LOST"
        if "away" in market_lower and "draw" in market_lower:
            return "WON" if away_score >= home_score else "LOST"
        if "home" in market_lower and "away" in market_lower:
            return "WON" if home_score != away_score else "LOST"
            
    # Totals (Goals)
    if "over" in market_lower or "under" in market_lower:
        total_goals = home_score + away_score
        if "over 1.5" in market_lower: return "WON" if total_goals > 1.5 else "LOST"
        if "over 2.5" in market_lower: return "WON" if total_goals > 2.5 else "LOST"
        if "under 2.5" in market_lower: return "WON" if total_goals < 2.5 else "LOST"
        
    # Asian Handicap (Simplified for +1.5/-1.5)
    if "handicap" in market_lower:
        if "+1.5" in market_lower and "home" in market_lower:
            return "WON" if (home_score + 1.5) > away_score else "LOST"
        if "-1.5" in market_lower and "home" in market_lower:
            return "WON" if (home_score - 1.5) > away_score else "LOST"
        if "+1.5" in market_lower and "away" in market_lower:
            return "WON" if (away_score + 1.5) > home_score else "LOST"
            
    return "VOID"

@app.get("/api/update-results")
def update_results():
    """Fetches finished matches and updates Supabase with WON/LOST status."""
    print("🔄 Starting Result Tracker...")
    
    response = supabase.table("predictions").select("*").eq("status", "PENDING").execute()
    pending_picks = response.data
    
    if not pending_picks:
        return {"message": "No pending predictions to update."}
    
    dates_to_check = list(set([p.get('match_date', '')[:10] for p in pending_picks if p.get('match_date')]))
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    
    updated_count = 0
    
    for check_date in dates_to_check:
        url = f"https://v3.football.api-sports.io/fixtures?date={check_date}&status=FT"
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            finished_games = res.json().get('response', [])
            game_lookup = {f"{g['teams']['home']['name']} vs {g['teams']['away']['name']}": g for g in finished_games}
            
            for pick in pending_picks:
                if not pick.get('match_date'):
                    continue
                    
                if pick['match_date'][:10] == check_date:
                    match_key = pick['match_name']
                    if match_key in game_lookup:
                        game = game_lookup[match_key]
                        home_score = game['goals']['home']
                        away_score = game['goals']['away']
                        
                        result_status = evaluate_bet(pick['selected_market'], home_score, away_score)
                        
                        supabase.table("predictions").update({
                            "status": result_status,
                            "actual_result": f"{home_score}-{away_score}"
                        }).eq("id", pick['id']).execute()
                        
                        updated_count += 1
                        print(f"  -> {match_key}: {result_status} (Score: {home_score}-{away_score})")

    return {"message": f"Updated {updated_count} predictions."}

# ==========================================
# 5. ACCUMULATOR BUILDER (OLD - KEEP FOR BACKWARDS COMPAT)
# ==========================================
class AccumulatorRequest(BaseModel):
    target_odds: float = 10.0
    risk_profile: str = "safe"
    start_date: str = None
    end_date: str = None

@app.post("/api/build-accumulator")
async def build_accumulator(request: AccumulatorRequest):
    start_date = datetime.strptime(request.start_date, '%Y-%m-%d').date() if request.start_date else None
    end_date = datetime.strptime(request.end_date, '%Y-%m-%d').date() if request.end_date else None
    
    matches = fetch_advanced_markets(start_date, end_date)
    print(f"\n--- BUILDING {request.risk_profile.upper()} ACCUMULATOR ---")
    
    results = await asyncio.gather(*[analyze_match_with_risk_profile(m, request.risk_profile) for m in matches[:3]])
    
    approved_picks = []
    for i, result in enumerate(results):
        if result and i < len(matches):
            result['match_name'] = matches[i]['match_name']
            result['league'] = matches[i]['league']
            result['match_date'] = matches[i].get('match_date')
            result['model_used'] = f"Llama-3.3-70B-{request.risk_profile.capitalize()}"
            approved_picks.append(result)
    
    if request.risk_profile == "safe":
        approved_picks.sort(key=lambda x: x['confidence'], reverse=True)
    else:
        approved_picks.sort(key=lambda x: x['estimated_odds'] * x['confidence'] / 100, reverse=True)
    
    accumulator = []
    total_odds = 1.0
    slip_id = f"SLIP-{datetime.now().strftime('%Y%m%d-%H%M')}"
    
    for pick in approved_picks:
        if total_odds >= request.target_odds * 0.9: break
        accumulator.append(pick)
        total_odds *= pick['estimated_odds']
        
        try:
            supabase.table("predictions").insert({
                "slip_id": slip_id, "match_name": pick['match_name'], "league": pick['league'],
                "match_date": pick.get('match_date'), "selected_market": pick['selected_market'],
                "estimated_odds": pick['estimated_odds'], "confidence": pick['confidence'],
                "risk_profile": request.risk_profile, "model_used": pick['model_used'], "status": "PENDING"
            }).execute()
        except Exception as e: print(f"Supabase Save Error: {e}")

    return {
        "slip_id": slip_id, "target_odds": request.target_odds, "actual_odds": round(total_odds, 2),
        "risk_profile": request.risk_profile, "number_of_legs": len(accumulator), "picks": accumulator
    }

@app.get("/api/history")
def get_history():
    try:
        response = supabase.table("predictions").select("*").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

    # Force Railway Deploy - Updating CORS