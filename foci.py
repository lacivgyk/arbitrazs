import streamlit as st 
import requests
from datetime import datetime

# --- Oldal konfiguráció ---
st.set_page_config(page_title="Foci Arbitrázs Fogadás Figyelő", layout="wide", initial_sidebar_state="expanded")

st.title("🎯 Foci Arbitrázs Fogadás Figyelő")
st.caption("Keresd meg a biztos nyeremény lehetőségét – valós idejű odds elemzés")

# API kulcs bekérése
API_KEY = st.sidebar.text_input("API kulcs megadása", type="password")

if not API_KEY:
    st.warning("Kérlek, add meg az API kulcsot a folytatáshoz.")
    st.stop()  # Megállítja a további futást, amíg nincs kulcs

REGION = 'us,us2,us_dfs,us_ex,uk,eu,au'
MARKET = 'h2h'
TOTAL_STAKE = 100000

# Régió színek
REGION_COLORS = {
    'us': '🔵',
    'us2': '🔵',
    'us_dfs': '🔵',
    'us_ex': '🔵',
    'uk': '🟣',
    'eu': '🟢',
    'au': '🟡'
}

# Bookmaker és régió hozzárendelés
BOOKMAKER_REGIONS = {
    # ... (a meglévő dictionary változatlanul)
}

# Foci sportágak
SPORTS = [
    ('soccer_epl', 'Foci (EPL)', 3),
    ('soccer_uefa_champs_league', 'Foci (BL)', 3),
    ('soccer_spain_la_liga', 'Foci (La Liga)', 3)
]

found_any = False

with st.sidebar:
    st.header("⚙️ Beállítások")
    TOTAL_STAKE = st.slider("Teljes tét összeg (Ft)", 1000, 200000, 100000, 1000)
    min_margin = st.slider("Minimális elvárt profit (%)", 0.1, 10.0, 1.5, 0.1)
    selected_sports = st.multiselect("Válassz sportágakat", [s[1] for s in SPORTS], default=[s[1] for s in SPORTS])
    show_live_only = st.checkbox("Csak élő meccsek megjelenítése", False)
    limit_to_selected = st.checkbox("Csak 22Bet, 20Bet, Betwinner, Rabona megjelenítése", value=False)
    limited_sites = {"22Bet", "20Bet", "Betwinner", "Rabona"}

all_sites = sorted(set(BOOKMAKER_REGIONS.keys()))
default_disabled_sites = [
    "Betfair Exchange",
    "Betfair Sportsbook",
    "Coolbet",
    "1xBet",
    "Betsson",
    "Paddy Power",
]

# Csak azokat hagyjuk meg default értékként, amelyek ténylegesen benne vannak az all_sites-ban
default_disabled_sites = [site for site in default_disabled_sites if site in all_sites]

disabled_sites = st.multiselect(
    "🛑 Kikapcsolandó oldalak",
    all_sites,
    default=default_disabled_sites
)

for SPORT, sport_name, outcome_count in SPORTS:
    if sport_name not in selected_sports:
        continue

    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/?regions={REGION}&markets=h2h&apiKey={API_KEY}"
    res = requests.get(url)
    if res.status_code != 200:
        st.error(f"❌ {sport_name} odds lekérése sikertelen ({res.status_code})")
        continue

    for match in res.json():
        home, away = match.get("home_team"), match.get("away_team")
        status, start = match.get("status"), match.get("commence_time")
        if show_live_only and status != "live":
            continue

        try:
            start_str = datetime.fromisoformat(start.replace("Z", "+00:00")).strftime('%Y-%m-%d %H:%M:%S')
        except:
            start_str = "Ismeretlen"

        best_odds = {home: {"odds": 0, "site": ""}, away: {"odds": 0, "site": ""}}

        for book in match.get("bookmakers", []):
            site = book['title']
            if limit_to_selected and site not in limited_sites:
                continue
            if site in disabled_sites:
                continue

            for outcome in book['markets'][0]['outcomes']:
                name, price = outcome['name'], outcome['price']
                if name == home and price > best_odds[home]['odds']:
                    best_odds[home] = {"odds": price, "site": site}
                elif name == away and price > best_odds[away]['odds']:
                    best_odds[away] = {"odds": price, "site": site}
                elif name == "Draw" and price > best_odds.get("Draw", {}).get("odds", 0):
                    best_odds["Draw"] = {"odds": price, "site": site}

        odds = [v["odds"] for v in best_odds.values() if v["odds"] > 0]
        if len(odds) != 3:
            continue

        inv_sum = sum(1 / o for o in odds)
        if inv_sum >= 1 or (1 - inv_sum) * 100 < min_margin:
            continue

        found_any = True
        with st.expander(f"{sport_name} - {home} vs {away}"):
            st.markdown(f"#### 🕒 Meccs kezdete: {start_str}")
            st.markdown(f"#### 🧮 Profit margin: {(1 - inv_sum) * 100:.2f}%")
            cols = st.columns(len(best_odds))
            for i, (outcome, info) in enumerate(best_odds.items()):
                region = BOOKMAKER_REGIONS.get(info['site'], 'unknown')
                emoji = REGION_COLORS.get(region, '⚪')
                label = f"{info['site']} ({region})"
                with cols[i]:
                    st.metric(label=f"{emoji} {outcome}", value=info['odds'], delta=label)

            stakes = [TOTAL_STAKE / (odd * inv_sum) for odd in odds]
            profits = [stakes[i] * odds[i] - TOTAL_STAKE for i in range(3)]

            st.markdown("---")
            st.markdown("### 💰 Tételosztás")
            for i, (outcome, stake) in enumerate(zip(best_odds.keys(), stakes)):
                st.markdown(f"- {outcome}: **{stake:.2f} Ft**")

            st.markdown("### 📈 Lehetséges profit")
            for i, (outcome, profit) in enumerate(zip(best_odds.keys(), profits)):
                st.markdown(f"- {outcome}: **{profit:.2f} Ft**")

if not found_any:
    st.warning("Nincs találat a keresett sportágban.")
