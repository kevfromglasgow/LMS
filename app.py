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

# --- 3. CUSTOM STYLING (CSS) ---
def inject_custom_css():
    st.markdown("""
    <style>
        /* 1. NUCLEAR BACKGROUND FIX */
        /* Target the main view container with !important to override Streamlit Dark Mode */
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(rgba(10, 10, 10, 0.8), rgba(10, 10, 10, 0.9)), 
                        url('https://images.unsplash.com/photo-1522778119026-d647f0565c6a?q=80&w=2070&auto=format&fit=crop') !important;
            background-size: cover !important;
            background-position: center !important;
            background-attachment: fixed !important;
            background-repeat: no-repeat !important;
        }
        
        /* 2. TEXT HEADERS */
        h1, h2, h3, p, div, span { 
            font-family: 'Helvetica Neue', sans-serif; 
        }
        h1, h2, h3 {
            color: #ffffff !important; 
            text-transform: uppercase; 
            text-shadow: 0 2px 4px rgba(0,0,0,0.8);
        }
        
        /* 3. METRIC CARDS (Frosted Glass) */
        div[data-testid="stMetric"] {
            background-color: rgba(20, 20, 20, 0.7) !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            padding: 15px !important; 
            border-radius: 10px !important; 
            backdrop-filter: blur(10px);
        }
        div[data-testid="stMetricLabel"] { color: #00ff87 !important; }
        div[data-testid="stMetricValue"] { color: #ffffff !important; }
        
        /* 4. BUTTONS */
        .stButton button {
            background-color: #38003c !important; 
            color: #00ff87 !important;
            border: 1px solid #00ff87 !important; 
            font-weight: bold !important;
            box-shadow: 0 0 10px rgba(0, 255, 135, 0.2);
            transition: all 0.3s ease;
        }
        .stButton button:hover {
            transform: scale(1.05);
            box-shadow: 0 0 20px rgba(0, 255, 135, 0.6);
        }
        
        /* 5. MATCH CARD CSS (No Indentation Issues) */
        .match-card {
            background-color: rgba(26, 28, 36, 0.9);
            border-radius: 12px;
            padding: 12px 16px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border: 1px solid rgba(255,255,255,0.05);
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            backdrop-filter: blur(5px);
        }
        .team-container {
            flex: 1; display: flex; align-items: center;
            font-weight: 700; color: white; font-size: 15px; letter-spacing: 0.5px;
        }
        .home-team { justify-content: flex-end; text-align: right; }
        .away-team { justify-content: flex-start; text-align: left; }
        .crest-img { width: 38px; height: 38px; object-fit: contain; margin: 0 15px; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.5)); }
        
        .score-box {
            flex: 0 0 110px; text-align: center;
        }
        .score-text { font-size: 20px; font-weight: 800; color: #00ff87; margin: 0; line-height: 1; }
        .time-text { font-size: 18px; font-weight: 700; color: white; margin: 0; line-height: 1; }
        .status-text { font-size: 10px; color: #bbb; text-transform: uppercase; margin-top: 5px; letter-spacing: 1px; }
        
    </style>
    """, unsafe_allow_html=True)

# --- 4. HELPER FUNCTIONS ---
@st.cache_data(ttl=3600)
def get_current_gameweek():
    url = f"https://api.football-data.org/v4/competitions/{PL_COMPETITION_ID}/matches?status=SCHEDULED"
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        matches = response.json().get('matches', [])
        return matches[0]['matchday'] if matches else 38
    except:
        return None

@st.cache_data(ttl=600)
def get_matches_for_gameweek(gw):
    url = f"https://api.football-data.org/v4/competitions/{PL_COMPETITION_ID}/matches?matchday={gw}"
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()['matches']
    except:
        return []

