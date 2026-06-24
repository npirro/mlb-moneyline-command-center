import os
import math
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Tuple, Optional

import numpy as np
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
import pytz

st.set_page_config(page_title="MLB Moneyline Command Center", page_icon="⚾", layout="wide", initial_sidebar_state="collapsed")
BUILD_VERSION = "v8-tightened-thresholds"

EASTERN = pytz.timezone("America/New_York")
ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
MLB_SCHEDULE = "https://statsapi.mlb.com/api/v1/schedule"
MLB_TEAM_STATS = "https://statsapi.mlb.com/api/v1/teams/{team_id}/stats"
MLB_PLAYER_STATS = "https://statsapi.mlb.com/api/v1/people/{person_id}/stats"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"

TEAM_ALIASES = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL", "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC", "Chicago White Sox": "CHW", "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL", "Detroit Tigers": "DET", "Houston Astros": "HOU", "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN", "New York Mets": "NYM", "New York Yankees": "NYY", "Oakland Athletics": "ATH",
    "Athletics": "ATH", "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD",
    "San Francisco Giants": "SF", "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR", "Washington Nationals": "WSH",
}

# Robust team-name matching across MLB Stats API and The Odds API.
# The Odds API can return slightly different franchise names/locations, so we normalize before matching.
TEAM_NAME_NORMALIZATION = {
    "oakland athletics": "athletics",
    "athletics": "athletics",
    "a's": "athletics",
    "az diamondbacks": "arizona diamondbacks",
    "la dodgers": "los angeles dodgers",
    "los angeles dodgers": "los angeles dodgers",
    "la angels": "los angeles angels",
    "los angeles angels": "los angeles angels",
    "ny yankees": "new york yankees",
    "new york yankees": "new york yankees",
    "ny mets": "new york mets",
    "new york mets": "new york mets",
    "st louis cardinals": "st louis cardinals",
    "st. louis cardinals": "st louis cardinals",
    "chi cubs": "chicago cubs",
    "chicago cubs": "chicago cubs",
    "chi white sox": "chicago white sox",
    "chicago white sox": "chicago white sox",
    "sd padres": "san diego padres",
    "sf giants": "san francisco giants",
    "tb rays": "tampa bay rays",
    "kc royals": "kansas city royals",
}

def norm_team_name(name: str) -> str:
    if not name:
        return ""
    import re
    n = str(name).lower().strip()
    n = n.replace("&", "and")
    n = re.sub(r"[^a-z0-9 ]+", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return TEAM_NAME_NORMALIZATION.get(n, n)

def pair_key(team_a: str, team_b: str, day: str = "") -> tuple:
    teams = sorted([norm_team_name(team_a), norm_team_name(team_b)])
    return tuple(teams + ([day] if day else []))

def html_escape(x):
    import html
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return html.escape(str(x))

def fmt_pct(x, digits=1):
    try:
        if pd.isna(x): return "—"
        return f"{float(x):.{digits}f}%"
    except Exception:
        return "—"

# Dark dashboard styling inspired by the mockup.
st.markdown("""
<style>
:root { --bg:#07131f; --panel:#0e2130; --panel2:#102636; --text:#f5f7fb; --muted:#a9bac8; --green:#31e56b; --red:#ff4545; --yellow:#ffc928; --blue:#2e8cff; }
.stApp { background: radial-gradient(circle at top left, #0b2537 0%, #06101b 42%, #030912 100%); color: var(--text); }
.block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1600px; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0a1824 0%, #07111d 100%); border-right: 1px solid #20374a; }
.metric-card, .panel { background: linear-gradient(180deg, rgba(17,38,54,.96), rgba(10,24,36,.96)); border: 1px solid #263d50; border-radius: 12px; padding: 16px; box-shadow: 0 10px 24px rgba(0,0,0,.22); }
.metric-title { color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; font-weight: 700; }
.metric-value { color: var(--text); font-size: 2rem; font-weight: 800; margin-top: .2rem; }
.green { color: var(--green); } .red { color: var(--red); } .yellow { color: var(--yellow); } .blue { color: var(--blue); }
.badge { display:inline-block; border-radius: 999px; padding: 4px 10px; font-size: .78rem; font-weight: 800; border: 1px solid rgba(255,255,255,.12); }
.badge-a { background: rgba(49,229,107,.12); color: var(--green); }
.badge-b { background: rgba(255,201,40,.12); color: var(--yellow); }
.badge-no { background: rgba(255,69,69,.12); color: var(--red); }
.badge-lean { background: rgba(46,140,255,.12); color: var(--blue); }
.section-title { color: var(--green); text-transform: uppercase; font-weight: 900; letter-spacing: .05em; margin: 0 0 10px 0; }
.small-note { color: var(--muted); font-size: .88rem; }
hr { border-color: #20374a !important; }
[data-testid="stMetricValue"] { color: #f6fbff; }
.stDataFrame { border: 1px solid #263d50; border-radius: 12px; overflow: hidden; }
button[kind="primary"] { background: linear-gradient(90deg,#12b76a,#168cff) !important; border: 1px solid #51ffa3 !important; color:#03101a !important; font-weight:900 !important; border-radius:10px !important; }
.stTabs [data-baseweb="tab-list"] { gap: 10px; background: rgba(5,14,24,.45); padding: 8px; border-radius: 14px; border: 1px solid #1d3447; }
.stTabs [data-baseweb="tab"] { background: rgba(18,43,62,.9); border-radius: 999px; color: #b6cad8; padding: 8px 18px; font-weight: 800; }
.stTabs [aria-selected="true"] { background: linear-gradient(90deg,rgba(49,229,107,.22),rgba(46,140,255,.22)) !important; color: #ffffff !important; border: 1px solid rgba(49,229,107,.65); }
.hero { background: linear-gradient(135deg, rgba(49,229,107,.18), rgba(46,140,255,.10) 45%, rgba(255,201,40,.08)); border: 1px solid rgba(49,229,107,.35); border-radius: 18px; padding: 18px 20px; margin-bottom: 14px; box-shadow: 0 18px 42px rgba(0,0,0,.35); }
.hero-title { font-size: 2.1rem; font-weight: 950; color: #ffffff; line-height: 1.05; }
.hero-sub { color:#b8cad7; font-size: .95rem; margin-top: 6px; }
.big-status { font-size: 1.8rem; font-weight: 950; letter-spacing:.04em; }
[data-testid="stDataFrame"] { background: rgba(12,28,42,.75); border-radius: 14px; }

/* V3 polish: full-width app, denser cards, closer to the dashboard mockup */
[data-testid="stHeader"], [data-testid="stToolbar"], footer { visibility: hidden; height: 0px; }
[data-testid="stSidebar"], section[data-testid="stSidebar"] { display: none !important; width:0 !important; min-width:0 !important; }
[data-testid="collapsedControl"] { display:none !important; }
html, body, [class*="css"] { font-size: 14px; }
.block-container { padding: .35rem .85rem 1.25rem .85rem; max-width: 100% !important; }
section.main > div { max-width: 100% !important; }
/* Sidebar disabled in v4; controls live in top expander */
.hero { margin-top: 0; padding: 14px 18px; }
.hero-title { font-size: 1.9rem; }
.metric-card { min-height: 96px; padding: 14px 16px; }
.metric-value { font-size: 1.75rem; }
.panel-tight { background: linear-gradient(180deg, rgba(17,38,54,.96), rgba(10,24,36,.96)); border: 1px solid #263d50; border-radius: 12px; padding: 14px; box-shadow: 0 10px 24px rgba(0,0,0,.22); margin-bottom: 12px; }
.left-rail-card { background: linear-gradient(180deg, rgba(14,33,48,.98), rgba(8,19,30,.98)); border: 1px solid #263d50; border-radius: 12px; padding: 14px; margin-bottom: 12px; }
.status-pill { display:inline-block; padding: 7px 14px; border-radius: 999px; font-weight: 950; letter-spacing:.04em; background: linear-gradient(90deg,#ffb020,#ff8a00); color:#06101b; text-transform: uppercase; }
.status-pill.bad { background: linear-gradient(90deg,#ff4d4d,#8b1d2c); color:#fff; }
.status-pill.good { background: linear-gradient(90deg,#27e56f,#0e9444); color:#06101b; }
.rail-grade { font-size: 2.25rem; font-weight: 950; color: #fff; line-height:1; margin-top: 8px; }
.rail-line { display:flex; justify-content:space-between; border-bottom: 1px solid rgba(255,255,255,.06); padding: 5px 0; color: #d7e6f0; font-size:.9rem; }
.rail-line b { color:#31e56b; }
.top-nav { display:flex; align-items:center; gap:10px; border:1px solid #1d3447; border-radius:14px; padding:8px 10px; background:rgba(5,14,24,.55); margin: 8px 0 12px 0; }
.nav-pill { border-radius:999px; padding:8px 14px; background:rgba(18,43,62,.9); color:#b6cad8; font-weight:800; font-size:.88rem; }
.nav-pill.active { background:linear-gradient(90deg,rgba(49,229,107,.30),rgba(46,140,255,.20)); color:white; border:1px solid rgba(49,229,107,.65); }
div[data-testid="stHorizontalBlock"] { gap: .75rem; }
.stDataFrame [data-testid="stTable"] { font-size: .85rem; }
[data-testid="stExpander"] { border: 1px solid #263d50; border-radius: 12px; background: rgba(10,24,36,.74); }

</style>
""", unsafe_allow_html=True)


def safe_get_json(url: str, params: Dict[str, Any], timeout: int = 20) -> Optional[dict]:
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.session_state.setdefault("errors", []).append(f"API error: {url} — {e}")
        return None


def american_to_implied(odds: float) -> float:
    if odds is None or (isinstance(odds, float) and math.isnan(odds)):
        return np.nan
    odds = float(odds)
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def american_to_decimal(odds: float) -> float:
    odds = float(odds)
    if odds < 0:
        return 1 + 100 / abs(odds)
    return 1 + odds / 100


def decimal_to_american(decimal_odds: float) -> int:
    if decimal_odds >= 2:
        return int(round((decimal_odds - 1) * 100))
    return int(round(-100 / (decimal_odds - 1)))


def parlay_american(odds_list: List[float]) -> Optional[int]:
    odds_list = [o for o in odds_list if pd.notna(o)]
    if not odds_list:
        return None
    dec = np.prod([american_to_decimal(o) for o in odds_list])
    return decimal_to_american(dec)


def norm_pct(val, default=0.5):
    try:
        if val is None: return default
        v = float(val)
        if v > 1: v = v / 100
        return max(0, min(1, v))
    except Exception:
        return default


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


@st.cache_data(ttl=3600)
def load_park_data():
    try:
        return pd.read_csv("park_data.csv")
    except Exception:
        return pd.DataFrame(columns=["venue", "city", "lat", "lon", "park_factor"])


@st.cache_data(ttl=300)
def fetch_odds(api_key: str, regions: str, bookmakers: str) -> List[dict]:
    def count_outcomes(events):
        if not isinstance(events, list):
            return 0
        total = 0
        for ev in events:
            for book in ev.get("bookmakers", []):
                for market in book.get("markets", []):
                    if market.get("key") == "h2h":
                        total += len(market.get("outcomes", []))
        return total

    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": "h2h",
        "oddsFormat": "american",
        "dateFormat": "iso",
    }
    if bookmakers.strip():
        params["bookmakers"] = bookmakers.strip()
    data = safe_get_json(ODDS_API_BASE, params=params)
    events = data if isinstance(data, list) else []

    # Critical fallback: some API keys/plans or regions return zero markets when a bookmaker filter is used.
    # If that happens, retry without bookmaker filtering so the dashboard still gets live odds.
    if bookmakers.strip() and count_outcomes(events) == 0:
        st.session_state.setdefault("errors", []).append("Bookmaker filter returned no odds. Retried with all available US books.")
        params.pop("bookmakers", None)
        data2 = safe_get_json(ODDS_API_BASE, params=params)
        events = data2 if isinstance(data2, list) else events
    return events


@st.cache_data(ttl=300)
def fetch_schedule(day: date) -> List[dict]:
    params = {
        "sportId": 1,
        "date": day.strftime("%Y-%m-%d"),
        "hydrate": "probablePitcher,team,venue",
    }
    data = safe_get_json(MLB_SCHEDULE, params=params)
    games = []
    if not data:
        return games
    for d in data.get("dates", []):
        games.extend(d.get("games", []))
    return games


@st.cache_data(ttl=1800)
def fetch_team_stats(team_id: int, group: str = "hitting", lookback_days: int = 14) -> Dict[str, Any]:
    # Uses season stats plus recent date range when the endpoint supports it. Falls back gracefully.
    out = {"season": {}, "recent": {}}
    season = safe_get_json(MLB_TEAM_STATS.format(team_id=team_id), {"stats": "season", "group": group})
    if season:
        try:
            out["season"] = season["stats"][0]["splits"][0].get("stat", {})
        except Exception:
            pass
    end = datetime.now(EASTERN).date()
    start = end - timedelta(days=lookback_days)
    recent = safe_get_json(MLB_TEAM_STATS.format(team_id=team_id), {
        "stats": "byDateRange", "group": group,
        "startDate": start.strftime("%m/%d/%Y"), "endDate": end.strftime("%m/%d/%Y")
    })
    if recent:
        try:
            out["recent"] = recent["stats"][0]["splits"][0].get("stat", {})
        except Exception:
            pass
    return out


@st.cache_data(ttl=1800)
def fetch_pitcher_stats(person_id: int) -> Dict[str, Any]:
    data = safe_get_json(MLB_PLAYER_STATS.format(person_id=person_id), {"stats": "season", "group": "pitching"})
    if not data:
        return {}
    try:
        return data["stats"][0]["splits"][0].get("stat", {})
    except Exception:
        return {}


@st.cache_data(ttl=900)
def fetch_weather(lat: float, lon: float, game_time_iso: str) -> Dict[str, Any]:
    try:
        game_dt = pd.to_datetime(game_time_iso, utc=True).tz_convert(EASTERN)
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation_probability",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": "America/New_York",
            "forecast_days": 3,
        }
        data = safe_get_json(OPEN_METEO, params=params, timeout=15)
        if not data or "hourly" not in data:
            return {}
        df = pd.DataFrame(data["hourly"])
        df["time"] = pd.to_datetime(df["time"])
        target = pd.Timestamp(game_dt.replace(minute=0, second=0, microsecond=0).replace(tzinfo=None))
        if df.empty:
            return {}
        df["diff"] = (df["time"] - target).abs()
        row = df.sort_values("diff").iloc[0].to_dict()
        return row
    except Exception:
        return {}


def pitcher_score(stat: Dict[str, Any]) -> Tuple[float, List[str]]:
    if not stat:
        return 15.0, ["Probable pitcher stats missing"]
    notes = []
    era = float(stat.get("era", 4.5) or 4.5)
    whip = float(stat.get("whip", 1.35) or 1.35)
    k9 = float(stat.get("strikeoutsPer9Inn", 8.0) or 8.0)
    bb9 = float(stat.get("walksPer9Inn", 3.2) or 3.2)
    innings = float(stat.get("inningsPitched", 0) or 0)
    kbb = k9 - bb9
    score = 15
    score += clamp((4.50 - era) * 3.0, -8, 8)
    score += clamp((1.30 - whip) * 12.0, -6, 6)
    score += clamp((kbb - 4.5) * 1.3, -6, 6)
    if innings < 20:
        score -= 2
        notes.append("Small SP sample")
    if era < 3.5 and whip < 1.25: notes.append("Strong SP profile")
    if kbb < 3: notes.append("Low K-BB signal")
    return clamp(score, 0, 30), notes


