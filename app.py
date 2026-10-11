import json
import os
import random
import string

from flask import Flask, redirect, render_template, request, send_from_directory, url_for
from flask_socketio import SocketIO, emit, join_room

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = "vote-to-play-secret"
socketio = SocketIO(app, cors_allowed_origins="*")

with open(os.path.join(BASE_DIR, "heroes_data.json"), "r", encoding="utf-8") as f:
    HEROES = json.load(f)

rooms = {}


def generate_room_code():
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))


def ensure_room_host(room):
    if not room.get("players"):
        return
    if room.get("host") not in room["players"]:
        room["host"] = next(iter(room["players"].keys()))


def room_snapshot(room, username=None):
    ensure_room_host(room)
    players = [
        {"username": player_name, "is_host": player_name == room["host"], "is_target": player_name == room["target_player"]}
        for player_name in room["players"].keys()
    ]
    return {
        "code": room["code"],
        "state": room["state"],
        "host": room["host"],
        "players": players,
        "target_player": room["target_player"],
        "suggestions": room["suggestions"],
        "selection_options": room["selection_options"],
        "message": room["message"],
        "winner": room.get("winner"),
        "my_username": username,
        "can_start": username == room["host"] and room["state"] == "lobby" and len(room["players"]) >= 2,
    }


def emit_room_state(room_code):
    room = rooms.get(room_code)
    if not room:
        return
    for username, player_data in room["players"].items():
        socketio.emit("room_state", room_snapshot(room, username), to=player_data["sid"])


def start_round(room):
    ensure_room_host(room)
    if len(room["players"]) < 2:
        room["state"] = "lobby"
        room["message"] = "Need at least 2 players to start a suggestion round."
        emit_room_state(room["code"])
        return

    players = list(room["players"].keys())
    if room.get("target_index") is None:
        room["target_index"] = 0

    target = players[room["target_index"] % len(players)]
    room["target_index"] = (room["target_index"] + 1) % len(players)
    room["state"] = "suggesting"
    room["target_player"] = target
    room["suggestions"] = {}
    room["selection_options"] = []
    room["winner"] = None
    room["message"] = f"{target} is the target player. Everyone else should suggest one hero."
    emit_room_state(room["code"])


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/room")
def room_page():
    room_code = request.args.get("room_code", "").strip().upper()
    username = request.args.get("username", "").strip()
    if not username:
        return redirect(url_for("index"))
    if not room_code:
        room_code = generate_room_code()
        return redirect(url_for("room_page", room_code=room_code, username=username))
    return render_template("room.html", room_code=room_code, username=username, heroes=HEROES)


@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(os.path.join(BASE_DIR, "images"), filename)


@socketio.on("join_room")
def handle_join_room(data):
    if not data:
        return

    room_code = (data.get("room_code") or "").strip().upper()
    username = (data.get("username") or "").strip()

    if not room_code or not username:
        emit("join_error", {"message": "Room code and username are required."})
        return

    room = rooms.get(room_code)
    if not room:
        room = {
            "code": room_code,
            "host": username,
            "players": {},
            "state": "lobby",
            "target_player": None,
            "suggestions": {},
            "selection_options": [],
            "message": "Lobby is open. Start a round when everyone is ready.",
            "target_index": 0,
        }
        rooms[room_code] = room

    username_map = {player_name.lower(): player_name for player_name in room["players"].keys()}
    if username.lower() in username_map:
        emit("join_error", {"message": "That username is already in the room."})
        return

    room["players"][username] = {"sid": request.sid}
    ensure_room_host(room)
    join_room(room_code)
    emit("join_success", {"room_code": room_code, "username": username}, to=request.sid)
    emit_room_state(room_code)


@socketio.on("start_round")
def handle_start_round(data):
    room_code = (data.get("room_code") or "").strip().upper()
    username = (data.get("username") or "").strip()
    room = rooms.get(room_code)

    if not room or username != room["host"]:
        return

    start_round(room)


@socketio.on("submit_suggestion")
def handle_submit_suggestion(data):
    room_code = (data.get("room_code") or "").strip().upper()
    username = (data.get("username") or "").strip()
    hero_key = (data.get("hero_key") or "").strip()
    room = rooms.get(room_code)

    if not room or room["state"] != "suggesting":
        return
    if username == room["target_player"] or username not in room["players"]:
        return
    if hero_key not in HEROES:
        return

    room["suggestions"][username] = hero_key
    room["message"] = f"{username} submitted a suggestion. Waiting for the remaining players."

    non_target_players = [player_name for player_name in room["players"].keys() if player_name != room["target_player"]]
    if len(room["suggestions"]) >= len(non_target_players):
        room["state"] = "choosing"
        room["selection_options"] = [
            {
                "username": submitter,
                "hero_key": hero_key,
                "hero_name": HEROES[hero_key]["localized_name"],
                "image_path": f"/images/{hero_key}.png",
            }
            for submitter, hero_key in room["suggestions"].items()
        ]
        room["message"] = f"{room['target_player']}, choose the hero you want to pick."
        emit("suggestions_ready", {"options": room["selection_options"]}, room=room_code)
    emit_room_state(room_code)


@socketio.on("choose_suggestion")
def handle_choose_suggestion(data):
    room_code = (data.get("room_code") or "").strip().upper()
    username = (data.get("username") or "").strip()
    hero_key = (data.get("hero_key") or "").strip()
    room = rooms.get(room_code)

    if not room or room["state"] != "choosing":
        return
    if username != room["target_player"]:
        return
    if hero_key not in {option["hero_key"] for option in room["selection_options"]}:
        return

    selected = next(option for option in room["selection_options"] if option["hero_key"] == hero_key)
    room["winner"] = {
        "hero_key": hero_key,
        "hero_name": HEROES[hero_key]["localized_name"],
        "image_path": f"/images/{hero_key}.png",
        "selected_by": username,
    }
    room["state"] = "complete"
    room["message"] = f"{username} picked {HEROES[hero_key]['localized_name']}!"
    emit("round_result", room["winner"], room=room_code)
    emit_room_state(room_code)


@socketio.on("disconnect")
def handle_disconnect():
    for room_code, room in list(rooms.items()):
        for username, player_data in list(room["players"].items()):
            if player_data["sid"] == request.sid:
                was_host = room["host"] == username
                del room["players"][username]
                if not room["players"]:
                    del rooms[room_code]
                    return

                if was_host:
                    room["host"] = next(iter(room["players"].keys()))
                else:
                    ensure_room_host(room)

                if room["target_player"] == username:
                    room["target_player"] = None
                emit_room_state(room_code)
                return


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
