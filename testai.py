import streamlit as st
import requests
import numpy as np
import plotly.graph_objects as go
import difflib

API_KEY_FOOTBALL = "a7f4136aa92e4837892a63ed97550c9a"
API_KEY_ODDS = "596739ddfd6a4d8f7eeaf6f5ff9c3ac9"

BASE_URL_FOOTBALL = "https://api.football-data.org/v4/"
BASE_URL_ODDS = "https://api.the-odds-api.com/v4/"

HEADERS_FOOTBALL = {"X-Auth-Token": API_KEY_FOOTBALL}

st.set_page_config(page_title="Több focibajnokság Tippadó", layout="wide")
st.title("⚽ Több focibajnokság sportfogadási tippadó")

@st.cache_data(show_spinner=False)
def get_competitions():
    url = f"{BASE_URL_FOOTBALL}competitions"
    r = requests.get(url, headers=HEADERS_FOOTBALL)
    if r.status_code != 200:
        st.error(f"Hiba a bajnokságok lekérésekor: {r.status_code} - {r.text}")
        return []
    data = r.json()
    comps = [c for c in data.get("competitions", []) if c.get("area") and c.get("plan") != "TIER_OTHER"]
    return comps

@st.cache_data(show_spinner=False)
def get_upcoming_matches(competition_id):
    url = f"{BASE_URL_FOOTBALL}competitions/{competition_id}/matches?status=SCHEDULED"
    r = requests.get(url, headers=HEADERS_FOOTBALL)
    if r.status_code != 200:
        st.error(f"Hiba a mérkőzések lekérésekor: {r.status_code} - {r.text}")
        return []
    return r.json().get("matches", [])

@st.cache_data(show_spinner=False)
def get_team_past_matches(team_id, limit=50):
    url = f"{BASE_URL_FOOTBALL}teams/{team_id}/matches?status=FINISHED&limit={limit}"
    r = requests.get(url, headers=HEADERS_FOOTBALL)
    if r.status_code != 200:
        st.error(f"Hiba a csapat múltbéli meccseinek lekérésekor: {r.status_code}")
        return []
    return r.json().get("matches", [])

@st.cache_data(show_spinner=False)
def get_odds_data(sport="soccer_epl", regions="uk,eu,us", markets="h2h"):
    url = f"{BASE_URL_ODDS}sports/{sport}/odds"
    params = {
        "apiKey": API_KEY_ODDS,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal"
    }
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        else:
            st.error("Az odds API válasz formátuma nem megfelelő.")
            return []
    except Exception as e:
        st.error(f"Odds API hiba: {e}")
        return []

def normalize_name(name):
    return name.lower().replace(" ", "").replace("-", "").replace(".", "")

def fuzzy_match(name1, name2, threshold=0.75):
    ratio = difflib.SequenceMatcher(None, name1, name2).ratio()
    return ratio >= threshold

def get_average_odds_for_match(odds_data, home_team, away_team):
    home_norm = normalize_name(home_team)
    away_norm = normalize_name(away_team)
    home_odds_list = []
    draw_odds_list = []
    away_odds_list = []
    for match in odds_data:
        home_api = normalize_name(match["home_team"])
        away_api = normalize_name(match["away_team"])
        if fuzzy_match(home_norm, home_api) and fuzzy_match(away_norm, away_api):
            for bookmaker in match.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market["key"] == "h2h":
                        for outcome in market.get("outcomes", []):
                            name = normalize_name(outcome["name"])
                            price = outcome["price"]
                            if fuzzy_match(name, home_norm):
                                home_odds_list.append(price)
                            elif name == "draw":
                                draw_odds_list.append(price)
                            elif fuzzy_match(name, away_norm):
                                away_odds_list.append(price)
            break
    def avg(lst):
        return round(sum(lst) / len(lst), 2) if lst else None
    return avg(home_odds_list), avg(draw_odds_list), avg(away_odds_list)