def offense_score(stats: Dict[str, Any]) -> Tuple[float, List[str]]:
    season = stats.get("season", {}) if stats else {}
    recent = stats.get("recent", {}) if stats else {}
    notes = []
    ops = float(season.get("ops", .710) or .710)
    avg = float(season.get("avg", .245) or .245)
    runs = float(season.get("runs", 0) or 0)
    recent_ops = float(recent.get("ops", ops) or ops)
    score = 12.5
    score += clamp((ops - .710) * 45, -8, 8)
    score += clamp((avg - .245) * 35, -3, 3)
    score += clamp((recent_ops - ops) * 25, -4, 4)
    if recent_ops > ops + .050: notes.append("Recent offense heating up")
    if ops < .675: notes.append("Below-average offense")
    return clamp(score, 0, 25), notes


def bullpen_team_pitching_score(stats: Dict[str, Any]) -> Tuple[float, List[str]]:
    # This is not true bullpen-only unless a paid feed is added. It uses team pitching as a proxy.
    season = stats.get("season", {}) if stats else {}
    recent = stats.get("recent", {}) if stats else {}
    notes = []
    era = float(season.get("era", 4.30) or 4.30)
    whip = float(season.get("whip", 1.32) or 1.32)
    recent_era = float(recent.get("era", era) or era)
    score = 7.5
    score += clamp((4.30 - era) * 1.5, -4, 4)
    score += clamp((1.32 - whip) * 6, -3, 3)
    score += clamp((era - recent_era) * 0.8, -3, 3)
    if recent_era > era + .75: notes.append("Recent pitching/bullpen risk")
    if recent_era < era - .75: notes.append("Recent run prevention strong")
    return clamp(score, 0, 15), notes


def environment_score(park_factor: float, weather: Dict[str, Any], is_home: bool) -> Tuple[float, List[str]]:
    # Moneyline environment mostly affects volatility, not side direction. We score lower for chaos.
    notes = []
    score = 7.0
    if park_factor >= 1.08:
        score -= 1.5; notes.append("High-run park increases chaos")
    if park_factor <= .94:
        score += .5; notes.append("Run-suppressing park")
    try:
        wind = float(weather.get("wind_speed_10m", 0) or 0)
        temp = float(weather.get("temperature_2m", 70) or 70)
        precip = float(weather.get("precipitation_probability", 0) or 0)
        if wind > 15: score -= 1.0; notes.append("Wind risk")
        if temp > 88: score -= .5; notes.append("Hot-weather run boost")
        if precip > 40: score -= 1.5; notes.append("Rain/delay risk")
    except Exception:
        pass
    return clamp(score, 0, 10), notes


def market_edge_score(model_pct: float, implied_pct: float) -> float:
    edge = (model_pct - implied_pct) * 100
    return clamp(10 + edge * 1.6, 0, 20)


def tier_from(edge_pct: float, score: float, odds: float, risk_flags: List[str]) -> str:
    # v8 tightened rules:
    # Tiny positive edges are NOT recommended plays. They are only watchlist/entertainment candidates.
    # Suggested legs require at least ~2% model edge plus a reasonable score.
    if "Game started" in risk_flags:
        return "No Bet"
    if odds < -280 or odds > 220:
        if score >= 82 and edge_pct >= 5.0:
            return "B+"
        if score >= 70 and edge_pct >= 1.0:
            return "Lean"
        if score >= 62 and edge_pct >= 0.0:
            return "Thin Edge"
        return "No Bet"
    if edge_pct >= 5.0 and score >= 72:
        return "A"
    if edge_pct >= 3.0 and score >= 68:
        return "B+"
    if edge_pct >= 2.0 and score >= 64:
        return "B"
    if edge_pct >= 1.0 and score >= 60:
        return "Lean"
    if edge_pct >= 0.0 and score >= 55:
        return "Thin Edge"
    return "No Bet"


def slate_status(qlegs: int, tier_a: int, tier_bp: int) -> Tuple[str, str]:
    if qlegs >= 6: return "STRONG BOARD", "5-leg main + optional 6th"
    if qlegs == 5: return "PLAYABLE BOARD", "5-leg main ticket"
    if qlegs in (3,4): return "LIMITED BOARD", "3–4 leg card"
    if qlegs == 2: return "WEAK BOARD", "Singles or tiny 2-leg"
    if qlegs == 1: return "VERY WEAK", "Single only"
    return "NO PLAY", "No serious play"


def grade_from(qlegs: int, avg_edge: float) -> str:
    val = qlegs * 8 + avg_edge * 5
    if val >= 65: return "A-"
    if val >= 52: return "B+"
    if val >= 42: return "B-"
    if val >= 30: return "C+"
    return "D"


def parse_odds_events(odds_events: List[dict]) -> Dict[Tuple[str, str, str], dict]:
    # Key by sorted team names + commencement to match later.
    out = {}
    for ev in odds_events:
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        start = ev.get("commence_time", "")
        key = pair_key(home, away, start[:10])
        outcomes = []
        for book in ev.get("bookmakers", []):
            btitle = book.get("title", book.get("key", ""))
            for market in book.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for o in market.get("outcomes", []):
                    outcomes.append({"team": o.get("name"), "team_norm": norm_team_name(o.get("name")), "price": o.get("price"), "book": btitle})
        out[key] = {"home": home, "away": away, "start": start, "outcomes": outcomes, "raw": ev}
    return out


def best_price_for_team(outcomes: List[dict], team: str) -> Tuple[Optional[float], str, float]:
    rows = [o for o in outcomes if o.get("team_norm") == norm_team_name(team) and o.get("price") is not None]
    if not rows:
        return np.nan, "", np.nan
    # For American odds, higher price is always better (+120 > +105; -110 > -130)
    best = sorted(rows, key=lambda x: x["price"], reverse=True)[0]
    implieds = [american_to_implied(r["price"]) for r in rows]
    return best["price"], best["book"], float(np.mean(implieds))


def no_vig_market_prob(team_avg_imp: float, opp_avg_imp: float) -> float:
    s = team_avg_imp + opp_avg_imp
    if not s or pd.isna(s):
        return np.nan
    return team_avg_imp / s


