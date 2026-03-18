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
    TREASURER_PASSWORD = st.secrets.get("TREASURER_PASSWORD", "money123")
    
except Exception as e:
    st.error(f"Error connecting to secrets: {e}")
    st.stop()

PL_COMPETITION_ID = 2021
ENTRY_FEE = 10

# --- 3. THE COMPLETE CUSTOM CSS ---
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
        h1, h2, h3, h4, h5, h6, p, label { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; }

        /* PLAYER CARDS */
        .player-row-container { display: flex; flex-direction: column; gap: 10px; margin-bottom: 30px; }
        
        .player-card {
            background-color: #28002B; border: 1px solid rgba(0, 255, 135, 0.3); border-radius: 12px;
            padding: 12px 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: transform 0.2s;
            display: flex; align-items: center; justify-content: space-between; width: 100%;
        }
        .player-card:hover { transform: translateY(-2px); border-color: #00ff87; }

        .player-card-eliminated {
            background-color: #1a1a1a; border: 1px solid #444; border-radius: 12px;
            padding: 10px 20px; display: flex; align-items: center; justify-content: space-between; width: 100%;
            opacity: 0.8;
        }
        
        .pc-name { font-size: 16px; font-weight: 700; color: #fff; flex: 1; text-align: left; overflow-wrap: break-word; }
        .pc-center { flex: 0 0 100px; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .pc-badge { width: 35px; height: 35px; object-fit: contain; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.5)); }
        
        .status-tag-win { font-size: 10px; background: #00ff87; color: #1F0022; padding: 2px 6px; border-radius: 4px; font-weight: 800; margin-top: 4px; }
        .status-tag-loss { font-size: 10px; background: #ff4b4b; color: white; padding: 2px 6px; border-radius: 4px; font-weight: 800; margin-top: 4px; }
        
        .pc-team { font-size: 14px; color: #00ff87; font-weight: 600; flex: 1; text-align: right; text-transform: uppercase; }
        .pc-eliminated-text { font-size: 12px; color: #ff4b4b; font-weight: 600; flex: 1; text-align: right; text-transform: uppercase; }

        /* MATCH CARDS */
        .match-card {
            background-color: #28002B; border-radius: 12px; padding: 12px 10px;
            margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.05); box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            display: flex; flex-direction: column; 
        }
        .team-container { flex: 1; display: flex; align-items: center; font-weight: 700; color: white; font-size: 15px; min-width: 0; }
        .home-team { justify-content: flex-end; text-align: right; }
        .away-team { justify-content: flex-start; text-align: left; }
        .crest-img { width: 38px; height: 38px; object-fit: contain; margin: 0 10px; }
        
        .score-box { flex: 0 0 90px; text-align: center; background-color: #1F0022; border-radius: 8px; padding: 5px 0; }
        .score-text { font-size: 18px; font-weight: 800; color: #00ff87; line-height: 1; }
        .status-text { font-size: 9px; color: #ddd; text-transform: uppercase; margin-top: 5px; font-weight: 600; }

        /* BANNERS */
        .banner-container { text-align: center; padding: 20px; border-radius: 10px; margin-bottom: 20px; animation: pulse 2s infinite; }
        .banner-rollover { background-color: #ff4b4b; color: white; box-shadow: 0 0 20px rgba(255, 75, 75, 0.6); }
        .banner-winner { background-color: #FFD700; color: #28002B; box-shadow: 0 0 20px rgba(255, 215, 0, 0.6); }
        .banner-title { font-family: 'Teko', sans-serif; font-size: 36px; font-weight: 700; margin: 0; }
        @keyframes pulse { 0% {transform:scale(1);} 50% {transform:scale(1.02);} 100% {transform:scale(1);} }

        /* BUTTONS */
        div.stButton > button { background-color: #28002B !important; color: #ffffff !important; border: 1px solid #00ff87 !important; font-weight: 700 !important; }
        div.stButton > button:hover { background-color: #00ff87 !important; border-color: #28002B !important; color: #28002B !important; }
        div.stFormSubmitButton > button { background-color: #00ff87 !important; color: #28002B !important; width: 100%; }
        
        /* EXPANDERS */
        .streamlit-expanderHeader { background-color: #28002B !important; color: #ffffff !important; border-radius: 8px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. DATA LOGIC & SETTINGS ---

@st.cache_data(ttl=60)
def get_game_settings():
    doc = db.collection('settings').document('config').get()
    if doc.exists:
        d = doc.to_dict()
        return {'rollover_multiplier': d.get('rollover_multiplier', 1), 'current_gw': d.get('current_gw', 1)}
    return {'rollover_multiplier': 1, 'current_gw': 1}

def update_game_settings(multiplier=None, gw=None):
    ref = db.collection('settings').document('config')
    updates = {}
    if multiplier is not None: updates['rollover_multiplier'] = multiplier
    if gw is not None: updates['current_gw'] = gw
    ref.set(updates, merge=True)
    st.cache_data.clear()

@st.cache_data(ttl=60)
def get_all_players_full():
    docs = db.collection('players').stream()
    return [doc.to_dict() for doc in docs]

@st.cache_data(ttl=60)
def get_all_picks_for_gw(gw):
    return [p.to_dict() for p in db.collection('picks').where('matchday', '==', gw).stream()]

@st.cache_data(ttl=300)
def get_matches_for_gameweek(gw):
    headers = {'X-Auth-Token': API_KEY}
    try:
        r = requests.get(f"https://api.football-data.org/v4/competitions/{PL_COMPETITION_ID}/matches?matchday={gw}", headers=headers)
        if r.status_code == 429: return []
        return r.json().get('matches', [])
    except: return []

# --- 5. BATCH OPERATIONS (CRITICAL IMPROVEMENT) ---

def admin_reset_game(current_gw, is_rollover=False):
    batch = db.batch()
    # Reset all players
    players = db.collection('players').stream()
    for p in players:
        p_ref = db.collection('players').document(p.id)
        batch.update(p_ref, {'status': 'pending', 'used_teams': [], 'eliminated_gw': None, 'paid': False})
    
    # Wipe current picks
    picks = db.collection('picks').where('matchday', '==', current_gw).stream()
    for p in picks:
        batch.delete(db.collection('picks').document(p.id))
    
    # Update Multiplier
    curr = get_game_settings()
    new_mult = (curr['rollover_multiplier'] + 1) if is_rollover else 1
    batch.set(db.collection('settings').document('config'), {'rollover_multiplier': new_mult}, merge=True)
    
    batch.commit()
    st.cache_data.clear()
    return "ROLLOVER!" if is_rollover else "RESET!"

# --- 6. UI COMPONENT FUNCTIONS ---

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

def display_player_status(picks, matches, players_data, reveal_mode=False):
    team_results = calculate_team_results(matches)
    user_pick_map = {p['user']: p['team'] for p in picks}
    crest_map = {m['homeTeam']['name']: m['homeTeam']['crest'] for m in matches}
    crest_map.update({m['awayTeam']['name']: m['awayTeam']['crest'] for m in matches})
    
    active_players = [p for p in players_data if p.get('status') in ['active', 'pending']]
    elim_players = [p for p in players_data if p.get('status') == 'eliminated']
    
    # --- STILL STANDING ---
    with st.expander(f"🛡️ STILL STANDING ({len(active_players)})", expanded=True):
        active_html = ""
        for p in sorted(active_players, key=lambda x: x['name']):
            name, team = p['name'], user_pick_map.get(p['name'])
            res = team_results.get(team, 'PENDING')
            
            if team:
                if reveal_mode:
                    badge_url = crest_map.get(team, "")
                    status_tag = '<div class="status-tag-win">THROUGH</div>' if res == 'WIN' else ""
                    mid = f'<img src="{badge_url}" class="pc-badge">{status_tag}'
                    btm = f'<div class="pc-team">{team}</div>'
                else:
                    mid, btm = '<span style="font-size:24px">🔒</span>', '<div class="pc-team">HIDDEN</div>'
            else:
                mid, btm = '<span style="font-size:24px">⏳</span>', '<div class="pc-team" style="color:#aaa">NO PICK</div>'
            
            active_html += f'<div class="player-card"><div class="pc-name">{name}</div><div class="pc-center">{mid}</div>{btm}</div>'
        st.markdown(f'<div class="player-row-container">{active_html}</div>', unsafe_allow_html=True)

    # --- THE FALLEN ---
    if elim_players:
        with st.expander(f"🪦 THE FALLEN ({len(elim_players)})", expanded=False):
            elim_html = ""
            for p in sorted(elim_players, key=lambda x: x.get('eliminated_gw', 0), reverse=True):
                gw_out = p.get('eliminated_gw', '?')
                elim_html += f'<div class="player-card-eliminated"><div class="pc-name" style="color:#aaa">{p["name"]}</div><div class="pc-center">💀</div><div class="pc-team" style="color:#ff4b4b">OUT GW{gw_out}</div></div>'
            st.markdown(f'<div class="player-row-container">{elim_html}</div>', unsafe_allow_html=True)

def display_fixtures(matches):
    st.subheader("Fixtures")
    for m in matches:
        h, a = m['homeTeam'], m['awayTeam']
        score_html = f'<div class="score-text">{m["score"]["fullTime"]["home"]} - {m["score"]["fullTime"]["away"]}</div>' if m['status'] == 'FINISHED' else '<div class="score-text">VS</div>'
        st.markdown(f"""
        <div class="match-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div class="team-container home-team"><span>{h['name']}</span><img src="{h['crest']}" class="crest-img"></div>
                <div class="score-box">{score_html}<div class="status-text">{m['status']}</div></div>
                <div class="team-container away-team"><img src="{a['crest']}" class="crest-img"><span>{a['name']}</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- 7. MAIN APP LOGIC ---

def main():
    inject_custom_css()
    settings = get_game_settings()
    current_gw = settings['current_gw']
    
    # --- ADMIN SIDEBAR ---
    with st.sidebar:
        st.header("🔧 Admin Panel")
        if 'admin_logged_in' not in st.session_state: st.session_state.admin_logged_in = False
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if pwd == ADMIN_PASSWORD: st.session_state.admin_logged_in = True; st.rerun()
        
        if st.session_state.admin_logged_in:
            st.subheader("🎮 Master Game Control")
            new_gw = st.number_input("Active Gameweek", 1, 38, value=current_gw)
            if st.button("Update Global Gameweek"):
                update_game_settings(gw=new_gw)
                st.rerun()
            
            st.divider()
            st.subheader("⚡ Danger Zone")
            if st.button("🔄 HARD RESET"): st.warning(admin_reset_game(current_gw, False)); st.rerun()
            if st.button("💀 ROLLOVER"): st.error(admin_reset_game(current_gw, True)); st.rerun()

    # --- HERO SECTION ---
    st.markdown('<div class="hero-title">LAST MAN STANDING</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-subtitle">PREMIER LEAGUE SEASON 25/26 • GW{current_gw}</div>', unsafe_allow_html=True)

    matches = get_matches_for_gameweek(current_gw)
    if not matches: st.warning("Fixtures currently unavailable."); st.stop()

    # Pot & Deadline Info
    all_players = get_all_players_full()
    pot = len([p for p in all_players if p.get('paid', False)]) * ENTRY_FEE * settings['rollover_multiplier']
    
    first_ko = datetime.fromisoformat(matches[0]['utcDate'].replace('Z', ''))
    deadline, reveal_time = first_ko - timedelta(hours=1), first_ko - timedelta(minutes=30)
    now = datetime.utcnow()

    c1, c2 = st.columns(2)
    c1.metric("💰 Prize Pot", f"£{pot}")
    c2.metric("⏰ Deadline", "EXPIRED" if now > deadline else deadline.strftime("%a %H:%M"))

    # Selection Form
    st.divider()
    st.subheader("🎯 Make Your Selection")
    picks_this_week = {p['user'] for p in get_all_picks_for_gw(current_gw)}
    elig_to_pick = sorted([p['name'] for p in all_players if p.get('status') in ['active', 'pending'] and p['name'] not in picks_this_week])
    
    user_choice = st.selectbox("Select your name:", ["Choose..."] + ["➕ New Player"] + elig_to_pick)
    
    if user_choice != "Choose...":
        actual_name = st.text_input("Full Name:").strip().title() if user_choice == "➕ New Player" else user_choice
        
        if actual_name:
            p_ref = db.collection('players').document(actual_name)
            p_doc = p_ref.get()
            if p_doc.exists and p_doc.to_dict().get('status') == 'eliminated':
                st.error("You have been eliminated.")
            else:
                used = p_doc.to_dict().get('used_teams', []) if p_doc.exists else []
                valid_teams = sorted(list(set([m['homeTeam']['name'] for m in matches] + [m['awayTeam']['name'] for m in matches])))
                avail_teams = [t for t in valid_teams if t not in used]
                
                if now > deadline: st.error("Gameweek Locked.")
                else:
                    with st.form("pick_form"):
                        team_choice = st.selectbox("Pick Team:", avail_teams)
                        if st.form_submit_button("SUBMIT PICK"):
                            db.collection('picks').document(f"{actual_name}_GW{current_gw}").set({'user': actual_name, 'team': team_choice, 'matchday': current_gw, 'timestamp': datetime.now()})
                            p_ref.set({'name': actual_name, 'used_teams': firestore.ArrayUnion([team_choice]), 'status': 'active'}, merge=True)
                            st.success("Pick Locked In!"); st.cache_data.clear(); st.rerun()

    # WINNER / ROLLOVER BANNERS
    survivors = [p for p in all_players if p.get('status') in ['active', 'pending']]
    if len(survivors) == 0 and len(all_players) > 0:
        st.markdown('<div class="banner-container banner-rollover"><div class="banner-title">💀 GAME OVER • ROLLOVER 💀</div></div>', unsafe_allow_html=True)
    elif len(survivors) == 1:
        st.markdown(f'<div class="banner-container banner-winner"><div class="banner-title">🏆 WINNER: {survivors[0]["name"]} 🏆</div></div>', unsafe_allow_html=True)

    st.divider()
    display_player_status(get_all_picks_for_gw(current_gw), matches, all_players, reveal_mode=(now > reveal_time))
    display_fixtures(matches)

if __name__ == "__main__":
    main()
