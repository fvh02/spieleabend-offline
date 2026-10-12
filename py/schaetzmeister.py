"""Schätzmeister: an estimation question, everyone types a number – the closest guesses score."""

import random
import re

from common import RuleError
from party import PartyGame

# (question, answer, unit, note) – answers are commonly cited values, rounded where it says "etwa".
QUESTIONS = [
    ("Wie hoch ist der Mount Everest?", 8849, "m", ""),
    ("Wie hoch ist die Zugspitze?", 2962, "m", ""),
    ("Wie hoch ist der Kilimandscharo?", 5895, "m", ""),
    ("Wie hoch ist der Eiffelturm mit Antennen?", 330, "m", ""),
    ("Wie hoch ist der Kölner Dom?", 157, "m", ""),
    ("Wie hoch ist das Burj Khalifa in Dubai?", 828, "m", ""),
    ("Wie viele Stockwerke hat das Burj Khalifa?", 163, "", ""),
    ("Wie hoch ist das Brandenburger Tor?", 26, "m", ""),
    ("Wie lang ist der Rhein?", 1233, "km", ""),
    ("Wie lang ist der Panamakanal?", 82, "km", "etwa"),
    ("Wie weit ist der Mond im Mittel von der Erde entfernt?", 384400, "km", ""),
    ("Wie viele Kilometer misst der Erdumfang am Äquator?", 40075, "km", ""),
    ("Wie groß ist der Durchmesser der Erde?", 12742, "km", "im Mittel"),
    ("Wie tief ist die tiefste Stelle des Marianengrabens?", 10994, "m", "etwa"),
    ("Wie lang ist die Chinesische Mauer mit allen Abschnitten?", 21196, "km", "laut Vermessung 2012"),
    ("Wie groß ist Deutschland?", 357600, "km²", "etwa"),
    ("Wie groß ist der Bodensee?", 536, "km²", ""),
    ("Wie weit ist es von Berlin nach München – Luftlinie?", 504, "km", "etwa"),
    ("Wie viele Kilometer Autobahn gibt es in Deutschland?", 13200, "km", "etwa"),
    ("Wie lang ist ein Fußballfeld bei einer WM?", 105, "m", ""),
    ("Wie lang ist ein Marathon?", 42195, "m", ""),
    ("Wie schnell ist das Licht?", 299792, "km/s", ""),
    ("Wie viele Sekunden braucht das Sonnenlicht bis zur Erde?", 499, "s", "etwa 8 Minuten 19 Sekunden"),
    ("Wie viele Tage braucht der Mond für eine Runde um die Erde?", 27.3, "Tage", "siderisch"),
    ("Wie alt ist das Universum?", 13.8, "Mrd. Jahre", ""),
    ("Wie viel Prozent der Erdoberfläche sind mit Wasser bedeckt?", 71, "%", ""),
    ("Wie viele Länder sind Mitglied der Vereinten Nationen?", 193, "", ""),
    ("Wie viele Sprachen gibt es auf der Welt?", 7000, "", "etwa"),
    ("Wie viele Menschen leben auf der Erde?", 8.1, "Mrd.", "etwa, 2024"),
    ("Wie viele Menschen leben in Deutschland?", 84, "Mio.", "etwa"),
    ("Wie viele Menschen leben in Berlin?", 3.8, "Mio.", "etwa"),
    ("In welchem Jahr fiel die Berliner Mauer?", 1989, "", ""),
    ("In welchem Jahr wurde die Bundesrepublik Deutschland gegründet?", 1949, "", ""),
    ("In welchem Jahr landeten die ersten Menschen auf dem Mond?", 1969, "", ""),
    ("In welchem Jahr sank die Titanic?", 1912, "", ""),
    ("In welchem Jahr fand die erste Fußball-WM statt?", 1930, "", ""),
    ("In welchem Jahr wurde das Euro-Bargeld eingeführt?", 2002, "", ""),
    ("In welchem Jahr wurde Google gegründet?", 1998, "", ""),
    ("In welchem Jahr wurde das erste iPhone vorgestellt?", 2007, "", ""),
    ("In welchem Jahr erschien das erste Harry-Potter-Buch?", 1997, "", ""),
    ("In welchem Jahr wurde Coca-Cola erfunden?", 1886, "", ""),
    ("In welchem Jahr wurde Albert Einstein geboren?", 1879, "", ""),
    ("Um welches Jahr druckte Gutenberg mit beweglichen Lettern?", 1450, "", "etwa"),
    ("Wie alt wurde Johann Wolfgang von Goethe?", 82, "Jahre", ""),
    ("Wie viele Knochen hat ein erwachsener Mensch?", 206, "", ""),
    ("Wie viele Zähne hat ein Erwachsener mit Weisheitszähnen?", 32, "", ""),
    ("Wie viele Liter Blut hat ein erwachsener Mensch?", 5, "Liter", "etwa"),
    ("Wie viele Haare wachsen auf einem menschlichen Kopf?", 100000, "", "etwa"),
    ("Wie viele Herzen hat ein Oktopus?", 3, "", ""),
    ("Wie viele Tasten hat ein Klavier?", 88, "", ""),
    ("Wie viele Sinfonien hat Beethoven komponiert?", 9, "", ""),
    ("Wie viele Felder hat ein Schachbrett?", 64, "", ""),
    ("Wie viele Karten hat ein Skatblatt?", 32, "", ""),
    ("Wie viele Augen hat ein normaler Spielwürfel zusammen?", 21, "", ""),
    ("Wie viele Sterne sind auf der Europaflagge?", 12, "", ""),
    ("Wie viele Streifen hat die Flagge der USA?", 13, "", ""),
    ("Wie viele Minuten hat eine Woche?", 10080, "", ""),
    ("Wie viele Sekunden hat ein Tag?", 86400, "", ""),
    ("Bei wie viel Grad Fahrenheit kocht Wasser?", 212, "°F", ""),
    ("Wie viele Kalorien haben 100 g Butter?", 740, "kcal", "etwa"),
    ("Wie viele Tore fielen beim WM-Halbfinale Brasilien gegen Deutschland 2014?", 8, "", "7:1"),
    ("Wie viele Stufen führen im Kölner Dom auf die Aussichtsplattform?", 533, "", ""),
    ("Wie viele Monde hat der Mars?", 2, "", ""),
    ("Wie viele Minuten dauert ein Handballspiel ohne Verlängerung?", 60, "min", ""),
]


