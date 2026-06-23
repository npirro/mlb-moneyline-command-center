# MLB Moneyline Command Center v6

## Fixes in v6
- Adds real working navigation with Streamlit controls: Command Center, Full Slate, Ticket Builder, Diagnostics, Results / Export.
- Keeps the mockup-style dashboard as a visual Command Center snapshot.
- Adds visible diagnostics instead of hiding them in an expander.
- Adds odds-first fallback mode. If MLB schedule/team matching fails, the app builds the board directly from The Odds API events so odds do not show as `None`.
- Adds a visible v6 marker in the header.

## Deploy
Replace the old files in your GitHub repo with these files, commit changes, then reboot the Streamlit app.

Required Streamlit secret:
```toml
ODDS_API_KEY = "your_key_here"
```
