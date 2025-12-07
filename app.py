import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
from google.cloud import firestore
import streamlit_authenticator as stauth
import bcrypt

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Last Man Standing", layout="centered")

# --- 2. SECRETS & DATABASE SETUP ---
try:
    API_KEY = st.secrets["FOOTBALL_API_KEY"]
    db = firestore.Client.from_service_account_info(st.secrets["firebase"])
except Exception as e:
    st.error(f"Error connecting to secrets or database: {e}")
    st.stop()

PL_COMPETITION_ID = 2021  # Premier League ID
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

        /* 2. HEADERS */
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
        h1, h2, h3 { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; text-transform: uppercase; }

        /* 3. METRIC CARDS */
        div[data-testid="stMetric"] {
            background-color: #28002B !important; border: 1px solid rgba(255,255,255,0.1);
            padding: 15px !important; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        div[data-testid="stMetricLabel"] { color: #00ff87 !important; }
        div[data-testid="stMetricValue"] { color: #ffffff !important; }

        /* 4. MATCH CARDS */
        .match-card {
            background-color: #28002B; border-radius: 12px; padding: 12px 10px;
            margin-bottom: 15px; 
            border: 1px solid rgba(255,255,255,0.05); box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            display: flex; flex-direction: column; 
            transition: transform 0.2s ease;
        }
        .match-card:hover { border-color: #00ff87; transform: translateY(-2px); }

        .match-info-row {
            display: flex; align-items: center; justify-content: space-between; width: 100%;
        }

        .picks-row {
            display: flex; justify-content: space-between; width: 100%;
            margin-top: 10px; padding-top: 8px;
            border-top: 1px solid rgba(255,255,255,0.08);
            font-size: 12px; color: #aaa;
        }

        .team-container {
            flex: 1; display: flex; align-items: center; font-weight: 700; color: white;
            font-size: 15px; letter-spacing: 0.5px; min-width: 0;
        }
        .team-container span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; }
        .home-team { justify-content: flex-end; text-align: right; }
        .home-team span { text-align: right; }
        .away-team { justify-content: flex-start; text-align: left; }
        .away-team span { text-align: left; }
        
        .crest-img { 
            width: 38px; height: 38px; object-fit: contain; margin: 0 10px; flex-shrink: 0;
            filter: drop-shadow(0 2px 2px rgba(0,0,0,0.5)); 
        }

        .score-box {
            flex: 0 0 90px; text-align: center; background-color: #1F0022;
            border-radius: 8px; padding: 5px 0; border: 1px solid rgba(255,255,255,0.05); margin: 0 5px;
        }
        .score-text { font-size: 18px; font-weight: 800; color: #00ff87; margin: 0; line-height: 1; }
        .time-text { font-size: 16px; font-weight: 700; color: white; margin: 0; line-height: 1; }
        .status-text { font-size: 9px; color: #ddd; text-transform: uppercase; margin-top: 5px; letter-spacing: 1px; font-weight: 600; }
        
        .home-picks { text-align: right; width: 45%; }
        .away-picks { text-align: left; width: 45%; }
        .pick-name { 
            color: #00ff87; font-weight: 600; margin-left: 5px; margin-right: 5px;
            display: inline-block;
        }

        .stButton button {
            background-color: #28002B !important; color: #ffffff !important;
            border: 1px solid #00ff87 !important; font-weight: 800 !important;
            text-transform: uppercase;
        }
        
        @media (max-width: 600px) {
            .team-container { font-size: 12px; }
            .crest-img { width: 25px; height: 25px; margin: 0 5px; }
            .hero-title { font-size: 40px; }
        }
    </style>
    """, unsafe_allow_html=True)

# --- 4. HELPER FUNCTIONS ---
def fetch_users():
    users = {}
    try:
        docs = db.collection('players').stream()
        for doc in docs:
            data = doc.to_dict()
            if data.get('password'):
                users[doc.id] = {
                    'name': data.get('name', doc.id),
                    'password': data.get('password'),
                    'email': data.get('email', '')
                }
    except: pass
    if not users:
        users = {'admin': {'name':'Admin','password':'$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW','email':''}}
    return users

def get_all_picks_for_gw(gw):
    try:
        picks_ref = db.collection('picks').where('matchday', '==', gw).stream()
        return [p.to_dict() for p in picks_ref]
    except:
        return []

@st.cache_data(ttl=3600)
def get_current_gameweek():
    url = f"https://api.football-data.org/v4/competitions/{PL_COMPETITION_ID}/matches?status=SCHEDULED"
    headers = {'X-Auth-Token': API_KEY}
    try:
        r = requests.get(url, headers=headers)
        return r.json()['matches'][0]['matchday'] if r.json()['matches'] else 38
    except: return None

@st.cache_data(ttl=600)
def get_matches_for_gameweek(gw):
    url = f"https://api.football-data.org/v4/competitions/{PL_COMPETITION_ID}/matches?matchday={gw}"
    headers = {'X-Auth-Token': API_KEY}
    try:
        r = requests.get(url, headers=headers)
        return r.json()['matches']
    except: return []

def get_gameweek_deadline(matches):
    dates = [datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00')) for m in matches]
    return min(dates) if dates else datetime.now()

def display_fixtures_visual(matches, all_picks, show_picks=False):
    st.subheader(f"Gameweek {matches[0]['matchday']} Fixtures")
    
    for match in matches:
        home = match['homeTeam']
        away = match['awayTeam']
        status = match['status']
        dt = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
        
        # 1. CENTER CONTENT (No spaces!)
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

        # 2. PICKS LIST (No spaces!)
        picks_html = ""
        if show_picks:
            home_pickers = [p['user'] for p in all_picks if p['team'] == home['name']]
            away_pickers = [p['user'] for p in all_picks if p['team'] == away['name']]
            
            h_str = ", ".join([f"<span class='pick-name'>{u}</span>" for u in home_pickers])
            a_str = ", ".join([f"<span class='pick-name'>{u}</span>" for u in away_pickers])
            
            if h_str or a_str:
                picks_html = f'<div class="picks-row"><div class="home-picks">{h_str}</div><div class="away-picks">{a_str}</div></div>'

        # 3. RENDER CARD (Flush left!)
        st.markdown(f"""
<div class="match-card">
<div class="match-info-row">
<div class="team-container home-team">
<span>{home['name']}</span>
<img src="{home['crest']}" class="crest-img">
</div>
<div class="score-box">
{center_html}
</div>
<div class="team-container away-team">
<img src="{away['crest']}" class="crest-img">
<span>{away['name']}</span>
</div>
</div>
{picks_html}
</div>
""", unsafe_allow_html=True)

# --- 5. MAIN APP LOGIC ---
def main():
    inject_custom_css()
    users_dict = fetch_users()

    with st.sidebar:
        st.header("🔧 Admin")
        with st.expander("Hash Gen"):
            p = st.text_input("Pass:", type="password")
            if p: st.code(bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode())
        
        st.divider()
        simulate_reveal = st.checkbox("Simulate Pick Reveal", value=False)

    authenticator = stauth.Authenticate({'usernames': users_dict}, 'lms_cookie_v23', 'lms_key', 30)

    if st.session_state["authentication_status"]:
        name = st.session_state["name"]
        username = st.session_state["username"]
        
        with st.sidebar:
            st.write(f"User: **{name}**")
            authenticator.logout('Logout', 'main')

        st.markdown("""
            <div class="hero-container">
                <div class="hero-title">LAST MAN STANDING</div>
                <div class="hero-subtitle">PREMIER LEAGUE 24/25</div>
            </div>
        """, unsafe_allow_html=True)

        gw = get_current_gameweek()
        if not gw: st.stop()
        matches = get_matches_for_gameweek(gw)
        if not matches: st.stop()
        
        all_picks = get_all_picks_for_gw(gw)
        display_fixtures_visual(matches, all_picks, show_picks=simulate_reveal)
        st.write("") 

        # --- DEADLINE LOGIC ---
        upcoming = [m for m in matches if m['status'] == 'SCHEDULED']
        first_kickoff = get_gameweek_deadline(upcoming) if upcoming else get_gameweek_deadline(matches)
        
        # FORCE FUTURE for testing
        now = datetime.now()
        first_kickoff = now + timedelta(days=1)
        
        deadline = first_kickoff - timedelta(hours=1)
        reveal_time = first_kickoff - timedelta(minutes=30)
        
        if simulate_reveal:
            reveal_time = now - timedelta(hours=1)

        c1, c2 = st.columns(2)
        with c1: st.metric("💰 Prize Pot", f"£{len(users_dict) * ENTRY_FEE}")
        with c2: st.metric("DEADLINE", deadline.strftime("%a %H:%M"))

        tab1, tab2 = st.tabs(["🎯 Make Selection", "👀 Opponent Watch"])

        with tab1:
            pick_id = f"{username}_GW{gw}"
            pick_ref = db.collection('picks').document(pick_id)
            pick_doc = pick_ref.get()

            if pick_doc.exists:
                team = pick_doc.to_dict().get('team')
                st.success(f"LOCKED IN: {team}")
            else:
                user_ref = db.collection('players').document(username)
                user_doc = user_ref.get()
                used = user_doc.to_dict().get('used_teams', []) if user_doc.exists else []
                valid = set([m['homeTeam']['name'] for m in matches] + [m['awayTeam']['name'] for m in matches])
                available = sorted([t for t in valid if t not in used])

                if not available: st.warning("No teams.")
                else:
                    with st.form("pick"):
                        choice = st.selectbox("Select Team:", available)
                        if st.form_submit_button("LOCK IN PICK"):
                            pick_ref.set({'user': username, 'team': choice, 'matchday': gw, 'timestamp': datetime.now()})
                            user_ref.set({'used_teams': firestore.ArrayUnion([choice]), 'status': 'active'}, merge=True)
                            st.rerun()
                if used: st.info(f"Used: {', '.join(used)}")

        with tab2:
            picks_data = []
            for p in all_picks:
                u, t = p.get('user'), p.get('team')
                is_revealed = (now > reveal_time) or (u == username)
                show = t if is_revealed else "HIDDEN 🔒"
                picks_data.append({"User": u, "Pick": show})
            
            if picks_data: st.dataframe(pd.DataFrame(picks_data), use_container_width=True, hide_index=True)
            else: st.caption("No picks yet.")

    else:
        st.markdown("""
            <div class="hero-container">
                <div class="hero-title">LAST MAN STANDING</div>
                <div class="hero-subtitle">LOGIN OR REGISTER</div>
            </div>
        """, unsafe_allow_html=True)
        tab_login, tab_register = st.tabs(["Log In", "Sign Up"])
        with tab_login:
            authenticator.login('main')
            if st.session_state["authentication_status"] is False: st.error('Incorrect')
            elif st.session_state["authentication_status"] is None: st.warning('Enter details')
        with tab_register:
            with st.form("register_form"):
                st.subheader("Create Account")
                u = st.text_input("Username").lower().strip()
                n = st.text_input("Full Name")
                p = st.text_input("Password", type="password")
                e = st.text_input("Email")
                if st.form_submit_button("Register"):
                    if not u or not p: st.error("Missing fields")
                    elif u in users_dict: st.error("Taken!")
                    else:
                        h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
                        db.collection('players').document(u).set({'name':n,'password':h,'email':e,'status':'active','used_teams':[]})
                        st.success("Created! Log in now.")
                        st.rerun()

if __name__ == "__main__":
    main()
