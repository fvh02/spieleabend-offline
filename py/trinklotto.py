"""Trinklotto: everyone secretly gets a colour, a number and an animal. Each call names a group
("Alle mit Blau trinken 2") – the phones show right away who is hit."""

import random
import time

from common import RuleError
from party import PartyGame

COLORS = [("rot", "Rot", "#ef4444"), ("blau", "Blau", "#3b82f6"), ("gruen", "Grün", "#22c55e"),
          ("gelb", "Gelb", "#eab308"), ("lila", "Lila", "#a855f7"), ("orange", "Orange", "#f97316")]
ANIMALS = [("katze", "Katze", "🐱", "Katzen"), ("hund", "Hund", "🐶", "Hunde"), ("fuchs", "Fuchs", "🦊", "Füchse"),
           ("baer", "Bär", "🐻", "Bären"), ("pinguin", "Pinguin", "🐧", "Pinguine"), ("frosch", "Frosch", "🐸", "Frösche")]
COLOR = {c[0]: c for c in COLORS}
ANIMAL = {a[0]: a for a in ANIMALS}


def sips(n: int) -> str:
    return f"{n} Schluck" if n == 1 else f"{n} Schlucke"


class Game(PartyGame):
    KIND = "trinklotto"
    MIN_PLAYERS, MAX_PLAYERS = 2, 16
    ROUNDS = (20, 10, 30, 50)
    TIMES = (0, 15, 25, 40)          # 0 = the host taps for the next call, otherwise automatic
    INPUT_PHASES = ()
    SHUFFLE_EVERY = 6

    def __init__(self, code: str):
        super().__init__(code)
        self.traits: dict[str, dict] = {}
        self.call: dict = {}
        self.since_shuffle = 0

    def deal(self) -> None:
        """Balanced: every colour/number/animal is used about equally often."""
        gamers = self.gamers
        colors = [c[0] for c in COLORS] * (len(gamers) // 6 + 1)
        numbers = list(range(1, 7)) * (len(gamers) // 6 + 1)
        animals = [a[0] for a in ANIMALS] * (len(gamers) // 6 + 1)
        for pool in (colors, numbers, animals):
            random.shuffle(pool)
        self.traits = {p.id: {"color": colors[i], "number": numbers[i], "animal": animals[i]} for i, p in enumerate(gamers)}
        self.since_shuffle = 0

    def start(self) -> None:
        self.deal()
        super().start()

    def make_call(self) -> dict:
        t = list(self.traits.values())
        n = random.choice((1, 1, 2, 2, 3))
        color = random.choice([x["color"] for x in t])
        number = random.choice([x["number"] for x in t])
        animal = random.choice([x["animal"] for x in t])
        c, a = COLOR[color], ANIMAL[animal]
        options = [
            (5, f"Alle mit {c[1]} trinken {sips(n)}!", lambda x: x["color"] == color, n, "drink", {"color": color}),
            (5, f"Wer die {number} hat, trinkt {sips(n)}!", lambda x: x["number"] == number, n, "drink", {"number": number}),
            (4, f"Alle {a[3]} trinken {sips(n)}!",
             lambda x: x["animal"] == animal, n, "drink", {"animal": animal}),
            (2, f"Alle mit gerader Zahl trinken {sips(n)}!", lambda x: x["number"] % 2 == 0, n, "drink", {"even": True}),
            (2, f"Alle mit ungerader Zahl trinken {sips(n)}!", lambda x: x["number"] % 2 == 1, n, "drink", {"odd": True}),
            (2, "Alle mit einer Zahl größer als 4 trinken 1 Schluck!", lambda x: x["number"] > 4, 1, "drink", {"gt": 4}),
            (3, f"{c[1]} verteilt {sips(n + 1)}!", lambda x: x["color"] == color, n + 1, "give", {"color": color}),
            (3, f"Wer die {number} hat, verteilt {sips(n + 1)}!", lambda x: x["number"] == number, n + 1, "give", {"number": number}),
            (2, f"Alle außer {c[1]} trinken 1 Schluck!", lambda x: x["color"] != color, 1, "drink", {"not_color": color}),
            (1, f"Wasserfall für alle {a[3]} – startet, sobald ihr bereit seid!",
             lambda x: x["animal"] == animal, 3, "drink", {"animal": animal}),
            (1, f"{c[1]} und alle {a[3]} stoßen an und trinken 2 Schlucke!",
             lambda x: x["color"] == color or x["animal"] == animal, 2, "drink", {"color": color, "animal": animal}),
        ]
        if self.since_shuffle >= self.SHUFFLE_EVERY and random.random() < .5:
            return {"text": "🔀 Neu gemischt! Alle bekommen neue Farben, Zahlen und Tiere.", "kind": "shuffle", "hits": [], "n": 0, "match": {}}
        weights = [o[0] for o in options]
        _, text, test, amount, kind, match = random.choices(options, weights=weights)[0]
        hits = [pid for pid, x in self.traits.items() if test(x)]
        return {"text": text, "kind": kind, "hits": hits, "n": amount, "match": match}

    def setup_round(self) -> None:
        call = self.make_call()
        if call["kind"] == "shuffle":
            self.deal()
        else:
            self.since_shuffle += 1
        self.call = call
        for pid in call["hits"]:
            p = self.player(pid)
            if p and call["kind"] == "drink":
                p.gained = call["n"]
                p.score += call["n"]
        self.phase = "reveal"
        self.phase_end = 0.0
        if self.seconds:
            self.phase_end = time.time() + self.seconds

    def on_deadline(self) -> None:
        if self.state == "playing" and self.phase == "reveal":
            if self.round >= self.rounds:
                self.finish()
            else:
                self.next_round()

    def advance(self) -> None:
        pass

    def play(self, player, msg: dict) -> None:
        raise RuleError("Gerade nicht möglich")

    def extra_view(self, me) -> dict:
        traits = self.traits.get(me.id) if me else None
        mine = None
        if traits:
            c, a = COLOR[traits["color"]], ANIMAL[traits["animal"]]
            mine = {"color": c[1], "hex": c[2], "number": traits["number"], "animal": a[1], "emoji": a[2]}
        return {
            "call": {"text": self.call.get("text", ""), "kind": self.call.get("kind", ""), "n": self.call.get("n", 0),
                     "hits": self.call.get("hits", [])},
            "mine": mine,
            "legend": {"colors": [[c[1], c[2]] for c in COLORS], "animals": [[a[1], a[2]] for a in ANIMALS]},
        }


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
