# MLB Moneyline Command Center — v18 Label Cleanup

This is the clean v18 package. It should show the visible marker:

**v18 label cleanup**

## What v18 fixes

- Renames **Trap Favorites / Do Not Use** to **Overpriced / No-Edge Favorites**.
- Keeps the model logic unchanged from v17.
- Keeps no-play/watchlist display cleanup from v17.
- Keeps pregame-only filtering and gray/provisional lineup warnings.
- Keeps the bet tracker included.

## Deploy

Upload these files directly to the same GitHub folder Streamlit deploys from. Replace the current files, commit changes, then reboot Streamlit.

Main file path: `app.py`

Secrets:

```toml
ODDS_API_KEY = "your_key_here"
```