def calc_stats(matches, team_id):
    wins = draws = losses = goals_for = goals_against = 0
    yellow_cards = red_cards = 0
    last5 = []
    for m in matches:
        home = m["homeTeam"]["id"]
        away = m["awayTeam"]["id"]
        home_goals = m["score"]["fullTime"]["home"]
        away_goals = m["score"]["fullTime"]["away"]
        # Lapok (büntetőlapok) - events vagy bookings, ha van
        yc, rc = 0, 0
        if "bookings" in m:
            for booking in m["bookings"]:
                if booking["team"]["id"] == team_id:
                    if booking["card"] == "YELLOW_CARD":
                        yc += 1
                    elif booking["card"] == "RED_CARD":
                        rc += 1
        elif "events" in m:
            for event in m["events"]:
                if event.get("team", {}).get("id") == team_id and event.get("type") == "CARD":
                    if event.get("detail") == "Yellow Card":
                        yc += 1
                    elif event.get("detail") == "Red Card":
                        rc += 1
        yellow_cards += yc
        red_cards += rc

        if home_goals is None or away_goals is None:
            continue
        if team_id == home:
            goals_for += home_goals
            goals_against += away_goals
            if home_goals > away_goals:
                wins += 1
                last5.append("W")
            elif home_goals == away_goals:
                draws += 1
                last5.append("D")
            else:
                losses += 1
                last5.append("L")
        elif team_id == away:
            goals_for += away_goals
            goals_against += home_goals
            if away_goals > home_goals:
                wins += 1
                last5.append("W")
            elif away_goals == home_goals:
                draws += 1
                last5.append("D")
            else:
                losses += 1
                last5.append("L")
    total = wins + draws + losses
    if total == 0:
        return None
    return {
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "win_ratio": wins / total,
        "draw_ratio": draws / total,
        "loss_ratio": losses / total,
        "avg_goals_for": goals_for / total,
        "avg_goals_against": goals_against / total,
        "matches_played": total,
        "avg_yellow_cards": yellow_cards / total if total else 0,
        "avg_red_cards": red_cards / total if total else 0,
        "goal_diff": (goals_for - goals_against) / total,
        "last5": last5[:5]
    }

def get_head_to_head_stats(team1_id, team2_id, limit=50):
    team1_matches = get_team_past_matches(team1_id, limit=limit)
    team2_matches = get_team_past_matches(team2_id, limit=limit)

    h2h_matches = []
    for m in team1_matches:
        home = m["homeTeam"]["id"]
        away = m["awayTeam"]["id"]
        if (home == team1_id and away == team2_id) or (home == team2_id and away == team1_id):
            h2h_matches.append(m)
    if len(h2h_matches) < 1:
        for m in team2_matches:
            home = m["homeTeam"]["id"]
            away = m["awayTeam"]["id"]
            if (home == team1_id and away == team2_id) or (home == team2_id and away == team1_id):
                h2h_matches.append(m)

    wins_team1 = draws = wins_team2 = 0
    for m in h2h_matches:
        home = m["homeTeam"]["id"]
        away = m["awayTeam"]["id"]
        home_goals = m["score"]["fullTime"]["home"]
        away_goals = m["score"]["fullTime"]["away"]
        if home_goals is None or away_goals is None:
            continue
        if home_goals == away_goals:
            draws += 1
        elif (home == team1_id and home_goals > away_goals) or (away == team1_id and away_goals > home_goals):
            wins_team1 += 1
        else:
            wins_team2 += 1

    total = wins_team1 + wins_team2 + draws
    if total == 0:
        return None

    return {
        "matches": total,
        "team1_wins": wins_team1,
        "team2_wins": wins_team2,
        "draws": draws,
        "team1_win_ratio": wins_team1 / total,
        "team2_win_ratio": wins_team2 / total,
        "draw_ratio": draws / total
    }

