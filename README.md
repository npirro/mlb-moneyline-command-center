# MLB Moneyline Command Center — v17 No-Play Display Cleanup

This is the clean v17 package. It should show the visible marker:

**v17 no-play display cleanup**

## What v17 fixes

- If there are 0 official suggested legs, the main card now says **No Suggested Legs — Watchlist Only**.
- Thin Edge / No Bet rows are shown only as watchlist context, not as official recommendations.
- Estimated hit percentage and ticket odds are based on official legs, not best-available context rows.
- Pregame model still excludes started/live games from recommendations.
- Projected/unconfirmed lineups remain gray/provisional.
- Bet tracker remains included.

## Deploy

Upload the files in this ZIP directly to the same GitHub folder Streamlit deploys from. Replace the current files, commit changes, then reboot Streamlit.

Main file path: `app.py`

Secrets:

```toml
ODDS_API_KEY = "your_key_here"
```
