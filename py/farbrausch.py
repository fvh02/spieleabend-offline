"""Farbrausch: get rid of all your cards by matching colour or symbol (rules, no networking).

108 cards: in red, yellow, green and blue one 0, two each of 1–9, Skip, Reverse and Draw Two;
plus four Wild and four Wild Draw Four. Whoever plays their last card wins the round and scores
the cards left in the other hands. "Letzte Karte!" must be called when one card is left."""

import random
import secrets

from common import RuleError

COLORS = ("r", "y", "g", "b")
COLOR_NAMES = {"r": "Rot", "y": "Gelb", "g": "Grün", "b": "Blau"}
ACTIONS = ("skip", "rev", "+2")
WILDS = ("wild", "+4")
MIN_PLAYERS, MAX_PLAYERS = 2, 10
HAND = 7
TARGETS = (0, 200, 500)  # 0 = a single round


def new_deck() -> list[dict]:
    deck, n = [], 0
    for c in COLORS:
        values = ["0"] + [str(v) for v in range(1, 10)] * 2 + list(ACTIONS) * 2
        for v in values:
            deck.append({"id": n, "c": c, "v": v})
            n += 1
    for v in WILDS:
        for _ in range(4):
            deck.append({"id": n, "c": "w", "v": v})
            n += 1
    random.shuffle(deck)
    return deck


def points(card: dict) -> int:
    if card["v"] in WILDS:
        return 50
    if card["v"] in ACTIONS:
        return 20
    return int(card["v"])


def label(card: dict) -> str:
    names = {"skip": "Aussetzen", "rev": "Richtungswechsel", "+2": "+2", "wild": "Farbwahl", "+4": "+4"}
    v = names.get(card["v"], card["v"])
    return v if card["c"] == "w" else f"{COLOR_NAMES[card['c']]} {v}"


class Player:
    def __init__(self, name: str, is_bot: bool = False):
        self.id = secrets.token_hex(4)
        self.name = name
        self.is_bot = is_bot
        self.hand: list[dict] = []
        self.total = 0
        self.called = False  # "Letzte Karte!" called for the current last card


