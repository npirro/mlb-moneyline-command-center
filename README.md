# MLB Moneyline Command Center v13 — Bet Tracker

Deploy this Streamlit app from GitHub. It includes the v12 three-bucket winner-first model plus an integrated Bet Tracker page.

## Setup
1. Upload these files to your GitHub repo.
2. In Streamlit Community Cloud, set the main file path to `app.py`.
3. Add this in Streamlit Secrets:

```toml
ODDS_API_KEY = "your_the_odds_api_key_here"
```

## v13 changes
- Adds a real **Bet Tracker** navigation page.
- Save Core, Suggested Winner-First, Watchlist, or manual full-board selections to tracker.
- Logs Ticket ID, date, bucket, ticket type, team, odds, model %, edge, score, tier, risk, stake, result, miss reason, read quality, and notes.
- Allows result editing and tracker CSV download.
- Adds performance summaries by bucket, ticket type, and miss reason.

## Usage
Open the app, refresh odds/model, then go to **Bet Tracker** and save whichever legs you are testing. After games finish, update Result and Miss Reason.
