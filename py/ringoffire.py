"""Ring of Fire: draw a card in turn – every card has a drinking rule. The 4th King empties the cup."""

import random

from common import RuleError
from party import PartyGame

SUITS = ["♥", "♦", "♣", "♠"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "B", "D", "K"]
RULES = {
    "A": ("Wasserfall", "Alle trinken gleichzeitig. Du hörst als Erste:r auf – die anderen erst, wenn die Person vor ihnen aufhört."),
    "2": ("Du", "Bestimme jemanden, der trinkt."),
    "3": ("Ich", "Du trinkst selbst."),
    "4": ("Boden", "Alle berühren den Boden – wer zuletzt dran ist, trinkt."),
    "5": ("Daumenmeister", "Wann immer du unauffällig den Daumen auf den Tisch legst, müssen alle nachmachen. Wer zuletzt reagiert, trinkt. Gilt bis zur nächsten 5."),
    "6": ("Himmel", "Alle zeigen nach oben – wer zuletzt zeigt, trinkt."),
    "7": ("Kategorie", "Nenne eine Kategorie (z. B. Automarken). Reihum nennt jeder etwas dazu – wer nichts weiß, trinkt."),
    "8": ("Trinkpartner", "Wähle eine Person: Immer wenn du trinkst, trinkt sie mit. Gilt bis zur nächsten 8."),
    "9": ("Reim", "Sag ein Wort, reihum wird gereimt – wer keinen Reim findet, trinkt."),
    "10": ("Regel", "Stell eine neue Regel auf (z. B. kein „Ja“ sagen). Wer sie bricht, trinkt."),
    "B": ("Ich hab noch nie", "Alle heben drei Finger. Reihum sagt jeder „Ich hab noch nie …“ – wer es schon hat, senkt einen Finger. Keine Finger mehr: trinken."),
    "D": ("Fragemeister", "Bis zur nächsten Dame: Wer auf deine Frage antwortet, trinkt."),
    "K": ("King's Cup", "Gieß einen Schluck deines Getränks in den Becher in der Mitte. Wer den vierten König zieht, trinkt den Becher aus!"),
}


class Game(PartyGame):
    KIND = "ringoffire"
    MIN_PLAYERS, MAX_PLAYERS = 2, 16
    ROUNDS = (52,)
    TIMES = (0,)
    INPUT_PHASES = ("draw",)

    def __init__(self, code: str):
        super().__init__(code)
        self.deck: list[tuple[str, str]] = []
        self.order: list[str] = []
        self.turn = 0
        self.active: str | None = None
        self.card = None            # last drawn (rank, suit)
        self.drawn_by: str | None = None
        self.kings = 0
        self.history: list[dict] = []
        self.holders: dict[str, str] = {}   # "5" / "8" / "D" -> player id holding that role

    def settings_view(self) -> dict:
        return {}

    def start(self) -> None:
        self.deck = [(r, s) for s in SUITS for r in RANKS]
        random.shuffle(self.deck)
        self.order = [p.id for p in self.gamers]
        random.shuffle(self.order)
        self.turn, self.kings, self.card, self.drawn_by = 0, 0, None, None
        self.history, self.holders = [], {}
        super().start()

    def setup_round(self) -> None:
        humans = [pid for pid in self.order if self.player(pid) and not self.player(pid).is_bot] or self.order
        while self.order[self.turn % len(self.order)] not in humans:
            self.turn += 1
        self.active = self.order[self.turn % len(self.order)]
        self.begin("draw", timed=False)

    def next_round(self) -> None:
        self.round += 1
        self.setup_round()

    def play(self, player, msg: dict) -> None:
        if msg.get("t") != "draw":
            raise RuleError("Unbekannte Aktion")
        if player.id != self.active:
            raise RuleError(f"{self.player(self.active).name} ist dran")
        self.advance()

    def advance(self) -> None:
        if not self.deck:
            self.finish()
            return
        rank, suit = self.deck.pop()
        self.card, self.drawn_by = (rank, suit), self.active
        drawer = self.player(self.active)
        if rank == "K":
            self.kings += 1
        if rank in ("5", "8", "D"):
            self.holders[rank] = self.active
        title = RULES[rank][0]
        self.history.append({"rank": rank, "suit": suit, "by": self.active})
        self.turn += 1
        if drawer:
            drawer.score += 1
        if rank == "K" and self.kings == 4:
            self.note(f"👑 {drawer.name if drawer else '?'} zieht den vierten König – Becher austrinken!")
            self.finish()
            return
        self.note(f"{drawer.name if drawer else '?'}: {title}")
        if not self.deck:
            self.finish()
            return
        self.setup_round()

    # Placeholders draw for themselves so the table never waits.
    def pending_bots(self) -> list:
        active = self.player(self.active) if self.active else None
        return [active] if self.state == "playing" and active and active.is_bot else []

    def bot_step(self, bot) -> None:
        self.advance()

    def finish(self) -> None:
        self.state = "finished"
        self.phase_end = 0.0

    def view_for(self, viewer_id) -> dict:
        view = super().view_for(viewer_id)
        rank = self.card[0] if self.card else None
        view.update(
            active=self.active, left=len(self.deck), kings=self.kings, drawn_by=self.drawn_by,
            card={"rank": rank, "suit": self.card[1], "title": RULES[rank][0], "rule": RULES[rank][1]} if self.card else None,
            history=self.history[-8:][::-1], holders=self.holders, rules={r: RULES[r][0] for r in RANKS},
        )
        for p in view["players"]:
            p["done"] = p["id"] == self.active
        return view


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
