"""Offline hub: runs on the host's phone (in Pyodide) instead of the Spieleabend server.

One evening = one group of devices (the host plus everyone who scanned the host's code). The host
picks a game; everyone is seated in that game automatically. The browser pages of the games are the
same as on the server: they think they talk to a WebSocket, the shell relays their messages here.

JS calls:   connect(token, kind) · disconnect(token) · handle(token, json) · tick() · set_device(...)
Python returns a JSON list of outgoing messages: [[token, message], …]
"""

import json
import random
import time

from common import RuleError
import farbrausch
import galgenraten
import imposter
import kritzelpost
import luegenbaron
import nochnie
import pferderennen
import punchline
import pyramide
import ringoffire
import schaetzmeister
import schnellmaler
import stapeljagd
import tiefpunkt
import trinklotto
import wahrheit
import werwuerde

GAMES = {"stapeljagd": stapeljagd, "tiefpunkt": tiefpunkt, "kritzelpost": kritzelpost, "farbrausch": farbrausch,
         "schnellmaler": schnellmaler, "galgenraten": galgenraten, "imposter": imposter,
         "schaetzmeister": schaetzmeister, "werwuerde": werwuerde, "luegenbaron": luegenbaron, "punchline": punchline,
         "nochnie": nochnie, "wahrheit": wahrheit, "ringoffire": ringoffire, "trinklotto": trinklotto,
         "pyramide": pyramide, "pferderennen": pferderennen}
BOT_DELAY = 0.9
BOT_NAMES = ["Robo", "Karla", "Bitty", "Otto", "Zora", "Pixel", "Toni", "Mops"]


