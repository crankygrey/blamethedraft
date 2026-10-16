import json
import os
import random
import uuid

from flask import Flask, render_template, request, send_from_directory, session
from flask_socketio import SocketIO, emit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or uuid.uuid4().hex
socketio = SocketIO(app, cors_allowed_origins="*")

with open(os.path.join(BASE_DIR, "heroes_data.json"), "r", encoding="utf-8") as f:
    HEROES = json.load(f)

with open(
    os.path.join(BASE_DIR, "funny_dota_2_banter_quotes.json"),
    "r",
    encoding="utf-8",
) as f:
    BANTER_QUOTES = json.load(f)

SUGGESTIONS_PER_PLAYER = 2

game = {
    "players": {},
    "next_player_number": 1,
    "state": "lobby",
    "target_player": None,
    "target_history": set(),
    "suggestions": {},
    "banter_quote": None,
    "message": "The shared game is open. Start a round when at least two players are here.",
}
RECONNECT_GRACE_SECONDS = 30


def set_banter_quote(category):
    quotes = BANTER_QUOTES.get(category, [])
    if not quotes:
        raise ValueError(f"No banter quotes configured for category: {category}")

    previous_id = (game.get("banter_quote") or {}).get("id")
    candidates = [quote for quote in quotes if quote.get("id") != previous_id]
    game["banter_quote"] = random.choice(candidates or quotes)


def game_snapshot(player_id):
    players = [
        {
            "id": joined_player_id,
            "username": player["username"],
            "is_target": joined_player_id == game["target_player"],
            "is_connected": bool(player["sids"]),
        }
        for joined_player_id, player in game["players"].items()
    ]
    connected_players = sum(bool(player["sids"]) for player in game["players"].values())

    results = []
    if game["state"] == "complete":
        for suggester_id, hero_keys in game["suggestions"].items():
            suggester = game["players"].get(suggester_id)
            if suggester is None:
                continue
            results.append(
                {
                    "player_id": suggester_id,
                    "username": suggester["username"],
                    "heroes": [
                        {
                            "hero_key": hero_key,
                            "hero_name": HEROES[hero_key]["localized_name"],
                            "image_path": f"/images/{hero_key}.png",
                        }
                        for hero_key in hero_keys
                    ],
                }
            )

    target = game["players"].get(game["target_player"])

    return {
        "state": game["state"],
        "players": players,
        "target_player": game["target_player"],
        "target_name": target["username"] if target else None,
        "suggestions": game["suggestions"],
        "suggestions_per_player": SUGGESTIONS_PER_PLAYER,
        "results": results,
        "banter_quote": game["banter_quote"],
        "message": game["message"],
        "my_player_id": player_id,
        "can_start": (
            connected_players >= 2
            and game["state"] in ("lobby", "complete")
            and player_id not in game["target_history"]
        ),
    }


def emit_game_state():
    for player_id, player in game["players"].items():
        for sid in tuple(player["sids"]):
            socketio.emit("game_state", game_snapshot(player_id), to=sid)


def complete_round_if_ready():
    non_target_players = [
        player_id
        for player_id, player in game["players"].items()
        if player["sids"]
        if player_id != game["target_player"]
    ]
    if not non_target_players or not all(
        player_id in game["suggestions"] for player_id in non_target_players
    ):
        return

    game["state"] = "complete"
    set_banter_quote("hero_locked_in")
    target_name = game["players"][game["target_player"]]["username"]
    total_heroes = sum(len(hero_keys) for hero_keys in game["suggestions"].values())
    game["message"] = (
        f"All suggestions are in: {total_heroes} heroes for {target_name}. "
        f"{target_name} picks one in the Dota client."
    )

    active_players = {
        active_player_id
        for active_player_id, player in game["players"].items()
        if player["sids"]
    }
    if active_players.issubset(game["target_history"]):
        game["target_history"].clear()


def start_round(player_id):
    players = [
        active_player_id
        for active_player_id, player in game["players"].items()
        if player["sids"]
    ]
    if len(players) < 2:
        game["message"] = "At least two browsers must be here to start a round."
        emit_game_state()
        return

    if player_id not in players or player_id in game["target_history"]:
        return

    target = player_id
    game["target_history"].add(target)
    game["state"] = "suggesting"
    game["target_player"] = target
    game["suggestions"] = {}
    set_banter_quote("troll_suggestions")
    target_name = game["players"][target]["username"]
    game["message"] = (
        f"{target_name} started the round and is the target. "
        f"Everyone else should suggest {SUGGESTIONS_PER_PLAYER} heroes."
    )
    emit_game_state()


@app.route("/")
def index():
    player_id = session.setdefault("player_id", uuid.uuid4().hex)
    return render_template("room.html", player_id=player_id, heroes=HEROES)


