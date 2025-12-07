import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
from google.cloud import firestore
import streamlit_authenticator as stauth

# --- CONFIGURATION ---
API_KEY = st.secrets["FOOTBALL_API_KEY"]
PL_COMPETITION_ID = 2021  # Premier League ID for Football-Data.org
ENTRY_FEE = 10

# --- DATABASE CONNECTION ---
# Assumes you have set up firestore credentials in .streamlit/secrets.toml
db = firestore.Client.from_service_account_info(st.secrets["firebase"])

# --- HELPER FUNCTIONS ---
def get_fixtures():
    """Fetch upcoming PL matches from API"""
    url = f"https://api.football-data.org/v4/competitions/{PL_COMPETITION_ID}/matches?status=SCHEDULED"
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers)
    data = response.json()
    return data['matches']

def get_gameweek_deadline(matches):
    """Find the kickoff time of the very first game in the list"""
    if not matches:
        return datetime.now() + timedelta(days=365) # Fallback
    
    first_match = min([datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00')) for m in matches])
    return first_match

# --- MAIN APP ---
def main():
    st.set_page_config(page_title="Last Man Standing", layout="wide")
    
    # 1. AUTHENTICATION (Simplified for brevity)
    # In production, load hashed passwords from Firestore, not hardcoded
    name, authentication_status, username = stauth.Authenticate(
        {'usernames': {'jdoe': {'name':'John Doe', 'password':'hashed_password'}}},
        'some_cookie_name', 'some_signature_key', cookie_expiry_days=30
    ).login('Login', 'main')

    if authentication_status:
        st.title(f"⚽ Last Man Standing")
        st.write(f"Welcome, **{name}**")

        # Fetch Data
        matches = get_fixtures()
        if not matches:
            st.warning("No upcoming matches found.")
            st.stop()
            
        first_kickoff = get_gameweek_deadline(matches)
        deadline = first_kickoff - timedelta(hours=1)
        reveal_time = first_kickoff - timedelta(minutes=30)
        current_time = datetime.now(first_kickoff.tzinfo)

        # 2. PRIZE POT CALCULATION
        # Fetch all active players from DB
        players_ref = db.collection('players').where('status', '==', 'active').stream()
        active_player_count = len(list(players_ref))
        st.metric(label="💰 Current Prize Pot", value=f"£{active_player_count * ENTRY_FEE}")

        # 3. GAME TABS
        tab1, tab2, tab3 = st.tabs(["My Pick", "All Selections", "Stats"])

        with tab1:
            st.subheader("Make Your Selection")
            
            # Check Deadline
            if current_time > deadline:
                st.error(f"🚫 Gameweek Locked. Deadline was {deadline.strftime('%H:%M')}")
            else:
                st.info(f"⏳ Deadline: {deadline.strftime('%A %d %b at %H:%M')}")
                
                # Filter out teams user has already used (fetch from DB)
                user_doc = db.collection('players').document(username).get()
                used_teams = user_doc.to_dict().get('used_teams', []) if user_doc.exists else []
                
                # Create list of available teams for this week
                home_teams = [m['homeTeam']['name'] for m in matches]
                away_teams = [m['awayTeam']['name'] for m in matches]
                all_teams = set(home_teams + away_teams)
                available_teams = [t for t in all_teams if t not in used_teams]
                
                choice = st.selectbox("Pick a team to WIN:", available_teams)
                
                if st.button("Submit Pick"):
                    # Save to Firestore
                    db.collection('picks').document(f"{username}_GW{matches[0]['matchday']}").set({
                        'user': username,
                        'team': choice,
                        'timestamp': datetime.now(),
                        'matchday': matches[0]['matchday']
                    })
                    st.success(f"Locked in: {choice}")

        with tab2:
            st.subheader("Opponent Watch")
            
            # Fetch all picks for current matchday
            current_matchday = matches[0]['matchday']
            picks_ref = db.collection('picks').where('matchday', '==', current_matchday).stream()
            
            picks_data = []
            for pick in picks_ref:
                p = pick.to_dict()
                # 4. VISIBILITY LOGIC
                if current_time < reveal_time and p['user'] != username:
                    display_team = "HIDDEN 🔒"
                else:
                    display_team = p['team']
                
                picks_data.append({"Player": p['user'], "Selection": display_team})
            
            st.dataframe(pd.DataFrame(picks_data))

    elif authentication_status is False:
        st.error('Username/password is incorrect')
    elif authentication_status is None:
        st.warning('Please enter your username and password')

if __name__ == "__main__":
    main()