def estimate_result(home_stats, away_stats, h2h_stats, home_odds, draw_odds, away_odds):
    home_advantage = 0.1

    if h2h_stats is None:
        h2h_home_win_ratio = h2h_away_win_ratio = h2h_draw_ratio = 1/3
    else:
        h2h_home_win_ratio = h2h_stats["team1_win_ratio"]
        h2h_away_win_ratio = h2h_stats["team2_win_ratio"]
        h2h_draw_ratio = h2h_stats["draw_ratio"]

    home_prob = (
        0.4 * home_stats["win_ratio"] +
        0.2 * away_stats["loss_ratio"] +
        0.2 * h2h_home_win_ratio +
        home_advantage
    )
    away_prob = (
        0.4 * away_stats["win_ratio"] +
        0.2 * home_stats["loss_ratio"] +
        0.2 * h2h_away_win_ratio
    )
    draw_prob = (
        0.4 * (home_stats["draw_ratio"] + away_stats["draw_ratio"]) / 2 +
        0.2 * h2h_draw_ratio
    )

    if home_odds and draw_odds and away_odds:
        inv_home_odds = 1 / home_odds
        inv_draw_odds = 1 / draw_odds
        inv_away_odds = 1 / away_odds
        odds_sum = inv_home_odds + inv_draw_odds + inv_away_odds

        odds_home_prob = inv_home_odds / odds_sum
        odds_draw_prob = inv_draw_odds / odds_sum
        odds_away_prob = inv_away_odds / odds_sum

        home_prob = 0.6 * home_prob + 0.4 * odds_home_prob
        away_prob = 0.6 * away_prob + 0.4 * odds_away_prob
        draw_prob = 0.6 * draw_prob + 0.4 * odds_draw_prob

    total = home_prob + draw_prob + away_prob
    home_prob /= total
    draw_prob /= total
    away_prob /= total

    return home_prob, draw_prob, away_prob

def plot_form_pie(stats, team_name):
    labels = ['Győzelem', 'Döntetlen', 'Vereség']
    values = [stats['wins'], stats['draws'], stats['losses']]
    colors = ['green', 'gray', 'red']
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, marker_colors=colors, hole=0.4)])
    fig.update_layout(title=f"{team_name} utolsó {stats['matches_played']} meccse eredményei")
    st.plotly_chart(fig, use_container_width=True)

competitions = get_competitions()
if not competitions:
    st.error("Nem sikerült lekérni a bajnokságokat.")
    st.stop()

football_comps = [c for c in competitions if c.get("area") and c.get("plan") != "TIER_OTHER"]
competition_options = [(comp["name"], comp["id"], comp["area"]["name"]) for comp in football_comps]
competition_options_sorted = sorted(competition_options, key=lambda x: x[0])

selected_competition = st.selectbox(
    "Válassz focibajnokságot:",
    competition_options_sorted,
    format_func=lambda x: f"{x[0]} ({x[2]})"
)

comp_name, comp_id, comp_area = selected_competition

matches = get_upcoming_matches(comp_id)
if not matches:
    st.warning("Nincs elérhető mérkőzés a kiválasztott bajnokságban.")
    st.stop()

match_options = []
for m in matches:
    home = m["homeTeam"]["name"]
    away = m["awayTeam"]["name"]
    date = m["utcDate"][:10]
    match_options.append((f"{home} vs {away} ({date})", m))

selected_str, selected_match = st.selectbox("Válassz mérkőzést:", match_options, format_func=lambda x: x[0])
home_team = selected_match["homeTeam"]
away_team = selected_match["awayTeam"]

odds_sport_key = "soccer_epl"
odds_data = get_odds_data(sport=odds_sport_key, regions="uk,eu,us", markets="h2h")
home_odds, draw_odds, away_odds = get_average_odds_for_match(odds_data, home_team["name"], away_team["name"])

col1, col2 = st.columns(2)

with col1:
    st.subheader(f"{home_team['name']} statisztikái")
    home_past_matches = get_team_past_matches(home_team["id"])
    home_stats = calc_stats(home_past_matches, home_team["id"])
    if home_stats:
        st.write(f"Utolsó {home_stats['matches_played']} mérkőzés:")
        st.write(f"- Győzelem: {home_stats['wins']} ({home_stats['win_ratio']*100:.1f}%)")
        st.write(f"- Döntetlen: {home_stats['draws']} ({home_stats['draw_ratio']*100:.1f}%)")
        st.write(f"- Vereség: {home_stats['losses']} ({home_stats['loss_ratio']*100:.1f}%)")
        st.write(f"- Átlagos lőtt gól: {home_stats['avg_goals_for']:.2f}")
        st.write(f"- Átlagos kapott gól: {home_stats['avg_goals_against']:.2f}")
        st.write(f"- Átlagos sárga lap: {home_stats['avg_yellow_cards']:.2f}")
        st.write(f"- Átlagos piros lap: {home_stats['avg_red_cards']:.2f}")
        st.write(f"- Átlagos gólkülönbség: {home_stats['goal_diff']:.2f}")
        st.write(f"- Legutóbbi 5 meccs: {' '.join(home_stats['last5'])}")
        plot_form_pie(home_stats, home_team['name'])
    else:
        st.warning("Nincs elegendő adat a csapat statisztikáihoz.")

