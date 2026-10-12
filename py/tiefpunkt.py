"""Tiefpunkt: collect as few points as possible in a 3x4 grid (rules, no networking)."""

import random
import secrets

from common import RuleError

ROWS, COLS = 3, 4
SLOTS = ROWS * COLS
MIN_PLAYERS, MAX_PLAYERS = 2, 8
TARGETS = (50, 100, 150)


def new_deck() -> list[int]:
    deck = [-2] * 5 + [-1] * 10 + [0] * 15 + [v for v in range(1, 13) for _ in range(10)]
    random.shuffle(deck)
    return deck


def column(index: int) -> list[int]:
    c = index % COLS
    return [c + r * COLS for r in range(ROWS)]


class Player:
    def __init__(self, name: str, is_bot: bool = False):
        self.id = secrets.token_hex(4)
        self.name = name
        self.is_bot = is_bot
        self.total = 0
        self.history: list[int] = []
        self.grid: list[dict | None] = []  # {"v": int, "up": bool} or None once a column is removed

    def visible_sum(self) -> int:
        return sum(c["v"] for c in self.grid if c and c["up"])

    def face_down(self) -> list[int]:
        return [i for i, c in enumerate(self.grid) if c and not c["up"]]


class Game:
    KIND = "tiefpunkt"

    def __init__(self, code: str):
        self.code = code
        self.players: list[Player] = []
        self.host_id: str | None = None
        self.state = "lobby"   # lobby | playing | finished
        self.phase = "setup"   # setup (flip two) | turn | round_end
        self.target = 100
        self.deck: list[int] = []
        self.discard: list[int] = []
        self.turn = 0
        self.drawn: int | None = None
        self.drawn_from: str | None = None   # deck | discard
        self.must_flip = False
        self.ender: str | None = None        # player who uncovered all cards first
        self.final_left: set[str] = set()    # players still owed a last turn
        self.round = 0
        self.round_scores: dict[str, dict] = {}
        self.starter: str | None = None      # who opens the next round
        self.winner: str | None = None
        self.log: list[str] = []
        self.removed: list[int] = []         # grid slots removed by the last action (for animations)

    # -- shared interface ----------------------------------------------------
    def new_player(self, name: str, is_bot: bool = False) -> Player:
        return Player(name, is_bot)

    def player(self, player_id):
        return next((p for p in self.players if p.id == player_id), None)

    @property
    def current(self):
        if self.state == "playing" and self.phase == "turn" and self.players:
            return self.players[self.turn]
        return None

    def note(self, text: str) -> None:
        self.log.append(text)
        del self.log[:-30]

    def configure(self, settings: dict) -> None:
        target = int(settings.get("target") or 100)
        self.target = target if target in TARGETS else 100

    def add_player(self, player: Player) -> None:
        if self.state != "lobby":
            raise RuleError("Das Spiel läuft bereits")
        if len(self.players) >= MAX_PLAYERS:
            raise RuleError(f"Maximal {MAX_PLAYERS} Spieler")
        self.players.append(player)
        if self.host_id is None and not player.is_bot:
            self.host_id = player.id

    def remove_player(self, player_id: str) -> None:
        player = self.player(player_id)
        if not player:
            return
        index = self.players.index(player)
        self.players.remove(player)
        if self.host_id == player_id:
            self.host_id = next((p.id for p in self.players if not p.is_bot), None)
        self.final_left.discard(player_id)
        if self.state == "playing":
            if len(self.players) < MIN_PLAYERS:
                self.finish()
                return
            if index < self.turn:
                self.turn -= 1
            self.turn %= len(self.players)
            self.drawn = self.drawn_from = None
            self.must_flip = False
            self.note(f"{player.name} hat das Spiel verlassen")

    def start(self) -> None:
        if len(self.players) < MIN_PLAYERS:
            raise RuleError("Mindestens 2 Spieler nötig")
        for p in self.players:
            p.total, p.history = 0, []
        self.round = 0
        self.winner = None
        self.log = []
        self.starter = None
        self.state = "playing"
        self.note(f"Neues Spiel bis {self.target} Punkte")
        self.start_round()

    # -- rounds --------------------------------------------------------------
    def start_round(self) -> None:
        self.round += 1
        self.deck = new_deck()
        for p in self.players:
            p.grid = [{"v": self.deck.pop(), "up": False} for _ in range(SLOTS)]
        self.discard = [self.deck.pop()]
        self.phase = "setup"
        self.drawn = self.drawn_from = None
        self.must_flip = False
        self.ender = None
        self.final_left = set()
        self.round_scores = {}
        self.removed = []
        self.note(f"Runde {self.round}: jeder deckt 2 Karten auf")

    def setup_flip(self, player: Player, index: int) -> None:
        if len([c for c in player.grid if c["up"]]) >= 2:
            raise RuleError("Du hast schon 2 Karten aufgedeckt")
        self._slot(player, index, face_down=True)["up"] = True
        if all(len([c for c in p.grid if c["up"]]) >= 2 for p in self.players):
            self.phase = "turn"
            starter = self.player(self.starter) if self.starter else None
            if not starter:  # first round: highest sum of the two open cards starts
                starter = max(self.players, key=lambda p: p.visible_sum())
            self.turn = self.players.index(starter)
            self.note(f"{starter.name} beginnt")

    def _slot(self, player: Player, index: int, face_down: bool = False) -> dict:
        if not 0 <= index < SLOTS or player.grid[index] is None:
            raise RuleError("Ungültiges Feld")
        if face_down and player.grid[index]["up"]:
            raise RuleError("Diese Karte ist schon offen")
        return player.grid[index]

    def _draw(self) -> int:
        if not self.deck:
            top = self.discard.pop()
            self.deck, self.discard = self.discard, [top]
            random.shuffle(self.deck)
            self.note("Der Ablagestapel wurde neu gemischt")
        return self.deck.pop()

    def _remove_columns(self, player: Player) -> None:
        for c in range(COLS):
            slots = column(c)
            cards = [player.grid[i] for i in slots]
            if all(cards) and all(x["up"] for x in cards) and len({x["v"] for x in cards}) == 1:
                for i in slots:
                    self.discard.append(player.grid[i]["v"])
                    player.grid[i] = None
                self.removed.extend(slots)
                self.note(f"{player.name} räumt eine Spalte mit drei {cards[0]['v']} ab")

    def _end_turn(self, player: Player) -> None:
        self._remove_columns(player)
        self.drawn = self.drawn_from = None
        self.must_flip = False
        if self.ender:
            self.final_left.discard(player.id)
        elif not player.face_down():
            self.ender = player.id
            self.final_left = {p.id for p in self.players if p.id != player.id}
            self.note(f"{player.name} hat alle Karten offen – jeder hat noch einen Zug")
        if self.ender and not self.final_left:
            self.end_round()
            return
        self.turn = (self.turn + 1) % len(self.players)

    def end_round(self) -> None:
        for p in self.players:
            for c in p.grid:
                if c:
                    c["up"] = True
            self._remove_columns(p)
        scores = {p.id: p.visible_sum() for p in self.players}
        doubled = False
        ender = self.player(self.ender)
        if ender and scores[ender.id] > 0 and any(s <= scores[ender.id] for pid, s in scores.items() if pid != ender.id):
            scores[ender.id] *= 2
            doubled = True
            self.note(f"{ender.name} war nicht allein am niedrigsten – Punkte verdoppelt")
        for p in self.players:
            p.total += scores[p.id]
            p.history.append(scores[p.id])
        self.round_scores = {"scores": scores, "doubled": self.ender if doubled else None}
        self.starter = self.ender
        self.phase = "round_end"
        if any(p.total >= self.target for p in self.players):
            self.finish()

    def finish(self) -> None:
        self.state = "finished"
        best = min(self.players, key=lambda p: p.total) if self.players else None
        self.winner = best.name if best else None
        if best:
            self.note(f"🏆 {best.name} gewinnt mit {best.total} Punkten!")

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool) -> None:
        self.removed = []
        kind = msg.get("t")
        player = self.player(player_id)
        if not player or self.state != "playing":
            raise RuleError("Gerade nicht möglich")
        if kind == "next_round":
            if self.phase != "round_end":
                raise RuleError("Die Runde läuft noch")
            if not is_host:
                raise RuleError("Nur der Gastgeber startet die nächste Runde")
            self.start_round()
            return
        if self.phase == "setup":
            if kind != "flip":
                raise RuleError("Decke zuerst 2 Karten auf")
            self.setup_flip(player, int(msg.get("index", -1)))
            return
        if self.phase != "turn" or self.current is not player:
            raise RuleError("Du bist nicht am Zug")

        if kind == "draw":
            if self.drawn is not None or self.must_flip:
                raise RuleError("Du hast schon eine Karte gezogen")
            self.drawn, self.drawn_from = self._draw(), "deck"
        elif kind == "take":
            if self.drawn is not None or self.must_flip:
                raise RuleError("Du hast schon eine Karte gezogen")
            self.drawn, self.drawn_from = self.discard.pop(), "discard"
            if not self.discard:  # keep a visible discard pile
                self.discard.append(self._draw())
        elif kind == "swap":
            if self.drawn is None:
                raise RuleError("Ziehe zuerst eine Karte")
            slot = self._slot(player, int(msg.get("index", -1)))
            self.discard.append(slot["v"])
            slot["v"], slot["up"] = self.drawn, True
            self._end_turn(player)
        elif kind == "drop":
            if self.drawn is None or self.drawn_from != "deck":
                raise RuleError("Eine Karte vom Ablagestapel musst du tauschen")
            self.discard.append(self.drawn)
            self.drawn = None
            self.must_flip = True
        elif kind == "flip":
            if not self.must_flip:
                raise RuleError("Ziehe zuerst eine Karte")
            self._slot(player, int(msg.get("index", -1)), face_down=True)["up"] = True
            self._end_turn(player)
        else:
            raise RuleError("Unbekannte Aktion")

    # -- bots ----------------------------------------------------------------
    def pending_bots(self) -> list:
        if self.state != "playing":
            return []
        if self.phase == "setup":
            return [p for p in self.players if p.is_bot and len([c for c in p.grid if c["up"]]) < 2]
        current = self.current
        return [current] if current and current.is_bot else []

    def bot_step(self, bot: Player) -> None:
        if self.phase == "setup":
            self.act(bot.id, {"t": "flip", "index": random.choice(bot.face_down())}, False)
            return
        if self.must_flip:
            self.act(bot.id, {"t": "flip", "index": self._bot_flip_choice(bot)}, False)
            return
        if self.drawn is None:
            top = self.discard[-1]
            if self._bot_target(bot, top, strict=True) is not None:
                self.act(bot.id, {"t": "take"}, False)
            else:
                self.act(bot.id, {"t": "draw"}, False)
            return
        target = self._bot_target(bot, self.drawn, strict=self.drawn_from == "deck")
        if target is None and self.drawn_from == "discard":
            target = self._bot_target(bot, self.drawn, strict=False)
        if target is not None:
            self.act(bot.id, {"t": "swap", "index": target}, False)
        else:
            self.act(bot.id, {"t": "drop"}, False)

    @staticmethod
    def _completes(bot: Player, value: int):
        for c in range(COLS):
            slots = column(c)
            cards = [bot.grid[i] for i in slots]
            if not all(cards):
                continue
            same = [i for i in slots if bot.grid[i]["up"] and bot.grid[i]["v"] == value]
            if len(same) == 2:
                rest = [i for i in slots if i not in same][0]
                return rest
        return None

    def _bot_target(self, bot: Player, value: int, strict: bool):
        """Slot to swap `value` into, or None if keeping it is not worth it."""
        done = self._completes(bot, value)
        if done is not None:
            return done
        open_cards = [(c["v"], i) for i, c in enumerate(bot.grid) if c and c["up"]]
        worst = max(open_cards, default=None)
        if worst and worst[0] - value >= 3:
            return worst[1]
        hidden = bot.face_down()
        # Revealing the last hidden card ends the round – only with a decent score.
        if hidden and value <= 4 and (len(hidden) > 1 or bot.visible_sum() + value <= 10):
            return random.choice(hidden)
        if not strict:
            if worst and worst[0] > value:
                return worst[1]
            if hidden:
                return random.choice(hidden)
        return None

    def _bot_flip_choice(self, bot: Player) -> int:
        hidden = bot.face_down()
        return random.choice(hidden)

    # -- view ----------------------------------------------------------------
    def view_for(self, viewer_id) -> dict:
        reveal = self.phase == "round_end" or self.state == "finished"

        def grid(p):
            return [None if c is None else {"v": c["v"] if (c["up"] or reveal) else None, "up": c["up"] or reveal}
                    for c in p.grid]

        current = self.current
        return {
            "kind": self.KIND, "code": self.code, "state": self.state, "phase": self.phase,
            "host": self.host_id, "settings": {"target": self.target}, "round": self.round,
            "players": [{
                "id": p.id, "name": p.name, "bot": p.is_bot, "total": p.total, "history": p.history,
                "grid": grid(p), "visible": p.visible_sum(),
                "ready": len([c for c in p.grid if c and c["up"]]) >= 2,
            } for p in self.players],
            "turn": current.id if current else None,
            "deck_count": len(self.deck), "discard_top": self.discard[-1] if self.discard else None,
            "drawn": self.drawn, "drawn_from": self.drawn_from, "must_flip": self.must_flip,
            "ender": self.ender, "final_left": sorted(self.final_left),
            "round_scores": self.round_scores, "removed": self.removed,
            "winner": self.winner, "log": self.log[-8:],
        }
