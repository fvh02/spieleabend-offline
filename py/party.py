"""Shared rules for the party games (Schätzmeister, Wer würde eher, Lügenbaron, Punchline).

Everyone answers on the phone, then the round is revealed. One device can become the "Host" screen
(e.g. a TV): it does not play, it only shows the question, who has answered and the results.
Players who leave become placeholders that answer nothing, so a round never waits for them.
"""

import secrets
import time

from common import RuleError


class Player:
    def __init__(self, name: str, is_bot: bool = False):
        self.id = secrets.token_hex(4)
        self.name = name
        self.is_bot = is_bot
        self.screen = False
        self.score = 0
        self.gained = 0
        self.answer = None   # what this player entered in the current input phase
        self.pick = None     # what this player chose in a vote/pick phase


class PartyGame:
    KIND = ""
    NO_BOTS = True
    MIN_PLAYERS, MAX_PLAYERS = 3, 16
    ROUNDS = (8, 5, 10, 12)            # first one is the default
    TIMES = (60, 45, 90, 0)            # seconds per input phase, 0 = no limit
    INPUT_PHASES: tuple[str, ...] = ()  # phases in which everyone has to answer

    def __init__(self, code: str):
        self.code = code
        self.players: list[Player] = []
        self.host_id: str | None = None
        self.state = "lobby"     # lobby | playing | finished
        self.phase = ""
        self.round = 0
        self.rounds = self.ROUNDS[0]
        self.seconds = self.TIMES[0]
        self.phase_end = 0.0
        self.used: set = set()
        self.log: list[str] = []

    # -- shared interface ----------------------------------------------------
    def new_player(self, name: str, is_bot: bool = False) -> Player:
        return Player(name, is_bot)

    def player(self, player_id):
        return next((p for p in self.players if p.id == player_id), None)

    def note(self, text: str) -> None:
        self.log.append(text)
        del self.log[:-30]

    @property
    def screen(self):
        return next((p for p in self.players if p.screen), None)

    @property
    def gamers(self) -> list[Player]:
        """Everyone who plays (not the Host screen)."""
        return [p for p in self.players if not p.screen]

    def configure(self, settings: dict) -> None:
        rounds = settings.get("rounds")
        self.rounds = int(rounds) if rounds is not None and int(rounds) in self.ROUNDS else self.ROUNDS[0]
        seconds = settings.get("seconds")
        self.seconds = int(seconds) if seconds is not None and int(seconds) in self.TIMES else self.TIMES[0]
        self.configure_more(settings)

    def configure_more(self, settings: dict) -> None:
        pass

    def settings_view(self) -> dict:
        return {"rounds": self.rounds, "seconds": self.seconds}

    def add_player(self, player: Player) -> None:
        if player.is_bot:
            raise RuleError("In diesem Spiel gibt es keine Computer-Spieler")
        if self.state != "lobby":
            raise RuleError("Das Spiel läuft bereits")
        if len(self.players) >= self.MAX_PLAYERS + 1:  # + the Host screen
            raise RuleError(f"Maximal {self.MAX_PLAYERS} Spieler")
        self.players.append(player)
        if self.host_id is None:
            self.host_id = player.id

    def remove_player(self, player_id: str) -> None:
        player = self.player(player_id)
        if player:
            self.players.remove(player)
        if self.host_id == player_id:
            self.host_id = next((p.id for p in self.players if not p.is_bot), None)

    def start(self) -> None:
        if len(self.gamers) < self.MIN_PLAYERS:
            raise RuleError(f"Mindestens {self.MIN_PLAYERS} Spieler nötig (der Host-Bildschirm zählt nicht)")
        if len(self.gamers) > self.MAX_PLAYERS:
            raise RuleError(f"Maximal {self.MAX_PLAYERS} Spieler")
        for p in self.players:
            p.score = 0
        self.round = 0
        self.used = set()
        self.log = []
        self.state = "playing"
        self.next_round()

    # -- rounds --------------------------------------------------------------
    def next_round(self) -> None:
        self.round += 1
        for p in self.players:
            p.answer = p.pick = None
            p.gained = 0
        self.setup_round()

    def setup_round(self) -> None:
        raise NotImplementedError

    def begin(self, phase: str, timed: bool = True) -> None:
        self.phase = phase
        self.phase_end = time.time() + self.seconds if timed and self.seconds else 0.0

    @property
    def deadline(self) -> float | None:
        return self.phase_end if self.state == "playing" and self.phase_end else None

    def on_deadline(self) -> None:
        if self.state == "playing" and self.phase in self.INPUT_PHASES:
            self.advance()

    def advance(self) -> None:
        """The current input phase is over (everyone answered, time is up or the host skipped)."""
        raise NotImplementedError

    def done(self, attr: str) -> bool:
        return all(getattr(p, attr) is not None for p in self.gamers)

    def finish(self) -> None:
        self.state = "finished"
        self.phase_end = 0.0
        best = max(self.gamers, key=lambda p: p.score, default=None)
        if best and best.score:
            self.note(f"🏆 {best.name} gewinnt mit {best.score} Punkten")

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool) -> None:
        kind = msg.get("t")
        player = self.player(player_id)
        if not player:
            raise RuleError("Gerade nicht möglich")
        if kind == "screen":
            if self.state != "lobby":
                raise RuleError("Der Host-Bildschirm wird vor dem Start gewählt")
            current = self.screen
            if current and current is not player:
                raise RuleError(f"{current.name} ist schon Host")
            player.screen = not player.screen
            return
        if self.state != "playing":
            raise RuleError("Gerade nicht möglich")
        if kind == "next":
            if not is_host:
                raise RuleError("Nur der Gastgeber geht weiter")
            if self.phase != "reveal":
                raise RuleError("Die Runde läuft noch")
            if self.round >= self.rounds:
                self.finish()
            else:
                self.next_round()
            return
        if kind == "skip":
            if not is_host:
                raise RuleError("Nur der Gastgeber kann das")
            if self.phase not in self.INPUT_PHASES:
                raise RuleError("Gerade nicht möglich")
            self.advance()
            return
        if kind == "end_game":
            if not is_host:
                raise RuleError("Nur der Gastgeber kann das Spiel beenden")
            self.finish()
            return
        if player.screen:
            raise RuleError("Der Host-Bildschirm zeigt nur an")
        if self.phase not in self.INPUT_PHASES:
            raise RuleError("Gerade nicht möglich")
        self.play(player, msg)

    def play(self, player: Player, msg: dict) -> None:
        raise NotImplementedError

    # -- players who left: they answer nothing, so nobody waits for them ------
    def pending_bots(self) -> list:
        if self.state != "playing" or self.phase not in self.INPUT_PHASES:
            return []
        attr = self.phase_attr()
        return [p for p in self.gamers if p.is_bot and getattr(p, attr) is None]

    def phase_attr(self) -> str:
        return "answer"

    def bot_step(self, bot: Player) -> None:
        setattr(bot, self.phase_attr(), "")
        if self.done(self.phase_attr()):
            self.advance()

    # -- view ----------------------------------------------------------------
    def view_for(self, viewer_id) -> dict:
        me = self.player(viewer_id)
        attr = self.phase_attr() if self.phase in self.INPUT_PHASES else None
        view = {
            "kind": self.KIND, "code": self.code, "state": self.state, "phase": self.phase,
            "host": self.host_id, "settings": self.settings_view(), "round": self.round, "rounds": self.rounds,
            "screen": self.screen.id if self.screen else None,
            "players": [{"id": p.id, "name": p.name, "bot": p.is_bot, "screen": p.screen, "score": p.score, "gained": p.gained,
                         "done": bool(attr) and getattr(p, attr) is not None} for p in self.players],
            "remaining": max(0, round(self.phase_end - time.time(), 1)) if self.deadline else None,
            "seconds": self.seconds,
            "log": self.log[-6:],
        }
        view.update(self.extra_view(me))
        return view

    def extra_view(self, me: Player | None) -> dict:
        return {}


def normalize(text: str) -> str:
    """For comparing answers: lower case, no punctuation, single spaces."""
    keep = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return " ".join(keep.split())


def clean(text, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]
