import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
from google.cloud import firestore

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Last Man Standing", layout="centered")

# --- 2. SECRETS & DATABASE SETUP ---
try:
    API_KEY = st.secrets["FOOTBALL_API_KEY"]
    db = firestore.Client.from_service_account_info(st.secrets["firebase"])
except Exception as e:
    st.error(f"Error connecting to secrets or database: {e}")
    st.stop()

PL_COMPETITION_ID = 2021
ENTRY_FEE = 10

# --- 3. CUSTOM CSS ---
def inject_custom_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Teko:wght@600;700&display=swap');
        
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(rgba(31, 0, 34, 0.85), rgba(31, 0, 34, 0.95)), 
                        url('https://images.unsplash.com/photo-1693517393451-a71a593c9870?q=80&w=1770&auto=format&fit=crop') !important;
            background-size: cover !important;
            background-position: center !important;
            background-attachment: fixed !important;
            background-repeat: no-repeat !important;
        }

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
        h1, h2, h3 { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; text-transform: uppercase; letter-spacing: 1px; }

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
        
        .pc-name { font-size: 16px; font-weight: 700; color: #fff; flex: 1; text-align: left; }
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
        
        div[data-testid="stMetric"] { background-color: #28002B !important; border-radius: 10px; padding: 10px !important; }
        div[data-testid="stMetricLabel"] { color: #00ff87 !important; }
        div[data-testid="stMetricValue"] { color: #ffffff !important; }
        
        .stButton button { background-color: #28002B !important; color: white !important; border: 1px solid #00ff87 !important; }
        input[type="text"] { color: #ffffff !important; font-weight: bold; background-color: rgba(255,255,255,0.1) !important; border: 1px solid #00ff87 !important; }
        
        @media (max-width: 600px) {
            .team-container { font-size: 12px; }
            .crest-img { width: 25px; height: 25px; margin: 0 5px; }
            .hero-title { font-size: 40px; }
        }
    </style>
    """, unsafe_allow_html=True)

# --- 4. HELPER FUNCTIONS ---
def get_all_players_full():
    """Fetch FULL player data (name, status, eliminated_gw)"""
    try:
        docs = db.collection('players').stream()
        return [doc.to_dict() for doc in docs]
    except: return []

def get_all_picks_for_gw(gw):
    try: return [p.to_dict() for p in db.collection('picks').where('matchday', '==', gw).stream()]
    except: return []

@st.cache_data(ttl=3600)
def get_current_gameweek_from_api():
    headers = {'X-Auth-Token': API_KEY}
    r = requests.get(f"https://api.football-data.org/v4/competitions/{PL_COMPETITION_ID}/matches?status=SCHEDULED", headers=headers)
    return r.json()['matches'][0]['matchday'] if r.json()['matches'] else 38

@st.cache_data(ttl=600)
def get_matches_for_gameweek(gw):
    headers = {'X-Auth-Token': API_KEY}
    r = requests.get(f"https://api.football-data.org/v4/competitions/{PL_COMPETITION_ID}/matches?matchday={gw}", headers=headers)
    return r.json()['matches']

def get_gameweek_deadline(matches):
    dates = [datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00')) for m in matches]
    return min(dates) if dates else datetime.now()

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

def admin_eliminate_losers(gw, matches):
    team_results = calculate_team_results(matches)
    picks = get_all_picks_for_gw(gw)
    count = 0
    for p in picks:
        user = p['user']
        team = p['team']
        result = team_results.get(team, 'PENDING')
        if result == 'LOSE':
            # Mark as eliminated AND save which week it happened
            db.collection('players').document(user).update({
                'status': 'eliminated',
                'eliminated_gw': gw
            })
            count += 1
    return count

def admin_reset_game(current_gw):
    docs = db.collection('players').stream()
    for doc in docs:
        db.collection('players').document(doc.id).update({'status': 'active', 'used_teams': [], 'eliminated_gw': None})
    picks = db.collection('picks').where('matchday', '==', current_gw).stream()
    for pick in picks:
        db.collection('picks').document(pick.id).delete()

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
        # If eliminated, calculate WHICH week. Week 1 = GW9.
        # If len(picks) is 1, they lost week 1 (GW9).
        eliminated_gw = (len(picks) + 8) if not is_active else None 
        
        used_teams = []
        for i, raw_team in enumerate(picks):
            gw = i + 9
            team_name = fix_team(raw_team)
            used_teams.append(team_name)
            
            result = 'WIN'
            if not is_active and i == len(picks) - 1:
                result = 'LOSS'
            
            db.collection('picks').document(f"{name}_GW{gw}").set({
                'user': name, 'team': team_name, 'matchday': gw, 
                'timestamp': datetime.now(), 'result': result
            })

        db.collection('players').document(name).set({
            'name': name, 'status': status, 'used_teams': used_teams, 
            'eliminated_gw': eliminated_gw,
            'email': '', 'password': ''
        })
        count_players += 1
    return count_players

def display_player_status(picks, matches, players_data, reveal_mode=False):
    """
    Displays two lists:
    1. Survivors (Active)
    2. The Fallen (Eliminated - Sorted by Elimination Week)
    """
    st.subheader("WEEKLY LEADERBOARD")
    team_results = calculate_team_results(matches)
    
    # Create Map of User -> Pick for THIS week
    user_pick_map = {p['user']: p['team'] for p in picks}
    
    crest_map = {}
    for m in matches:
        crest_map[m['homeTeam']['name']] = m['homeTeam']['crest']
        crest_map[m['awayTeam']['name']] = m['awayTeam']['crest']
        
    # --- SPLIT PLAYERS INTO ACTIVE & ELIMINATED ---
    active_players = []
    eliminated_players = []
    
    for p in players_data:
        if p.get('status') == 'eliminated':
            eliminated_players.append(p)
        else:
            active_players.append(p)
            
    # Sort Active: Alphabetical
    active_players.sort(key=lambda x: x['name'])
    
    # Sort Eliminated: Highest GW (Recently Eliminated) at Top, Lowest GW (First Out) at Bottom
    # Default to 0 if data missing
    eliminated_players.sort(key=lambda x: x.get('eliminated_gw', 0), reverse=True)

    # --- RENDER ACTIVE PLAYERS ---
    active_html = ""
    for p in active_players:
        name = p['name']
        team = user_pick_map.get(name, None)
        
        # Visibility Logic
        if team:
            if reveal_mode:
                badge_url = crest_map.get(team, "")
                result = team_results.get(team, 'PENDING')
                status_html = ""
                if result == 'WIN': status_html = '<div class="status-tag-win">THROUGH</div>'
                elif result == 'LOSE': status_html = '<div class="status-tag-loss">OUT</div>'
                
                mid = f'<img src="{badge_url}" class="pc-badge">{status_html}' if badge_url else '<span class="pc-hidden">⚽</span>'
                btm = f'<div class="pc-team">{team}</div>'
            else:
                mid = '<span class="pc-hidden">🔒</span>'
                btm = '<div class="pc-team">HIDDEN</div>'
        else:
            # Haven't picked yet
            mid = '<span class="pc-hidden">⏳</span>'
            btm = '<div class="pc-team" style="color:#aaa">NO PICK</div>'

        active_html += f'<div class="player-card"><div class="pc-name">{name}</div><div class="pc-center">{mid}</div>{btm}</div>'
    
    st.markdown(f'<div class="player-row-container">{active_html}</div>', unsafe_allow_html=True)

    # --- RENDER ELIMINATED PLAYERS ---
    if eliminated_players:
        st.markdown("### 🪦 THE FALLEN")
        elim_html = ""
        for p in eliminated_players:
            name = p['name']
            gw_out = p.get('eliminated_gw', '?')
            
            mid = '<span class="pc-hidden" style="opacity:0.5">💀</span>'
            btm = f'<div class="pc-eliminated-text">OUT GW{gw_out}</div>'
            
            elim_html += f'<div class="player-card-eliminated"><div class="pc-name" style="color:#888">{name}</div><div class="pc-center">{mid}</div>{btm}</div>'
            
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
        st.header("🔧 Admin")
        simulate_reveal = st.checkbox("Simulate Pick Reveal", value=False)
        st.divider()
        gw_override = st.slider("📆 Override Gameweek", min_value=1, max_value=38, value=15)
        st.divider()
        if st.button("💀 Eliminate Losers (Current GW)"):
            gw = gw_override
            m = get_matches_for_gameweek(gw)
            count = admin_eliminate_losers(gw, m)
            st.success(f"Processed! {count} players eliminated.")
            st.cache_data.clear() 
            st.rerun()
        if st.button("🔄 Start New Game (Reset All)"):
            admin_reset_game(gw_override)
            st.success("Game Reset!")
            st.cache_data.clear()
            st.rerun()
        if st.button("⚡ Inject Spreadsheet Data (Weeks 9-15)"):
            count = bulk_import_history()
            st.success(f"Imported {count} players!")
            st.cache_data.clear()
            st.rerun()

    st.markdown("""
        <div class="hero-container">
            <div class="hero-title">LAST MAN STANDING</div>
            <div class="hero-subtitle">PREMIER LEAGUE 24/25</div>
        </div>
    """, unsafe_allow_html=True)
    
    gw = gw_override
    matches = get_matches_for_gameweek(gw)
    
    if not matches:
        st.warning("No matches found.")
        st.stop()
    
    all_picks = get_all_picks_for_gw(gw)
    # New: Fetch full player objects for sorting
    all_players_full = get_all_players_from_db() 
    
    first_kickoff = datetime.now() + timedelta(days=1) 
    deadline = first_kickoff - timedelta(hours=1)
    reveal_time = first_kickoff - timedelta(minutes=30)
    
    if simulate_reveal: reveal_time = datetime.now() - timedelta(hours=1)
    now = datetime.now()
    is_reveal_active = (now > reveal_time)

    # Pass full player list to display function
    display_player_status(all_picks, matches, all_players_full, reveal_mode=is_reveal_active)
    display_fixtures_visual(matches)
    
    # Calculate Active Pot
    active_count = len([p for p in all_players_full if p.get('status') == 'active'])
    
    st.write("")
    c1, c2 = st.columns(2)
    with c1: st.metric("💰 Prize Pot", f"£{active_count * ENTRY_FEE}")
    with c2: st.metric("DEADLINE", deadline.strftime("%a %H:%M"))

    st.markdown("---")
    st.subheader("🎯 Make Your Selection")

    # Only show ACTIVE players in dropdown
    # We create a list of names for the dropdown
    player_names = sorted([p['name'] for p in all_players_full])
    options = ["Select your name...", "➕ I am a New Player"] + player_names
    selected_option = st.selectbox("Who are you?", options)
    actual_user_name = None

    if selected_option == "➕ I am a New Player":
        new_name_input = st.text_input("Enter your full name (First & Last):")
        if new_name_input:
            clean_name = new_name_input.strip().title()
            if clean_name in player_names:
                st.error(f"'{clean_name}' already exists!")
            else:
                actual_user_name = clean_name
    elif selected_option != "Select your name...":
        actual_user_name = selected_option

    if actual_user_name:
        user_ref = db.collection('players').document(actual_user_name)
        user_doc = user_ref.get()
        
        if user_doc.exists and user_doc.to_dict().get('status') == 'eliminated':
            st.error(f"❌ Sorry {actual_user_name}, you have been eliminated!")
            st.info("Wait for a new game to start to rejoin.")
        else:
            pick_id = f"{actual_user_name}_GW{gw}"
            pick_ref = db.collection('picks').document(pick_id)
            existing_pick = pick_ref.get()

            if existing_pick.exists:
                team = existing_pick.to_dict().get('team')
                st.success(f"✅ Pick confirmed for **{actual_user_name}**: **{team}**")
                st.caption("Contact admin to change.")
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
                            st.rerun()
                if used: st.info(f"Teams used by {actual_user_name}: {', '.join(used)}")

if __name__ == "__main__":
    main()
