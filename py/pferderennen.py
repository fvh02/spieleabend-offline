"""Pferderennen: everyone bets sips on one of the four aces. Cards are drawn – the ace of that suit moves
forward. Side cards can throw horses back. Bets on losing horses are drunk, the winners hand out double."""

import random
import time

from common import RuleError
from party import PartyGame

SUITS = ["♥", "♦", "♣", "♠"]
NAMES = {"♥": "Herz", "♦": "Karo", "♣": "Kreuz", "♠": "Pik"}
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "B", "D", "K"]
TRACK = 7                    # side cards; a horse wins when it passes the last one
STEP_SECONDS = 1.6


class Game(PartyGame):
    KIND = "pferderennen"
    MIN_PLAYERS, MAX_PLAYERS = 2, 16
    ROUNDS = (3, 1, 5)
    TIMES = (45, 30, 0)
    INPUT_PHASES = ("bet",)

    def __init__(self, code: str):
        super().__init__(code)
        self.deck: list[tuple[str, str]] = []
        self.side: list[tuple[str, str]] = []
        self.side_open = 0
        self.pos = {s: 0 for s in SUITS}
        self.draw = None
        self.event = ""
        self.winner = ""

    def setup_round(self) -> None:
        deck = [(r, s) for s in SUITS for r in RANKS]
        random.shuffle(deck)
        self.side = [deck.pop() for _ in range(TRACK)]
        self.deck = deck
        self.side_open = 0
        self.pos = {s: 0 for s in SUITS}
        self.draw, self.event, self.winner = None, "", ""
        self.begin("bet")

    def play(self, player, msg: dict) -> None:
        if msg.get("t") != "bet":
            raise RuleError("Unbekannte Aktion")
        suit = msg.get("suit")
        amount = int(msg.get("sips") or 0)
        if suit not in SUITS or not 1 <= amount <= 5:
            raise RuleError("Bitte ein Pferd und 1–5 Schlucke wählen")
        player.answer = {"suit": suit, "sips": amount}
        if self.done("answer"):
            self.advance()

    def bot_step(self, bot) -> None:
        bot.answer = {}            # placeholders don't bet
        if self.done("answer"):
            self.advance()

    def advance(self) -> None:
        """Betting is over: off they go."""
        self.phase = "race"
        self.phase_end = time.time() + STEP_SECONDS

    def on_deadline(self) -> None:
        if self.state != "playing":
            return
        if self.phase == "bet":
            self.advance()
        elif self.phase == "race":
            self.step()

    def step(self) -> None:
        if not self.deck:
            self.end_race(max(self.pos, key=self.pos.get))
            return
        rank, suit = self.deck.pop()
        self.draw = {"rank": rank, "suit": suit}
        self.pos[suit] += 1
        self.event = f"{NAMES[suit]} läuft vor"
        if self.pos[suit] > TRACK:
            self.end_race(suit)
            return
        # Every horse passed the next side card: turn it over, that suit falls back one field.
        if self.side_open < TRACK and min(self.pos.values()) > self.side_open:
            back = self.side[self.side_open]
            self.side_open += 1
            self.pos[back[1]] = max(0, self.pos[back[1]] - 1)
            self.event = f"Seitenkarte {back[0]}{back[1]}: {NAMES[back[1]]} fällt zurück!"
        self.phase_end = time.time() + STEP_SECONDS

    def end_race(self, suit: str) -> None:
        self.winner = suit
        for p in self.gamers:
            bet = p.answer or {}
            if not bet.get("suit"):
                continue
            if bet["suit"] == suit:
                p.gained = -2 * bet["sips"]       # negative = hands out
            else:
                p.gained = bet["sips"]
                p.score += bet["sips"]
        self.phase = "reveal"
        self.phase_end = 0.0
        self.note(f"🏆 {NAMES[suit]} gewinnt das Rennen")

    def view_for(self, viewer_id) -> dict:
        view = super().view_for(viewer_id)
        me = self.player(viewer_id)
        show_bets = self.phase != "bet"
        view.update(
            pos=self.pos, track=TRACK, side=[{"rank": r, "suit": s} if i < self.side_open else None for i, (r, s) in enumerate(self.side)],
            draw=self.draw, event=self.event, winner=self.winner, names=NAMES, left=len(self.deck),
            bets={p.id: p.answer for p in self.gamers if p.answer} if show_bets else {},
            my_bet=me.answer if me else None,
        )
        return view


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
