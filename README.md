# MLB Moneyline Parlay Command Center v7

v7 fixes the biggest functional issue from v6: it builds the betting board from The Odds API first, then enriches with MLB schedule/probable pitchers when matching is available. This prevents the app from showing every leg with `Odds: None` when schedule matching fails.

## Deploy update
1. Unzip this package.
2. Upload these files to the same GitHub repo location as your current `app.py`.
3. Replace the existing files.
4. Commit changes.
5. Reboot the Streamlit app.

## Important
Leave the Bookmakers filter blank at first. This uses all available US books and avoids filtering out odds that your API key/plan may not return.

Secrets:
```toml
ODDS_API_KEY = "your_key_here"
```