def build_board(day: date, api_key: str, regions: str, bookmakers: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    st.session_state["errors"] = []
    st.session_state["matched_games"] = 0
    odds_events = fetch_odds(api_key, regions, bookmakers)
    schedule = fetch_schedule(day)
    park_df = load_park_data()
    odds_map = parse_odds_events(odds_events)
    rows = []
    warnings = []

    for game in schedule:
        teams = game.get("teams", {})
        home_info = teams.get("home", {})
        away_info = teams.get("away", {})
        home_team = home_info.get("team", {})
        away_team = away_info.get("team", {})
        home = home_team.get("name", "")
        away = away_team.get("name", "")
        venue = game.get("venue", {}).get("name", "")
        start_iso = game.get("gameDate", "")
        game_state = game.get("status", {}).get("abstractGameState", "")
        key_date = start_iso[:10]
        odds_key = pair_key(home, away, key_date)
        odds_event = odds_map.get(odds_key)
        # If exact-date name match failed, try team pair only.
        if odds_event is None:
            for k, v in odds_map.items():
                if set(k[:2]) == set(pair_key(home, away)):
                    odds_event = v
                    break
        outcomes = odds_event.get("outcomes", []) if odds_event else []
        if outcomes:
            st.session_state["matched_games"] = st.session_state.get("matched_games", 0) + 1

        park_row = park_df[park_df["venue"].str.lower() == venue.lower()]
        if park_row.empty:
            park_factor, lat, lon = 1.00, np.nan, np.nan
        else:
            park_factor = float(park_row.iloc[0]["park_factor"])
            lat, lon = float(park_row.iloc[0]["lat"]), float(park_row.iloc[0]["lon"])
        weather = fetch_weather(lat, lon, start_iso) if pd.notna(lat) else {}

        # Probable pitchers
        home_pp = home_info.get("probablePitcher", {}) or {}
        away_pp = away_info.get("probablePitcher", {}) or {}
        home_pp_stats = fetch_pitcher_stats(home_pp.get("id")) if home_pp.get("id") else {}
        away_pp_stats = fetch_pitcher_stats(away_pp.get("id")) if away_pp.get("id") else {}

        # Team stats
        home_hit = fetch_team_stats(home_team.get("id"), "hitting") if home_team.get("id") else {}
        away_hit = fetch_team_stats(away_team.get("id"), "hitting") if away_team.get("id") else {}
        home_pitch = fetch_team_stats(home_team.get("id"), "pitching") if home_team.get("id") else {}
        away_pitch = fetch_team_stats(away_team.get("id"), "pitching") if away_team.get("id") else {}

        matchup = [
            {"team": home, "opp": away, "team_id": home_team.get("id"), "is_home": True, "pp": home_pp, "pp_stats": home_pp_stats, "opp_pp_stats": away_pp_stats, "hit": home_hit, "pitch": home_pitch, "opp_hit": away_hit, "opp_pitch": away_pitch, "record": home_info.get("leagueRecord", {}), "opp_record": away_info.get("leagueRecord", {})},
            {"team": away, "opp": home, "team_id": away_team.get("id"), "is_home": False, "pp": away_pp, "pp_stats": away_pp_stats, "opp_pp_stats": home_pp_stats, "hit": away_hit, "pitch": away_pitch, "opp_hit": home_hit, "opp_pitch": home_pitch, "record": away_info.get("leagueRecord", {}), "opp_record": home_info.get("leagueRecord", {})},
        ]
        # Calculate category raw scores for both teams then compare.
        cats = {}
        for m in matchup:
            sp, sp_notes = pitcher_score(m["pp_stats"])
            off, off_notes = offense_score(m["hit"])
            bp, bp_notes = bullpen_team_pitching_score(m["pitch"])
            env, env_notes = environment_score(park_factor, weather, m["is_home"])
            cats[m["team"]] = {"sp": sp, "off": off, "bp": bp, "env": env, "notes": sp_notes + off_notes + bp_notes + env_notes}

        for m in matchup:
            opp_team = m["opp"]
            team = m["team"]
            odds, book, team_avg_imp = best_price_for_team(outcomes, team)
            opp_odds, opp_book, opp_avg_imp = best_price_for_team(outcomes, opp_team)
            implied = american_to_implied(odds) if pd.notna(odds) else np.nan
            market_consensus = no_vig_market_prob(team_avg_imp, opp_avg_imp)

            team_record = norm_pct(m.get("record", {}).get("pct"), .5)
            opp_record = norm_pct(m.get("opp_record", {}).get("pct"), .5)
            record_edge = (team_record - opp_record) * 12

            sp_edge = (cats[team]["sp"] - cats[opp_team]["sp"]) / 30 * 12
            off_edge = (cats[team]["off"] - cats[opp_team]["off"]) / 25 * 8
            bp_edge = (cats[team]["bp"] - cats[opp_team]["bp"]) / 15 * 5
            home_edge = 2.2 if m["is_home"] else -0.8
            market_anchor = ((market_consensus - .5) * 40) if pd.notna(market_consensus) else 0
            model_pct = .50 + (market_anchor + record_edge + sp_edge + off_edge + bp_edge + home_edge) / 100
            model_pct = clamp(model_pct, .25, .75)

            edge_pct = (model_pct - implied) * 100 if pd.notna(implied) else np.nan
            market_points = market_edge_score(model_pct, implied) if pd.notna(implied) else 0
            total_score = cats[team]["sp"] + cats[team]["off"] + cats[team]["bp"] + market_points + cats[team]["env"]
            risk_flags = []
            if not m["pp"]: risk_flags.append("Pitcher TBD")
            if not outcomes: risk_flags.append("Odds missing")
            if game_state != "Preview": risk_flags.append("Game started")
            if any("risk" in n.lower() for n in cats[team]["notes"]): risk_flags.append("Bullpen/Weather risk")
            if odds < -220: risk_flags.append("Expensive favorite")
            if odds > 160: risk_flags.append("Long dog")
            tier = tier_from(edge_pct if pd.notna(edge_pct) else -99, total_score, odds if pd.notna(odds) else 0, risk_flags)
            if tier in ["A", "B+"] and "Pitcher TBD" in risk_flags:
                tier = "B"

            if "Pitcher TBD" in risk_flags:
                warnings.append(f"{team}: probable pitcher missing")
            if odds_event and abs((team_avg_imp if pd.notna(team_avg_imp) else 0) - (implied if pd.notna(implied) else 0)) > .025:
                risk_flags.append("Shop price")

            rows.append({
                "Start": pd.to_datetime(start_iso, utc=True).tz_convert(EASTERN).strftime("%-I:%M %p") if start_iso else "",
                "Game": f"{away} @ {home}",
                "Team": team,
                "Abbr": TEAM_ALIASES.get(team, team[:3].upper()),
                "Opponent": opp_team,
                "Home/Away": "Home" if m["is_home"] else "Away",
                "Venue": venue,
                "Odds": odds,
                "Book": book,
                "Implied %": implied * 100 if pd.notna(implied) else np.nan,
                "Market %": market_consensus * 100 if pd.notna(market_consensus) else np.nan,
                "Model Win %": model_pct * 100,
                "Edge %": edge_pct,
                "Score": round(total_score, 1),
                "Tier": tier,
                "Risk": ", ".join(risk_flags) if risk_flags else "Clean",
                "Probable Pitcher": m["pp"].get("fullName", "TBD") if m["pp"] else "TBD",
                "SP Score": round(cats[team]["sp"], 1),
                "Offense Score": round(cats[team]["off"], 1),
                "Bullpen Proxy": round(cats[team]["bp"], 1),
                "Market Score": round(market_points, 1),
                "Environment Score": round(cats[team]["env"], 1),
                "Notes": "; ".join(cats[team]["notes"][:5]) or "No major flags",
                "Temp": weather.get("temperature_2m", np.nan),
                "Wind": weather.get("wind_speed_10m", np.nan),
                "Precip %": weather.get("precipitation_probability", np.nan),
                "Park Factor": park_factor,
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Tier", "Edge %", "Score"], ascending=[True, False, False])
    meta = {"warnings": sorted(set(warnings)), "errors": st.session_state.get("errors", []), "odds_events": len(odds_events), "odds_outcomes": sum(len(v.get("outcomes", [])) for v in odds_map.values()), "schedule_games": len(schedule), "matched_games": st.session_state.get("matched_games", 0)}
    return df, meta


def format_odds(o):
    try:
        return f"{int(o):+d}"
    except Exception:
        return ""


def style_tier(t):
    if t == "A": return "badge badge-a"
    if t == "B+": return "badge badge-b"
    if t == "B": return "badge badge-b"
    if t == "Lean": return "badge badge-lean"
    return "badge badge-no"


def render_metric(title, value, subtitle="", color=""):
    st.markdown(f"""
    <div class='metric-card'>
      <div class='metric-title'>{title}</div>
      <div class='metric-value {color}'>{value}</div>
      <div class='small-note'>{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def recommended_tickets(qdf: pd.DataFrame) -> pd.DataFrame:
    if qdf.empty:
        return pd.DataFrame()
    core = qdf.sort_values(["Tier", "Edge %", "Score"], ascending=[True, False, False]).copy()
    # Custom ranking: A > B+ > B > Lean
    rankmap = {"A": 0, "B+": 1, "B": 2, "Lean": 3, "Thin Edge": 4}
    core["tier_rank"] = core["Tier"].map(rankmap).fillna(9)
    core = core.sort_values(["tier_rank", "Edge %", "Score"], ascending=[True, False, False])
    rows = []
    for n in [1,2,3,4,5,6]:
        legs = core.head(n)
        if len(legs) < n: continue
        odds_list = legs["Odds"].dropna().tolist()
        est_odds = parlay_american(odds_list)
        hit = np.prod(legs["Model Win %"] / 100) * 100
        status = "Supported"
        if n >= 5 and len(core[core["Tier"].isin(["A", "B+"])]) < n: status = "Not recommended"
        if n == 6: status = "High risk booster"
        rows.append({"Ticket Type": f"{n}-Leg" if n > 1 else "Single", "Legs": n, "Estimated Odds": format_odds(est_odds) if est_odds is not None else "", "Est. Hit %": round(hit, 1), "Status": status, "Teams": " / ".join(legs["Abbr"].tolist())})
    return pd.DataFrame(rows)



def _display_cols(df, cols):
    return df[[c for c in cols if c in df.columns]].copy()



def _tier_color(t):
    return {"A":"good","B+":"warn","B":"warn","Lean":"info","Thin Edge":"info","No Bet":"bad"}.get(str(t), "info")

def _odds_html(o):
    txt = format_odds(o)
    cls = "pos" if txt.startswith("+") else "neg" if txt.startswith("-") else "muted"
    return f"<span class='{cls}'>{html_escape(txt or '—')}</span>"

def html_table(df: pd.DataFrame, cols: List[str], limit: int = 8, small: bool = False) -> str:
    if df is None or df.empty:
        return "<div class='empty'>No rows to show.</div>"
    view = df[[c for c in cols if c in df.columns]].head(limit).copy()
    rows = []
    rows.append("<table class='dash-table{}'><thead><tr>".format(" small" if small else ""))
    for c in view.columns:
        rows.append(f"<th>{html_escape(c)}</th>")
    rows.append("</tr></thead><tbody>")
    for _, r in view.iterrows():
        lineup_val = str(r.get("Lineup Status", "")).lower()
        risk_val = str(r.get("Risk", "")).lower()
        row_cls = ""
        if "game started" in risk_val or "started" in lineup_val:
            row_cls = " class='started'"
        elif "projected" in lineup_val or "unconfirmed" in lineup_val or "unknown" in lineup_val or "provisional" in lineup_val:
            row_cls = " class='provisional'"
        rows.append(f"<tr{row_cls}>")
        for c in view.columns:
            val = r[c]
            if c == "Odds":
                cell = _odds_html(val)
            elif c in ["Model Win %", "Implied %", "Edge %", "Market %"]:
                cell = fmt_pct(val)
                if c == "Edge %":
                    try:
                        cell = f"<span class='{'pos' if float(val)>=0 else 'badtxt'}'>{fmt_pct(val)}</span>"
                    except Exception: pass
            elif c == "Tier":
                cls = _tier_color(val)
                cell = f"<span class='tier {cls}'>{html_escape(val)}</span>"
            elif c == "Lineup Status":
                lv = str(val)
                lcls = "lineup-confirmed" if "Confirmed" in lv else ("lineup-started" if "Started" in lv else "lineup-projected")
                cell = f"<span class='lineup-pill {lcls}'>{html_escape(lv)}</span>"
            else:
                cell = html_escape(val)
            rows.append(f"<td>{cell}</td>")
        rows.append("</tr>")
    rows.append("</tbody></table>")
    return "".join(rows)

def render_custom_command_center(df, meta, qualified, full_ticket_qualified, best_available, boosters, traps, target_date, qlegs, tier_a, tier_bp, play_type, status, grade, max_height=1120):
    # Decide core ticket rows.
    if len(full_ticket_qualified) >= 5:
        core = full_ticket_qualified.sort_values(["Tier", "Edge %", "Score"], ascending=[True, False, False]).head(5)
        main_msg = "Main 5-leg ticket supported"
    elif len(qualified) >= 1:
        core = qualified.sort_values(["Tier", "Edge %", "Score"], ascending=[True, False, False]).head(min(len(qualified), 4))
        main_msg = f"Smaller {len(core)}-leg card / singles only"
    else:
        core = best_available.head(5)
        main_msg = "No core legs — showing best available"

    hit3 = np.prod((best_available.head(3)["Model Win %"] / 100)) * 100 if len(best_available) >= 3 else 0
    parlay_odds = parlay_american(core["Odds"].dropna().tolist()) if not core.empty else None
    warnings = meta.get("warnings", [])[:4]
    errors = meta.get("errors", [])[:3]
    diag = f"Odds events: {meta.get('odds_events', 0)} • Outcomes: {meta.get('odds_outcomes', 0)} • Matched games: {meta.get('matched_games', 0)}"
    status_cls = "good" if qlegs >= 5 else ("warn" if qlegs >= 3 else "bad")
    top_candidate = best_available.iloc[0] if not best_available.empty else df.iloc[0]

    css = """
    <style>
    body{margin:0;background:#030914;color:#f6fbff;font-family:Inter,Segoe UI,Arial,sans-serif;}
    .cc{background:radial-gradient(circle at 10% 0%,#102a3a 0,#06111d 42%,#020711 100%);padding:18px;border-radius:0;color:#f6fbff;}
    .top{height:56px;display:flex;align-items:center;gap:18px;border-bottom:1px solid #1c3548;margin-bottom:14px;}
    .logo{font-size:28px;font-weight:950;letter-spacing:.01em;}
    .nav{margin-left:auto;display:flex;gap:18px;color:#c9d7e3;font-weight:800;font-size:13px}.nav span:first-child{color:#27a9ff;border-bottom:3px solid #2b8cff;padding-bottom:17px}
    .update{font-size:11px;color:#b7c5d0;text-align:right}.btn{background:#1178d8;padding:10px 18px;border-radius:7px;color:white;font-weight:900}
    .grid{display:grid;grid-template-columns:180px 1.5fr 1fr;gap:14px}.rail,.panel,.card{background:linear-gradient(180deg,#0e2130,#081827);border:1px solid #213b50;border-radius:8px;box-shadow:0 10px 24px rgba(0,0,0,.25)}
    .rail{padding:14px}.datebox{border:1px solid #2a4256;border-radius:6px;padding:8px;text-align:center;width:62px;display:inline-block;color:#d7e4ee;font-weight:900}.games{font-size:36px;font-weight:950;margin-left:15px;vertical-align:middle}.label{font-size:11px;text-transform:uppercase;color:#b8c9d6;font-weight:900;letter-spacing:.06em}.pill{display:inline-block;border-radius:999px;padding:8px 15px;font-weight:950;text-transform:uppercase;font-size:12px}.pill.good{background:#1ee06b;color:#06101a}.pill.warn{background:#ffb11b;color:#06101a}.pill.bad{background:#ff4e55;color:white}.grade{font-size:34px;font-weight:950;margin:10px 0 0}.railrow{display:flex;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.08);padding:6px 0;font-size:13px;color:#d9e7ef}.railrow b{color:#31e56b}.warntext{color:#ffc928;font-size:12px;margin:7px 0}.errtext{color:#ff6161;font-size:11px;margin:6px 0}.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:14px}.card{padding:13px 15px;min-height:82px}.card .val{font-size:28px;font-weight:950;margin-top:9px}.green{color:#31e56b}.yellow{color:#ffc928}.blue{color:#2e8cff}.panel{padding:14px;margin-bottom:14px}.title{color:#31e56b;text-transform:uppercase;font-weight:950;letter-spacing:.08em;font-size:15px;margin-bottom:10px}.redtitle{color:#ff5757}.subgrid{display:grid;grid-template-columns:1.7fr 1fr;gap:14px}.dash-table{width:100%;border-collapse:collapse;font-size:13px;overflow:hidden}.dash-table th{color:#c5d3df;text-transform:uppercase;font-size:10px;letter-spacing:.04em;text-align:left;border-bottom:1px solid #244258;padding:9px 8px}.dash-table td{border-bottom:1px solid rgba(255,255,255,.07);padding:9px 8px;color:#eff6fb;white-space:nowrap}.dash-table tr.provisional td{color:#8796a3;background:rgba(128,139,150,.08)}.dash-table tr.started td{color:#6f7b86;background:rgba(80,80,80,.10);text-decoration:line-through}.lineup-pill{border-radius:999px;padding:3px 8px;font-weight:950;font-size:10px;text-transform:uppercase}.lineup-confirmed{background:rgba(49,229,107,.16);color:#31e56b}.lineup-projected{background:rgba(150,160,170,.16);color:#9aa7b3}.lineup-started{background:rgba(255,80,80,.15);color:#ff6a6a}.dash-table.small{font-size:12px}.dash-table.small td{padding:7px 7px}.pos{color:#31e56b;font-weight:950}.neg{color:#ff5757;font-weight:950}.badtxt{color:#ff5757;font-weight:950}.muted{color:#8ea3b4}.tier{border-radius:999px;padding:3px 8px;font-weight:950;font-size:11px}.tier.good{background:rgba(49,229,107,.14);color:#31e56b}.tier.warn{background:rgba(255,201,40,.14);color:#ffc928}.tier.info{background:rgba(46,140,255,.14);color:#2e8cff}.tier.bad{background:rgba(255,69,69,.14);color:#ff5757}.ticketstats{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid #203b50;border-radius:8px;margin-top:12px}.ticketstats div{padding:12px;text-align:center;border-right:1px solid #203b50}.ticketstats div:last-child{border-right:0}.big{font-size:22px;font-weight:950}.detail{display:grid;grid-template-columns:1fr 1fr;gap:10px}.note{color:#aabcc9;font-size:12px}.breakrow{display:flex;justify-content:space-between;margin:7px 0;font-size:12px}.bar{height:8px;background:#163144;border-radius:999px;overflow:hidden}.bar span{display:block;height:100%;background:#36d566}.empty{padding:18px;color:#9db1c1;font-size:13px}.footer{font-size:11px;color:#7f91a1;text-align:center;margin-top:8px}.diag{font-size:11px;color:#8fa2b1;margin-top:8px}.teamhead{font-size:20px;font-weight:950;margin:5px 0}.risk{color:#ffc928;font-size:12px}.statusbox{font-size:30px;font-weight:950}.side-stack{display:grid;gap:14px}
    </style>
    """
    html = f"""
    {css}<div class='cc'>
      <div class='top'><div class='logo'>⚾ MLB MONEYLINE PARLAY COMMAND CENTER</div><div class='nav'><span>Command Center Snapshot</span></div><div class='update'>Last Updated: {datetime.now(EASTERN).strftime('%-I:%M %p ET')}<br>{target_date.strftime('%b %-d, %Y')}</div><div class='btn'>v16 lineup status + pregame filter</div></div>
      <div class='grid'>
        <div class='rail'>
          <div class='label'>Today's Slate</div><div style='margin:10px 0 8px;'><span class='datebox'>{target_date.strftime('%a').upper()}<br>{target_date.strftime('%b %-d').upper()}</span><span class='games'>{meta.get('schedule_games',0)}</span></div><div class='note'>games today</div><hr style='border-color:#20384c;margin:14px 0;'>
          <div class='label'>Slate Status</div><div style='margin:10px 0'><span class='pill {status_cls}'>{html_escape(status)}</span></div><div class='grade'>{html_escape(grade)}</div><div class='note'>slate grade</div>
          <div style='margin-top:16px'><div class='railrow'><span>Suggested Legs</span><b>{qlegs}</b></div><div class='railrow'><span>Tier A Legs</span><b>{tier_a}</b></div><div class='railrow'><span>Tier B+ Legs</span><b style='color:#ffc928'>{tier_bp}</b></div><div class='railrow'><span>Best Play</span><b style='color:#ffc928'>{html_escape(play_type)}</b></div></div>
          <hr style='border-color:#20384c;margin:14px 0;'><div class='label'>Data Warnings</div>
          {''.join([f"<div class='warntext'>⚠ {html_escape(w)}</div>" for w in warnings]) or "<div class='note' style='margin-top:8px'>No major warnings.</div>"}
          {''.join([f"<div class='errtext'>• {html_escape(e)}</div>" for e in errors])}
          <div class='diag'>{html_escape(diag)}</div>
        </div>
        <div>
          <div class='metrics'>
            <div class='card'><div class='label'>Games Today</div><div class='val blue'>{meta.get('schedule_games',0)}</div><div class='note'>View full slate</div></div>
            <div class='card'><div class='label'>Suggested Legs</div><div class='val green'>{qlegs}</div><div class='note'>Core/smaller card</div></div>
            <div class='card'><div class='label'>Tier A Legs</div><div class='val green'>{tier_a}</div><div class='note'>Best plays</div></div>
            <div class='card'><div class='label'>Tier B+ Legs</div><div class='val yellow'>{tier_bp}</div><div class='note'>Solid plays</div></div>
            <div class='card'><div class='label'>Est. Hit % (3-leg)</div><div class='val'>{hit3:.1f}%</div><div class='note'>Based on top 3</div></div>
          </div>
          <div class='panel'><div class='title'>Suggested Smaller-Card Legs</div>{html_table(core, ['Team','Opponent','Odds','Book','Model Win %','Implied %','Edge %','Tier','Risk'], 6)}
            <div class='ticketstats'><div><div class='label'>Estimated Odds</div><div class='big pos'>{html_escape(format_odds(parlay_odds) if parlay_odds is not None else '—')}</div></div><div><div class='label'>Est. Hit %</div><div class='big blue'>{(np.prod(core['Model Win %']/100)*100 if not core.empty else 0):.1f}%</div></div><div><div class='label'>Ticket Grade</div><div class='big yellow'>{html_escape(grade)}</div></div><div><div class='label'>Recommendation</div><div class='big yellow'>{html_escape(play_type)}</div></div><div><div class='label'>Read</div><div class='big'>{html_escape(main_msg)}</div></div></div>
          </div>
          <div class='panel'><div class='title'>Best Available / Watchlist Context</div>{html_table(best_available, ['Team','Opponent','Odds','Book','Model Win %','Implied %','Edge %','Score','Tier','Risk','Start'], 10, small=True)}</div>
        </div>
        <div class='side-stack'>
          <div class='panel'><div class='title'>Optional Lean / Booster Legs</div>{html_table(boosters, ['Team','Odds','Model Win %','Edge %','Tier','Risk'], 4, small=True)}<div class='note'>Optional only. Use for higher payout only if you accept more risk.</div></div>
          <div class='panel'><div class='title redtitle'>Trap Favorites / Do Not Use</div>{html_table(traps, ['Team','Opponent','Odds','Model Win %','Implied %','Risk'], 6, small=True)}</div>
          <div class='panel'><div class='title'>Team / Game Breakdown</div><div class='teamhead'>{html_escape(top_candidate['Team'])}</div><div class='note'>Moneyline: {_odds_html(top_candidate['Odds'])} at {html_escape(top_candidate['Book'])} • Tier {html_escape(top_candidate['Tier'])}</div><div class='detail'><div><div class='label'>Model Win Probability</div><div class='big green'>{fmt_pct(top_candidate['Model Win %'])}</div></div><div><div class='label'>Edge</div><div class='big pos'>{fmt_pct(top_candidate['Edge %'])}</div></div></div>
            <div style='margin-top:12px'>
              {''.join([f"<div class='breakrow'><span>{name}</span><b>{val}/{mx}</b></div><div class='bar'><span style='width:{max(0,min(100,float(val)/mx*100))}%'></span></div>" for name,val,mx in [('Starting Pitcher',top_candidate['SP Score'],30),('Offense',top_candidate['Offense Score'],25),('Bullpen',top_candidate['Bullpen Proxy'],15),('Market',top_candidate['Market Score'],20),('Environment',top_candidate['Environment Score'],10)]])}
            </div><div class='risk' style='margin-top:10px'>{html_escape(top_candidate['Risk'])}</div><div class='note'>{html_escape(str(top_candidate['Notes'])[:180])}</div></div>
        </div>
      </div><div class='footer'>The models and data shown are for informational purposes only. Bet responsibly.</div>
    </div>
    """
    components.html(html, height=max_height, scrolling=True)


# -----------------------------
# v13 Bet Tracker Helpers
# -----------------------------
TRACKER_COLUMNS = [
    "Ticket ID", "Date", "Bucket", "Ticket Type", "Team", "Opponent", "Odds", "Book",
    "Model Win %", "Implied %", "Edge %", "Score", "Tier", "Risk", "Stake",
    "Result", "Profit/Loss", "Miss Reason", "Read Quality", "Notes", "Logged At"
]


def tracker_path() -> str:
    return "results_tracker.csv"


def load_tracker() -> pd.DataFrame:
    try:
        t = pd.read_csv(tracker_path())
    except Exception:
        t = pd.DataFrame(columns=TRACKER_COLUMNS)
    for c in TRACKER_COLUMNS:
        if c not in t.columns:
            t[c] = "" if c not in ["Stake", "Profit/Loss", "Odds", "Model Win %", "Implied %", "Edge %", "Score"] else np.nan
    return t[TRACKER_COLUMNS]


def save_tracker_df(t: pd.DataFrame) -> None:
    for c in TRACKER_COLUMNS:
        if c not in t.columns:
            t[c] = ""
    t[TRACKER_COLUMNS].to_csv(tracker_path(), index=False)


def tracker_profit_from_american(odds, stake, result):
    try:
        odds = float(odds); stake = float(stake)
    except Exception:
        return np.nan
    result = str(result).strip().lower()
    if result in ["loss", "lost", "l"]:
        return -stake
    if result in ["push", "void", "cancelled", "p"]:
        return 0.0
    if result not in ["win", "won", "w"]:
        return np.nan
    if odds > 0:
        return stake * (odds / 100.0)
    return stake * (100.0 / abs(odds))


def render_bet_tracker(df, qualified, full_ticket_qualified, best_available, target_date):
    st.subheader("Bet Tracker")
    st.caption("Save the current model recommendations, mark results later, and see whether the buckets are actually producing winners. This tracks legs and tickets separately by Ticket ID.")

    bucket_options = {
        "Core Parlay Legs": full_ticket_qualified.copy() if isinstance(full_ticket_qualified, pd.DataFrame) else pd.DataFrame(),
        "Suggested Winner-First Legs": qualified.copy() if isinstance(qualified, pd.DataFrame) else pd.DataFrame(),
        "Watchlist / Value Dogs": best_available.copy() if isinstance(best_available, pd.DataFrame) else pd.DataFrame(),
        "Full Board Manual Select": df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(),
    }

    with st.container(border=True):
        st.markdown("#### Save current recommendations to tracker")
        c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])
        with c1:
            bucket_name = st.selectbox("Bucket to save", list(bucket_options.keys()))
        source = bucket_options[bucket_name]
        if bucket_name == "Watchlist / Value Dogs" and not source.empty and not qualified.empty:
            source = source[~source.index.isin(qualified.index)]
        if not source.empty:
            source = source.copy().head(12)
            source["Display"] = source.apply(lambda r: f"{r.get('Team','')} vs {r.get('Opponent','')} | {format_odds(r.get('Odds'))} | Edge {r.get('Edge %', 0):.1f}% | MW% {r.get('Model Win %', 0):.1f}%", axis=1)
        with c2:
            ticket_type = st.selectbox("Ticket type", ["Single", "2-Leg", "3-Leg", "4-Leg", "5-Leg", "6-Leg", "Custom"])
        with c3:
            stake = st.number_input("Stake", min_value=0.0, value=0.0, step=1.0)
        with c4:
            ticket_note = st.text_input("Ticket note", value="")

        if source.empty:
            st.info("No rows available in that bucket right now.")
        else:
            default_n = 1 if ticket_type == "Single" else int(ticket_type.split("-")[0]) if "-Leg" in ticket_type else min(3, len(source))
            default_labels = source["Display"].tolist()[:min(default_n, len(source))]
            selected_labels = st.multiselect("Choose legs to save", source["Display"].tolist(), default=default_labels)
            preview = source[source["Display"].isin(selected_labels)].drop(columns=["Display"], errors="ignore")
            if not preview.empty:
                st.dataframe(_display_cols(preview, ["Team","Opponent","Odds","Book","Model Win %","Implied %","Edge %","Score","Tier","Risk"]), use_container_width=True, hide_index=True)
            if st.button("💾 Save selected legs to tracker", type="primary", use_container_width=True):
                if preview.empty:
                    st.warning("Select at least one leg first.")
                else:
                    existing = load_tracker()
                    ticket_id = f"{pd.to_datetime(target_date).strftime('%Y%m%d')}-{datetime.now(EASTERN).strftime('%H%M%S')}"
                    now = datetime.now(EASTERN).strftime("%Y-%m-%d %H:%M:%S")
                    rows = []
                    for _, r in preview.iterrows():
                        rows.append({
                            "Ticket ID": ticket_id,
                            "Date": str(target_date),
                            "Bucket": bucket_name,
                            "Ticket Type": ticket_type,
                            "Team": r.get("Team", ""),
                            "Opponent": r.get("Opponent", ""),
                            "Odds": r.get("Odds", np.nan),
                            "Book": r.get("Book", ""),
                            "Model Win %": r.get("Model Win %", np.nan),
                            "Implied %": r.get("Implied %", np.nan),
                            "Edge %": r.get("Edge %", np.nan),
                            "Score": r.get("Score", np.nan),
                            "Tier": r.get("Tier", ""),
                            "Risk": r.get("Risk", ""),
                            "Stake": stake,
                            "Result": "Pending",
                            "Profit/Loss": np.nan,
                            "Miss Reason": "",
                            "Read Quality": "",
                            "Notes": ticket_note,
                            "Logged At": now,
                        })
                    out = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
                    save_tracker_df(out)
                    st.success(f"Saved {len(rows)} leg(s) under Ticket ID {ticket_id}.")

    tracker = load_tracker()
    st.markdown("#### Tracker log")
    if tracker.empty:
        st.info("No tracked bets yet. Save current recommendations above to start building history.")
        return

    # Coerce numeric fields for summaries.
    numeric_cols = ["Stake", "Profit/Loss", "Odds", "Model Win %", "Implied %", "Edge %", "Score"]
    for c in numeric_cols:
        tracker[c] = pd.to_numeric(tracker[c], errors="coerce")

    c1, c2, c3, c4 = st.columns(4)
    settled = tracker[tracker["Result"].astype(str).str.lower().isin(["win", "loss", "push", "won", "lost", "w", "l", "p"])]
    wins = settled[settled["Result"].astype(str).str.lower().isin(["win", "won", "w"])]
    losses = settled[settled["Result"].astype(str).str.lower().isin(["loss", "lost", "l"])]
    pl = tracker["Profit/Loss"].sum(skipna=True)
    stake_sum = tracker["Stake"].sum(skipna=True)
    roi = (pl / stake_sum * 100) if stake_sum else 0
    c1.metric("Tracked Legs", len(tracker))
    c2.metric("Settled Hit Rate", f"{(len(wins)/max(1, len(wins)+len(losses))*100):.1f}%")
    c3.metric("Profit / Loss", f"${pl:.2f}")
    c4.metric("ROI", f"{roi:.1f}%")

    st.markdown("#### Mark results")
    st.caption("Edit Result, Profit/Loss, Miss Reason, Read Quality, or Notes, then click Save Tracker Updates. Profit/Loss can be typed manually; singles can also be auto-filled with the helper below.")
    edited = st.data_editor(
        tracker,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "Result": st.column_config.SelectboxColumn("Result", options=["Pending", "Win", "Loss", "Push"]),
            "Miss Reason": st.column_config.SelectboxColumn("Miss Reason", options=["", "Starter issue", "Bullpen collapse", "Lineup issue", "Market moved", "Weather/park", "Random variance", "Bad model read", "Other"]),
            "Read Quality": st.column_config.SelectboxColumn("Read Quality", options=["", "Good read, won", "Good read, lost randomly", "Bad read", "Too close to call"]),
        }
    )
    b1, b2, b3 = st.columns([1,1,2])
    with b1:
        if st.button("🧮 Auto-fill single-leg P/L", use_container_width=True):
            tmp = edited.copy()
            for i, r in tmp.iterrows():
                if pd.isna(r.get("Profit/Loss")) or str(r.get("Profit/Loss", "")).strip() == "":
                    tmp.at[i, "Profit/Loss"] = tracker_profit_from_american(r.get("Odds"), r.get("Stake"), r.get("Result"))
            save_tracker_df(tmp)
            st.success("Auto-filled available single-leg P/L values and saved.")
    with b2:
        if st.button("💾 Save tracker updates", type="primary", use_container_width=True):
            save_tracker_df(edited)
            st.success("Tracker updated.")
    with b3:
        st.download_button("Download tracker CSV", data=edited.to_csv(index=False), file_name="mlb_bet_tracker.csv", mime="text/csv", use_container_width=True)

    st.markdown("#### Performance breakdowns")
    tc1, tc2 = st.columns(2)
    with tc1:
        by_bucket = tracker.groupby("Bucket", dropna=False).agg(
            Legs=("Team", "count"),
            Avg_Model_Win=("Model Win %", "mean"),
            Avg_Edge=("Edge %", "mean"),
            Profit_Loss=("Profit/Loss", "sum"),
            Stake=("Stake", "sum"),
        ).reset_index()
        if not by_bucket.empty:
            by_bucket["ROI %"] = np.where(by_bucket["Stake"] > 0, by_bucket["Profit_Loss"] / by_bucket["Stake"] * 100, 0)
        st.dataframe(by_bucket, use_container_width=True, hide_index=True)
    with tc2:
        by_ticket = tracker.groupby("Ticket Type", dropna=False).agg(
            Legs=("Team", "count"),
            Profit_Loss=("Profit/Loss", "sum"),
            Stake=("Stake", "sum"),
        ).reset_index()
        if not by_ticket.empty:
            by_ticket["ROI %"] = np.where(by_ticket["Stake"] > 0, by_ticket["Profit_Loss"] / by_ticket["Stake"] * 100, 0)
        st.dataframe(by_ticket, use_container_width=True, hide_index=True)

    st.markdown("#### Miss reason breakdown")
    miss = tracker[tracker["Miss Reason"].astype(str).str.len() > 0]
    if miss.empty:
        st.caption("No miss reasons logged yet.")
    else:
        st.dataframe(miss.groupby("Miss Reason").size().reset_index(name="Count"), use_container_width=True, hide_index=True)

def main():
    # v5 renders the mockup-style header inside the custom command-center component.

    # Controls are inside the page instead of the Streamlit sidebar so the app looks like a real dashboard.
    with st.expander("⚙️ Dashboard controls", expanded=False):
        today = datetime.now(EASTERN).date()
        c1, c2, c3, c4 = st.columns([1,1,2,1])
        with c1:
            target_date = st.date_input("Slate date", today)
        with c2:
            regions = st.selectbox("Sportsbook region", ["us", "us2", "uk", "eu", "au"], index=0)
        with c3:
            bookmakers = st.text_input("Bookmakers filter", value="", placeholder="Leave blank for all available books")
        with c4:
            model_mode = st.selectbox("Model strictness", ["Balanced", "Conservative", "Aggressive"], index=0)

        c5, c6, c7, c8 = st.columns([1,1,1,1])
        default_edge = 1.5 if model_mode == "Aggressive" else (2.0 if model_mode == "Balanced" else 3.0)
        with c5:
            min_edge = st.slider("Suggested-leg minimum edge %", 0.0, 8.0, default_edge, 0.5)
        with c6:
            max_fav = st.slider("Max favorite price", -300, -120, -260, 5)
        with c7:
            max_dog = st.slider("Max underdog price", 100, 250, 200, 5)
        with c8:
            refresh = st.button("🔄 Refresh odds + model", type="primary", use_container_width=True)

        api_key = ""
        try:
            api_key = st.secrets.get("ODDS_API_KEY", "")
        except Exception:
            api_key = os.environ.get("ODDS_API_KEY", "")
        if not api_key:
            api_key = st.text_input("Odds API key", type="password")
        st.caption("On Streamlit Cloud, store ODDS_API_KEY in app secrets so it is not public.")

    # Defaults when controls are closed after first render.
    if 'target_date' not in locals():
        target_date = datetime.now(EASTERN).date(); regions='us'; bookmakers=''; model_mode='Balanced'; min_edge=2.0; max_fav=-260; max_dog=200; refresh=False
        try:
            api_key = st.secrets.get("ODDS_API_KEY", "")
        except Exception:
            api_key = os.environ.get("ODDS_API_KEY", "")

    if not api_key:
        st.warning("Add your The Odds API key in Streamlit secrets or paste it in Dashboard controls to run the dashboard.")
        st.stop()

    if refresh:
        fetch_odds.clear(); fetch_schedule.clear(); fetch_team_stats.clear(); fetch_pitcher_stats.clear(); fetch_weather.clear()

    with st.spinner("Loading live odds, MLB slate, probable pitchers, team stats, and weather..."):
        df, meta = build_board(target_date, api_key, regions, bookmakers)

    if df.empty:
        st.error("No slate/odds data loaded. Check API key, date, and any API errors below.")
        if meta.get("errors"):
            st.code("\n".join(meta["errors"][:10]))
        st.stop()

    # v10 winner-first parlay logic.
    # This is NOT pure +EV singles mode. Official parlay legs must be likely winners first,
    # then have enough price value to avoid overpaying.
    price_ok = (df["Odds"].notna()) & (df["Odds"] >= max_fav) & (df["Odds"] <= max_dog)
    clean_risk = ~df["Risk"].str.contains("Game started|Odds missing|Long dog", case=False, na=False)

    # Official parlay candidates: winner-first filter.
    raw_parlay = df[
        price_ok
        & clean_risk
        & (df["Model Win %"].fillna(0) >= 54.0)
        & (df["Edge %"].fillna(-99) >= max(1.5, min_edge))
        & (df["Score"].fillna(0) >= 70.0)
        & (df["Tier"].isin(["A", "B+", "B"]))
    ].copy()

    # One side per game, with conflict protection. If both sides grade too close, skip the game.
    qualified = one_side_per_game(raw_parlay, min_edge_gap=0.75)
    eligible = qualified.copy()

    # Stronger full-ticket legs: higher win probability or stronger edge.
    full_ticket_qualified = qualified[
        (qualified["Model Win %"].fillna(0) >= 56.0)
        & (qualified["Edge %"].fillna(-99) >= 2.0)
        & (qualified["Tier"].isin(["A", "B+"]))
    ].copy()

    # Value dogs/watchlist are shown for transparency, but are NOT parlay legs.
    value_watchlist = df[
        price_ok
        & (df["Model Win %"].fillna(0) >= 45.0)
        & (df["Edge %"].fillna(-99) >= 3.0)
    ].copy()
    value_watchlist = one_side_per_game(value_watchlist, min_edge_gap=0.75)

    # Best available is parlay candidates first; otherwise winner-leaning teams that are closest to qualifying.
    near_miss = df[price_ok & (df["Model Win %"].fillna(0) >= 51.0)].copy()
    near_miss = one_side_per_game(near_miss.sort_values(["Model Win %", "Edge %", "Score"], ascending=[False, False, False]), min_edge_gap=0.50)
    watchlist = pd.concat([value_watchlist, near_miss], ignore_index=True).drop_duplicates(subset=["Team","Opponent","Game"], keep="first") if not value_watchlist.empty or not near_miss.empty else pd.DataFrame()
    if not watchlist.empty:
        watchlist = watchlist.sort_values(["Model Win %", "Edge %", "Score"], ascending=[False, False, False]).head(10)
    fallback = one_side_per_game(df[price_ok].sort_values(["Model Win %", "Score", "Edge %"], ascending=[False, False, False]), min_edge_gap=0.50).head(10)
    best_available = qualified if not qualified.empty else (watchlist if not watchlist.empty else fallback)

    tier_a = int((full_ticket_qualified["Tier"] == "A").sum()) if "full_ticket_qualified" in locals() and not full_ticket_qualified.empty else 0
    tier_bp = int((full_ticket_qualified["Tier"] == "B+").sum()) if "full_ticket_qualified" in locals() and not full_ticket_qualified.empty else 0
    qlegs = len(qualified)
    avg_edge = qualified["Edge %"].mean() if qlegs else 0
    status, play_type = slate_status(qlegs, tier_a, tier_bp)
    if len(full_ticket_qualified) < 5 and not best_available.empty:
        if qlegs >= 3:
            status = "SMALLER CARD"
            play_type = f"{min(qlegs,4)}-leg / singles"
        else:
            status = "WATCHLIST ONLY"
            play_type = "No official play"
    grade = grade_from(qlegs, avg_edge)

    # v5 primary render: custom HTML command center first, not native Streamlit tabs.
    taken_tmp = set(best_available.head(5).index) if not best_available.empty else set()
    boosters_tmp = df[(~df.index.isin(taken_tmp)) & (df["Odds"] >= max_fav) & (df["Odds"] <= max_dog)].sort_values(["Model Win %","Edge %","Score"], ascending=[False, False, False]).head(4)
    traps_tmp = df[((df["Odds"] < -120) & (df["Edge %"] < 0.5)) | (df["Risk"].str.contains("Expensive", na=False))].sort_values(["Odds","Edge %"]).head(6)
    render_custom_command_center(df, meta, qualified, full_ticket_qualified, best_available, boosters_tmp, traps_tmp, target_date, qlegs, tier_a, tier_bp, play_type, status, grade)
    st.caption("v16 lineup status + pregame filter: Official suggested legs require at least 2% edge and Tier B or better. Lean/Thin Edge teams are watchlist only, not official recommended plays.")

    with st.expander("Advanced views: full slate, ticket builder, diagnostics", expanded=False):
        st.subheader("Full Slate Board")
        st.dataframe(_display_cols(df, ["Start","Game","Team","Opponent","Home/Away","Odds","Book","Market %","Model Win %","Implied %","Edge %","Score","Tier","Risk","Probable Pitcher","Notes"]), use_container_width=True, hide_index=True)
        st.subheader("Auto Ticket Builder")
        ticket_source = eligible if not eligible.empty else best_available
        ticket_df = recommended_tickets(ticket_source if not ticket_source.empty else df[df["Edge %"] > -2])
        st.dataframe(ticket_df, use_container_width=True, hide_index=True)
        st.subheader("Export")
        st.download_button("Download today’s board CSV", data=df.to_csv(index=False), file_name=f"mlb_board_{target_date}.csv", mime="text/csv")
        st.download_button("Download suggested winner-first CSV", data=qualified.to_csv(index=False), file_name=f"suggested_legs_{target_date}.csv", mime="text/csv")
        st.subheader("API Diagnostics")
        st.json(meta)
        if meta.get("errors"):
            st.code("\n".join(meta["errors"][:20]))
    return

    # Tabs remain functional, but the first tab is designed as the dense command center.
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Command Center", "Full Slate", "Ticket Builder", "Team Detail", "Results / Export"])

    with tab1:
        # v5: fully custom HTML command-center render to match the mockup much more closely than native Streamlit cards/tables.
        taken_tmp = set(best_available.head(5).index) if not best_available.empty else set()
        boosters_tmp = df[(~df.index.isin(taken_tmp)) & (df["Odds"] >= max_fav) & (df["Odds"] <= max_dog)].sort_values(["Model Win %","Edge %","Score"], ascending=[False, False, False]).head(4)
        traps_tmp = df[((df["Odds"] < -120) & (df["Edge %"] < 0.5)) | (df["Risk"].str.contains("Expensive", na=False))].sort_values(["Odds","Edge %"]).head(6)
        render_custom_command_center(df, meta, qualified, full_ticket_qualified, best_available, boosters_tmp, traps_tmp, target_date, qlegs, tier_a, tier_bp, play_type, status, grade)
        with st.expander("Open native Streamlit tables / debug view", expanded=False):
            rail, body = st.columns([1.08, 6.2], gap="medium")
            with rail:
                pill_class = "good" if qlegs >= 5 else ("bad" if qlegs <= 1 else "")
                st.markdown(f"""
                <div class='left-rail-card'>
                  <div class='metric-title'>Today's Slate</div>
                  <div style='font-size:.9rem;color:#b8cad7;margin-top:6px;'>{target_date.strftime('%a %b %-d')}</div>
                  <div class='metric-value blue'>{meta.get('schedule_games', 0)}</div>
                  <div class='small-note'>games today</div>
                  <hr />
                  <div class='metric-title'>Slate Status</div>
                  <div style='margin-top:8px;'><span class='status-pill {pill_class}'>{status}</span></div>
                  <div class='rail-grade'>{grade}</div>
                  <div class='small-note'>slate grade</div>
                  <div style='margin-top:12px;'>
                    <div class='rail-line'><span>Suggested Legs</span><b>{qlegs}</b></div>
                    <div class='rail-line'><span>5-Leg A Legs</span><b>{tier_a}</b></div>
                    <div class='rail-line'><span>5-Leg B+ Legs</span><b style='color:#ffc928'>{tier_bp}</b></div>
                    <div class='rail-line'><span>Best Play</span><b style='color:#ffc928'>{play_type}</b></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("<div class='left-rail-card'><div class='metric-title'>Data Warnings</div>", unsafe_allow_html=True)
                warning_lines = meta.get("warnings", [])[:5]
                if warning_lines:
                    for w in warning_lines:
                        st.markdown(f"<div style='color:#ffc928;font-size:.86rem;margin-top:7px;'>⚠️ {w}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='small-note'>No major API warnings.</div>", unsafe_allow_html=True)
                st.markdown("<div style='color:#9db3c5;font-size:.78rem;margin-top:10px;'>Lineups are not fully confirmed in this free-data version. Refresh close to first pitch.</div></div>", unsafe_allow_html=True)

                st.markdown(f"""
                <div class='left-rail-card'>
                  <div class='metric-title'>Refresh Settings</div>
                  <div class='rail-line'><span>Mode</span><b>{model_mode}</b></div>
                  <div class='rail-line'><span>Min Edge</span><b>{min_edge:.1f}%</b></div>
                  <div class='rail-line'><span>Max Fav</span><b>{max_fav}</b></div>
                  <div class='rail-line'><span>Max Dog</span><b>+{max_dog}</b></div>
                  <div class='small-note' style='margin-top:8px;'>Last refresh: {datetime.now(EASTERN).strftime('%-I:%M %p ET')}</div>
                </div>
                """, unsafe_allow_html=True)

            with body:
                c1,c2,c3,c4,c5,c6 = st.columns(6)
                with c1: render_metric("Games Today", meta.get("schedule_games", 0), "View full slate", "blue")
                with c2: render_metric("Suggested Legs", qlegs, "Core/smaller card", "green")
                with c3: render_metric("Tier A Legs", tier_a, "Best plays", "green")
                with c4: render_metric("Tier B+ Legs", tier_bp, "Solid plays", "yellow")
                with c5: render_metric("Best Play Type", play_type, "Recommended", "yellow")
                hit3 = np.prod((best_available.head(3)["Model Win %"] / 100)) * 100 if len(best_available) >= 3 else 0
                with c6: render_metric("Est. Hit % (3-leg)", f"{hit3:.1f}%" if hit3 else "—", "Based on top 3", "")

                top_left, top_right = st.columns([2.15, 1], gap="medium")
                with top_left:
                    st.markdown("<div class='panel-tight'><div class='section-title'>Suggested Smaller-Card Legs</div>", unsafe_allow_html=True)
                    main_cols = ["Team","Opponent","Odds","Book","Model Win %","Implied %","Edge %","Tier","Risk","Probable Pitcher"]
                    if len(full_ticket_qualified) >= 5:
                        main_ticket = full_ticket_qualified.sort_values(["Tier", "Edge %", "Score"], ascending=[True, False, False]).head(5)
                        st.dataframe(_display_cols(main_ticket, main_cols), use_container_width=True, hide_index=True, height=250)
                        odds_val = parlay_american(main_ticket["Odds"].tolist())
                        st.success(f"Recommended 5-leg main ticket: {format_odds(odds_val)} estimated odds. Slate grade: {grade}.")
                    elif qlegs >= 3:
                        main_ticket = qualified.sort_values(["Tier", "Edge %", "Score"], ascending=[True, False, False]).head(qlegs)
                        st.dataframe(_display_cols(main_ticket, main_cols), use_container_width=True, hide_index=True, height=210)
                        odds_val = parlay_american(main_ticket["Odds"].tolist())
                        st.warning(f"Only {qlegs} qualified legs. Smaller {qlegs}-leg card supported at about {format_odds(odds_val)}. Do not force a 5-leg ticket unless using boosters.")
                    elif qlegs > 0:
                        st.dataframe(_display_cols(qualified, main_cols), use_container_width=True, hide_index=True, height=160)
                        st.warning("Use singles or a tiny 2-leg only. No main parlay.")
                    else:
                        st.error("No core model legs under the current filters. Showing best available / near-miss candidates instead.")
                        st.markdown("**Best available smaller-play / near-miss candidates:**")
                        st.dataframe(_display_cols(best_available, main_cols), use_container_width=True, hide_index=True, height=260)
                    st.markdown("</div>", unsafe_allow_html=True)

                with top_right:
                    st.markdown("<div class='panel-tight'><div class='section-title'>Optional Lean / Booster Legs</div>", unsafe_allow_html=True)
                    taken = set(best_available.head(5).index)
                    boosters = df[(~df.index.isin(taken)) & (df["Odds"] >= max_fav) & (df["Odds"] <= max_dog)].sort_values(["Model Win %","Edge %","Score"], ascending=[False, False, False]).head(4)
                    if boosters.empty:
                        st.caption("No booster leg recommended.")
                    else:
                        st.dataframe(_display_cols(boosters, ["Team","Odds","Model Win %","Edge %","Tier","Risk"]), use_container_width=True, hide_index=True, height=180)
                        st.caption("Optional only. Use for higher payout only if you accept more risk.")
                    st.markdown("</div>", unsafe_allow_html=True)

                    st.markdown("<div class='panel-tight'><div class='section-title red'>Trap Favorites / Do Not Use</div>", unsafe_allow_html=True)
                    traps = df[((df["Odds"] < -120) & (df["Edge %"] < 0.5)) | (df["Risk"].str.contains("Expensive", na=False))].sort_values(["Odds","Edge %"]).head(6)
                    if traps.empty:
                        st.caption("No major trap favorites detected.")
                    else:
                        st.dataframe(_display_cols(traps, ["Team","Opponent","Odds","Model Win %","Implied %","Risk"]), use_container_width=True, hide_index=True, height=180)
                    st.markdown("</div>", unsafe_allow_html=True)

                bottom_left, bottom_right = st.columns([1.5, 1], gap="medium")
                with bottom_left:
                    st.markdown("<div class='panel-tight'><div class='section-title'>All Qualified Legs / Best Available</div>", unsafe_allow_html=True)
                    show_cols = ["Start","Team","Opponent","Odds","Book","Model Win %","Implied %","Edge %","Score","Tier","Risk"]
                    st.dataframe(_display_cols(best_available, show_cols), use_container_width=True, hide_index=True, height=330)
                    st.markdown("</div>", unsafe_allow_html=True)

                with bottom_right:
                    st.markdown("<div class='panel-tight'><div class='section-title'>Team / Game Breakdown</div>", unsafe_allow_html=True)
                    default_team = best_available.iloc[0]["Team"] if not best_available.empty else df.iloc[0]["Team"]
                    selected = st.selectbox("Select team", df["Team"].tolist(), index=df["Team"].tolist().index(default_team) if default_team in df["Team"].tolist() else 0, key="cc_team_select")
                    row = df[df["Team"] == selected].iloc[0]
                    st.markdown(f"<div style='font-size:1.2rem;font-weight:900;color:white;'>{row['Team']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='small-note'>Moneyline: <b>{format_odds(row['Odds'])}</b> at {row['Book']} • Tier {row['Tier']} • {row['Risk']}</div>", unsafe_allow_html=True)
                    a,b = st.columns(2)
                    with a:
                        st.metric("Model Win %", f"{row['Model Win %']:.1f}%", f"Edge {row['Edge %']:.1f}%")
                    with b:
                        st.metric("Score", f"{row['Score']:.1f}", row['Probable Pitcher'])
                    breakdown = pd.DataFrame({"Category": ["Starting Pitcher","Offense","Bullpen","Market","Environment"], "Score": [row["SP Score"], row["Offense Score"], row["Bullpen Proxy"], row["Market Score"], row["Environment Score"]], "Max": [30,25,15,20,10]})
                    st.dataframe(breakdown, use_container_width=True, hide_index=True, height=210)
                    st.caption(str(row["Notes"])[:240])
                    st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.subheader("Full Slate Board")
        tier_filter = st.multiselect("Tier filter", ["A","B+","B","Lean","No Bet"], default=["A","B+","B","Lean","No Bet"])
        fdf = df[df["Tier"].isin(tier_filter)].copy()
        st.dataframe(_display_cols(fdf, ["Start","Game","Team","Opponent","Home/Away","Odds","Book","Market %","Model Win %","Implied %","Edge %","Score","Tier","Risk","Probable Pitcher","Notes"]), use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("Auto Ticket Builder")
        ticket_source = eligible if not eligible.empty else best_available
        ticket_df = recommended_tickets(ticket_source if not ticket_source.empty else df[df["Edge %"] > -2])
        if ticket_df.empty:
            st.info("No ticket combinations available.")
        else:
            st.dataframe(ticket_df, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Core Legs**")
            st.dataframe(_display_cols(best_available.head(6), ["Team","Odds","Model Win %","Edge %","Tier","Risk"]), use_container_width=True, hide_index=True)
        with c2:
            st.markdown("**Optional Add-Ons**")
            st.dataframe(_display_cols(boosters, ["Team","Odds","Model Win %","Edge %","Tier","Risk"]) if 'boosters' in locals() and not boosters.empty else pd.DataFrame(), use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("Team / Game Breakdown")
        teams = df["Team"].tolist()
        selected = st.selectbox("Select team", teams, key="detail_team_select")
        row = df[df["Team"] == selected].iloc[0]
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            st.metric("Model Win Probability", f"{row['Model Win %']:.1f}%", f"Edge {row['Edge %']:.1f}%")
            st.metric("Moneyline", format_odds(row["Odds"]), row["Book"])
            st.metric("Tier", row["Tier"], row["Risk"])
        with c2:
            breakdown = pd.DataFrame({"Category": ["Starting Pitcher","Offense","Bullpen Proxy","Market Edge","Environment"], "Score": [row["SP Score"], row["Offense Score"], row["Bullpen Proxy"], row["Market Score"], row["Environment Score"]], "Max": [30,25,15,20,10]})
            st.dataframe(breakdown, use_container_width=True, hide_index=True)
        with c3:
            st.write("**Key Notes**")
            for note in str(row["Notes"]).split(";"):
                st.write(f"✅ {note.strip()}")
            st.write("**Weather**")
            st.write(f"Temp: {row['Temp']}°F | Wind: {row['Wind']} mph | Precip: {row['Precip %']}%")
            st.write(f"Park Factor: {row['Park Factor']}")

    with tab5:
        st.subheader("Results / Export")
        st.write("Export today’s board and append your results later. The CSV tracker is included in the ZIP.")
        st.download_button("Download today’s board CSV", data=df.to_csv(index=False), file_name=f"mlb_board_{target_date}.csv", mime="text/csv")
        st.download_button("Download qualified legs CSV", data=qualified.to_csv(index=False), file_name=f"qualified_legs_{target_date}.csv", mime="text/csv")
        try:
            tracker = pd.read_csv("results_tracker.csv")
            st.dataframe(tracker, use_container_width=True, hide_index=True)
        except Exception:
            st.info("No tracker file found yet.")
        if meta.get("errors"):
            with st.expander("API errors / diagnostics"):
                st.code("\n".join(meta["errors"][:20]))


# -----------------------------
# v6 overrides: odds-first fallback + real navigation pages
# -----------------------------
_BUILD_BOARD_SCHEDULE_FIRST = build_board

def _event_is_target_date(ev: dict, day: date) -> bool:
    try:
        ts = ev.get("commence_time", "")
        if not ts:
            return True
        dt = pd.to_datetime(ts, utc=True).tz_convert(EASTERN).date()
        return dt == day
    except Exception:
        return True

def _schedule_lookup(schedule: List[dict]) -> Dict[tuple, dict]:
    out = {}
    for game in schedule:
        try:
            teams = game.get("teams", {})
            h = teams.get("home", {}).get("team", {}).get("name", "")
            a = teams.get("away", {}).get("team", {}).get("name", "")
            start_iso = game.get("gameDate", "")
            out[pair_key(h, a)] = {"game": game, "start_iso": start_iso}
        except Exception:
            pass
    return out

def build_board(day: date, api_key: str, regions: str, bookmakers: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """v6: use schedule-first model when matching works; if odds do not match schedule, build from odds directly.
    This prevents the dashboard from showing Odds=None and zero suggested legs when the Odds API is returning valid events.
    """
    df, meta = _BUILD_BOARD_SCHEDULE_FIRST(day, api_key, regions, bookmakers)
    if meta.get("matched_games", 0) > 0 or meta.get("odds_events", 0) == 0:
        meta["build_mode"] = "schedule-first"
        return df, meta

    st.session_state["errors"] = meta.get("errors", []) + ["v6 fallback used: schedule/odds team matching failed, so board was built directly from Odds API events."]
    odds_events = fetch_odds(api_key, regions, bookmakers)
    odds_events = [ev for ev in odds_events if _event_is_target_date(ev, day)] or odds_events
    schedule = fetch_schedule(day)
    sched_map = _schedule_lookup(schedule)
    odds_map = parse_odds_events(odds_events)
    rows = []
    matched_sched = 0

    for key, odds_event in odds_map.items():
        home = odds_event.get("home", "")
        away = odds_event.get("away", "")
        start_iso = odds_event.get("start", "")
        sched_info = sched_map.get(pair_key(home, away), {})
        game = sched_info.get("game", {})
        if game:
            matched_sched += 1
        teams = game.get("teams", {}) if game else {}
        home_pp = teams.get("home", {}).get("probablePitcher", {}) if game else {}
        away_pp = teams.get("away", {}).get("probablePitcher", {}) if game else {}
        venue = game.get("venue", {}).get("name", "") if game else ""
        outcomes = odds_event.get("outcomes", [])
        for team, opp, is_home, pp in [(home, away, True, home_pp), (away, home, False, away_pp)]:
            odds, book, team_avg_imp = best_price_for_team(outcomes, team)
            opp_odds, opp_book, opp_avg_imp = best_price_for_team(outcomes, opp)
            implied = american_to_implied(odds) if pd.notna(odds) else np.nan
            market_consensus = no_vig_market_prob(team_avg_imp, opp_avg_imp)
            # Odds-first model: market consensus is anchor; best-price edge comes from comparing no-vig consensus to best available implied price.
            home_adj = 0.012 if is_home else -0.004
            model_pct = clamp((market_consensus if pd.notna(market_consensus) else 0.50) + home_adj, .28, .74)
            edge_pct = (model_pct - implied) * 100 if pd.notna(implied) else np.nan
            # Scores are intentionally market-led in fallback mode; full model resumes when schedule matching works.
            market_points = market_edge_score(model_pct, implied) if pd.notna(implied) else 0
            base_score = 52 + market_points + (edge_pct if pd.notna(edge_pct) else -5) * 2.2 + (4 if is_home else 0)
            total_score = clamp(base_score, 35, 88)
            risk_flags = []
            if has_started: risk_flags.append("Game started")
            if not pp: risk_flags.append("Pitcher TBD")
            if pd.isna(odds): risk_flags.append("Odds missing")
            if pd.notna(odds) and odds < -220: risk_flags.append("Expensive favorite")
            if pd.notna(odds) and odds > 180: risk_flags.append("Long dog")
            risk_flags.append("Odds-first fallback")
            tier = tier_from(edge_pct if pd.notna(edge_pct) else -99, total_score, odds if pd.notna(odds) else 0, risk_flags)
            # In fallback mode, allow B/Lean suggestions so user sees smaller-card candidates, but do not overlabel as A.
            if tier == "A": tier = "B+"
            try:
                start_fmt = pd.to_datetime(start_iso, utc=True).tz_convert(EASTERN).strftime("%-I:%M %p")
            except Exception:
                start_fmt = ""
            rows.append({
                "Start": start_fmt,
                "Game": f"{away} @ {home}",
                "Team": team,
                "Abbr": TEAM_ALIASES.get(team, team[:3].upper()),
                "Opponent": opp,
                "Home/Away": "Home" if is_home else "Away",
                "Venue": venue,
                "Odds": odds,
                "Book": book,
                "Implied %": implied * 100 if pd.notna(implied) else np.nan,
                "Market %": market_consensus * 100 if pd.notna(market_consensus) else np.nan,
                "Model Win %": model_pct * 100,
                "Edge %": edge_pct,
                "Score": round(total_score, 1),
                "Tier": tier,
                "Risk": ", ".join(risk_flags),
                "Probable Pitcher": pp.get("fullName", "TBD") if pp else "TBD",
                "Lineup Status": "Started/Live" if has_started else "Projected lineup",
                "Pregame Status": pregame_status,
                "SP Score": 15.0,
                "Offense Score": 12.0,
                "Bullpen Proxy": 7.5,
                "Market Score": round(market_points, 1),
                "Environment Score": 5.0,
                "Notes": "Built from live odds because schedule/odds matching failed. Use as smaller-card/watchlist unless full data matches.",
                "Temp": np.nan,
                "Wind": np.nan,
                "Precip %": np.nan,
                "Park Factor": 1.0,
            })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["Edge %", "Score"], ascending=[False, False])
    meta2 = {
        "warnings": ["Odds-first fallback mode active. Suggested legs are usable for watchlist/smaller-card review, but full pitcher/team model did not match the odds feed."],
        "errors": st.session_state.get("errors", []),
        "odds_events": len(odds_events),
        "odds_outcomes": sum(len(v.get("outcomes", [])) for v in odds_map.values()),
        "schedule_games": len(schedule),
        "matched_games": 0,
        "matched_schedule_in_fallback": matched_sched,
        "build_mode": "odds-first-fallback",
    }
    return out, meta2


def one_side_per_game(df: pd.DataFrame, min_edge_gap: float = 0.75) -> pd.DataFrame:
    """Keep at most one recommended side per game.

    Ranking is winner-first, then edge, then score. If the top two sides in the same
    game are too close on edge and model win probability, the game is treated as a
    conflict and skipped for official recommendations.
    """
    if df is None or df.empty or "Game" not in df.columns:
        return df.copy() if df is not None else pd.DataFrame()
    d = df.copy()
    for col in ["Model Win %", "Edge %", "Score", "Odds"]:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce")
    chosen = []
    # preserve sorted order only inside each game based on our explicit winner-first priority
    for _, g in d.groupby("Game", dropna=False, sort=False):
        g = g.sort_values(["Model Win %", "Edge %", "Score"], ascending=[False, False, False])
        if len(g) >= 2:
            top = g.iloc[0]
            second = g.iloc[1]
            edge_gap = abs(float(top.get("Edge %", 0) or 0) - float(second.get("Edge %", 0) or 0))
            win_gap = abs(float(top.get("Model Win %", 0) or 0) - float(second.get("Model Win %", 0) or 0))
            # If both sides are essentially the same read, skip the game entirely.
            if edge_gap < min_edge_gap and win_gap < 2.0:
                continue
        chosen.append(g.iloc[0])
    if not chosen:
        return d.iloc[0:0].copy()
    out = pd.DataFrame(chosen)
    return out.sort_values(["Model Win %", "Edge %", "Score"], ascending=[False, False, False]).reset_index(drop=True)

def _qualification(df: pd.DataFrame, min_edge: float, max_fav: int, max_dog: int):
    """v10 qualification used by the tabbed views: winner-first parlay mode."""
    dfx = df.copy()
    for col in ["Edge %", "Score", "Odds", "Model Win %"]:
        if col in dfx.columns:
            dfx[col] = pd.to_numeric(dfx[col], errors="coerce")
    price_ok = (dfx["Odds"].notna()) & (dfx["Odds"] >= max_fav) & (dfx["Odds"] <= max_dog)
    clean_risk = ~dfx["Risk"].str.contains("Game started|Odds missing|Long dog", case=False, na=False) if "Risk" in dfx.columns else True
    raw = dfx[
        price_ok & clean_risk
        & (dfx["Model Win %"].fillna(0) >= 54.0)
        & (dfx["Edge %"].fillna(-99) >= max(1.5, min_edge))
        & (dfx["Score"].fillna(0) >= 70.0)
        & (dfx["Tier"].isin(["A", "B+", "B"]))
    ].copy()
    qualified = one_side_per_game(raw, min_edge_gap=0.75)
    eligible = qualified.copy()
    full_ticket_qualified = qualified[(qualified["Model Win %"].fillna(0) >= 56.0) & (qualified["Edge %"].fillna(-99) >= 2.0) & (qualified["Tier"].isin(["A", "B+"]))].copy()
    watch = dfx[price_ok & (dfx["Model Win %"].fillna(0) >= 51.0)].sort_values(["Model Win %", "Edge %", "Score"], ascending=[False, False, False]).copy()
    best_available = qualified if not qualified.empty else one_side_per_game(watch, min_edge_gap=0.50).head(10)
    return eligible, qualified, full_ticket_qualified, best_available


# -----------------------------
# v7 overrides: odds-first board + real suggested legs
# -----------------------------
@st.cache_data(ttl=240)
def fetch_odds(api_key: str, regions: str, bookmakers: str) -> List[dict]:
    """v7: transparent Odds API fetch with exact diagnostics and no forced bookmaker filter."""
    st.session_state["odds_api_debug"] = {}
    params = {
        "apiKey": api_key,
        "regions": regions or "us",
        "markets": "h2h",
        "oddsFormat": "american",
        "dateFormat": "iso",
    }
    if str(bookmakers or "").strip():
        params["bookmakers"] = str(bookmakers).strip()
    try:
        r = requests.get(ODDS_API_BASE, params=params, timeout=20)
        st.session_state["odds_api_debug"] = {
            "status_code": r.status_code,
            "url_without_key": r.url.replace(api_key, "***") if api_key else r.url,
            "response_preview": r.text[:700],
            "bookmaker_filter_used": params.get("bookmakers", "ALL AVAILABLE"),
        }
        if r.status_code != 200:
            st.session_state.setdefault("errors", []).append(f"Odds API HTTP {r.status_code}: {r.text[:500]}")
            return []
        data = r.json()
        events = data if isinstance(data, list) else []
        # If a bookmaker filter was used and no outcomes came back, retry all books.
        def outcome_count(evs):
            total = 0
            for ev in evs or []:
                for b in ev.get("bookmakers", []):
                    for m in b.get("markets", []):
                        if m.get("key") == "h2h":
                            total += len(m.get("outcomes", []))
            return total
        if params.get("bookmakers") and outcome_count(events) == 0:
            st.session_state.setdefault("errors", []).append("Bookmaker filter returned zero outcomes. Retried with all available books.")
            params.pop("bookmakers", None)
            r2 = requests.get(ODDS_API_BASE, params=params, timeout=20)
            st.session_state["odds_api_debug_retry"] = {
                "status_code": r2.status_code,
                "url_without_key": r2.url.replace(api_key, "***") if api_key else r2.url,
                "response_preview": r2.text[:700],
            }
            if r2.status_code == 200:
                data2 = r2.json()
                events = data2 if isinstance(data2, list) else events
            else:
                st.session_state.setdefault("errors", []).append(f"Odds API retry HTTP {r2.status_code}: {r2.text[:500]}")
        return events
    except Exception as e:
        st.session_state.setdefault("errors", []).append(f"Odds API request failed: {e}")
        st.session_state["odds_api_debug"] = {"exception": str(e)}
        return []


def _extract_best_prices_for_event(ev: dict) -> Dict[str, dict]:
    rows_by_team = {}
    for book in ev.get("bookmakers", []) or []:
        book_title = book.get("title") or book.get("key") or ""
        for market in book.get("markets", []) or []:
            if market.get("key") != "h2h":
                continue
            for out in market.get("outcomes", []) or []:
                nm = out.get("name")
                price = out.get("price")
                if nm is None or price is None:
                    continue
                key = norm_team_name(nm)
                rows_by_team.setdefault(key, {"team_name": nm, "prices": []})
                rows_by_team[key]["prices"].append({"price": price, "book": book_title})
    best = {}
    for key, val in rows_by_team.items():
        prices = val["prices"]
        if not prices:
            continue
        b = sorted(prices, key=lambda x: x["price"], reverse=True)[0]
        imps = [american_to_implied(x["price"]) for x in prices if x.get("price") is not None]
        best[key] = {
            "team_name": val["team_name"],
            "odds": b["price"],
            "book": b["book"],
            "avg_implied": float(np.mean(imps)) if imps else np.nan,
            "book_count": len(prices),
        }
    return best


def _sched_by_pair(day: date) -> Dict[tuple, dict]:
    sched = fetch_schedule(day)
    out = {}
    for game in sched:
        try:
            teams = game.get("teams", {})
            h = teams.get("home", {}).get("team", {}).get("name", "")
            a = teams.get("away", {}).get("team", {}).get("name", "")
            out[pair_key(h, a)] = game
        except Exception:
            pass
    return out


def build_board(day: date, api_key: str, regions: str, bookmakers: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """v7: odds-first. If live odds exist, build the betting board from the odds feed, then enrich with MLB schedule.
    This prevents the dashboard from showing 15 games with Odds=None when the odds feed name matching fails.
    """
    st.session_state["errors"] = []
    odds_events = fetch_odds(api_key, regions, bookmakers)
    odds_events = [ev for ev in odds_events if _event_is_target_date(ev, day)] or odds_events
    schedule_map = _sched_by_pair(day)
    rows = []
    matched_schedule = 0
    outcomes_total = 0
    for ev in odds_events:
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        start_iso = ev.get("commence_time", "")
        has_started = False
        pregame_status = "Pregame"
        try:
            start_dt = pd.to_datetime(start_iso, utc=True)
            has_started = pd.Timestamp.now(tz="UTC") >= start_dt
            pregame_status = "Started/Live" if has_started else "Pregame"
        except Exception:
            start_dt = None
            has_started = False
            pregame_status = "Pregame status unknown"
        if not home or not away:
            continue
        best = _extract_best_prices_for_event(ev)
        outcomes_total += sum(v.get("book_count",0) for v in best.values())
        game = schedule_map.get(pair_key(home, away), {})
        if game:
            matched_schedule += 1
        teams = game.get("teams", {}) if game else {}
        home_pp = teams.get("home", {}).get("probablePitcher", {}) if game else {}
        away_pp = teams.get("away", {}).get("probablePitcher", {}) if game else {}
        home_rec = teams.get("home", {}).get("leagueRecord", {}) if game else {}
        away_rec = teams.get("away", {}).get("leagueRecord", {}) if game else {}
        venue = game.get("venue", {}).get("name", "") if game else ""
        hkey, akey = norm_team_name(home), norm_team_name(away)
        h = best.get(hkey, {})
        a = best.get(akey, {})
        # If names differ, fuzzy fallback by containment.
        if not h:
            h = next((v for k,v in best.items() if hkey in k or k in hkey), {})
        if not a:
            a = next((v for k,v in best.items() if akey in k or k in akey), {})
        for team, opp, is_home, this, other, pp, rec, opp_rec in [
            (home, away, True, h, a, home_pp, home_rec, away_rec),
            (away, home, False, a, h, away_pp, away_rec, home_rec),
        ]:
            odds = this.get("odds", np.nan)
            book = this.get("book", "")
            team_avg_imp = this.get("avg_implied", np.nan)
            opp_avg_imp = other.get("avg_implied", np.nan)
            implied = american_to_implied(odds) if pd.notna(odds) else np.nan
            market_pct = no_vig_market_prob(team_avg_imp, opp_avg_imp)
            rec_edge = (norm_pct(rec.get("pct"), .5) - norm_pct(opp_rec.get("pct"), .5)) * 0.035
            home_edge = 0.012 if is_home else -0.004
            # Market-led model, with tiny record/home adjustment when schedule exists.
            model_pct = clamp((market_pct if pd.notna(market_pct) else .50) + rec_edge + home_edge, .28, .74)
            edge_pct = (model_pct - implied) * 100 if pd.notna(implied) else np.nan
            market_points = market_edge_score(model_pct, implied) if pd.notna(implied) else 0
            score = clamp(55 + market_points + (edge_pct if pd.notna(edge_pct) else -4)*2.8 + (3 if is_home else 0), 35, 90)
            risk_flags = []
            if has_started: risk_flags.append("Game started")
            if not pp: risk_flags.append("Pitcher TBD")
            if pd.isna(odds): risk_flags.append("Odds missing")
            if pd.notna(odds) and odds < -260: risk_flags.append("Very expensive favorite")
            elif pd.notna(odds) and odds < -220: risk_flags.append("Expensive favorite")
            if pd.notna(odds) and odds > 200: risk_flags.append("Long dog")
            if not game: risk_flags.append("Odds-only")
            tier = tier_from(edge_pct if pd.notna(edge_pct) else -99, score, odds if pd.notna(odds) else 0, risk_flags)
            # Do not overstate confidence in odds-first mode.
            if tier == "A" and not game:
                tier = "B+"
            try:
                start_fmt = pd.to_datetime(start_iso, utc=True).tz_convert(EASTERN).strftime("%-I:%M %p")
            except Exception:
                start_fmt = ""
            rows.append({
                "Start": start_fmt,
                "Game": f"{away} @ {home}",
                "Team": team,
                "Abbr": TEAM_ALIASES.get(team, team[:3].upper()),
                "Opponent": opp,
                "Home/Away": "Home" if is_home else "Away",
                "Venue": venue,
                "Odds": odds,
                "Book": book,
                "Implied %": implied * 100 if pd.notna(implied) else np.nan,
                "Market %": market_pct * 100 if pd.notna(market_pct) else np.nan,
                "Model Win %": model_pct * 100,
                "Edge %": edge_pct,
                "Score": round(score, 1),
                "Tier": tier,
                "Risk": ", ".join(risk_flags) if risk_flags else "Clean",
                "Probable Pitcher": pp.get("fullName", "TBD") if pp else "TBD",
                "Lineup Status": "Started/Live" if has_started else "Projected lineup",
                "Pregame Status": pregame_status,
                "SP Score": 15.0,
                "Offense Score": 12.5,
                "Bullpen Proxy": 7.5,
                "Market Score": round(market_points, 1),
                "Environment Score": 6.0,
                "Notes": "v16 pregame model. Started games excluded; projected lineups are gray/provisional.",
                "Temp": np.nan,
                "Wind": np.nan,
                "Precip %": np.nan,
                "Park Factor": 1.0,
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        if "Lineup Status" not in df.columns:
            df["Lineup Status"] = "Projected lineup"
        if "Pregame Status" not in df.columns:
            df["Pregame Status"] = np.where(df.get("Risk", "").astype(str).str.contains("Game started", case=False, na=False), "Started/Live", "Pregame")
    if df.empty:
        # If the odds API is not returning data, show schedule-only diagnostics rather than fake betting legs.
        df, meta = _BUILD_BOARD_SCHEDULE_FIRST(day, api_key, regions, bookmakers)
        meta["build_mode"] = "schedule-only-no-odds"
        meta["odds_api_debug"] = st.session_state.get("odds_api_debug", {})
        meta["odds_api_debug_retry"] = st.session_state.get("odds_api_debug_retry", {})
        return df, meta
    df = df.sort_values(["Edge %", "Score"], ascending=[False, False])
    live_excluded = int(df["Risk"].astype(str).str.contains("Game started", case=False, na=False).sum()) if "Risk" in df.columns else 0
    meta = {
        "warnings": ["v16 odds-first pregame mode active. Started/live games are excluded from recommendations. Projected/unconfirmed lineups are gray/provisional."] + ([f"{live_excluded} started/live games excluded from pregame recommendations."] if live_excluded else []),
        "errors": st.session_state.get("errors", []),
        "odds_events": len(odds_events),
        "odds_outcomes": outcomes_total,
        "schedule_games": len(schedule_map),
        "matched_games": matched_schedule,
        "build_mode": "v7-odds-first",
        "odds_api_debug": st.session_state.get("odds_api_debug", {}),
        "odds_api_debug_retry": st.session_state.get("odds_api_debug_retry", {}),
    }
    return df, meta



def one_side_per_game(df: pd.DataFrame, min_edge_gap: float = 0.75) -> pd.DataFrame:
    """Keep at most one recommended side per game.

    Ranking is winner-first, then edge, then score. If the top two sides in the same
    game are too close on edge and model win probability, the game is treated as a
    conflict and skipped for official recommendations.
    """
    if df is None or df.empty or "Game" not in df.columns:
        return df.copy() if df is not None else pd.DataFrame()
    d = df.copy()
    for col in ["Model Win %", "Edge %", "Score", "Odds"]:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce")
    chosen = []
    # preserve sorted order only inside each game based on our explicit winner-first priority
    for _, g in d.groupby("Game", dropna=False, sort=False):
        g = g.sort_values(["Model Win %", "Edge %", "Score"], ascending=[False, False, False])
        if len(g) >= 2:
            top = g.iloc[0]
            second = g.iloc[1]
            edge_gap = abs(float(top.get("Edge %", 0) or 0) - float(second.get("Edge %", 0) or 0))
            win_gap = abs(float(top.get("Model Win %", 0) or 0) - float(second.get("Model Win %", 0) or 0))
            # If both sides are essentially the same read, skip the game entirely.
            if edge_gap < min_edge_gap and win_gap < 2.0:
                continue
        chosen.append(g.iloc[0])
    if not chosen:
        return d.iloc[0:0].copy()
    out = pd.DataFrame(chosen)
    return out.sort_values(["Model Win %", "Edge %", "Score"], ascending=[False, False, False]).reset_index(drop=True)

def _qualification(df: pd.DataFrame, min_edge: float, max_fav: int, max_dog: int):
    """v11 winner-first qualification.

    This separates true parlay candidates from pure value dogs.

    Winner-First Suggested Legs:
      - Team must be more likely than not to win (52%+ model win probability)
      - Team must not be badly overpriced (positive edge threshold)
      - One side per game only

    Core / Full-Ticket Legs:
      - Stronger winner threshold (54%+)
      - Stronger edge threshold (1.5%+ or selected min edge)
      - Score 70+

    Value dogs can appear in the watchlist but are not official parlay legs.
    """
    dfx = df.copy()
    for col in ["Edge %", "Score", "Odds", "Model Win %", "Implied %"]:
        if col in dfx.columns:
            dfx[col] = pd.to_numeric(dfx[col], errors="coerce")

    price_ok = (dfx["Odds"].notna()) & (dfx["Odds"] >= max_fav) & (dfx["Odds"] <= max_dog)
    clean_risk = ~dfx["Risk"].str.contains("Game started|Odds missing|Long dog|High risk", case=False, na=False) if "Risk" in dfx.columns else True
    base = dfx[price_ok & clean_risk].copy()

    # v11 keeps winner-first, but does not require an unrealistic 54%+ for every smaller-card candidate.
    # This is the key distinction:
    #   suggested = can win + not overpriced
    #   core/full ticket = stronger winner + stronger edge
    suggested_min_win = 52.0
    suggested_min_edge = 0.5 if float(min_edge) <= 2.0 else max(0.75, float(min_edge) - 1.25)

    suggested_raw = base[
        (base["Model Win %"].fillna(0) >= suggested_min_win)
        & (base["Edge %"].fillna(-99) >= suggested_min_edge)
        & (base["Score"].fillna(0) >= 66.0)
    ].copy()
    suggested_raw["Parlay Class"] = "Suggested Winner-First"
    suggested = one_side_per_game(
        suggested_raw.sort_values(["Model Win %", "Edge %", "Score"], ascending=[False, False, False]),
        min_edge_gap=0.50
    )

    core_min_edge = max(1.5, float(min_edge) if float(min_edge) <= 3.0 else float(min_edge) - 0.5)
    core_raw = base[
        (base["Model Win %"].fillna(0) >= 54.0)
        & (base["Edge %"].fillna(-99) >= core_min_edge)
        & (base["Score"].fillna(0) >= 70.0)
        & (base["Tier"].isin(["A", "B+", "B", "Lean"]))
    ].copy()
    core_raw["Parlay Class"] = "Core Parlay"
    core = one_side_per_game(
        core_raw.sort_values(["Model Win %", "Edge %", "Score"], ascending=[False, False, False]),
        min_edge_gap=0.75
    )

    full_ticket_qualified = core[
        (core["Model Win %"].fillna(0) >= 55.0)
        & (core["Edge %"].fillna(-99) >= max(1.5, float(min_edge)))
        & (core["Score"].fillna(0) >= 72.0)
    ].copy() if not core.empty else core.copy()

    # v16 cleanup:
    # Suggested Winner-First Legs are the official smaller-card candidates.
    # Lean / Thin Edge rows are useful context only and must NOT appear in the main suggested card.
    eligible = suggested.copy()
    qualified = suggested[
        (suggested["Tier"].isin(["A", "B+", "B"]))
        & (suggested["Edge %"].fillna(-99) >= 2.0)
    ].copy()

    # Watchlist: winner-leaning but thin edge, plus high-edge dogs that are not parlay-safe.
    winner_watch = base[
        (base["Model Win %"].fillna(0) >= 50.0)
        & (base["Score"].fillna(0) >= 62.0)
        & (~base.index.isin(suggested_raw.index))
    ].copy()
    winner_watch["Parlay Class"] = "Winner Watchlist"

    value_dogs = base[
        (base["Model Win %"].fillna(0) >= 45.0)
        & (base["Model Win %"].fillna(0) < 52.0)
        & (base["Edge %"].fillna(-99) >= 2.5)
    ].copy()
    value_dogs["Parlay Class"] = "Value Dog / Singles Only"

    watch = pd.concat([winner_watch, value_dogs], ignore_index=False) if not winner_watch.empty or not value_dogs.empty else pd.DataFrame()
    if not watch.empty:
        watch = one_side_per_game(
            watch.sort_values(["Model Win %", "Edge %", "Score"], ascending=[False, False, False]),
            min_edge_gap=0.50
        ).head(10)

    best_available = qualified if not qualified.empty else watch
    return eligible, qualified, full_ticket_qualified, best_available


# -----------------------------
# v13 Bet Tracker Helpers
# -----------------------------
TRACKER_COLUMNS = [
    "Ticket ID", "Date", "Bucket", "Ticket Type", "Team", "Opponent", "Odds", "Book",
    "Model Win %", "Implied %", "Edge %", "Score", "Tier", "Risk", "Stake",
    "Result", "Profit/Loss", "Miss Reason", "Read Quality", "Notes", "Logged At"
]


def tracker_path() -> str:
    return "results_tracker.csv"


def load_tracker() -> pd.DataFrame:
    try:
        t = pd.read_csv(tracker_path())
    except Exception:
        t = pd.DataFrame(columns=TRACKER_COLUMNS)
    for c in TRACKER_COLUMNS:
        if c not in t.columns:
            t[c] = "" if c not in ["Stake", "Profit/Loss", "Odds", "Model Win %", "Implied %", "Edge %", "Score"] else np.nan
    return t[TRACKER_COLUMNS]


def save_tracker_df(t: pd.DataFrame) -> None:
    for c in TRACKER_COLUMNS:
        if c not in t.columns:
            t[c] = ""
    t[TRACKER_COLUMNS].to_csv(tracker_path(), index=False)


def tracker_profit_from_american(odds, stake, result):
    try:
        odds = float(odds); stake = float(stake)
    except Exception:
        return np.nan
    result = str(result).strip().lower()
    if result in ["loss", "lost", "l"]:
        return -stake
    if result in ["push", "void", "cancelled", "p"]:
        return 0.0
    if result not in ["win", "won", "w"]:
        return np.nan
    if odds > 0:
        return stake * (odds / 100.0)
    return stake * (100.0 / abs(odds))


def render_bet_tracker(df, qualified, full_ticket_qualified, best_available, target_date):
    st.subheader("Bet Tracker")
    st.caption("Save the current model recommendations, mark results later, and see whether the buckets are actually producing winners. This tracks legs and tickets separately by Ticket ID.")

    bucket_options = {
        "Core Parlay Legs": full_ticket_qualified.copy() if isinstance(full_ticket_qualified, pd.DataFrame) else pd.DataFrame(),
        "Suggested Winner-First Legs": qualified.copy() if isinstance(qualified, pd.DataFrame) else pd.DataFrame(),
        "Watchlist / Value Dogs": best_available.copy() if isinstance(best_available, pd.DataFrame) else pd.DataFrame(),
        "Full Board Manual Select": df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(),
    }

    with st.container(border=True):
        st.markdown("#### Save current recommendations to tracker")
        c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])
        with c1:
            bucket_name = st.selectbox("Bucket to save", list(bucket_options.keys()))
        source = bucket_options[bucket_name]
        if bucket_name == "Watchlist / Value Dogs" and not source.empty and not qualified.empty:
            source = source[~source.index.isin(qualified.index)]
        if not source.empty:
            source = source.copy().head(12)
            source["Display"] = source.apply(lambda r: f"{r.get('Team','')} vs {r.get('Opponent','')} | {format_odds(r.get('Odds'))} | Edge {r.get('Edge %', 0):.1f}% | MW% {r.get('Model Win %', 0):.1f}%", axis=1)
        with c2:
            ticket_type = st.selectbox("Ticket type", ["Single", "2-Leg", "3-Leg", "4-Leg", "5-Leg", "6-Leg", "Custom"])
        with c3:
            stake = st.number_input("Stake", min_value=0.0, value=0.0, step=1.0)
        with c4:
            ticket_note = st.text_input("Ticket note", value="")

        if source.empty:
            st.info("No rows available in that bucket right now.")
        else:
            default_n = 1 if ticket_type == "Single" else int(ticket_type.split("-")[0]) if "-Leg" in ticket_type else min(3, len(source))
            default_labels = source["Display"].tolist()[:min(default_n, len(source))]
            selected_labels = st.multiselect("Choose legs to save", source["Display"].tolist(), default=default_labels)
            preview = source[source["Display"].isin(selected_labels)].drop(columns=["Display"], errors="ignore")
            if not preview.empty:
                st.dataframe(_display_cols(preview, ["Team","Opponent","Odds","Book","Model Win %","Implied %","Edge %","Score","Tier","Risk"]), use_container_width=True, hide_index=True)
            if st.button("💾 Save selected legs to tracker", type="primary", use_container_width=True):
                if preview.empty:
                    st.warning("Select at least one leg first.")
                else:
                    existing = load_tracker()
                    ticket_id = f"{pd.to_datetime(target_date).strftime('%Y%m%d')}-{datetime.now(EASTERN).strftime('%H%M%S')}"
                    now = datetime.now(EASTERN).strftime("%Y-%m-%d %H:%M:%S")
                    rows = []
                    for _, r in preview.iterrows():
                        rows.append({
                            "Ticket ID": ticket_id,
                            "Date": str(target_date),
                            "Bucket": bucket_name,
                            "Ticket Type": ticket_type,
                            "Team": r.get("Team", ""),
                            "Opponent": r.get("Opponent", ""),
                            "Odds": r.get("Odds", np.nan),
                            "Book": r.get("Book", ""),
                            "Model Win %": r.get("Model Win %", np.nan),
                            "Implied %": r.get("Implied %", np.nan),
                            "Edge %": r.get("Edge %", np.nan),
                            "Score": r.get("Score", np.nan),
                            "Tier": r.get("Tier", ""),
                            "Risk": r.get("Risk", ""),
                            "Stake": stake,
                            "Result": "Pending",
                            "Profit/Loss": np.nan,
                            "Miss Reason": "",
                            "Read Quality": "",
                            "Notes": ticket_note,
                            "Logged At": now,
                        })
                    out = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
                    save_tracker_df(out)
                    st.success(f"Saved {len(rows)} leg(s) under Ticket ID {ticket_id}.")

    tracker = load_tracker()
    st.markdown("#### Tracker log")
    if tracker.empty:
        st.info("No tracked bets yet. Save current recommendations above to start building history.")
        return

    # Coerce numeric fields for summaries.
    numeric_cols = ["Stake", "Profit/Loss", "Odds", "Model Win %", "Implied %", "Edge %", "Score"]
    for c in numeric_cols:
        tracker[c] = pd.to_numeric(tracker[c], errors="coerce")

    c1, c2, c3, c4 = st.columns(4)
    settled = tracker[tracker["Result"].astype(str).str.lower().isin(["win", "loss", "push", "won", "lost", "w", "l", "p"])]
    wins = settled[settled["Result"].astype(str).str.lower().isin(["win", "won", "w"])]
    losses = settled[settled["Result"].astype(str).str.lower().isin(["loss", "lost", "l"])]
    pl = tracker["Profit/Loss"].sum(skipna=True)
    stake_sum = tracker["Stake"].sum(skipna=True)
    roi = (pl / stake_sum * 100) if stake_sum else 0
    c1.metric("Tracked Legs", len(tracker))
    c2.metric("Settled Hit Rate", f"{(len(wins)/max(1, len(wins)+len(losses))*100):.1f}%")
    c3.metric("Profit / Loss", f"${pl:.2f}")
    c4.metric("ROI", f"{roi:.1f}%")

    st.markdown("#### Mark results")
    st.caption("Edit Result, Profit/Loss, Miss Reason, Read Quality, or Notes, then click Save Tracker Updates. Profit/Loss can be typed manually; singles can also be auto-filled with the helper below.")
    edited = st.data_editor(
        tracker,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "Result": st.column_config.SelectboxColumn("Result", options=["Pending", "Win", "Loss", "Push"]),
            "Miss Reason": st.column_config.SelectboxColumn("Miss Reason", options=["", "Starter issue", "Bullpen collapse", "Lineup issue", "Market moved", "Weather/park", "Random variance", "Bad model read", "Other"]),
            "Read Quality": st.column_config.SelectboxColumn("Read Quality", options=["", "Good read, won", "Good read, lost randomly", "Bad read", "Too close to call"]),
        }
    )
    b1, b2, b3 = st.columns([1,1,2])
    with b1:
        if st.button("🧮 Auto-fill single-leg P/L", use_container_width=True):
            tmp = edited.copy()
            for i, r in tmp.iterrows():
                if pd.isna(r.get("Profit/Loss")) or str(r.get("Profit/Loss", "")).strip() == "":
                    tmp.at[i, "Profit/Loss"] = tracker_profit_from_american(r.get("Odds"), r.get("Stake"), r.get("Result"))
            save_tracker_df(tmp)
            st.success("Auto-filled available single-leg P/L values and saved.")
    with b2:
        if st.button("💾 Save tracker updates", type="primary", use_container_width=True):
            save_tracker_df(edited)
            st.success("Tracker updated.")
    with b3:
        st.download_button("Download tracker CSV", data=edited.to_csv(index=False), file_name="mlb_bet_tracker.csv", mime="text/csv", use_container_width=True)

    st.markdown("#### Performance breakdowns")
    tc1, tc2 = st.columns(2)
    with tc1:
        by_bucket = tracker.groupby("Bucket", dropna=False).agg(
            Legs=("Team", "count"),
            Avg_Model_Win=("Model Win %", "mean"),
            Avg_Edge=("Edge %", "mean"),
            Profit_Loss=("Profit/Loss", "sum"),
            Stake=("Stake", "sum"),
        ).reset_index()
        if not by_bucket.empty:
            by_bucket["ROI %"] = np.where(by_bucket["Stake"] > 0, by_bucket["Profit_Loss"] / by_bucket["Stake"] * 100, 0)
        st.dataframe(by_bucket, use_container_width=True, hide_index=True)
    with tc2:
        by_ticket = tracker.groupby("Ticket Type", dropna=False).agg(
            Legs=("Team", "count"),
            Profit_Loss=("Profit/Loss", "sum"),
            Stake=("Stake", "sum"),
        ).reset_index()
        if not by_ticket.empty:
            by_ticket["ROI %"] = np.where(by_ticket["Stake"] > 0, by_ticket["Profit_Loss"] / by_ticket["Stake"] * 100, 0)
        st.dataframe(by_ticket, use_container_width=True, hide_index=True)

    st.markdown("#### Miss reason breakdown")
    miss = tracker[tracker["Miss Reason"].astype(str).str.len() > 0]
    if miss.empty:
        st.caption("No miss reasons logged yet.")
    else:
        st.dataframe(miss.groupby("Miss Reason").size().reset_index(name="Count"), use_container_width=True, hide_index=True)

def main():
    st.markdown("""
    <div class='hero'>
      <div class='hero-title'>⚾ MLB Moneyline Parlay Command Center <span style='font-size:.9rem;color:#31e56b;'>v16 lineup status + pregame filter</span></div>
      <div class='hero-sub'>Live odds, winner-first model scoring, three-bucket recommendations, diagnostics, and integrated bet tracking.</div>
    </div>
    """, unsafe_allow_html=True)

    today = datetime.now(EASTERN).date()
    with st.expander("⚙️ Dashboard controls", expanded=False):
        c1, c2, c3, c4 = st.columns([1,1,2,1])
        with c1:
            target_date = st.date_input("Slate date", today)
        with c2:
            regions = st.selectbox("Sportsbook region", ["us", "us2", "uk", "eu", "au"], index=0)
        with c3:
            bookmakers = st.text_input("Bookmakers filter", value="", placeholder="Leave blank to use all available books")
        with c4:
            model_mode = st.selectbox("Model strictness", ["Balanced", "Conservative", "Aggressive"], index=0)
        c5, c6, c7, c8 = st.columns([1,1,1,1])
        default_edge = 1.5 if model_mode == "Aggressive" else (2.0 if model_mode == "Balanced" else 3.0)
        with c5:
            min_edge = st.slider("Official suggested-leg min edge %", 1.0, 8.0, default_edge, 0.5)
        with c6:
            max_fav = st.slider("Max favorite price", -300, -120, -260, 5)
        with c7:
            max_dog = st.slider("Max underdog price", 100, 250, 200, 5)
        with c8:
            refresh = st.button("🔄 Refresh odds + model", type="primary", use_container_width=True)
        try:
            api_key = st.secrets.get("ODDS_API_KEY", "")
        except Exception:
            api_key = os.environ.get("ODDS_API_KEY", "")
        if not api_key:
            api_key = st.text_input("Odds API key", type="password")
        st.caption("If no odds appear, open the Diagnostics page below. v16 diagnostics show odds counts, live-excluded count, and fallback status.")
    if 'target_date' not in locals():
        target_date=today; regions='us'; bookmakers=''; model_mode='Balanced'; min_edge=2.0; max_fav=-260; max_dog=200; refresh=False
        try:
            api_key=st.secrets.get("ODDS_API_KEY", "")
        except Exception:
            api_key=os.environ.get("ODDS_API_KEY", "")
    if not api_key:
        st.warning("Add ODDS_API_KEY in Streamlit secrets or paste it in Dashboard controls.")
        st.stop()
    if refresh:
        fetch_odds.clear(); fetch_schedule.clear(); fetch_team_stats.clear(); fetch_pitcher_stats.clear(); fetch_weather.clear()
    with st.spinner("Loading live odds, slate, pitchers, stats, and weather..."):
        df, meta = build_board(target_date, api_key, regions, bookmakers)
    if df.empty:
        st.error("No slate or odds data loaded. Open Diagnostics for details.")
        st.json(meta)
        st.stop()

    eligible, qualified, full_ticket_qualified, best_available = _qualification(df, min_edge, max_fav, max_dog)
    tier_a = int((full_ticket_qualified["Tier"] == "A").sum()) if not full_ticket_qualified.empty else 0
    tier_bp = int((full_ticket_qualified["Tier"] == "B+").sum()) if not full_ticket_qualified.empty else 0
    qlegs = len(qualified)
    avg_edge = qualified["Edge %"].mean() if qlegs and "Edge %" in qualified else 0
    status, play_type = slate_status(qlegs, tier_a, tier_bp)
    if len(full_ticket_qualified) < 5 and not best_available.empty:
        if qlegs >= 3:
            status = "SMALLER CARD"; play_type = f"{min(qlegs,4)}-leg / singles"
        else:
            status = "WATCHLIST ONLY"; play_type = "No full card"
    grade = grade_from(qlegs, avg_edge)

    # Real working navigation. The buttons inside the custom image-like dashboard are labels only.
    page = st.radio("View", ["Command Center", "Full Slate", "Ticket Builder", "Bet Tracker", "Diagnostics", "Results / Export"], horizontal=True, label_visibility="collapsed")

    taken_tmp = set(best_available.head(5).index) if not best_available.empty else set()
    price_ok = (df["Odds"].notna()) & (df["Odds"] >= max_fav) & (df["Odds"] <= max_dog)
    boosters_tmp = df[price_ok & (~df.index.isin(taken_tmp))].sort_values(["Model Win %","Edge %","Score"], ascending=[False, False, False]).head(4)
    traps_tmp = df[((df["Odds"] < -120) & (df["Edge %"].fillna(-99) < 0.5)) | (df["Risk"].str.contains("Expensive", na=False))].sort_values(["Odds","Edge %"]).head(6)

    diag_line = f"Build mode: {meta.get('build_mode','?')} | Odds events: {meta.get('odds_events',0)} | Outcomes: {meta.get('odds_outcomes',0)} | Matched games: {meta.get('matched_games',0)}"
    st.caption(diag_line)

    if page == "Command Center":
        render_custom_command_center(df, meta, qualified, full_ticket_qualified, best_available, boosters_tmp, traps_tmp, target_date, qlegs, tier_a, tier_bp, play_type, status, grade)
        st.info("Navigation and refresh controls are the real Streamlit controls above. The dashboard header is a visual snapshot so it can match the mockup more closely.")
        st.markdown("### Three-Bucket Recommendation View")
        b1, b2, b3 = st.tabs(["Core Parlay Legs", "Suggested Winner-First", "Watchlist / Value Dogs"])
        with b1:
            if full_ticket_qualified.empty:
                st.warning("No Core Parlay legs. No official 5-leg ticket is supported right now.")
            else:
                st.dataframe(_display_cols(full_ticket_qualified, ["Team","Opponent","Odds","Book","Model Win %","Implied %","Edge %","Score","Tier","Risk"]), use_container_width=True, hide_index=True)
        with b2:
            if qualified.empty:
                st.info("No Suggested Winner-First legs right now.")
            else:
                st.dataframe(_display_cols(qualified, ["Team","Opponent","Odds","Book","Model Win %","Implied %","Edge %","Score","Tier","Risk"]), use_container_width=True, hide_index=True)
        with b3:
            watch_source = best_available.copy() if not best_available.empty else pd.DataFrame()
            if not qualified.empty and not watch_source.empty:
                watch_source = watch_source[~watch_source.index.isin(qualified.index)]
            if watch_source.empty:
                price_ok_watch = (df["Odds"].notna()) & (df["Odds"] >= max_fav) & (df["Odds"] <= max_dog)
                watch_source = df[price_ok_watch].sort_values(["Model Win %","Edge %","Score"], ascending=[False, False, False]).head(8)
            st.dataframe(_display_cols(watch_source, ["Team","Opponent","Odds","Book","Model Win %","Implied %","Edge %","Score","Tier","Risk"]), use_container_width=True, hide_index=True)
    elif page == "Full Slate":
        st.subheader("Full Slate Board")
        st.dataframe(_display_cols(df, ["Start","Game","Team","Opponent","Home/Away","Odds","Book","Market %","Model Win %","Implied %","Edge %","Score","Tier","Risk","Probable Pitcher","Notes"]), use_container_width=True, hide_index=True)
    elif page == "Ticket Builder":
        st.subheader("Bucket 1 — Core Parlay Legs")
        st.caption("Strictest list. These are the only legs that can support a serious 5-leg ticket. Requires stronger win probability, edge, score, and one side per game.")
        core_view = full_ticket_qualified if not full_ticket_qualified.empty else pd.DataFrame()
        if core_view.empty:
            st.warning("No Core Parlay legs right now. That means no official 5-leg ticket is supported.")
        else:
            st.dataframe(_display_cols(core_view, ["Team","Opponent","Odds","Book","Model Win %","Implied %","Edge %","Score","Tier","Risk","Probable Pitcher"]), use_container_width=True, hide_index=True)

        st.subheader("Bucket 2 — Suggested Winner-First Legs")
        st.caption("Usable for singles, 2-leg, 3-leg, or smaller-card testing. These prioritize teams the model thinks can actually win, then check the price.")
        if qualified.empty:
            st.info("No Suggested Winner-First legs right now.")
        else:
            st.dataframe(_display_cols(qualified, ["Team","Opponent","Odds","Book","Model Win %","Implied %","Edge %","Score","Tier","Risk","Probable Pitcher"]), use_container_width=True, hide_index=True)

        st.subheader("Bucket 3 — Watchlist / Value Dogs / Near Misses")
        st.caption("These are not official parlay legs. They may have value, be close to qualifying, or be useful for paper tracking only.")
        watch_source = best_available.copy() if not best_available.empty else pd.DataFrame()
        if not qualified.empty and not watch_source.empty:
            watch_source = watch_source[~watch_source.index.isin(qualified.index)]
        if watch_source.empty:
            price_ok_watch = (df["Odds"].notna()) & (df["Odds"] >= max_fav) & (df["Odds"] <= max_dog)
            watch_source = df[price_ok_watch].sort_values(["Model Win %","Edge %","Score"], ascending=[False, False, False]).head(8)
        st.dataframe(_display_cols(watch_source, ["Team","Opponent","Odds","Book","Model Win %","Implied %","Edge %","Score","Tier","Risk","Probable Pitcher"]), use_container_width=True, hide_index=True)

        st.subheader("Auto Ticket Builder")
        ticket_source = qualified if not qualified.empty else pd.DataFrame()
        if ticket_source.empty:
            st.warning("No official suggested legs available, so no system ticket should be built right now.")
        else:
            st.dataframe(recommended_tickets(ticket_source), use_container_width=True, hide_index=True)

        st.subheader("Optional Boosters")
        st.caption("Display only. These are not automatically approved parlay legs.")
        st.dataframe(_display_cols(boosters_tmp, ["Team","Opponent","Odds","Book","Model Win %","Edge %","Tier","Risk"]), use_container_width=True, hide_index=True)
    elif page == "Bet Tracker":
        render_bet_tracker(df, qualified, full_ticket_qualified, best_available, target_date)
    elif page == "Diagnostics":
        st.subheader("API Diagnostics")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Build mode", meta.get("build_mode","?"))
        c2.metric("Odds events", meta.get("odds_events",0))
        c3.metric("Odds outcomes", meta.get("odds_outcomes",0))
        c4.metric("Matched games", meta.get("matched_games",0))
        st.json(meta)
        if meta.get("errors"):
            st.code("\n".join(meta["errors"][:30]))
        st.subheader("Rows with missing odds")
        missing = df[df["Odds"].isna()] if "Odds" in df else pd.DataFrame()
        st.dataframe(_display_cols(missing, ["Game","Team","Opponent","Risk","Probable Pitcher"]), use_container_width=True, hide_index=True)
    else:
        st.subheader("Results / Export")
        st.download_button("Download today’s board CSV", data=df.to_csv(index=False), file_name=f"mlb_board_{target_date}.csv", mime="text/csv")
        st.download_button("Download suggested winner-first CSV", data=qualified.to_csv(index=False), file_name=f"suggested_legs_{target_date}.csv", mime="text/csv")
        try:
            tracker_export = load_tracker()
            st.download_button("Download full bet tracker CSV", data=tracker_export.to_csv(index=False), file_name="mlb_bet_tracker.csv", mime="text/csv")
        except Exception:
            pass
        try:
            tracker = pd.read_csv("results_tracker.csv")
            st.dataframe(tracker, use_container_width=True, hide_index=True)
        except Exception:
            st.info("No tracker file found yet.")


if __name__ == "__main__":
    main()
