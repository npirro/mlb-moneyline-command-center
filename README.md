# MLB Moneyline Command Center — v16 Lineup Status + Pregame Filter

This is the clean v16 package. It should show the visible marker:

**v16 lineup status + pregame filter**

## What v16 adds

- Pregame model excludes started/live games from recommendations.
- Started/live games are marked as excluded so live odds do not contaminate pregame cards.
- Projected/unconfirmed lineups are shown as gray/provisional.
- Lineup status is displayed in recommendation tables.
- Official recommendation logic remains winner-first with one side per game.
- Bet tracker remains included.

## Deploy

Upload the files in this ZIP directly to the same GitHub folder Streamlit deploys from. Replace the current files, commit changes, then reboot Streamlit.

Main file path: `app.py`

Secrets:

```toml
ODDS_API_KEY = "your_key_here"
```
