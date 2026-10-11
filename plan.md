# Build Request: Dota 2 Peer-Suggestion Web App

I already have my data and assets set up in my project directory. Please use the following existing files and build the rest of the application:

## Existing Files in Project:
1. `heroes_data.json` - A JSON file containing A-Z sorted Dota 2 hero data, IDs, and local image paths (`images/<hero_key>.png`).
2. `images/` - A folder containing all the downloaded Dota 2 hero PNG icons.
3. `get_data.py` - The script used to fetch/update hero data.

## What I Need You To Create:
1. **`app.py`**: A Python Flask backend using **Flask-SocketIO** to handle real-time multiplayer rooms using an in-memory dictionary. It should support:
   - Creating a room with a short room code.
   - Joining a room with a username and room code.
   - Real-time player list updates.
   - A phase where players select 1 hero each to suggest for a target player.
   - A selection phase where the target player chooses between the suggested heroes.
2. **`requirements.txt`**: Include `flask`, `flask-socketio`, `gunicorn`, `gevent`, and `gevent-websocket`.
3. **`templates/index.html`**: A clean, lightweight landing page with Tailwind CSS (via CDN) to create or join a room.
4. **`templates/room.html`**: The active lobby and drafting screen that loads heroes dynamically from `heroes_data.json`, displays the hero icons from the local `/images` folder, handles real-time socket events, and manages the peer-suggestion and selection flow.