class Hub:
    def __init__(self) -> None:
        self.devices: dict[str, str] = {}       # token -> name, in the order they joined (host first)
        self.host: str | None = None
        self.kind: str | None = None
        self.game = None
        self.seats: dict[str, str] = {}         # token -> player id in the current game
        self.open: set[str] = set()             # tokens whose game page is connected
        self.out: list = []
        self.bot_due = 0.0
        self.deadline_seen = None

    # -- devices -------------------------------------------------------------
    def set_device(self, token: str, name: str, host: bool = False) -> None:
        self.devices[token] = str(name)[:20] or "Gast"
        if host:
            self.host = token
        # Someone (re)joins a running evening: give them a seat if the game has not started.
        if self.game and token not in self.seats and self.game.state == "lobby":
            self.seat(token)
            self.broadcast()

    def remove_device(self, token: str) -> None:
        self.devices.pop(token, None)
        self.leave(token)
        self.broadcast()

    def seat(self, token: str) -> None:
        player = self.game.new_player(self.devices.get(token, "Gast"))
        self.game.add_player(player)
        self.seats[token] = player.id
        if token == self.host:
            self.game.host_id = player.id

    # -- choosing a game -----------------------------------------------------
    def start_game(self, kind: str) -> str:
        if kind not in GAMES:
            raise RuleError("Unbekanntes Spiel")
        self.kind = kind
        self.game = GAMES[kind].Game("OFFL")
        self.game.configure({})
        self.seats = {}
        self.open = set()          # the pages of the previous game are gone
        for token in [self.host] + [t for t in self.devices if t != self.host]:
            if token in self.devices:
                try:
                    self.seat(token)
                except RuleError:
                    pass  # more devices than the game allows: they watch
        self.broadcast()
        return json.dumps(self.flush())

    def end_game(self) -> str:
        self.kind, self.game, self.seats, self.open = None, None, {}, set()
        return json.dumps(self.flush())

    # -- sending -------------------------------------------------------------
    def view(self, token: str) -> None:
        if token not in self.open:
            return
        pid = self.seats.get(token)
        if self.game and pid and self.game.player(pid):
            self.out.append([token, {"t": "game", "me": pid, "game": self.game.view_for(pid)}])
        else:
            self.out.append([token, {"t": "spectate", "kind": self.kind}])

    def broadcast(self) -> None:
        for token in list(self.open):
            self.view(token)

    def flush(self) -> list:
        out, self.out = self.out, []
        return out

    def flush_json(self) -> str:
        return json.dumps(self.flush())

    # -- page connections ----------------------------------------------------
    def connect(self, token: str, kind: str) -> str:
        if kind != self.kind:
            self.out.append([token, {"t": "spectate", "kind": self.kind}])
            return json.dumps(self.flush())
        self.open.add(token)
        self.out.append([token, {"t": "hello", "token": token}])
        pid = self.seats.get(token)
        player = self.game.player(pid) if self.game and pid else None
        if player and player.is_bot and player.name.endswith(" (Bot)"):
            # Back after a lost connection: take the seat over from the computer player again.
            player.is_bot = False
            player.name = player.name[:-6]
            self.game.note(f"{player.name} ist wieder da")
            self.broadcast()
        else:
            self.view(token)
        return json.dumps(self.flush())

    def disconnect(self, token: str) -> str:
        self.open.discard(token)
        return json.dumps(self.flush())

    def leave(self, token: str) -> None:
        pid = self.seats.get(token)
        game = self.game
        player = game.player(pid) if game and pid else None
        if not player:
            return
        if game.state == "playing":
            player.is_bot = True
            player.name += " (Bot)"
            game.note(f"{player.name} spielt jetzt für den Spieler weiter")
            if game.host_id == pid:
                game.host_id = next((p.id for p in game.players if not p.is_bot), None)
        else:
            game.remove_player(pid)
            self.seats.pop(token, None)

    def drop(self, token: str) -> str:
        """The device lost its connection: a computer player keeps its seat warm."""
        self.open.discard(token)
        self.leave(token)
        self.broadcast()
        return json.dumps(self.flush())

    # -- messages from the game pages ----------------------------------------
    def handle(self, token: str, raw: str) -> str:
        try:
            msg = json.loads(raw)
        except ValueError:
            return "[]"
        if "token" in msg and len(msg) == 1:
            return "[]"  # the page's greeting; the connection is already known
        try:
            self._handle(token, msg)
        except RuleError as err:
            self.out.append([token, {"t": "error", "msg": str(err)}])
        except (TypeError, ValueError, KeyError):
            self.out.append([token, {"t": "error", "msg": "Ungültige Eingabe"}])
        return json.dumps(self.flush())

    def _handle(self, token: str, msg: dict) -> None:
        game, kind = self.game, msg.get("t")
        if not game:
            raise RuleError("Gerade läuft kein Spiel")
        me = self.seats.get(token)
        if not me:
            raise RuleError("Du schaust bei diesem Spiel nur zu")
        is_host = game.host_id == me
        if kind == "add_bot":
            if not is_host:
                raise RuleError("Nur der Gastgeber kann Computer-Spieler hinzufügen")
            if getattr(game, "NO_BOTS", False):
                raise RuleError("In diesem Spiel gibt es keine Computer-Spieler")
            used = {p.name for p in game.players}
            game.add_player(game.new_player(next((n for n in BOT_NAMES if n not in used), f"Bot {len(game.players) + 1}"), is_bot=True))
        elif kind == "kick":
            if not is_host or game.state != "lobby":
                raise RuleError("Nur der Gastgeber kann vor dem Start Spieler entfernen")
            target = game.player(str(msg.get("id")))
            if target and target.id != me:
                for t, pid in list(self.seats.items()):
                    if pid == target.id:
                        self.seats.pop(t)
                game.remove_player(target.id)
        elif kind == "settings":
            if not is_host or game.state != "lobby":
                raise RuleError("Nur der Gastgeber kann das ändern")
            game.configure(msg.get("settings") or {})
        elif kind in ("start", "rematch"):
            if not is_host:
                raise RuleError("Nur der Gastgeber kann das Spiel starten")
            if kind == "rematch" and game.state != "finished":
                raise RuleError("Das Spiel läuft noch")
            game.start()
        elif kind == "leave":
            self.leave(token)  # the shell shows the game list; coming back takes the seat again
        elif kind in ("create", "join", "lobby"):
            return
        else:
            live = game.act(me, msg, is_host)
            if live is not None:
                for t in self.open:
                    if t in self.seats:
                        self.out.append([t, live])
                return
        self.broadcast()

    # -- time: computer players and deadlines ----------------------------------
    def tick(self) -> str:
        game = self.game
        if not game:
            return "[]"
        now = time.time()
        changed = False
        deadline = getattr(game, "deadline", None)
        if deadline is not None and now >= deadline:
            game.on_deadline()
            changed = True
        bots = game.pending_bots() if game.state == "playing" else []
        if bots:
            if not self.bot_due:
                self.bot_due = now + BOT_DELAY
            elif now >= self.bot_due:
                self.bot_due = 0.0
                try:
                    game.bot_step(bots[0])
                except RuleError:
                    pass
                changed = True
        else:
            self.bot_due = 0.0
        if changed:
            self.broadcast()
        return json.dumps(self.flush())


hub = Hub()
random.seed()
