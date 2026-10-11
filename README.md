# Vote to Play

A lightweight Flask + Socket.IO Dota 2 peer-suggestion game where players join a room, suggest heroes for a target player, and then vote on the best suggestion.

## Features

- Create or join a room with a short code
- Real-time lobby updates with Socket.IO
- Host-controlled round flow
- Suggestion phase for every non-target player
- Selection phase for the target player
- Dota 2 hero art served locally from the project asset folder

## Project structure

- `app.py` – Flask backend and Socket.IO logic
- `heroes_data.json` – hero metadata including local image paths
- `images/` – downloaded hero PNG assets
- `templates/` – landing page and room UI
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

- The app stores room state in memory only; restarting the server clears existing rooms.
- On Windows, `gevent` may require the Visual C++ build tools to compile if used in a production deployment setup.
- The app is designed for local testing and lightweight multiplayer room demos.
