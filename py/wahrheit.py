"""Wahrheit oder Trinken: in turn, one player gets a question – answer honestly out loud or drink."""

import random

from common import RuleError
from party import PartyGame

QUESTIONS = [
    "Was war dein peinlichster Moment in der Schule?",
    "Welche App benutzt du am meisten – und wie lange am Tag?",
    "Was ist das Seltsamste, das du je gegessen hast?",
    "Wen aus dieser Runde würdest du auf eine einsame Insel mitnehmen?",
    "Was war die schlechteste Ausrede, die du je benutzt hast?",
    "Welchen Song hörst du heimlich in Dauerschleife?",
    "Was ist deine größte Angst?",
    "Was war dein schlimmstes Date?",
    "Welche Lüge hast du deinen Eltern erzählt, die sie bis heute glauben?",
    "Was würdest du mit einer Million Euro als Erstes kaufen?",
    "Welche Gewohnheit von dir nervt andere am meisten?",
    "Wer hier hat den besten Kleidungsstil?",
    "Was ist das Kindischste, das du immer noch machst?",
    "Was war dein peinlichster Versprecher?",
    "Welches Geheimnis hast du am längsten für dich behalten?",
    "Welcher Promi war dein erster Schwarm?",
    "Was ist das Mutigste, das du je gemacht hast?",
    "Was hast du zuletzt gegoogelt?",
    "Welches Essen hasst du, isst es aber trotzdem aus Höflichkeit?",
    "Was war das teuerste, das du je kaputt gemacht hast?",
    "Mit wem aus dieser Runde würdest du eine WG gründen – und mit wem nie?",
    "Was ist dein unnötigstes Talent?",
    "Welche Serie hast du angefangen und dich nie getraut zuzugeben, dass du sie liebst?",
    "Was ist der schlimmste Rat, den du je befolgt hast?",
    "Wann hast du das letzte Mal geweint – und warum?",
    "Was würdest du an dir ändern, wenn du könntest?",
    "Was ist das Peinlichste in deiner Fotogalerie?",
    "Welche Nachricht hast du zuletzt bereut?",
    "Was ist dein Guilty Pleasure?",
    "Wen hast du zuletzt gestalkt – online natürlich?",
    "Was ist das Verrückteste, das du im Urlaub gemacht hast?",
    "Welche Regel hast du als Kind am häufigsten gebrochen?",
    "Was war dein erster Gedanke heute Morgen?",
    "Wen in dieser Runde kennst du am wenigsten – und was willst du über die Person wissen?",
    "Was ist das Netteste, das jemand je für dich getan hat?",
    "Welches Kompliment hörst du am liebsten?",
    "Was war das Letzte, das du heimlich gegessen hast?",
    "Was würdest du tun, wenn du einen Tag unsichtbar wärst?",
    "Welche drei Emojis beschreiben dich am besten?",
    "Was ist die längste Zeit, die du ohne Dusche ausgekommen bist?",
]


class Game(PartyGame):
    KIND = "wahrheit"
    MIN_PLAYERS, MAX_PLAYERS = 2, 16
    ROUNDS = (2, 1, 3, 5)              # rounds = times around the table
    TIMES = (0, 60, 90)
    INPUT_PHASES = ("turn",)

    def __init__(self, code: str):
        super().__init__(code)
        self.order: list[str] = []
        self.turn = 0
        self.active: str | None = None
        self.question = ""
        self.choice = ""                 # "truth" | "drink"
        self.drinks: dict[str, int] = {}

    def start(self) -> None:
        self.order = [p.id for p in self.gamers]
        random.shuffle(self.order)
        self.turn = 0
        super().start()

    @property
    def total_turns(self) -> int:
        return self.rounds * len(self.order)

    def view_round(self) -> int:
        return self.turn // max(1, len(self.order)) + 1

    def next_round(self) -> None:
        self.round += 1
        for p in self.players:
            p.answer = p.pick = None
            p.gained = 0
        self.setup_round()

    def setup_round(self) -> None:
        alive = [pid for pid in self.order if self.player(pid) and not self.player(pid).is_bot] or self.order
        while self.order[self.turn % len(self.order)] not in alive:
            self.turn += 1
        self.active = self.order[self.turn % len(self.order)]
        self.turn += 1
        pool = [q for q in QUESTIONS if q not in self.used] or QUESTIONS
        self.question = random.choice(pool)
        self.used.add(self.question)
        self.choice = ""
        self.begin("turn")

    def act(self, player_id: str, msg: dict, is_host: bool) -> None:
        if msg.get("t") == "next" and self.state == "playing" and self.phase == "reveal":
            if not is_host and player_id != self.active:
                raise RuleError("Der Gastgeber oder der Spieler am Zug geht weiter")
            if self.turn >= self.total_turns:
                self.finish()
            else:
                self.next_round()
            return
        super().act(player_id, msg, is_host)

    def play(self, player, msg: dict) -> None:
        if player.id != self.active:
            raise RuleError("Gerade ist jemand anderes dran")
        if msg.get("t") == "new_question":
            if self.choice:
                raise RuleError("Schon entschieden")
            others = [q for q in QUESTIONS if q != self.question]
            self.question = random.choice(others)
            return
        if msg.get("t") != "choose" or msg.get("choice") not in ("truth", "drink"):
            raise RuleError("Unbekannte Aktion")
        self.choice = msg["choice"]
        self.advance()

    def advance(self) -> None:
        active = self.player(self.active)
        if not self.choice:
            self.choice = "drink"        # time is up: drink
        if self.choice == "drink" and active:
            active.gained = 1
            active.score += 1
        self.begin("reveal", timed=False)

    def pending_bots(self) -> list:
        active = self.player(self.active) if self.active else None
        return [active] if self.state == "playing" and self.phase == "turn" and active and active.is_bot else []

    def bot_step(self, bot) -> None:
        self.choice = "drink"
        self.advance()

    def finish(self) -> None:
        self.state = "finished"
        self.phase_end = 0.0
        honest = min(self.gamers, key=lambda p: p.score, default=None)
        if honest:
            self.note(f"😇 {honest.name} war am ehrlichsten")

    def view_for(self, viewer_id) -> dict:
        view = super().view_for(viewer_id)
        view.update(round=self.view_round(), rounds=self.rounds, turn=self.turn, total_turns=self.total_turns,
                    active=self.active, question=self.question, choice=self.choice)
        for p in view["players"]:
            p["done"] = p["id"] == self.active and bool(self.choice)
        return view


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
