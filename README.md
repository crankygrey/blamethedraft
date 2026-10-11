# Vote to Play

A lightweight Flask + Socket.IO Dota 2 peer-suggestion game. Visitors are automatically grouped into one shared game, suggest heroes for a target player, and then let that player choose.

## Features

- Automatically join one shared game
- One participant identity per browser profile, shared across tabs
- Editable player names, shared across tabs for the same browser
- Real-time lobby updates with Socket.IO
- Any participant can start a round once at least two players are connected
- The player who starts the round becomes its target
- Players who have already been a target cannot start another round until everyone has had a turn
- Suggestion phase for every non-target player
- Selection phase for the target player
- Search hero names while suggesting or choosing
- Dota 2 hero art served locally from the project asset folder

## Project structure

- `app.py` – Flask backend and Socket.IO logic
- `heroes_data.json` – hero metadata including local image paths
- `images/` – downloaded hero PNG assets
- `templates/` – shared game UI
- `requirements.txt` – Python dependencies

## Run locally

1. Create and activate a virtual environment if desired.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the app:

   ```bash
   python app.py
   ```

4. Open the app in a browser:

   ```text
   http://127.0.0.1:5000
   ```

## Notes

- The app stores game state in memory only; restarting the server clears active players and rounds.
- Browser identity uses a signed Flask session cookie. Clearing browser cookies or using a different browser profile creates another player identity; this is not an anti-cheat or security boundary.
- A disconnected browser keeps its player identity for 30 seconds, allowing refresh/reconnect without changing its player number.
- Set a strong `SECRET_KEY` environment variable in Render so Flask session cookies can be verified consistently.
- Since the game state is in memory, run a single server worker/instance for all players to share the same game.
- On Windows, `gevent` may require the Visual C++ build tools to compile if used in a production deployment setup.
- The app is designed for local testing and lightweight multiplayer room demos.