def get_gameweek_deadline(matches):
    if not matches: return datetime.now() + timedelta(days=365)
    dates = [datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00')) for m in matches]
    return min(dates)

def display_fixtures_visual(matches):
    st.subheader(f"Gameweek {matches[0]['matchday']} Fixtures")
    
    for match in matches:
        home = match['homeTeam']
        away = match['awayTeam']
        status = match['status']
        dt = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
        
        # 1. Prepare CENTER content (Clean strings, no indentation)
        if status == 'FINISHED':
            h_score = match['score']['fullTime']['home']
            a_score = match['score']['fullTime']['away']
            center_html = f'<div class="score-text">{h_score} - {a_score}</div><div class="status-text">FT</div>'
            
        elif status in ['IN_PLAY', 'PAUSED']:
            h_score = match['score']['fullTime']['home']
            a_score = match['score']['fullTime']['away']
            center_html = f'<div class="score-text" style="color:#ff4b4b;">{h_score} - {a_score}</div><div class="status-text" style="color:#ff4b4b;">LIVE</div>'
            
        elif status == 'POSTPONED':
            center_html = '<div class="time-text">P-P</div><div class="status-text">Postponed</div>'
            
        else:
            time_str = dt.strftime("%H:%M")
            date_str = dt.strftime("%a %d")
            center_html = f'<div class="time-text">{time_str}</div><div class="status-text">{date_str}</div>'

        # 2. Render Card (Flush left to avoid code block issues)
        st.markdown(f"""
        <div class="match-card">
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
        """, unsafe_allow_html=True)

# --- 5. MAIN APP LOGIC ---
def main():
    inject_custom_css()

    with st.sidebar:
        st.header("🔧 Admin")
        with st.expander("Hash Gen"):
            p = st.text_input("Pass:", type="password")
            if p:
                h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
                st.code(h)

    # --- AUTH ---
    users_dict = {
        'jdoe': {
            'name': 'John Doe',
            'password': '$2b$12$Cs597m281AAw3Z7u0gJFZ.QRvruTkx4PAlhoZqgrqObvwq8qfzDVK',
            'email': 'jdoe@gmail.com'
        }
    }

    authenticator = stauth.Authenticate(
        {'usernames': users_dict},
        'lms_cookie_v12', # Bumped to v12 to force clean login
        'lms_key', 
        cookie_expiry_days=30
    )
    authenticator.login('main')

    if st.session_state["authentication_status"]:
        name = st.session_state["name"]
        username = st.session_state["username"]
        
        with st.sidebar:
            st.write(f"Logged in as **{name}**")
            authenticator.logout('Logout', 'main')

        st.title("⚽ LAST MAN STANDING")
        st.markdown("---")

        gw = get_current_gameweek()
        if not gw: st.stop()
        matches = get_matches_for_gameweek(gw)
        if not matches: st.stop()

        display_fixtures_visual(matches)
        
        st.write("") 

        first_kickoff = get_gameweek_deadline(matches)
        deadline = first_kickoff - timedelta(hours=1)
        reveal_time = first_kickoff - timedelta(minutes=30)
        now = datetime.now(first_kickoff.tzinfo)

        c1, c2 = st.columns(2)
        with c1: st.metric("💰 Prize Pot", f"£{10 * ENTRY_FEE}")
        with c2: st.metric("DEADLINE", deadline.strftime("%a %H:%M"))

        tab1, tab2 = st.tabs(["🎯 Make Selection", "👀 Opponent Watch"])

        with tab1:
            pick_id = f"{username}_GW{gw}"
            pick_ref = db.collection('picks').document(pick_id)
            pick_doc = pick_ref.get()

            if pick_doc.exists:
                team = pick_doc.to_dict().get('team')
                st.success(f"LOCKED IN: {team}")
            elif now > deadline:
                st.error("🚫 Gameweek Locked")
            else:
                user_ref = db.collection('players').document(username)
                user_doc = user_ref.get()
                used = user_doc.to_dict().get('used_teams', []) if user_doc.exists else []

                valid = set([m['homeTeam']['name'] for m in matches if m['status'] == 'SCHEDULED'] + 
                           [m['awayTeam']['name'] for m in matches if m['status'] == 'SCHEDULED'])
                available = sorted([t for t in valid if t not in used])

                if not available:
                    st.warning("No teams available to pick.")
                else:
                    with st.form("pick"):
                        choice = st.selectbox("Select Team:", available)
                        if st.form_submit_button("LOCK IN PICK"):
                            pick_ref.set({'user': username, 'team': choice, 'matchday': gw, 'timestamp': datetime.now()})
                            user_ref.set({'used_teams': firestore.ArrayUnion([choice]), 'status': 'active'}, merge=True)
                            st.rerun()
                
                if used: st.info(f"Used: {', '.join(used)}")

        with tab2:
            picks = db.collection('picks').where('matchday', '==', gw).stream()
            data = []
            for p in picks:
                d = p.to_dict()
                u, t = d.get('user'), d.get('team')
                show = "HIDDEN 🔒" if (now < reveal_time and u != username) else t
                data.append({"User": u, "Pick": show})
            
            if data: st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else: st.caption("No picks yet.")

    elif st.session_state["authentication_status"] is False:
        st.error('Incorrect Password')
    elif st.session_state["authentication_status"] is None:
        st.warning('Please log in')

if __name__ == "__main__":
    main()
