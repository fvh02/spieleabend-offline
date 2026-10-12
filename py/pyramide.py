"""Pyramide: everyone holds four cards. A pyramid of 15 cards is turned over one by one –
whoever holds the same value drinks (or hands out sips): the higher the row, the more sips."""

import random
import time

from common import RuleError
from party import PartyGame

SUITS = ["♥", "♦", "♣", "♠"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "B", "D", "K"]
ROWS = [5, 4, 3, 2, 1]               # bottom to top
HAND = 4


class Game(PartyGame):
    KIND = "pyramide"
    MIN_PLAYERS, MAX_PLAYERS = 2, 9      # 9 × 4 + 15 = 51 cards
    ROUNDS = (15,)
    TIMES = (0, 12, 20)                  # 0 = the host turns the cards, otherwise automatic
    INPUT_PHASES = ()

    def __init__(self, code: str):
        super().__init__(code)
        self.hands: dict[str, list[tuple[str, str]]] = {}
        self.pyramid: list[tuple[str, str]] = []
        self.turned = 0
        self.give_rows = 1               # 1 = rows 2 and 4 hand out sips instead of drinking

    def configure_more(self, settings: dict) -> None:
        give = settings.get("give")
        self.give_rows = 0 if give is not None and int(give) == 0 else 1

    def settings_view(self) -> dict:
        return {"seconds": self.seconds, "give": self.give_rows}

    def start(self) -> None:
        if len(self.gamers) > self.MAX_PLAYERS:
            raise RuleError(f"Maximal {self.MAX_PLAYERS} Spieler – sonst reichen die Karten nicht")
        deck = [(r, s) for s in SUITS for r in RANKS]
        random.shuffle(deck)
        self.hands = {p.id: [deck.pop() for _ in range(HAND)] for p in self.gamers}
        self.pyramid = [deck.pop() for _ in range(sum(ROWS))]
        self.turned = 0
        super().start()

    @staticmethod
    def row_of(index: int) -> int:
        """Row 1 (bottom, 5 cards) … row 5 (top, 1 card)."""
        total = 0
        for row, size in enumerate(ROWS, 1):
            total += size
            if index < total:
                return row
        return len(ROWS)

    def give(self, row: int) -> bool:
        return bool(self.give_rows) and row % 2 == 0

    def setup_round(self) -> None:
        # Round n turns pyramid card n-1.
        index = self.turned
        self.turned += 1
        rank = self.pyramid[index][0]
        row = self.row_of(index)
        for p in self.gamers:
            hits = sum(1 for card in self.hands.get(p.id, []) if card[0] == rank)
            if hits:
                p.gained = hits * row
                if not self.give(row):
                    p.score += p.gained
        self.phase = "reveal"
        self.phase_end = time.time() + self.seconds if self.seconds else 0.0

    def on_deadline(self) -> None:
        if self.state == "playing" and self.phase == "reveal":
            if self.turned >= len(self.pyramid):
                self.finish()
            else:
                self.next_round()

    def advance(self) -> None:
        pass

    def play(self, player, msg: dict) -> None:
        raise RuleError("Gerade nicht möglich")

    def view_for(self, viewer_id) -> dict:
        view = super().view_for(viewer_id)
        last = self.turned - 1
        row = self.row_of(last) if last >= 0 else 1
        view.update(
            pyramid=[{"rank": c[0], "suit": c[1]} if i < self.turned else None for i, c in enumerate(self.pyramid)],
            last=last, row=row, give=self.give(row), rows=ROWS, rounds=len(self.pyramid),
            hand=[{"rank": r, "suit": s} for r, s in self.hands.get(viewer_id, [])],
            hits={p.id: p.gained for p in self.gamers if p.gained},
            hands={pid: [{"rank": r, "suit": s} for r, s in cards] for pid, cards in self.hands.items()} if self.state == "finished" else {},
        )
        return view


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
