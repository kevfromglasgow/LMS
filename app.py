import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
from google.cloud import firestore
import streamlit_authenticator as stauth
import bcrypt

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Last Man Standing", layout="wide")

# --- 2. SECRETS & DATABASE SETUP ---
try:
    API_KEY = st.secrets["FOOTBALL_API_KEY"]
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
    
    dates = []
    for m in matches:
        dt = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00'))
        dates.append(dt)
        
    first_match = min(dates)
    return first_match

def display_fixtures_visual(matches):
    """Shows a visual grid of badges and kickoff times"""
    st.subheader(f"📅 Gameweek {matches[0]['matchday']} Fixtures")
    
    with st.container():
        cols = st.columns(3)
        for i, match in enumerate(matches):
            home_team = match['homeTeam']['name']
            home_crest = match['homeTeam']['crest']
            away_team = match['awayTeam']['name']
            away_crest = match['awayTeam']['crest']
            
            dt = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
            kickoff_str = dt.strftime("%a %H:%M")

            with cols[i % 3]:
                c1, c2, c3 = st.columns([1, 0.5, 1])
                with c1:
                    st.image(home_crest, width=50)
                    st.caption(home_team)
                with c2:
                    st.write(f"**VS**")
                    st.caption(kickoff_str)
                with c3:
                    st.image(away_crest, width=50)
                    st.caption(away_team)
                st.divider()

# --- 4. MAIN APP LOGIC ---
def main():
    
    with st.sidebar:
        st.header("🔧 Admin Tools")
        with st.expander("Password Hash Generator"):
            new_pass = st.text_input("Enter a password to hash:", type="password")
            if new_pass:
                hashed_bytes = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt())
                hashed_pw = hashed_bytes.decode('utf-8')
                st.code(hashed_pw, language="text")

    # --- AUTHENTICATION SETUP ---
    users_dict = {
        'jdoe': {
            'name': 'John Doe',
            # Use your WORKING hash here
            'password': '$2b$12$Cs597m281AAw3Z7u0gJFZ.QRvruTkx4PAlhoZqgrqObvwq8qfzDVK', 
            'email': 'jdoe@gmail.com'
        }
    }

    authenticator = stauth.Authenticate(
        {'usernames': users_dict},
        'lms_cookie_name_v4', # Bump version to force refresh
        'lms_signature_key', 
        cookie_expiry_days=30
    )

    authenticator.login('main')

    if st.session_state["authentication_status"]:
        username = st.session_state["username"]
        name = st.session_state["name"]
        
        with st.sidebar:
            st.divider()
            st.write(f"User: **{name}**")
            authenticator.logout('Logout', 'main')

        st.title(f"⚽ Last Man Standing")

        # --- DATA FETCH ---
        all_matches = get_fixtures()
        if not all_matches:
            st.warning("No upcoming matches found.")
            st.stop()
            
        # FILTER: Only keep games for the NEXT upcoming Matchday
        next_gw = all_matches[0]['matchday']
        matches = [m for m in all_matches if m['matchday'] == next_gw]
            
        # --- NEW VISUAL SECTION ---
        display_fixtures_visual(matches) 
        st.write("---") 

        # Calculate Deadlines
        first_kickoff = get_gameweek_deadline(matches)
        deadline = first_kickoff - timedelta(hours=1)
        reveal_time = first_kickoff - timedelta(minutes=30)
        current_time = datetime.now(first_kickoff.tzinfo)

        # Prize Pot
        st.metric(label="💰 Estimated Prize Pot", value=f"£{10 * ENTRY_FEE}")

        # Game Tabs
        tab1, tab2 = st.tabs(["My Pick", "All Selections"])

        # --- TAB 1: USER SELECTION ---
        with tab1:
            gw = matches[0]['matchday']
            st.subheader(f"Selection")
            
            pick_id = f"{username}_GW{gw}"
            current_pick_ref = db.collection('picks').document(pick_id)
            current_pick_doc = current_pick_ref.get()
            
            if current_pick_doc.exists:
                saved_pick = current_pick_doc.to_dict().get('team')
                st.success(f"✅ You have selected **{saved_pick}** for Gameweek {gw}.")
                st.info("Your pick is locked in. Good luck!")
                
            elif current_time > deadline:
                st.error(f"🚫 Gameweek Locked. Deadline was {deadline.strftime('%H:%M')}.")
            
            else:
                st.info(f"⏳ Deadline: {deadline.strftime('%A %d %b at %H:%M')}")
                
                user_ref = db.collection('players').document(username)
                user_doc = user_ref.get()
                used_teams = user_doc.to_dict().get('used_teams', []) if user_doc.exists else []
                
                home_teams = [m['homeTeam']['name'] for m in matches]
                away_teams = [m['awayTeam']['name'] for m in matches]
                all_teams = sorted(list(set(home_teams + away_teams)))
                available_teams = [t for t in all_teams if t not in used_teams]
                
                if not available_teams:
                    st.error("You have used all available teams!")
                else:
                    with st.form("pick_form"):
                        choice = st.selectbox("Pick a team to WIN:", available_teams)
                        submitted = st.form_submit_button("Lock In Pick")
                        
                        if submitted:
                            current_pick_ref.set({
                                'user': username,
                                'team': choice,
                                'matchday': gw,
                                'timestamp': datetime.now()
                            })
                            user_ref.set({
                                'used_teams': firestore.ArrayUnion([choice]),
                                'status': 'active'
                            }, merge=True)
                            st.success(f"Locked in: {choice}")
                            st.rerun()

                if used_teams:
                    st.divider()
                    st.caption(f"Teams used: {', '.join(used_teams)}")

        # --- TAB 2: OPPONENT WATCH ---
        with tab2:
            st.subheader("Opponent Watch")
            current_matchday = matches[0]['matchday']
            picks_ref = db.collection('picks').where('matchday', '==', current_matchday).stream()
            
            picks_data = []
            for pick in picks_ref:
                p = pick.to_dict()
                pick_user = p.get('user', 'Unknown')
                pick_team = p.get('team', 'Unknown')
                
                if current_time < reveal_time and pick_user != username:
                    display_team = "HIDDEN 🔒"
                else:
                    display_team = pick_team
                
                picks_data.append({"Player": pick_user, "Selection": display_team})
            
            if picks_data:
                st.dataframe(pd.DataFrame(picks_data), use_container_width=True)
            else:
                st.info("No picks yet.")

    elif st.session_state["authentication_status"] is False:
        st.error('Username/password is incorrect')
    elif st.session_state["authentication_status"] is None:
        st.warning('Please enter your username and password')

if __name__ == "__main__":
    main()
