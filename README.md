# MLB Moneyline Parlay Command Center

A hosted Streamlit dashboard for MLB moneyline parlay decision-making.

## What it does

- Pulls live/upcoming MLB moneyline odds from The Odds API
- Pulls today's MLB schedule and probable pitchers from MLB Stats API
- Pulls team hitting/pitching stats from MLB Stats API
- Pulls stadium weather from Open-Meteo
- Scores each team automatically
- Identifies qualified legs, optional booster legs, and trap favorites
- Builds 1-leg through 6-leg ticket options
- Exports full board and qualified legs to CSV
- Includes a results tracker CSV structure

## Important model note

This is an automated decision-support dashboard, not a guaranteed prediction engine.
It uses free/public data sources. Confirmed lineups and true bullpen availability are not included in this version because those usually require more reliable paid feeds or fragile scraping.

The dashboard includes warnings for missing pitchers, missing odds, started games, weather risk, expensive favorites, and price shopping.

## Files

- `app.py` — Streamlit dashboard
- `requirements.txt` — Python package dependencies
- `park_data.csv` — stadium coordinates and park-factor estimates
- `results_tracker.csv` — CSV structure for tracking outcomes
- `.streamlit/secrets.toml.example` — example API key storage

## Deployment: Streamlit Community Cloud

1. Unzip this folder.
2. Create a new GitHub repository, for example: `mlb-command-center`.
3. Upload all files from this folder into the repo.
4. Go to Streamlit Community Cloud.
5. Click **New app**.
6. Select your GitHub repo.
7. Set **Main file path** to:

```bash
app.py
```

8. Before deploying or immediately after deploying, open the app settings and add this in **Secrets**:

```toml
ODDS_API_KEY = "your_actual_the_odds_api_key_here"
```

9. Deploy the app.
10. Open the URL and click **Refresh odds + model**.

## Local run

```bash
pip install -r requirements.txt
streamlit run app.py
```

For local development, create a file at `.streamlit/secrets.toml` with:

```toml
ODDS_API_KEY = "your_actual_the_odds_api_key_here"
```

## The Odds API settings

The app uses:

- sport key: `baseball_mlb`
- market: `h2h`
- odds format: American
- default region: `us`

You can optionally filter books in the sidebar with comma-separated keys, such as:

```text
fanduel,draftkings,betmgm
```

Leave the filter blank to use all available books in the selected region.

## Dashboard rules

The dashboard does not force a 5-leg ticket.

- 0 qualified legs: no play
- 1 qualified leg: single only
- 2 qualified legs: singles or tiny 2-leg
- 3 qualified legs: smaller 3-leg supported
- 4 qualified legs: 3–4 leg card supported
- 5 qualified legs: main 5-leg ticket
- 6+ qualified legs: main 5-leg + optional 6th booster

## Suggested daily workflow

1. Open the dashboard.
2. Click **Refresh odds + model**.
3. Check **Slate Status**.
4. Review **Main Recommended Ticket** or **Core Legs**.
5. Check **Optional Booster Legs** only if you want a bigger payout.
6. Check **Trap Favorites / Do Not Use** before adding anything manually.
7. Refresh closer to first pitch.
8. Export the board and track results.

## Upgrade path

Most valuable paid/feed upgrades later:

1. Confirmed lineups
2. True bullpen usage by reliever over last 3 days
3. Injuries/transactions
4. Faster odds movements / opening-vs-current line
5. Historical backtesting database

