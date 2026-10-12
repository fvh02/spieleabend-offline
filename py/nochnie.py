"""Ich hab noch nie …: a statement, everyone answers secretly – whoever has done it drinks."""

import random

from common import RuleError
from party import PartyGame

MILD = [
    "… eine ganze Serie an einem Wochenende durchgeschaut.",
    "… im Kino geweint.",
    "… mich auf einer Party in der Küche versteckt.",
    "… beim Karaoke gesungen.",
    "… eine Pflanze sterben lassen.",
    "… eine Sprachnachricht über fünf Minuten verschickt.",
    "… meinen eigenen Geburtstag vergessen.",
    "… einen Flug verpasst.",
    "… in einem Escape Room festgesteckt.",
    "… im Urlaub einen Sonnenbrand bekommen.",
    "… ein Geschenk weiterverschenkt.",
    "… beim Monopoly geschummelt.",
    "… einen Kuchen anbrennen lassen.",
    "… im Schlafanzug einkaufen gewesen.",
    "… mich im Spiegel angesprochen.",
    "… mit einem Tier gesprochen, als wäre es ein Mensch.",
    "… einen Promi getroffen.",
    "… ein Lied auswendig gelernt, das ich peinlich finde.",
    "… meinen Schlüssel im Kühlschrank gefunden.",
    "… so getan, als würde ich telefonieren.",
    "… mich vor einem Nachbarn versteckt.",
    "… im Zug meine Station verschlafen.",
    "… eine Wette verloren.",
    "… beim Arzt gelogen, wie viel Sport ich mache.",
    "… ein Möbelstück falsch zusammengebaut.",
    "… im Restaurant das Essen anderer probiert, ohne zu fragen.",
    "… einen Film nur wegen des Trailers geschaut – und es bereut.",
    "… mich verlaufen, obwohl ich ein Navi hatte.",
    "… vor einer Spinne die Flucht ergriffen.",
    "… einen Tanzkurs gemacht.",
    "… im Fitnessstudio ein Jahresabo abgeschlossen und kaum genutzt.",
    "… ein Selfie mit einem Fremden gemacht.",
    "… einen Kaffee über die Tastatur gekippt.",
    "… heimlich die letzte Süßigkeit gegessen.",
    "… mir die Haare selbst geschnitten.",
    "… an einem Gewinnspiel teilgenommen – und gewonnen.",
    "… etwas online bestellt und nie zurückgeschickt, obwohl es nicht passte.",
    "… auf einem Festival gezeltet.",
    "… einen Marathon gelaufen.",
    "… ein Instrument angefangen und wieder aufgegeben.",
    "… mich in einer fremden Stadt ausgesperrt.",
    "… nachts um drei Uhr gekocht.",
    "… einen ganzen Tag im Bett verbracht.",
    "… eine Fahrradpanne selbst repariert.",
    "… im Schnee einen Engel gemacht.",
]
SPICY = [
    "… einem Date erzählt, ich hätte einen Termin, um früher zu gehen.",
    "… jemanden geghostet.",
    "… die Nachrichten einer anderen Person heimlich gelesen.",
    "… eine Ausrede erfunden, um nicht zu einer Party zu müssen.",
    "… bei einem Vorstellungsgespräch übertrieben.",
    "… mich in jemanden aus dieser Runde verknallt.",
    "… den Namen eines Dates vergessen.",
    "… ein Date nur wegen des Essens zugesagt.",
    "… eine peinliche Nachricht an die falsche Person geschickt.",
    "… einen Kater mit „Ich bin krank“ entschuldigt.",
    "… mit meinem Ex wieder etwas angefangen.",
    "… auf einer Hochzeit zu viel getrunken.",
    "… jemandem ein Kompliment gemacht, das ich nicht ernst meinte.",
    "… heimlich das Profil eines Ex angeschaut.",
    "… auf Tinder oder einer anderen Dating-App gewischt.",
    "… beim Flaschendrehen mitgespielt.",
    "… eine Nacht durchgefeiert und direkt zur Arbeit gegangen.",
    "… mich auf einer Party mit fremden Leuten angefreundet und nie wieder gesehen.",
    "… einen Liebesbrief geschrieben.",
    "… gelogen, wie alt ich bin.",
]


class Game(PartyGame):
    KIND = "nochnie"
    MIN_PLAYERS, MAX_PLAYERS = 2, 16
    ROUNDS = (15, 10, 20, 30)
    TIMES = (20, 15, 30, 0)
    INPUT_PHASES = ("answer",)

    def __init__(self, code: str):
        super().__init__(code)
        self.spicy = 0
        self.statement = ""

    def configure_more(self, settings: dict) -> None:
        spicy = settings.get("spicy")
        self.spicy = 1 if spicy is not None and int(spicy) == 1 else 0

    def settings_view(self) -> dict:
        return {**super().settings_view(), "spicy": self.spicy}

    def setup_round(self) -> None:
        source = MILD + SPICY if self.spicy else MILD
        pool = [s for s in source if s not in self.used] or source
        self.statement = random.choice(pool)
        self.used.add(self.statement)
        self.begin("answer")

    def play(self, player, msg: dict) -> None:
        if msg.get("t") != "answer":
            raise RuleError("Unbekannte Aktion")
        player.answer = bool(msg.get("yes"))
        if self.done("answer"):
            self.advance()

    def bot_step(self, bot) -> None:
        bot.answer = False
        if self.done("answer"):
            self.advance()

    def advance(self) -> None:
        for p in self.gamers:
            if p.answer is True:
                p.gained = 1
                p.score += 1  # sips: whoever "has" drinks
        self.begin("reveal", timed=False)

    def finish(self) -> None:
        self.state = "finished"
        self.phase_end = 0.0
        top = max(self.gamers, key=lambda p: p.score, default=None)
        if top and top.score:
            self.note(f"🍻 {top.name} hat am meisten erlebt ({top.score} Schlucke)")

    def extra_view(self, me) -> dict:
        reveal = self.phase == "reveal"
        return {
            "statement": self.statement,
            "drinkers": [p.id for p in self.gamers if p.answer is True] if reveal else [],
            "my_answer": me.answer if me else None,
        }


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