with col2:
    st.subheader(f"{away_team['name']} statisztikái")
    away_past_matches = get_team_past_matches(away_team["id"])
    away_stats = calc_stats(away_past_matches, away_team["id"])
    if away_stats:
        st.write(f"Utolsó {away_stats['matches_played']} mérkőzés:")
        st.write(f"- Győzelem: {away_stats['wins']} ({away_stats['win_ratio']*100:.1f}%)")
        st.write(f"- Döntetlen: {away_stats['draws']} ({away_stats['draw_ratio']*100:.1f}%)")
        st.write(f"- Vereség: {away_stats['losses']} ({away_stats['loss_ratio']*100:.1f}%)")
        st.write(f"- Átlagos lőtt gól: {away_stats['avg_goals_for']:.2f}")
        st.write(f"- Átlagos kapott gól: {away_stats['avg_goals_against']:.2f}")
        st.write(f"- Átlagos sárga lap: {away_stats['avg_yellow_cards']:.2f}")
        st.write(f"- Átlagos piros lap: {away_stats['avg_red_cards']:.2f}")
        st.write(f"- Átlagos gólkülönbség: {away_stats['goal_diff']:.2f}")
        st.write(f"- Legutóbbi 5 meccs: {' '.join(away_stats['last5'])}")
        plot_form_pie(away_stats, away_team['name'])
    else:
        st.warning("Nincs elegendő adat a csapat statisztikáihoz.")

st.subheader("Head-to-Head statisztikák")
h2h_stats = get_head_to_head_stats(home_team["id"], away_team["id"])
if h2h_stats:
    st.write(f"Összesen {h2h_stats['matches']} mérkőzés")
    st.write(f"- {home_team['name']} győzelmek: {h2h_stats['team1_wins']} ({h2h_stats['team1_win_ratio']*100:.1f}%)")
    st.write(f"- {away_team['name']} győzelmek: {h2h_stats['team2_wins']} ({h2h_stats['team2_win_ratio']*100:.1f}%)")
    st.write(f"- Döntetlenek: {h2h_stats['draws']} ({h2h_stats['draw_ratio']*100:.1f}%)")
else:
    st.info("Nincs elég head-to-head adat a két csapat között.")

st.subheader("Átlagos fogadási oddsok")
if home_odds and draw_odds and away_odds:
    st.write(f"**{home_team['name']} győzelem odds (átlag):** {home_odds}")
    st.write(f"**Döntetlen odds (átlag):** {draw_odds}")
    st.write(f"**{away_team['name']} győzelem odds (átlag):** {away_odds}")
else:
    st.info("Nem állnak rendelkezésre odds adatok ehhez a mérkőzéshez.")

if home_stats and away_stats:
    home_prob, draw_prob, away_prob = estimate_result(home_stats, away_stats, h2h_stats, home_odds, draw_odds, away_odds)
    st.subheader("Előrejelzés a statisztikák és oddsok alapján")
    st.write(f"**Hazai győzelem esélye:** {home_prob*100:.1f}%")
    st.write(f"**Döntetlen esélye:** {draw_prob*100:.1f}%")
    st.write(f"**Vendég győzelem esélye:** {away_prob*100:.1f}%")

    outcomes = ["Hazai győzelem", "Döntetlen", "Vendég győzelem"]
    probs = [home_prob, draw_prob, away_prob]
    tip = outcomes[np.argmax(probs)]
    st.markdown(f"### Ajánlott tipp: **{tip}**")
else:
    st.warning("Nem áll rendelkezésre elegendő adat az előrejelzéshez.")
