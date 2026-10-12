"""Wer würde eher …? Everyone votes for the player who fits the question best – then the big reveal."""

import random

from common import RuleError
from party import PartyGame

QUESTIONS = [
    "… nachts in einen Zoo einbrechen, um die Pinguine zu streicheln?",
    "… bei einer Quizshow eine Million gewinnen?",
    "… beim Wandern verloren gehen?",
    "… den eigenen Geburtstag vergessen?",
    "… einen Kaktus umbringen?",
    "… im Supermarkt das Auto vergessen?",
    "… bei einer Zombie-Apokalypse als Erstes erwischt werden?",
    "… bei einer Zombie-Apokalypse als Letztes übrig bleiben?",
    "… eine Woche nur von Pizza leben?",
    "… heimlich die Serie weiterschauen, die man zusammen schaut?",
    "… mit einem Promi ein Selfie machen und es nie posten?",
    "… beim Karaoke das Mikro nicht mehr hergeben?",
    "… die eigene Hochzeit verschlafen?",
    "… einen Streit mit einem Navi anfangen?",
    "… im Urlaub nur im Hotelzimmer bleiben?",
    "… sich einen Bart oder eine Frisur für eine Wette wachsen lassen?",
    "… auf einer Party als Erstes einschlafen?",
    "… als Letztes die Party verlassen?",
    "… ein Haustier nach einem Essen benennen?",
    "… einen Liebesbrief an die Lieblingsband schreiben?",
    "… beim Monopoly schummeln?",
    "… sich bei „Schlag den Star“ blamieren?",
    "… die Fernbedienung im Kühlschrank verstecken – aus Versehen?",
    "… in einer Reality-Show mitmachen?",
    "… nach Hollywood ziehen, um berühmt zu werden?",
    "… einen Marathon laufen?",
    "… beim Kochen die Küche abfackeln?",
    "… 50 Tabs im Browser offen haben?",
    "… beim Escape-Room als Erstes in Panik geraten?",
    "… die Antwort auf jede Quizfrage googeln wollen?",
    "… auf dem Flohmarkt etwas völlig Unnützes kaufen?",
    "… Weihnachtsgeschenke am 24. Dezember mittags kaufen?",
    "… den Spoiler zu einer Serie verraten?",
    "… mit Pflanzen reden?",
    "… sich auf einer Hochzeit danebenbenehmen?",
    "… im Kino laut mitfiebern?",
    "… jemanden mit dem falschen Namen ansprechen – und es nie korrigieren?",
    "… eine Sprachnachricht von 10 Minuten schicken?",
    "… auf eine einsame Insel ein Ladekabel mitnehmen statt Essen?",
    "… einen eigenen Podcast starten?",
    "… bei einem Horrorfilm die Augen zuhalten?",
    "… ein Tattoo mit einem Rechtschreibfehler haben?",
    "… im Fitnessstudio nur Selfies machen?",
    "… beim Spieleabend schlecht verlieren?",
    "… einen Wecker 10-mal auf Schlummern drücken?",
    "… das letzte Stück Pizza nehmen, ohne zu fragen?",
    "… sich in einer Großstadt ohne Handy zurechtfinden?",
    "… bei Glatteis als Erstes hinfallen?",
    "… im Restaurant das Essen zurückgehen lassen?",
    "… Präsident oder Kanzlerin werden?",
    "… in einer Band berühmt werden?",
    "… auswandern und ein Café am Strand eröffnen?",
    "… einen Pullover mit dem eigenen Gesicht tragen?",
    "… morgens um 5 Uhr freiwillig joggen gehen?",
    "… den Notruf wegen einer Spinne wählen?",
    "… eine Wette verlieren und es nie zugeben?",
    "… bei Ikea verloren gehen?",
    "… beim ersten Date über die Ex sprechen?",
    "… mit einem Einhorn-Kostüm einkaufen gehen?",
    "… das Geheimnis eines Freundes ausplaudern?",
    "… ohne Navi den Weg finden?",
    "… einen Kuchen backen, der gelingt?",
    "… sich in einen Schauspieler oder eine Schauspielerin verlieben?",
    "… eine Woche ohne Handy aushalten?",
    "… die eigenen Pflanzen mit Cola gießen?",
    "… auf dem Festival die Gummistiefel vergessen?",
    "… einen Tanz-Wettbewerb gewinnen?",
    "… sich im Hotel aussperren – im Bademantel?",
    "… heimlich die Hälfte der Chips allein essen?",
    "… bei „Wer wird Millionär?“ den Publikumsjoker bei der ersten Frage nehmen?",
]


class Game(PartyGame):
    KIND = "werwuerde"
    MIN_PLAYERS, MAX_PLAYERS = 3, 16
    ROUNDS = (10, 5, 15, 20)
    TIMES = (30, 20, 45, 0)
    INPUT_PHASES = ("vote",)

    def __init__(self, code: str):
        super().__init__(code)
        self.question = ""
        self.points = 1      # 1 = a point for voting with the majority, 0 = just for fun
        self.anonymous = 1   # 1 = nobody sees who voted for whom
        self.tally: dict[str, int] = {}
        self.titles: list[dict] = []

    def configure_more(self, settings: dict) -> None:
        points = settings.get("points")
        self.points = 0 if points is not None and int(points) == 0 else 1
        anonymous = settings.get("anonymous")
        self.anonymous = 0 if anonymous is not None and int(anonymous) == 0 else 1

    def settings_view(self) -> dict:
        return {**super().settings_view(), "points": self.points, "anonymous": self.anonymous}

    def start(self) -> None:
        self.titles = []
        super().start()

    def setup_round(self) -> None:
        pool = [q for q in QUESTIONS if q not in self.used] or QUESTIONS
        self.question = random.choice(pool)
        self.used.add(self.question)
        self.tally = {}
        self.begin("vote")

    def phase_attr(self) -> str:
        return "pick"

    def play(self, player, msg: dict) -> None:
        if msg.get("t") != "vote":
            raise RuleError("Unbekannte Aktion")
        target = self.player(str(msg.get("id")))
        if not target or target.screen:
            raise RuleError("Bitte einen Mitspieler wählen")
        player.pick = target.id  # changing the vote is allowed until everyone voted
        if self.done("pick"):
            self.advance()

    def advance(self) -> None:
        tally: dict[str, int] = {}
        for p in self.gamers:
            if p.pick:
                tally[p.pick] = tally.get(p.pick, 0) + 1
        self.tally = tally
        top = max(tally.values(), default=0)
        winners = [pid for pid, n in tally.items() if n == top] if top else []
        if self.points and winners:
            for p in self.gamers:
                if p.pick in winners:
                    p.gained = 1
                    p.score += 1
        names = [self.player(pid).name for pid in winners if self.player(pid)]
        self.titles.append({"question": self.question, "names": names, "votes": top})
        self.begin("reveal", timed=False)
        if names:
            self.note(f"{' & '.join(names)} – {self.question}")

    def extra_view(self, me) -> dict:
        reveal = self.phase == "reveal" or self.state == "finished"
        return {
            "question": self.question,
            "tally": self.tally if reveal else {},
            "picks": {p.id: p.pick for p in self.gamers} if reveal and not self.anonymous else {},
            "my_pick": me.pick if me else None,
            "titles": self.titles,
        }


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
