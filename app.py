import streamlit as st
import pandas as pd
import bcrypt
from datetime import datetime, timedelta
import requests
from google.cloud import firestore
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities.hasher import Hasher

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Last Man Standing", layout="wide")

# --- 2. SECRETS & DATABASE SETUP ---
try:
    # API Key (At the top level of your secrets)
    API_KEY = st.secrets["FOOTBALL_API_KEY"]
    
    # Firebase Connection (Matches [firebase] in your secrets)
    db = firestore.Client.from_service_account_info(st.secrets["firebase"])
except Exception as e:
    st.error(f"Error connecting to secrets or database: {e}")
    st.stop()

PL_COMPETITION_ID = 2021  # Premier League ID
ENTRY_FEE = 10

# --- 3. HELPER FUNCTIONS ---
def get_fixtures():
    """Fetch upcoming PL matches from API"""
    url = f"https://api.football-data.org/v4/competitions/{PL_COMPETITION_ID}/matches?status=SCHEDULED"
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data['matches']
    except Exception as e:
        st.error(f"Error fetching football data: {e}")
        return []

def get_gameweek_deadline(matches):
    """Find the kickoff time of the very first game in the list"""
    if not matches:
        return datetime.now() + timedelta(days=365) 
    
    # Parse dates from ISO format (handling timezone 'Z')
    dates = []
    for m in matches:
        # Replace 'Z' with +00:00 for UTC awareness
        dt = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00'))
        dates.append(dt)
        
    first_match = min(dates)
    return first_match

# --- 4. MAIN APP LOGIC ---
def main():
    
    # --- SIDEBAR: ADMIN HASH GENERATOR (Use this to create new passwords) ---
    with st.sidebar:
        st.header("🔧 Admin Tools")
        with st.expander("Password Hash Generator"):
            new_pass = st.text_input("Enter a password to hash:", type="password")
            if new_pass:
                # Generate hash using the library's utility
                hashed_pw = Hasher([new_pass]).generate()[0]
                st.code(hashed_pw, language="text")
                st.caption("Copy this hash and paste it into 'users_dict' in app.py")

    # --- AUTHENTICATION SETUP ---
    # REPLACE THE HASH BELOW with the one you generate in the sidebar!
    users_dict = {
        'jdoe': {
            'name': 'John Doe',
            'password': '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', # Default: "abc"
            'email': 'jdoe@gmail.com'
        }
    }

    authenticator = stauth.Authenticate(
        {'usernames': users_dict},
        'lms_cookie_name', 
        'lms_signature_key', 
        cookie_expiry_days=30
    )

    # Render Login Widget
    authenticator.login('main')

    # --- IF LOGGED IN ---
    if st.session_state["authentication_status"]:
        username = st.session_state["username"]
        name = st.session_state["name"]
        
        # Sidebar with Logout
        with st.sidebar:
            st.divider()
            st.write(f"User: **{name}**")
            authenticator.logout('Logout', 'main')

        st.title(f"⚽ Last Man Standing")

        # Fetch Data
        matches = get_fixtures()
        if not matches:
            st.warning("No upcoming matches found in the Premier League schedule.")
            st.stop()
            
        # Calculate Deadlines
        first_kickoff = get_gameweek_deadline(matches)
        deadline = first_kickoff - timedelta(hours=1)
        reveal_time = first_kickoff - timedelta(minutes=30)
        
        # Current time (timezone aware to match API data)
        current_time = datetime.now(first_kickoff.tzinfo)

        # Prize Pot Display
        st.metric(label="💰 Estimated Prize Pot", value=f"£{10 * ENTRY_FEE} (Example)")

        # Game Tabs
        tab1, tab2 = st.tabs(["My Pick", "All Selections"])

        # --- TAB 1: USER SELECTION ---
        with tab1:
            st.subheader(f"Gameweek {matches[0]['matchday']}")
            
            if current_time > deadline:
                st.error(f"🚫 Gameweek Locked. Deadline was {deadline.strftime('%H:%M')}")
            else:
                st.info(f"⏳ Deadline: {deadline.strftime('%A %d %b at %H:%M')}")
                
                # Fetch user's history from Firestore
                user_ref = db.collection('players').document(username)
                user_doc = user_ref.get()
                
                used_teams = []
                if user_doc.exists:
                    data = user_doc.to_dict()
                    used_teams = data.get('used_teams', [])
                
                # Available Teams
                home_teams = [m['homeTeam']['name'] for m in matches]
                away_teams = [m['awayTeam']['name'] for m in matches]
                all_teams = sorted(list(set(home_teams + away_teams)))
                
                # Filter out used teams
                available_teams = [t for t in all_teams if t not in used_teams]
                
                if not available_teams:
                    st.error("You have used all available teams!")
                else:
                    with st.form("pick_form"):
                        choice = st.selectbox("Pick a team to WIN:", available_teams)
                        submitted = st.form_submit_button("Lock In Pick")
                        
                        if submitted:
                            # 1. Save Pick to 'picks' collection
                            gw = matches[0]['matchday']
                            pick_id = f"{username}_GW{gw}"
                            
                            db.collection('picks').document(pick_id).set({
                                'user': username,
                                'team': choice,
                                'matchday': gw,
                                'timestamp': datetime.now()
                            })
                            
                            # 2. Update 'used_teams' in 'players' collection
                            user_ref.set({
                                'used_teams': firestore.ArrayUnion([choice]),
                                'status': 'active'
                            }, merge=True)
                            
                            st.success(f"Locked in: {choice}")
                            st.rerun()

                # Show History
                if used_teams:
                    st.write("---")
                    st.caption(f"Teams you have already used: {', '.join(used_teams)}")

        # --- TAB 2: OPPONENT WATCH ---
        with tab2:
            st.subheader("Opponent Watch")
            
            # Fetch all picks for this gameweek
            current_matchday = matches[0]['matchday']
            picks_ref = db.collection('picks').where('matchday', '==', current_matchday).stream()
            
            picks_data = []
            for pick in picks_ref:
                p = pick.to_dict()
                pick_user = p.get('user', 'Unknown')
                pick_team = p.get('team', 'Unknown')
                
                # Visibility Logic
                if current_time < reveal_time and pick_user != username:
                    display_team = "HIDDEN 🔒"
                else:
                    display_team = pick_team
                
                picks_data.append({"Player": pick_user, "Selection": display_team})
            
            if picks_data:
                st.dataframe(pd.DataFrame(picks_data), use_container_width=True)
            else:
                st.info("No picks have been made for this week yet.")

    # --- IF LOGIN FAILED ---
    elif st.session_state["authentication_status"] is False:
        st.error('Username/password is incorrect')
    elif st.session_state["authentication_status"] is None:
        st.warning('Please enter your username and password')

if __name__ == "__main__":
    main()