def parse_number(text: str) -> float | None:
    """German or English notation: "384.400", "8,1", "8.1", "1 000"."""
    raw = text.strip().replace(" ", "").replace("\u202f", "").replace("'", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", raw):
        raw = raw.replace(".", "")  # thousands separators
    try:
        return float(raw)
    except ValueError:
        return None


class Game(PartyGame):
    KIND = "schaetzmeister"
    MIN_PLAYERS, MAX_PLAYERS = 2, 16
    ROUNDS = (8, 5, 10, 15)
    TIMES = (45, 30, 60, 0)
    INPUT_PHASES = ("guess",)

    def __init__(self, code: str):
        super().__init__(code)
        self.question = None
        self.ranking: list[dict] = []

    def setup_round(self) -> None:
        pool = [q for q in QUESTIONS if q[0] not in self.used] or QUESTIONS
        self.question = random.choice(pool)
        self.used.add(self.question[0])
        self.ranking = []
        self.begin("guess")

    def play(self, player, msg: dict) -> None:
        if msg.get("t") != "guess":
            raise RuleError("Unbekannte Aktion")
        value = parse_number(str(msg.get("value", "")))
        if value is None:
            raise RuleError("Bitte eine Zahl eingeben")
        if not (-1e12 < value < 1e12):
            raise RuleError("Diese Zahl ist zu groß")
        player.answer = value
        if self.done("answer"):
            self.advance()

    def advance(self) -> None:
        answer = self.question[1]
        guesses = [p for p in self.gamers if isinstance(p.answer, float)]
        guesses.sort(key=lambda p: abs(p.answer - answer))
        # 3 / 2 / 1 points for the three closest (equal distance = equal points), +2 for a bullseye (within 1 %).
        rank, last, ranking = 0, None, []
        for i, p in enumerate(guesses):
            diff = abs(p.answer - answer)
            if diff != last:
                rank, last = i, diff
            points = max(0, 3 - rank)
            exact = diff <= abs(answer) * 0.01
            p.gained = points + (2 if exact else 0)
            p.score += p.gained
            ranking.append({"id": p.id, "value": p.answer, "rank": rank + 1, "points": p.gained, "exact": exact})
        self.ranking = ranking
        self.begin("reveal", timed=False)
        if ranking:
            best = self.player(ranking[0]["id"])
            self.note(f"{best.name} lag am nächsten dran")

    def extra_view(self, me) -> dict:
        q, answer, unit, note = self.question or ("", 0, "", "")
        reveal = self.phase == "reveal"
        return {
            "question": q, "unit": unit,
            "answer": answer if reveal else None, "note": note if reveal else "",
            "ranking": self.ranking if reveal else [],
            "my_answer": me.answer if me and isinstance(me.answer, float) else None,
        }


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