class Game:
    KIND = "farbrausch"

    def __init__(self, code: str):
        self.code = code
        self.players: list[Player] = []
        self.host_id: str | None = None
        self.state = "lobby"        # lobby | playing | finished
        self.phase = "turn"         # turn | round_end
        self.target = 0
        self.stacking = False
        self.deck: list[dict] = []
        self.discard: list[dict] = []
        self.color = "r"            # colour to follow (chosen colour after a wild)
        self.turn = 0
        self.direction = 1
        self.pending = 0            # cards the current player has to draw (stacking)
        self.drawn_id: int | None = None  # card drawn this turn that may still be played
        self.catchable: str | None = None  # player with one card who forgot to call, until the next action
        self.round = 0
        self.round_scores: dict = {}
        self.winner: str | None = None
        self.log: list[str] = []
        self.last: dict = {}        # last event for animations: {"kind", "by", "card", "n", "seq"}
        self.seq = 0

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
        target = settings.get("target")
        target = int(target) if target is not None else 0
        self.target = target if target in TARGETS else 0
        self.stacking = bool(int(settings.get("stacking") or 0))

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
        if self.state == "playing":
            self.discard[:0] = player.hand
            if len(self.players) < MIN_PLAYERS:
                self.finish()
                return
            if index < self.turn:
                self.turn -= 1
            self.turn %= len(self.players)
            self.drawn_id = None
            self.note(f"{player.name} hat das Spiel verlassen")

    def start(self) -> None:
        if len(self.players) < MIN_PLAYERS:
            raise RuleError("Mindestens 2 Spieler nötig")
        for p in self.players:
            p.total = 0
        self.round = 0
        self.winner = None
        self.log = []
        self.state = "playing"
        self.note("Neues Spiel – " + (f"bis {self.target} Punkte" if self.target else "eine Runde"))
        self.start_round()

    def _event(self, **event) -> None:
        self.seq += 1
        self.last = dict(event, seq=self.seq)

    # -- rounds --------------------------------------------------------------
    def start_round(self) -> None:
        self.round += 1
        self.deck = new_deck()
        for p in self.players:
            p.hand = [self.deck.pop() for _ in range(HAND)]
            p.called = False
        # Start with a number card so nobody begins with a penalty.
        while self.deck[-1]["v"] in ACTIONS + WILDS:
            self.deck.insert(0, self.deck.pop())
        self.discard = [self.deck.pop()]
        self.color = self.discard[-1]["c"]
        self.direction = 1
        self.pending = 0
        self.drawn_id = None
        self.catchable = None
        self.round_scores = {}
        self.phase = "turn"
        self.turn = (self.round - 1) % len(self.players)
        self._event(kind="deal")
        self.note(f"Runde {self.round}: {self.players[self.turn].name} beginnt")

    def _draw(self, player: Player, n: int) -> list[dict]:
        got = []
        for _ in range(n):
            if not self.deck:
                top = self.discard.pop()
                self.deck, self.discard = self.discard, [top]
                random.shuffle(self.deck)
                if self.deck:
                    self.note("Der Ablagestapel wurde neu gemischt")
            if not self.deck:
                break
            got.append(self.deck.pop())
        player.hand.extend(got)
        if len(player.hand) > 1:
            player.called = False
        return got

    def _next(self, steps: int = 1) -> int:
        return (self.turn + self.direction * steps) % len(self.players)

    def playable(self, card: dict) -> bool:
        top = self.discard[-1]
        if self.pending:
            # Only stacking cards help against a pending draw.
            return card["v"] == "+4" or (card["v"] == "+2" and top["v"] == "+2")
        return card["c"] == "w" or card["c"] == self.color or card["v"] == top["v"]

    def _end_turn(self, skip: int = 0) -> None:
        self.drawn_id = None
        self.turn = self._next(1 + skip)

    def end_round(self, winner: Player) -> None:
        gained = sum(points(c) for p in self.players for c in p.hand)
        winner.total += gained
        self.round_scores = {"winner": winner.id, "gained": gained,
                             "left": {p.id: sum(points(c) for c in p.hand) for p in self.players}}
        self.phase = "round_end"
        self.catchable = None
        self.note(f"{winner.name} hat keine Karten mehr" + (f" und bekommt {gained} Punkte" if self.target else ""))
        if not self.target or winner.total >= self.target:
            self.finish(winner)

    def finish(self, winner: Player | None = None) -> None:
        self.state = "finished"
        if winner is None and self.players:
            winner = max(self.players, key=lambda p: p.total) if self.target else min(self.players, key=lambda p: len(p.hand))
        self.winner = winner.name if winner else None
        if winner:
            self.note(f"🏆 {winner.name} gewinnt!")

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool) -> None:
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
        if self.phase != "turn":
            raise RuleError("Die Runde ist vorbei")
        if kind == "call":
            if len(player.hand) > 2 or (len(player.hand) == 2 and self.current is not player):
                raise RuleError("Das rufst du, wenn du nur noch eine Karte hast")
            player.called = True
            if self.catchable == player.id:
                self.catchable = None
            self._event(kind="call", by=player.id)
            self.note(f"{player.name}: „Letzte Karte!“")
            return
        if kind == "catch":
            target = self.player(str(msg.get("id")))
            if not target or self.catchable != target.id or target is player:
                raise RuleError("Zu spät – oder es gibt nichts zu erwischen")
            self._draw(target, 2)
            self.catchable = None
            self._event(kind="catch", by=player.id, target=target.id, n=2)
            self.note(f"{player.name} erwischt {target.name}: „Letzte Karte!“ vergessen – 2 Karten")
            return

        if self.current is not player:
            raise RuleError("Du bist nicht am Zug")

        if kind == "draw":
            if self.drawn_id is not None:
                raise RuleError("Du hast schon gezogen – spiele die Karte oder gib weiter")
            self.catchable = None  # the next action closes the window to catch someone
            if self.pending:
                n = self.pending
                got = self._draw(player, n)
                self.pending = 0
                self._event(kind="draw", by=player.id, n=len(got), ids=[c["id"] for c in got])
                self.note(f"{player.name} zieht {len(got)} Karten")
                self._end_turn()
                return
            got = self._draw(player, 1)
            self._event(kind="draw", by=player.id, n=len(got), ids=[c["id"] for c in got])
            if got and self.playable(got[0]):
                self.drawn_id = got[0]["id"]
            else:
                self.note(f"{player.name} zieht eine Karte")
                self._end_turn()
        elif kind == "pass":
            if self.drawn_id is None:
                raise RuleError("Ziehe zuerst eine Karte")
            self.catchable = None
            self.note(f"{player.name} zieht eine Karte und behält sie")
            self._end_turn()
        elif kind == "play":
            card = next((c for c in player.hand if c["id"] == msg.get("id")), None)
            if not card:
                raise RuleError("Diese Karte hast du nicht")
            if self.drawn_id is not None and card["id"] != self.drawn_id:
                raise RuleError("Nach dem Ziehen darfst du nur die gezogene Karte spielen")
            if not self.playable(card):
                raise RuleError("Die Karte passt nicht" if not self.pending else
                                f"Du musst {self.pending} Karten ziehen oder eine passende Plus-Karte legen")
            color = msg.get("color")
            if card["c"] == "w" and color not in COLORS:
                raise RuleError("Wähle eine Farbe")
            self._play(player, card, color)
        else:
            raise RuleError("Unbekannte Aktion")

    def _play(self, player: Player, card: dict, color: str | None) -> None:
        self.catchable = None
        player.hand.remove(card)
        self.discard.append(card)
        self.color = color if card["c"] == "w" else card["c"]
        self._event(kind="play", by=player.id, card=card)
        text = f"{player.name} legt {label(card)}"
        if card["c"] == "w":
            text += f" und wünscht sich {COLOR_NAMES[self.color]}"
        self.note(text)
        if len(player.hand) == 1 and not player.called:
            self.catchable = player.id
        if len(player.hand) != 1:
            player.called = False

        skip = 0
        if card["v"] == "skip":
            skip = 1
        elif card["v"] == "rev":
            self.direction *= -1
            if len(self.players) == 2:
                skip = 1
        elif card["v"] in ("+2", "+4"):
            self.pending += 2 if card["v"] == "+2" else 4
            if not self.stacking:
                victim = self.players[self._next()]
                got = self._draw(victim, self.pending)
                self.note(f"{victim.name} zieht {len(got)} Karten und setzt aus")
                self.last["victim"] = victim.id
                self.last["n"] = len(got)
                self.pending = 0
                skip = 1
        if not player.hand:
            self.drawn_id = None
            if self.pending:  # stacking: the next player still has to draw
                victim = self.players[self._next()]
                self._draw(victim, self.pending)
                self.pending = 0
            self.end_round(player)
            return
        self._end_turn(skip)

    # -- bots ----------------------------------------------------------------
    def pending_bots(self) -> list:
        if self.state != "playing" or self.phase != "turn":
            return []
        current = self.current
        # A bot may also catch a human who forgot to call.
        if self.catchable and any(p.is_bot and p.id != self.catchable for p in self.players):
            target = self.player(self.catchable)
            if target and not target.is_bot and random.random() < .5:
                return [next(p for p in self.players if p.is_bot and p.id != self.catchable)]
        return [current] if current and current.is_bot else []

    def bot_step(self, bot: Player) -> None:
        if self.catchable and self.catchable != bot.id and self.current is not bot:
            self.act(bot.id, {"t": "catch", "id": self.catchable}, False)
            return
        if len(bot.hand) == 2 and not bot.called and random.random() < .85 and any(self.playable(c) for c in bot.hand):
            bot.called = True
            self.note(f"{bot.name}: „Letzte Karte!“")
        if self.drawn_id is not None:
            card = next(c for c in bot.hand if c["id"] == self.drawn_id)
            self.act(bot.id, {"t": "play", "id": card["id"], "color": self._bot_color(bot)}, False)
            return
        options = [c for c in bot.hand if self.playable(c)]
        if not options:
            self.act(bot.id, {"t": "draw"}, False)
            return
        nxt = self.players[self._next()]
        danger = len(nxt.hand) <= 2

        def score(c):
            s = 0
            if c["c"] == "w":
                s -= 30 if not danger else -10   # save wilds unless the next player is close to winning
            if c["v"] in ACTIONS or c["v"] == "+4":
                s += 25 if danger else 5
            if c["c"] == self.color:
                s += 10
            s += points(c) / 10
            return s
        card = max(options, key=score)
        self.act(bot.id, {"t": "play", "id": card["id"], "color": self._bot_color(bot, card)}, False)

    @staticmethod
    def _bot_color(bot: Player, playing: dict | None = None) -> str:
        counts = {c: 0 for c in COLORS}
        for card in bot.hand:
            if card is not playing and card["c"] in counts:
                counts[card["c"]] += 1
        return max(COLORS, key=lambda c: (counts[c], random.random()))

    # -- view ----------------------------------------------------------------
    def view_for(self, viewer_id) -> dict:
        reveal = self.phase == "round_end" or self.state == "finished"
        me = self.player(viewer_id)
        current = self.current
        my_turn = current is not None and me is current
        return {
            "kind": self.KIND, "code": self.code, "state": self.state, "phase": self.phase,
            "host": self.host_id, "settings": {"target": self.target, "stacking": int(self.stacking)},
            "round": self.round,
            "players": [{
                "id": p.id, "name": p.name, "bot": p.is_bot, "count": len(p.hand), "total": p.total,
                "called": p.called and len(p.hand) == 1,
                "hand": p.hand if reveal else None,
            } for p in self.players],
            "hand": [dict(c, ok=my_turn and self.playable(c) and (self.drawn_id is None or c["id"] == self.drawn_id))
                     for c in (me.hand if me else [])],
            "turn": current.id if current else None,
            "top": self.discard[-1] if self.discard else None,
            "color": self.color, "direction": self.direction, "pending": self.pending,
            "drawn": self.drawn_id, "deck_count": len(self.deck),
            "catchable": self.catchable,
            "can_call": bool(me and not me.called and (len(me.hand) == 1 or (len(me.hand) == 2 and my_turn))),
            "round_scores": self.round_scores, "last": self.last,
            "winner": self.winner, "log": self.log[-8:],
        }
