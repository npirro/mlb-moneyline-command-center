# MLB Moneyline Command Center v10 — Winner-First Parlay Mode

This version changes the recommendation engine from edge-first to winner-first.

## What changed

- Official parlay legs require 54%+ model win probability.
- Official parlay legs still require positive edge versus the book.
- A team with edge but low win probability is moved to watchlist/value-dog context, not the main parlay list.
- Only one team per game can appear in official suggested legs.
- If both sides of a game are too close, the app skips that matchup for official recommendations.
- Full 5-leg tickets are stricter than smaller-card suggestions.

## Deploy

Upload these files to your existing GitHub repo, replacing the current app files:

- app.py
- requirements.txt
- park_data.csv
- results_tracker.csv
- README.md

Then commit changes and reboot the Streamlit app.

Keep your Streamlit secret as:

ODDS_API_KEY = "your_key_here"

## Rule interpretation

- Suggested Legs = parlay-eligible winner-first legs.
- Best Available / Watchlist = teams worth watching, not official parlay legs.
- Value dogs may have edge, but they are not parlay legs unless they also pass winner-first rules.
