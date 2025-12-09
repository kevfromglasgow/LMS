import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
from google.cloud import firestore

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Last Man Standing", layout="centered")

# --- 2. SECRETS & DATABASE SETUP ---
try:
    if "FOOTBALL_API_KEY" in st.secrets:
        API_KEY = st.secrets["FOOTBALL_API_KEY"]
    else:
        st.error("Missing 'FOOTBALL_API_KEY' in secrets.toml")
        st.stop()

    if "firebase" in st.secrets:
        db = firestore.Client.from_service_account_info(st.secrets["firebase"])
    else:
        st.error("Missing [firebase] section in secrets.toml")
        st.stop()
    
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")
    
except Exception as e:
    st.error(f"Error connecting to secrets: {e}")
    st.stop()

PL_COMPETITION_ID = 2021
ENTRY_FEE = 10

# --- 3. CUSTOM CSS ---
def inject_custom_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Teko:wght@600;700&display=swap');
        
        /* 1. BACKGROUND */
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(rgba(31, 0, 34, 0.85), rgba(31, 0, 34, 0.95)), 
                        url('https://images.unsplash.com/photo-1693517393451-a71a593c9870?q=80&w=1770&auto=format&fit=crop') !important;
            background-size: cover !important;
            background-position: center !important;
            background-attachment: fixed !important;
            background-repeat: no-repeat !important;
        }

        /* 2. HEADERS & TEXT */
        .hero-title {
            font-family: 'Teko', sans-serif; font-size: 60px; font-weight: 700;
            text-transform: uppercase; color: #ffffff; letter-spacing: 2px;
            margin: 0; line-height: 1; text-align: center;
            text-shadow: 0 0 10px rgba(0, 255, 135, 0.5);
        }
        .hero-subtitle {
            font-family: 'Helvetica Neue', sans-serif; font-size: 14px;
            color: #00ff87; text-transform: uppercase; letter-spacing: 3px;
            margin-top: 5px; font-weight: 600; text-align: center; margin-bottom: 20px;
        }
        h1, h2, h3, h4, h5, h6 { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; text-transform: uppercase; letter-spacing: 1px; }
        
        /* Force standard text to white if needed */
        p, label { color: #ffffff !important; }

        .player-row-container {
            display: flex; flex-direction: column; gap: 10px; margin-bottom: 30px;
        }
        
        /* ACTIVE CARD STYLE */
        .player-card {
            background-color: #28002B; border: 1px solid rgba(0, 255, 135, 0.3); border-radius: 12px;
            padding: 12px 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: transform 0.2s;
            display: flex; align-items: center; justify-content: space-between; width: 100%;
        }
        .player-card:hover { transform: translateY(-2px); border-color: #00ff87; }

        /* ELIMINATED CARD STYLE */
        .player-card-eliminated {
            background-color: #1a1a1a; /* Grey/Black */
            border: 1px solid #444; 
            border-radius: 12px;
            padding: 10px 20px; 
            display: flex; align-items: center; justify-content: space-between; width: 100%;
            opacity: 0.8;
        }
        
        /* NAME WRAPPING */
        .pc-name { 
            font-size: 16px; font-weight: 700; color: #fff; 
            flex: 1; text-align: left;
            white-space: normal !important;       
            overflow-wrap: break-word !important; 
            word-wrap: break-word !important;     
            min-width: 0 !important;              
            line-height: 1.2; 
            padding-right: 10px; 
        }
        
        .pc-center { flex: 0 0 100px; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .pc-badge { width: 35px; height: 35px; object-fit: contain; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.5)); }
        
        .status-tag-win { font-size: 10px; background: #00ff87; color: #1F0022; padding: 2px 6px; border-radius: 4px; font-weight: 800; margin-top: 4px; letter-spacing: 1px; }
        .status-tag-loss { font-size: 10px; background: #ff4b4b; color: white; padding: 2px 6px; border-radius: 4px; font-weight: 800; margin-top: 4px; letter-spacing: 1px; }
        
        .pc-hidden { font-size: 24px; }
        .pc-team { font-size: 14px; color: #00ff87; font-weight: 600; flex: 1; text-align: right; text-transform: uppercase; }
        .pc-eliminated-text { font-size: 12px; color: #ff4b4b; font-weight: 600; flex: 1; text-align: right; text-transform: uppercase; }

        .match-card {
            background-color: #28002B; border-radius: 12px; padding: 12px 10px;
            margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.05); box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            display: flex; flex-direction: column; 
        }
        .match-info-row { display: flex; align-items: center; justify-content: space-between; width: 100%; }

        .team-container { flex: 1; display: flex; align-items: center; font-weight: 700; color: white; font-size: 15px; min-width: 0; }
        .team-container span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; }
        .home-team { justify-content: flex-end; text-align: right; }
        .away-team { justify-content: flex-start; text-align: left; }
        .crest-img { width: 38px; height: 38px; object-fit: contain; margin: 0 10px; }
        
        .score-box { flex: 0 0 90px; text-align: center; background-color: #1F0022; border-radius: 8px; padding: 5px 0; }
        .score-text { font-size: 18px; font-weight: 800; color: #00ff87; line-height: 1; }
        .time-text { font-size: 16px; font-weight: 700; color: white; line-height: 1; }
        .status-text { font-size: 9px; color: #ddd; text-transform: uppercase; margin-top: 5px; font-weight: 600; }
        
        /* 5. METRIC CARDS (PRIZE POT / DEADLINE) */
        div[data-testid="stMetric"] { background-color: #28002B !important; border-radius: 10px; padding: 10px !important; }
        div[data-testid="stMetricLabel"] { color: #ffffff !important; } /* Force Label White */
        div[data-testid="stMetricValue"] { color: #ffffff !important; } /* Force Value White */
        
        /* 6. EXPANDER & RADIO (SELECTION BOX) */
        .streamlit-expanderHeader {
            background-color: #28002B !important;
            color: #ffffff !important; /* Force Title White */
            font-weight: 800 !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            border-radius: 8px !important;
        }
        .streamlit-expanderHeader p { color: #ffffff !important; } /* Double force paragraph inside */
        
        /* Radio Button List */
        div[role="radiogroup"] p { color: #ffffff !important; } /* Force Names White */
        div[role="radiogroup"] > label > div:first-of-type {
            background-color: #28002B !important;
        }
        
        /* 7. CAPTIONS & NOTIFICATIONS */
        div[data-testid="stCaptionContainer"] { color: #ffffff !important; } /* Force Captions White */
        
        /* ROLLOVER BANNER */
        .rollover-banner {
            background-color: #ff4b4b; color: white; text-align: center;
            padding: 15px; border-radius: 10px; margin-bottom: 20px;
            font-family: 'Teko', sans-serif; font-size: 30px; font-weight: 700;
            letter-spacing: 2px; box-shadow: 0 0 20px rgba(255, 75, 75, 0.6);
            animation: pulse 2s infinite;
        }
        .banner-container {
            text-align: center; padding: 20px; border-radius: 10px; margin-bottom: 20px;
            box-shadow: 0 0 20px rgba(0,0,0,0.5); animation: pulse 2s infinite;
        }
        .banner-rollover { background-color: #ff4b4b; color: white; box-shadow: 0 0 20px rgba(255, 75, 75, 0.6); }
        .banner-winner { background-color: #FFD700; color: #28002B; box-shadow: 0 0 20px rgba(255, 215, 0, 0.6); }
        .banner-title { font-family: 'Teko', sans-serif; font-size: 36px; font-weight: 700; margin: 0; line-height: 1; }
        .banner-subtitle { font-family: 'Helvetica Neue', sans-serif; font-size: 16px; font-weight: 600; margin-top: 5px; }
        @keyframes pulse { 0% {transform:scale(1);} 50% {transform:scale(1.02);} 100% {transform:scale(1);} }
        
        /* HERO LOGO */
        .hero-container { text-align: center; margin-bottom: 30px; }
        .hero-logo {
            width: 200px; height: auto; margin-bottom: 15px;
            filter: invert(1) drop-shadow(0 0 10px rgba(255,255,255,0.2));
        }
        
        .stButton button { background-color: #28002B !important; color: white !important; border: 1px solid #00ff87 !important; }
        input[type="text"], input[type="password"] { 
            color: #ffffff !important; font-weight: bold; 
            background-color: rgba(255,255,255,0.1) !important; 
            border: 1px solid #00ff87 !important; 
        }
        
        @media (max-width: 600px) {
            .team-container { font-size: 12px; }
            .crest-img { width: 25px; height: 25px; margin: 0 5px; }
            .hero-title { font-size: 40px; }
        }
    </style>
    """, unsafe_allow_html=True)

# --- 4. HELPER FUNCTIONS ---
@st.cache_data(ttl=60)
def get_all_players_full():
    """Fetch FULL player objects (name, status, eliminated_gw)"""
    try:
        docs = db.collection('players').stream()
        return [doc.to_dict() for doc in docs]
    except: return []

@st.cache_data(ttl=60)
def get_all_picks_for_gw(gw):
    try: return [p.to_dict() for p in db.collection('picks').where('matchday', '==', gw).stream()]
    except: return []

@st.cache_data(ttl=3600)
def get_current_gameweek_from_api():
    headers = {'X-Auth-Token': API_KEY}
    try:
        r = requests.get(f"https://api.football-data.org/v4/competitions/{PL_COMPETITION_ID}/matches?status=SCHEDULED", headers=headers)
        data = r.json()
        if not data.get('matches'): return 38
        suggested_gw = data['matches'][0]['matchday']
        
        prev_gw = suggested_gw - 1
        if prev_gw < 1: return suggested_gw
        matches_prev = get_matches_for_gameweek(prev_gw)
        if not matches_prev: return suggested_gw
        
        # Buffer logic: Last Kickoff + 135 mins
        last_kickoff_str = max([m['utcDate'] for m in matches_prev])
        last_kickoff = datetime.fromisoformat(last_kickoff_str.replace('Z', ''))
        buffer_time = last_kickoff + timedelta(minutes=130)
        
        if datetime.utcnow() < buffer_time:
            return prev_gw
        return suggested_gw
    except: return 15

@st.cache_data(ttl=600)
def get_matches_for_gameweek(gw):
    headers = {'X-Auth-Token': API_KEY}
    try:
        r = requests.get(f"https://api.football-data.org/v4/competitions/{PL_COMPETITION_ID}/matches?matchday={gw}", headers=headers)
        return r.json()['matches']
    except: return []

def format_deadline_date(dt):
    day = dt.day
    if 4 <= day <= 20 or 24 <= day <= 30: suffix = "th"
    else: suffix = ["st", "nd", "rd"][day % 10 - 1]
    return dt.strftime(f"%a {day}{suffix} %b %H:%M")

def get_gameweek_deadline(matches):
    dates = [datetime.fromisoformat(m['utcDate'].replace('Z', '')) for m in matches]
    return min(dates) if dates else datetime.utcnow()

def calculate_team_results(matches):
    results = {}
    for m in matches:
        home, away = m['homeTeam']['name'], m['awayTeam']['name']
        if m['status'] == 'FINISHED':
            h, a = m['score']['fullTime']['home'], m['score']['fullTime']['away']
            if h > a: results.update({home:'WIN', away:'LOSE'})
            elif a > h: results.update({away:'WIN', home:'LOSE'})
            else: results.update({home:'LOSE', away:'LOSE'}) 
        else:
            results.update({home:'PENDING', away:'PENDING'})
    return results

@st.cache_data(ttl=600)
def get_game_settings():
    doc = db.collection('settings').document('config').get()
    return doc.to_dict() if doc.exists else {'rollover_multiplier': 1}

def update_game_settings(multiplier):
    db.collection('settings').document('config').set({'rollover_multiplier': multiplier})

# --- AUTO ELIMINATION LOGIC ---
def auto_process_eliminations(gw, matches):
    team_results = calculate_team_results(matches)
    picks = get_all_picks_for_gw(gw)
    updates_made = False
    
    for p in picks:
        user = p['user']
        team = p['team']
        result = team_results.get(team, 'PENDING')
        
        if result == 'LOSE':
            player_ref = db.collection('players').document(user)
            player_data = player_ref.get()
            
            if player_data.exists:
                current_status = player_data.to_dict().get('status')
                if current_status == 'active':
                    player_ref.update({'status': 'eliminated', 'eliminated_gw': gw})
                    updates_made = True
    
    if updates_made:
        st.cache_data.clear()
        st.rerun()

def admin_reset_game(current_gw, is_rollover=False):
    docs = db.collection('players').stream()
    for doc in docs:
        db.collection('players').document(doc.id).update({'status': 'pending', 'used_teams': [], 'eliminated_gw': None})
    picks = db.collection('picks').where('matchday', '==', current_gw).stream()
    for pick in picks:
        db.collection('picks').document(pick.id).delete()

    current_settings = get_game_settings()
    current_mult = current_settings.get('rollover_multiplier', 1)
    new_mult = current_mult + 1 if is_rollover else 1
    update_game_settings(new_mult)
    return "ROLLOVER!" if is_rollover else "RESET!"

def bulk_import_history():
    def fix_team(t):
        mapping = {
            "Bournemouth": "AFC Bournemouth", "Arsenal": "Arsenal FC", "Chelsea": "Chelsea FC",
            "Brighton": "Brighton & Hove Albion FC", "Aston Villa": "Aston Villa FC",
            "Manchester City": "Manchester City FC", "Manchester United": "Manchester United FC",
            "Newcastle": "Newcastle United FC", "Crystal Palace": "Crystal Palace FC",
            "Fulham": "Fulham FC", "Nottingham Forest": "Nottingham Forest FC",
            "Liverpool": "Liverpool FC", "West Ham": "West Ham United FC",
            "Sunderland": "Sunderland AFC", "Brentford": "Brentford FC",
            "Wolverhampton Wanderers": "Wolverhampton Wanderers FC"
        }
        return mapping.get(t, t + " FC" if "FC" not in t else t)

    RAW_DATA = {
        "Aidan Mannion": ["Bournemouth", "Arsenal", "Chelsea", "Brighton", "Aston Villa", "Manchester City", "Manchester United"],
        "Alan Comiskey": ["Chelsea"],
        "Barry Mackintosh": ["Chelsea"],
        "Clevon Beadle": ["Manchester City"],
        "Colin Jackson": ["Manchester United", "Sunderland"],
        "Colin Taylor": ["Chelsea"],
        "Connor Smith": ["Bournemouth", "Arsenal", "Chelsea", "Liverpool"],
        "Conor Brady": ["Bournemouth", "Arsenal", "Crystal Palace"],
        "Danny Mulgrew": ["Chelsea"],
        "Drew Boult": ["Arsenal", "Manchester United"],
        "Fraser Robson": ["Bournemouth", "Manchester United"],
        "Gary McIntyre": ["Manchester City"],
        "John McAllister": ["Chelsea"],
        "Jonathan McCormack": ["Manchester City"],
        "Katie Arnold": ["Newcastle", "Arsenal", "Chelsea", "Aston Villa", "Manchester City", "Crystal Palace", "Brighton"],
        "Kevin Dorward": ["Chelsea"],
        "Kyle Goldie": ["Manchester City"],
        "Kirsti Chalmers": ["Chelsea"],
        "Lee Brady": ["Newcastle", "Fulham", "Nottingham Forest", "Bournemouth"],
        "Liam Samuels": ["Newcastle", "Manchester United"],
        "Lyndon Rambottom": ["Arsenal", "Brighton", "Chelsea", "Liverpool"],
        "Mark Roberts": ["Chelsea"],
        "Martin Brady": ["Chelsea"],
        "Max Dougall": ["Bournemouth", "Arsenal", "Chelsea", "Crystal Palace", "Aston Villa", "Manchester United", "Liverpool"],
        "Michael Cumming": ["Chelsea"],
        "Michael Gallagher": ["Newcastle", "Arsenal", "West Ham", "Liverpool"],
        "Michael Mullen": ["Manchester City"],
        "Nathanael Samuels": ["Chelsea"],
        "Phil McLean": ["Chelsea"],
        "Richard Cartner": ["Newcastle", "Sunderland"],
        "Scott Hendry": ["Manchester City"],
        "Sean Flatley": ["Manchester City"],
        "Stan Payne": ["Wolverhampton Wanderers"],
        "Theo Samuels": ["Newcastle", "Manchester City", "West Ham", "Chelsea", "Brentford", "Arsenal"],
        "Thomas Kolakovic": ["Chelsea"],
        "Thomas McArthur": ["Manchester City"],
        "Tom Wright": ["Chelsea"],
        "Zach Smith-Palmieri": ["Chelsea"]
    }

    count_players = 0
    for name, picks in RAW_DATA.items():
        is_active = (len(picks) == 7)
        status = 'active' if is_active else 'eliminated'
        eliminated_gw = (len(picks) + 8) if not is_active else None 
        used_teams = []
        for i, raw_team in enumerate(picks):
            gw = i + 9
            team_name = fix_team(raw_team)
            used_teams.append(team_name)
            result = 'WIN'
            if not is_active and i == len(picks) - 1: result = 'LOSS'
            
            db.collection('picks').document(f"{name}_GW{gw}").set({
                'user': name, 'team': team_name, 'matchday': gw, 
                'timestamp': datetime.now(), 'result': result
            })

        db.collection('players').document(name).set({
            'name': name, 'status': status, 'used_teams': used_teams, 
            'eliminated_gw': eliminated_gw, 'email': '', 'password': ''
        })
        count_players += 1
    return count_players

def display_player_status(picks, matches, players_data, reveal_mode=False):
    st.subheader("STILL STANDING")
    team_results = calculate_team_results(matches)
    user_pick_map = {p['user']: p['team'] for p in picks}
    crest_map = {}
    for m in matches:
        crest_map[m['homeTeam']['name']] = m['homeTeam']['crest']
        crest_map[m['awayTeam']['name']] = m['awayTeam']['crest']
        
    active_players = []
    eliminated_players = []
    for p in players_data:
        name = p['name']
        status = p.get('status')
        team = user_pick_map.get(name)
        result = team_results.get(team, 'PENDING') if team else 'PENDING'
        
        if status == 'eliminated':
            eliminated_players.append(p)
        elif status == 'active' and result == 'LOSE':
            p['pending_elimination'] = True 
            eliminated_players.append(p)
        else:
            active_players.append(p)
            
    active_players.sort(key=lambda x: x['name'])
    eliminated_players.sort(key=lambda x: (x.get('pending_elimination', False), x.get('eliminated_gw', 0)), reverse=True)

    active_html = ""
    for p in active_players:
        name = p['name']
        team = user_pick_map.get(name, None)
        
        if team:
            if reveal_mode:
                badge_url = crest_map.get(team, "")
                result = team_results.get(team, 'PENDING')
                status_html = ""
                if result == 'WIN': status_html = '<div class="status-tag-win">THROUGH</div>'
                mid = f'<img src="{badge_url}" class="pc-badge">{status_html}' if badge_url else '<span class="pc-hidden">⚽</span>'
                btm = f'<div class="pc-team">{team}</div>'
            else:
                mid = '<span class="pc-hidden">🔒</span>'
                btm = '<div class="pc-team">HIDDEN</div>'
        else:
            mid = '<span class="pc-hidden">⏳</span>'
            btm = '<div class="pc-team" style="color:#aaa">NO PICK</div>'

        active_html += f'<div class="player-card"><div class="pc-name">{name}</div><div class="pc-center">{mid}</div>{btm}</div>'
    
    st.markdown(f'<div class="player-row-container">{active_html}</div>', unsafe_allow_html=True)

    if eliminated_players:
        with st.expander(f"🪦 THE FALLEN ({len(eliminated_players)})", expanded=False):
            elim_html = ""
            for p in eliminated_players:
                name = p['name']
                if p.get('pending_elimination'):
                    team = user_pick_map.get(name)
                    badge_url = crest_map.get(team, "")
                    mid = f'<img src="{badge_url}" class="pc-badge"><div class="status-tag-loss">OUT</div>' if badge_url else '❌'
                    btm = f'<div class="pc-eliminated-text" style="color:#ff4b4b">PENDING ADMIN</div>'
                    card_class = "player-card"
                else:
                    gw_out = p.get('eliminated_gw', '?')
                    mid = '<span class="pc-hidden" style="opacity:0.5">💀</span>'
                    btm = f'<div class="pc-eliminated-text">OUT GW{gw_out}</div>'
                    card_class = "player-card-eliminated"
                elim_html += f'<div class="{card_class}"><div class="pc-name" style="color:#aaa">{name}</div><div class="pc-center">{mid}</div>{btm}</div>'
            st.markdown(f'<div class="player-row-container">{elim_html}</div>', unsafe_allow_html=True)

def display_fixtures_visual(matches):
    st.subheader(f"Fixtures")
    for match in matches:
        home, away = match['homeTeam'], match['awayTeam']
        status, dt = match['status'], datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
        
        if status == 'FINISHED':
            h, a = match['score']['fullTime']['home'], match['score']['fullTime']['away']
            center_html = f'<div class="score-text">{h} - {a}</div><div class="status-text">FT</div>'
        elif status in ['IN_PLAY', 'PAUSED']:
            h, a = match['score']['fullTime']['home'], match['score']['fullTime']['away']
            center_html = f'<div class="score-text" style="color:#ff4b4b;">{h} - {a}</div><div class="status-text" style="color:#ff4b4b;">LIVE</div>'
        elif status == 'POSTPONED':
            center_html = '<div class="time-text">P-P</div><div class="status-text">Postponed</div>'
        else:
            center_html = f'<div class="time-text">{dt.strftime("%H:%M")}</div><div class="status-text">{dt.strftime("%a %d")}</div>'

        st.markdown(f'<div class="match-card"><div class="match-info-row"><div class="team-container home-team"><span>{home["name"]}</span><img src="{home["crest"]}" class="crest-img"></div><div class="score-box">{center_html}</div><div class="team-container away-team"><img src="{away["crest"]}" class="crest-img"><span>{away["name"]}</span></div></div></div>', unsafe_allow_html=True)

# --- 5. MAIN APP LOGIC ---
def main():
    inject_custom_css()

    # --- ADMIN SIDEBAR ---
    with st.sidebar:
        st.header("🔧 Admin Panel")
        if 'admin_logged_in' not in st.session_state: st.session_state.admin_logged_in = False
        if not st.session_state.admin_logged_in:
            pwd = st.text_input("Admin Password", type="password")
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.cache_data.clear()
                st.rerun()
        else:
            if st.button("Logout"):
                st.session_state.admin_logged_in = False
                st.rerun()
            st.success("✅ Logged In")
            st.divider()
            
            real_gw = get_current_gameweek_from_api() 
            gw_override = st.slider("📆 Override Gameweek", min_value=1, max_value=38, value=15)
            
            st.divider()
            if st.button("🔄 ROLLOVER (Everyone Lost)"):
                msg = admin_reset_game(gw_override, is_rollover=True)
                st.warning(msg)
                st.cache_data.clear()
                st.rerun()
            if st.button("⚠️ HARD RESET (New Season)"):
                msg = admin_reset_game(gw_override, is_rollover=False)
                st.success(msg)
                st.cache_data.clear()
                st.rerun()
            if st.button("⚡ Inject Spreadsheet Data"):
                count = bulk_import_history()
                st.success(f"Imported {count} players!")
                st.cache_data.clear()
                st.rerun()
            
            # SIMULATION TOOLS
            st.divider()
            st.subheader("Test Simulations")
            if "sim_winner" not in st.session_state: st.session_state.sim_winner = False
            if "sim_rollover" not in st.session_state: st.session_state.sim_rollover = False
            
            if st.button("🏆 Toggle Sim Winner"):
                st.session_state.sim_winner = not st.session_state.sim_winner
                st.session_state.sim_rollover = False
                st.rerun()
            
            if st.button("💀 Toggle Sim Rollover"):
                st.session_state.sim_rollover = not st.session_state.sim_rollover
                st.session_state.sim_winner = False
                st.rerun()
            
            if st.session_state.sim_winner: st.warning("Simulating WINNER")
            if st.session_state.sim_rollover: st.warning("Simulating ROLLOVER")

    st.markdown("""
        <div class="hero-container">
            <img src="https://cdn.freebiesupply.com/images/large/2x/premier-league-logo-black-and-white.png" class="hero-logo">
            <div class="hero-title">LAST MAN STANDING</div>
            <div class="hero-subtitle">SEASON 25/26</div>
        </div>
    """, unsafe_allow_html=True)
    
    # --- HANDLING VARIABLES ---
    gw = 15
    sim_reveal = False
    
    if st.session_state.admin_logged_in:
        try: gw = gw_override
        except NameError: pass 
    else:
        gw = get_current_gameweek_from_api()
    
    matches = get_matches_for_gameweek(gw)
    if not matches:
        st.warning("No matches found.")
        st.stop()
    
    # --- AUTO ELIMINATION CHECK ---
    auto_process_eliminations(gw, matches)
    
    all_picks = get_all_picks_for_gw(gw)
    all_players_full = get_all_players_full()
    
    settings = get_game_settings()
    multiplier = settings.get('rollover_multiplier', 1)
    
    # --- REAL DEADLINE LOGIC ---
    upcoming = [m for m in matches if m['status'] == 'SCHEDULED']
    if upcoming:
        first_kickoff = get_gameweek_deadline(upcoming)
    else:
        first_kickoff = get_gameweek_deadline(matches)
        
    deadline = first_kickoff - timedelta(hours=1)
    reveal_time = first_kickoff - timedelta(minutes=30)
    
    now = datetime.utcnow()
    # Override for Admin Simulation
    if sim_reveal: reveal_time = now - timedelta(hours=1)
        
    is_reveal_active = (now > reveal_time)

    # 1. Metrics & Selection
    st.write("")
    c1, c2 = st.columns(2)
    
    # POT: Active + Eliminated (Ignore Pending)
    paid_players = len([p for p in all_players_full if p.get('status') in ['active', 'eliminated']])
    pot_total = paid_players * ENTRY_FEE * multiplier
    
    pot_label = f"💰 ROLLOVER POT ({multiplier}x)" if multiplier > 1 else "💰 Prize Pot"
    
    if now > deadline: deadline_text = "EXPIRED"
    else: deadline_text = format_deadline_date(deadline)
        
    with c1: st.metric(pot_label, f"£{pot_total}")
    with c2: st.metric("DEADLINE", deadline_text)

    st.markdown("---")
    st.subheader("🎯 Make Your Selection")

    # Filter: Active players who have NOT picked yet
    user_picks_this_week = {p['user'] for p in all_picks}
    active_available_names = sorted([
        p['name'] for p in all_players_full 
        if p.get('status') in ['active', 'pending'] and p['name'] not in user_picks_this_week
    ])
    
    options = ["Select your name...", "➕ I am a New Player"] + active_available_names
    
    # MOBILE FIX: Auto-Close Expander
    if "selected_radio_option" not in st.session_state:
        st.session_state.selected_radio_option = "Select your name..."
    if "expander_version" not in st.session_state:
        st.session_state.expander_version = 0

    def radio_callback():
        st.session_state.expander_version += 1

    expander_label = f"👤 {st.session_state.selected_radio_option}" if st.session_state.selected_radio_option != "Select your name..." else "👤 Tap to select your name..."
    expander_key = f"user_select_expander_{st.session_state.expander_version}"

    with st.expander(expander_label, expanded=False):
        st.radio(
            "List of Players:", 
            options, 
            key="selected_radio_option",
            label_visibility="collapsed",
            on_change=radio_callback
        )
    
    actual_user_name = None
    if st.session_state.selected_radio_option == "➕ I am a New Player":
        new_name_input = st.text_input("Enter your full name (First & Last):")
        if new_name_input:
            clean_name = new_name_input.strip().title()
            all_names = [p['name'] for p in all_players_full]
            if clean_name in all_names: st.error(f"'{clean_name}' already exists!")
            else: actual_user_name = clean_name
    elif st.session_state.selected_radio_option != "Select your name...":
        actual_user_name = st.session_state.selected_radio_option

    if actual_user_name:
        user_ref = db.collection('players').document(actual_user_name)
        user_doc = user_ref.get()
        if user_doc.exists and user_doc.to_dict().get('status') == 'eliminated':
            st.error(f"❌ Sorry {actual_user_name}, you have been eliminated!")
            st.info("Wait for a new game to start to rejoin.")
        else:
            pick_id = f"{actual_user_name}_GW{gw}"
            pick_ref = db.collection('picks').document(pick_id)
            if pick_ref.get().exists:
                st.success(f"✅ {actual_user_name} has already made a selection for Gameweek {gw}.")
                st.caption("See the 'Still Standing' list below for details (picks revealed 30 mins before kick-off).")
            else:
                if now > deadline:
                    st.error("🚫 Gameweek Locked")
                else:
                    used = user_doc.to_dict().get('used_teams', []) if user_doc.exists else []
                    valid = set([m['homeTeam']['name'] for m in matches] + [m['awayTeam']['name'] for m in matches])
                    available = sorted([t for t in valid if t not in used])
                    if not available: st.warning("No teams available.")
                    else:
                        with st.form("pick_form"):
                            team_choice = st.selectbox(f"Pick a team for {actual_user_name}:", available)
                            if st.form_submit_button("SUBMIT PICK"):
                                pick_ref.set({'user': actual_user_name, 'team': team_choice, 'matchday': gw, 'timestamp': datetime.now()})
                                user_ref.set({'name': actual_user_name, 'used_teams': firestore.ArrayUnion([team_choice]), 'status': 'active'}, merge=True)
                                st.success(f"✅ Pick Locked In for {actual_user_name}!")
                                st.cache_data.clear() 
                                st.rerun()
                    if used: st.info(f"Teams used by {actual_user_name}: {', '.join(used)}")

    st.markdown("---")
    
    # --- BANNER LOGIC ---
    active_count = len([p for p in all_players_full if p.get('status') == 'active'])
    
    sim_w = st.session_state.get('sim_winner', False)
    sim_r = st.session_state.get('sim_rollover', False)
    
    # 1. ROLLOVER (Everyone dead OR Sim Rollover)
    if (active_count == 0 and len(all_players_full) > 0) or sim_r:
        st.markdown("""
        <div class="banner-container banner-rollover">
            <div class="banner-title">💀 GAME OVER 💀</div>
            <div class="banner-subtitle">ROLLOVER INCOMING</div>
        </div>
        """, unsafe_allow_html=True)
        
    # 2. WINNER (1 Active AND (Sim Winner OR Active Player Actually Won))
    elif active_count == 1 or sim_w:
        survivor_name = "TEST WINNER"
        show_winner = False
        
        if sim_w:
            show_winner = True
        else:
            survivor = next((p for p in all_players_full if p['status'] == 'active'), None)
            if survivor:
                survivor_name = survivor['name']
                pick_data = next((p for p in all_picks if p['user'] == survivor_name), None)
                if pick_data:
                    team_res = calculate_team_results(matches)
                    if team_res.get(pick_data['team']) == 'WIN':
                        show_winner = True

        if show_winner:
            st.markdown(f"""
            <div class="banner-container banner-winner">
                <div class="banner-title">🏆 WE HAVE A WINNER! 🏆</div>
                <div class="banner-subtitle">{survivor_name} has won £{pot_total} - Congratulations!</div>
                <div style="font-size:12px; margin-top:5px;">A new game will begin soon.</div>
            </div>
            """, unsafe_allow_html=True)

    # 3. Status & Fixtures
    display_player_status(all_picks, matches, all_players_full, reveal_mode=is_reveal_active)
    display_fixtures_visual(matches)

if __name__ == "__main__":
    main()
