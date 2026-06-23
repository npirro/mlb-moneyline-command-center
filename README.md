# MLB Moneyline Command Center v11

v11 changes the recommendation engine from pure edge-first to practical winner-first:

- Suggested legs require 52%+ model win probability, positive value, and a reasonable score.
- Core/full-ticket legs stay stricter: 54%+ win probability, stronger edge, 70+ score.
- Value dogs are separated into watchlist/singles-only.
- Only one team per game can appear in suggested legs.
- If both sides of a game are too close, the app skips the game.

Deploy by replacing your existing GitHub repo files with these files, committing changes, then rebooting Streamlit.