@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(os.path.join(BASE_DIR, "images"), filename)


@app.route("/assets/logo.png")
@app.route("/assets/jug-drinks-your-tears.png")
def serve_brand_asset():
    filename = request.path.rsplit("/", 1)[-1]
    return send_from_directory(BASE_DIR, filename)


@socketio.on("join_game")
def handle_join_game():
    player_id = session.get("player_id")
    if not player_id:
        emit("join_error", {"message": "Player identity missing. Refresh the page to reconnect."})
        return

    player = game["players"].get(player_id)
    if player is None:
        player = {
            "username": f"Player {game['next_player_number']}",
            "sids": set(),
            "disconnect_token": None,
        }
        game["next_player_number"] += 1
        game["players"][player_id] = player

    player["disconnect_token"] = None
    player["sids"].add(request.sid)
    emit("join_success", {"username": player["username"]}, to=request.sid)
    emit_game_state()


@socketio.on("rename_player")
def handle_rename_player(data):
    player_id = session.get("player_id")
    player = game["players"].get(player_id)
    if player is None or request.sid not in player["sids"]:
        emit("rename_error", {"message": "Reconnect before changing your name."})
        return

    username = (data or {}).get("username", "").strip()
    if not username:
        emit("rename_error", {"message": "Enter a name before saving."})
        return
    if len(username) > 20:
        emit("rename_error", {"message": "Names must be 20 characters or fewer."})
        return
    if any(
        other_id != player_id
        and other["username"].casefold() == username.casefold()
        for other_id, other in game["players"].items()
    ):
        emit("rename_error", {"message": "That name is already being used."})
        return

    previous_name = player["username"]
    player["username"] = username
    game["message"] = f"{previous_name} changed their name to {username}."
    emit_game_state()
    for sid in tuple(player["sids"]):
        socketio.emit("rename_success", {"username": username}, to=sid)


@socketio.on("start_round")
def handle_start_round():
    player_id = session.get("player_id")
    if (
        player_id not in game["players"]
        or not game["players"][player_id]["sids"]
        or player_id in game["target_history"]
        or game["state"] not in ("lobby", "complete")
    ):
        return
    start_round(player_id)


@socketio.on("submit_suggestions")
def handle_submit_suggestions(data):
    player_id = session.get("player_id")
    hero_keys = (data or {}).get("hero_keys") or []

    if game["state"] != "suggesting":
        return
    if player_id == game["target_player"] or player_id not in game["players"]:
        return
    if player_id in game["suggestions"]:
        return
    if not isinstance(hero_keys, list) or len(hero_keys) != SUGGESTIONS_PER_PLAYER:
        return
    if len(set(hero_keys)) != SUGGESTIONS_PER_PLAYER:
        return
    if any(hero_key not in HEROES for hero_key in hero_keys):
        return

    game["suggestions"][player_id] = list(hero_keys)
    set_banter_quote("troll_suggestions")
    game["message"] = (
        f"{game['players'][player_id]['username']} sent {SUGGESTIONS_PER_PLAYER} hero suggestions. "
        "Waiting for the remaining players."
    )
    complete_round_if_ready()
    emit_game_state()


@socketio.on("disconnect")
def handle_disconnect():
    for player_id, player in list(game["players"].items()):
        if request.sid not in player["sids"]:
            continue

        player["sids"].remove(request.sid)
        if player["sids"]:
            return

        disconnect_token = uuid.uuid4().hex
        player["disconnect_token"] = disconnect_token
        emit_game_state()
        socketio.start_background_task(
            expire_disconnected_player,
            player_id,
            disconnect_token,
        )
        return


def expire_disconnected_player(player_id, disconnect_token):
    socketio.sleep(RECONNECT_GRACE_SECONDS)
    player = game["players"].get(player_id)
    if (
        player is None
        or player["sids"]
        or player["disconnect_token"] != disconnect_token
    ):
        return

    del game["players"][player_id]
    game["suggestions"].pop(player_id, None)
    game["target_history"].discard(player_id)

    if game["target_player"] == player_id and game["state"] == "suggesting":
        game["state"] = "lobby"
        game["target_player"] = None
        game["suggestions"] = {}
        game["message"] = "The target player left. Start a new round when ready."
    elif game["state"] == "suggesting" and sum(
        bool(player["sids"]) for player in game["players"].values()
    ) < 2:
        game["state"] = "lobby"
        game["target_player"] = None
        game["suggestions"] = {}
        game["message"] = "At least two browsers must be here to continue. Start a new round when ready."
    elif game["state"] == "suggesting":
        complete_round_if_ready()

    emit_game_state()


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
