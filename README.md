# MLB Moneyline Parlay Command Center v5

This version fixes two issues from v4:

1. **Visual layout**: the main Command Center is now rendered as a custom HTML/CSS dashboard inside Streamlit, so it looks much closer to the original dark mockup instead of normal Streamlit cards and white tables.
2. **Odds matching**: team matching is normalized, and the app retries The Odds API without a bookmaker filter if the selected books return zero odds. This should fix the issue where every team showed `Odds: None`.

## Files

- `app.py` — Streamlit app
- `requirements.txt` — Python dependencies
- `park_data.csv` — stadium coordinates/park factors
- `results_tracker.csv` — results tracker template

## Deploy update

Upload these files into the same GitHub repo location as your current `app.py` and commit changes. Then reboot the Streamlit app.

You do not need to redo your Streamlit secrets. Keep:

```toml
ODDS_API_KEY = "your_key_here"
```

## First thing to check after deploy

Open the app and expand **Advanced views → API Diagnostics** only if the dashboard still has no odds.

Look for:

- `odds_events`
- `odds_outcomes`
- `matched_games`

If `odds_outcomes` is 0, The Odds API is not returning odds for your API key/date/region.
If `odds_outcomes` is positive but `matched_games` is 0, team matching is the issue.
