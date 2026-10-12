"""Imposter: everyone gets the same secret word – except the imposter. Find them! (rules, no networking)

The phones hand out the roles, pick who starts and run the vote; the hints themselves are said out loud."""

import random
import secrets
import time

import wortschatz
from common import RuleError

MIN_PLAYERS, MAX_PLAYERS = 3, 16
TIMES = (0, 120, 180, 300)


class Player:
    def __init__(self, name: str, is_bot: bool = False):
        self.id = secrets.token_hex(4)
        self.name = name
        self.is_bot = is_bot
        self.total = 0
        self.gained = 0
        self.seen = False
        self.vote: str | None = None


class Game:
    KIND = "imposter"
    NO_BOTS = True

    def __init__(self, code: str):
        self.code = code
        self.players: list[Player] = []
        self.host_id: str | None = None
        self.state = "lobby"      # lobby | playing | finished
        self.phase = "reveal"     # reveal | clues | vote | guess | end
        self.imposter_count = 1
        self.hint = 1             # imposter sees the category
        self.seconds = 0
        self.round = 0
        self.word = ""
        self.category = ""
        self.imposters: list[str] = []
        self.order: list[str] = []
        self.caught: str | None = None
        self.options: list[str] = []
        self.guess: str | None = None
        self.winner = ""          # crew | imposter
        self.clue_end = 0.0
        self.used: set[str] = set()
        self.tally: dict[str, int] = {}
        self.log: list[str] = []

    # -- shared interface ----------------------------------------------------
    def new_player(self, name: str, is_bot: bool = False) -> Player:
        return Player(name, is_bot)

    def player(self, player_id):
        return next((p for p in self.players if p.id == player_id), None)

    def note(self, text: str) -> None:
        self.log.append(text)
        del self.log[:-30]

    def configure(self, settings: dict) -> None:
        count = int(settings.get("imposters") or 1)
        self.imposter_count = count if count in (1, 2) else 1
        hint = settings.get("hint")
        self.hint = 0 if hint is not None and int(hint) == 0 else 1
        seconds = settings.get("seconds")
        seconds = int(seconds) if seconds is not None else 0
        self.seconds = seconds if seconds in TIMES else 0

    def add_player(self, player: Player) -> None:
        if player.is_bot:
            raise RuleError("In diesem Spiel gibt es keine Computer-Spieler")
        if self.state != "lobby":
            raise RuleError("Das Spiel läuft bereits")
        if len(self.players) >= MAX_PLAYERS:
            raise RuleError(f"Maximal {MAX_PLAYERS} Spieler")
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
        if len(self.players) < MIN_PLAYERS:
            raise RuleError(f"Mindestens {MIN_PLAYERS} Spieler nötig")
        if self.state != "playing":
            for p in self.players:
                p.total = 0
            self.round = 0
            self.used = set()
        self.state = "playing"
        self.log = []
        self.start_round()

    # -- rounds --------------------------------------------------------------
    def start_round(self) -> None:
        self.round += 1
        pool = [(w, c) for w, c in wortschatz.ALL if w not in self.used] or wortschatz.ALL
        self.word, self.category = random.choice(pool)
        self.used.add(self.word)
        count = 2 if self.imposter_count == 2 and len(self.players) >= 5 else 1
        self.imposters = [p.id for p in random.sample(self.players, count)]
        order = [p.id for p in self.players]
        random.shuffle(order)
        # The imposter should not always have to speak first.
        if order[0] in self.imposters and random.random() < .7:
            order.append(order.pop(0))
        self.order = order
        for p in self.players:
            p.seen, p.vote, p.gained = False, None, 0
        self.caught = None
        self.options = []
        self.guess = None
        self.winner = ""
        self.tally = {}
        self.clue_end = 0.0
        self.phase = "reveal"
        self.note(f"Runde {self.round}: Schaut euch heimlich eure Karte an")

    @property
    def deadline(self) -> float | None:
        return self.clue_end if self.state == "playing" and self.phase == "clues" and self.clue_end else None

    def on_deadline(self) -> None:
        if self.state == "playing" and self.phase == "clues":
            self._to_vote()

    def _to_vote(self) -> None:
        self.phase = "vote"
        self.clue_end = 0.0
        self.note("Abstimmung: Wer ist der Imposter?")

    def _count_votes(self) -> None:
        tally: dict[str, int] = {}
        for p in self.players:
            if p.vote:
                tally[p.vote] = tally.get(p.vote, 0) + 1
        self.tally = tally
        top = max(tally.values(), default=0)
        leaders = [pid for pid, n in tally.items() if n == top]
        if len(leaders) != 1:
            self.note("Gleichstand – niemand wird enttarnt")
            self._finish_round("imposter")
            return
        target = self.player(leaders[0])
        if leaders[0] in self.imposters:
            self.caught = leaders[0]
            others = [w for w in wortschatz.CATEGORIES[self.category] if w != self.word]
            self.options = random.sample(others, min(7, len(others))) + [self.word]
            random.shuffle(self.options)
            self.phase = "guess"
            self.note(f"{target.name} ist ein Imposter! Letzte Chance: das Wort erraten")
        else:
            self.note(f"{target.name} war unschuldig!")
            self._finish_round("imposter")

    def _finish_round(self, winner: str) -> None:
        self.winner = winner
        for p in self.players:
            if winner == "imposter" and p.id in self.imposters:
                p.gained = 3
            elif winner == "crew" and p.id not in self.imposters:
                p.gained = 1 + (1 if p.vote in self.imposters else 0)
            p.total += p.gained
        self.phase = "end"
        names = ", ".join(self.player(i).name for i in self.imposters if self.player(i))
        self.note(("Die Crew gewinnt" if winner == "crew" else "Der Imposter gewinnt") + f" – Imposter: {names}")

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool) -> None:
        kind = msg.get("t")
        player = self.player(player_id)
        if not player or self.state != "playing":
            raise RuleError("Gerade nicht möglich")
        if kind == "seen":
            if self.phase != "reveal":
                return
            player.seen = True
            if all(p.seen for p in self.players):
                self.phase = "clues"
                self.clue_end = time.time() + self.seconds if self.seconds else 0.0
                first = self.player(self.order[0])
                self.note(f"{first.name} beginnt – jeder sagt reihum ein Wort")
        elif kind == "to_vote":
            if self.phase != "clues":
                raise RuleError("Gerade nicht möglich")
            if not is_host:
                raise RuleError("Der Gastgeber startet die Abstimmung")
            self._to_vote()
        elif kind == "vote":
            if self.phase != "vote":
                raise RuleError("Gerade wird nicht abgestimmt")
            target = self.player(str(msg.get("id")))
            if not target or target is player:
                raise RuleError("Bitte jemand anderen wählen")
            player.vote = target.id
            if all(p.vote for p in self.players):
                self._count_votes()
        elif kind == "guess_word":
            if self.phase != "guess" or player.id != self.caught:
                raise RuleError("Gerade nicht möglich")
            word = str(msg.get("word"))
            if word not in self.options:
                raise RuleError("Bitte ein Wort aus der Liste wählen")
            self.guess = word
            if word == self.word:
                self.note(f"{player.name} errät das Wort „{self.word}“ – und gewinnt trotzdem!")
                self._finish_round("imposter")
            else:
                self._finish_round("crew")
        elif kind == "next_round":
            if self.phase != "end":
                raise RuleError("Die Runde läuft noch")
            if not is_host:
                raise RuleError("Nur der Gastgeber startet die nächste Runde")
            self.start_round()
        elif kind == "end_game":
            if not is_host or self.phase != "end":
                raise RuleError("Nur der Gastgeber kann das Spiel beenden")
            self.state = "finished"
            best = max(self.players, key=lambda p: p.total, default=None)
            if best:
                self.note(f"🏆 {best.name} hat die meisten Punkte ({best.total})")
        else:
            raise RuleError("Unbekannte Aktion")

    # -- players who left during a game (they become computer players) ----------
    def pending_bots(self) -> list:
        if self.state != "playing":
            return []
        return [p for p in self.players if p.is_bot and (
            (self.phase == "reveal" and not p.seen) or (self.phase == "vote" and not p.vote)
            or (self.phase == "guess" and p.id == self.caught))]

    def bot_step(self, bot: Player) -> None:
        if self.phase == "reveal":
            self.act(bot.id, {"t": "seen"}, False)
        elif self.phase == "vote":
            others = [p.id for p in self.players if p is not bot]
            self.act(bot.id, {"t": "vote", "id": random.choice(others)}, False)
        elif self.phase == "guess":
            self.act(bot.id, {"t": "guess_word", "word": random.choice(self.options)}, False)

    # -- view ----------------------------------------------------------------
    def view_for(self, viewer_id) -> dict:
        me = self.player(viewer_id)
        imposter = viewer_id in self.imposters
        over = self.phase == "end" or self.state == "finished"
        return {
            "kind": self.KIND, "code": self.code, "state": self.state, "phase": self.phase,
            "host": self.host_id, "settings": {"imposters": self.imposter_count, "hint": self.hint, "seconds": self.seconds},
            "round": self.round,
            "players": [{"id": p.id, "name": p.name, "bot": p.is_bot, "total": p.total, "gained": p.gained,
                         "seen": p.seen, "voted": p.vote is not None,
                         "vote": p.vote if over or self.phase == "guess" else None,
                         "votes": self.tally.get(p.id, 0) if self.tally else None,
                         "imposter": p.id in self.imposters if over else None} for p in self.players],
            "role": ("imposter" if imposter else "crew") if me else None,
            "word": self.word if (not imposter or over) else None,
            "category": self.category if (not imposter or self.hint or over) else None,
            "imposter_count": len(self.imposters),
            "order": self.order, "caught": self.caught,
            "options": self.options if self.phase == "guess" else [],
            "guess": self.guess, "winner": self.winner, "my_vote": me.vote if me else None,
            "remaining": max(0, round(self.clue_end - time.time(), 1)) if self.deadline else None,
            "log": self.log[-6:],
        }
