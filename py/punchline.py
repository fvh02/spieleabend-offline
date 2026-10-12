"""Punchline: everyone completes the same sentence as funnily as possible, then all vote for the best one."""

import random

from common import RuleError
from party import PartyGame, clean, normalize

PROMPTS = [
    "Das Schlimmste, was man beim ersten Date sagen kann: „___“",
    "Der neue Werbeslogan der Deutschen Bahn: „___“",
    "Was Oma wirklich in ihrer Handtasche versteckt: ___",
    "Der schlechteste Name für ein Kreuzfahrtschiff: ___",
    "Die geheime Zutat in Mamas Kartoffelsalat: ___",
    "Was der Hund denkt, wenn wir das Haus verlassen: „___“",
    "Das unnötigste Produkt im Teleshopping: ___",
    "Die kürzeste Horrorgeschichte der Welt: „___“",
    "Ein Satz, den man nie bei einer Beerdigung sagen sollte: „___“",
    "Was wirklich im Bermudadreieck passiert: ___",
    "Der Grund, warum Dinosaurier ausgestorben sind: ___",
    "Die schlechteste Ausrede fürs Zuspätkommen: „___“",
    "Das Motto der nächsten Firmenfeier: ___",
    "Was in der Schublade mit den Kabeln wirklich lebt: ___",
    "Der neue Geschmack von Ritter Sport: ___",
    "Das Erste, was Aliens bei uns sehen sollten: ___",
    "Der schlechteste Tipp eines Fitnesstrainers: „___“",
    "Wenn mein Leben ein Film wäre, hieße er: „___“",
    "Die neueste olympische Disziplin: ___",
    "Was der Navi wirklich sagen will: „___“",
    "Das schlechteste Geschenk zum Hochzeitstag: ___",
    "Der Titel meiner Autobiografie: „___“",
    "Die neueste Regel im Kleingartenverein: „___“",
    "Was Katzen nachts heimlich machen: ___",
    "Der Satz, mit dem jede Familienfeier eskaliert: „___“",
    "Das schlimmste Hobby für einen Nachbarn: ___",
    "Was in jedem deutschen Keller zu finden ist: ___",
    "Der Inhalt des 11. Gebots: „Du sollst nicht ___“",
    "Der neue Superheld aus Deutschland: Captain ___",
    "Was der Weihnachtsmann im Rest des Jahres macht: ___",
    "Das ehrlichste Hotel-Motto: „___“",
    "Die neueste Funktion im nächsten Smartphone: ___",
    "Was man auf einer einsamen Insel garantiert nicht braucht: ___",
    "Die schlechteste Idee für ein Tattoo: ___",
    "Der Grund, warum der Drucker nie funktioniert: ___",
    "Das schlechteste Lied für den Hochzeitstanz: ___",
    "Ein Satz, den man nie zu einem Polizisten sagen sollte: „___“",
    "Die geheime Botschaft auf der Rückseite der Mona Lisa: „___“",
    "Was die Ente im Park über uns denkt: „___“",
    "Das neue Unterrichtsfach an deutschen Schulen: ___",
    "Der Grund, warum mein WLAN so langsam ist: ___",
    "Der schlechteste Name für ein Restaurant: ___",
    "Der Untertitel von „Der Herr der Ringe 4“: ___",
    "Was in der Kantine heute wirklich auf dem Teller liegt: ___",
    "Die schlimmste Nachricht, die der Pilot durchsagen kann: „___“",
    "Das beste Argument gegen Montage: ___",
    "Das Geheimnis eines langen Lebens: ___",
    "Die neueste Sendung im Nachmittagsprogramm: „___“",
    "Das schlechteste Thema für einen Smalltalk: ___",
    "Was der Bauarbeiter wirklich hinter dem Bauzaun macht: ___",
    "Mein Plan für die Zombie-Apokalypse: ___",
    "Die schlechteste Pizza-Kombination: Pizza mit ___",
    "Was ein Influencer zum Frühstück isst: ___",
    "Der Satz, der jeden Spieleabend ruiniert: „___“",
    "Das eigentliche Ende von „Titanic“: ___",
    "Die neue Bundesbehörde für ___",
    "Was Socken in der Waschmaschine wirklich machen: ___",
    "Das schlechteste Motto für einen Junggesellenabschied: „___“",
    "Der schlechteste Ort für einen Heiratsantrag: ___",
    "Der neue Duft von Tchibo: Eau de ___",
]


class Game(PartyGame):
    KIND = "punchline"
    MIN_PLAYERS, MAX_PLAYERS = 3, 12
    ROUNDS = (6, 4, 8, 10)
    TIMES = (75, 60, 120, 0)
    INPUT_PHASES = ("write", "vote")

    def __init__(self, code: str):
        super().__init__(code)
        self.prompt = ""
        self.entries: list[dict] = []   # {"id", "text", "author"}
        self.best: list[str] = []
        self.hall: list[dict] = []      # best line of each round

    def start(self) -> None:
        self.hall = []
        super().start()

    def setup_round(self) -> None:
        pool = [p for p in PROMPTS if p not in self.used] or PROMPTS
        self.prompt = random.choice(pool)
        self.used.add(self.prompt)
        self.entries, self.best = [], []
        self.begin("write")

    def phase_attr(self) -> str:
        return "answer" if self.phase == "write" else "pick"

    def play(self, player, msg: dict) -> None:
        kind = msg.get("t")
        if self.phase == "write" and kind == "write":
            text = clean(msg.get("text"), 80)
            if not normalize(text):
                raise RuleError("Bitte etwas eingeben")
            player.answer = text
            if self.done("answer"):
                self.advance()
        elif self.phase == "vote" and kind == "vote":
            entry = next((e for e in self.entries if e["id"] == msg.get("id")), None)
            if not entry:
                raise RuleError("Diese Antwort gibt es nicht")
            if entry["author"] == player.id:
                raise RuleError("Für dich selbst stimmen gilt nicht 😉")
            player.pick = entry["id"]
            if self.done("pick"):
                self.advance()
        else:
            raise RuleError("Gerade nicht möglich")

    def advance(self) -> None:
        if self.phase == "write":
            entries = [{"text": p.answer, "author": p.id} for p in self.gamers if p.answer]
            random.shuffle(entries)
            for n, e in enumerate(entries):
                e["id"] = f"e{n}"
            self.entries = entries
            for p in self.gamers:
                # Placeholders and anyone who wrote the only answer have nothing to vote for.
                others = [e for e in entries if e["author"] != p.id]
                p.pick = "" if p.is_bot or not others else None
            if len(entries) < 2 or self.done("pick"):
                self.score_round()
            else:
                self.begin("vote")
        elif self.phase == "vote":
            self.score_round()

    def score_round(self) -> None:
        votes = {e["id"]: 0 for e in self.entries}
        for p in self.gamers:
            if p.pick in votes:
                votes[p.pick] += 1
        for e in self.entries:
            e["votes"] = votes[e["id"]]
        top = max(votes.values(), default=0)
        self.best = [eid for eid, n in votes.items() if n == top and top > 0]
        for e in self.entries:
            author = self.player(e["author"])
            if author:
                author.gained = e["votes"] * 100 + (100 if e["id"] in self.best and len(self.best) == 1 else 0)
                author.score += author.gained
        for eid in self.best:
            e = next(x for x in self.entries if x["id"] == eid)
            author = self.player(e["author"])
            self.hall.append({"prompt": self.prompt, "text": e["text"], "name": author.name if author else "?"})
        self.begin("reveal", timed=False)

    def extra_view(self, me) -> dict:
        reveal = self.phase == "reveal" or self.state == "finished"
        entries = []
        if self.phase in ("vote", "reveal") or self.state == "finished":
            for e in self.entries:
                item = {"id": e["id"], "text": e["text"], "mine": bool(me and e["author"] == me.id)}
                if reveal:
                    item.update(author=e["author"], votes=e.get("votes", 0), best=e["id"] in self.best)
                entries.append(item)
        return {"prompt": self.prompt, "entries": entries, "hall": self.hall,
                "my_answer": me.answer if me else None, "my_pick": me.pick if me else None}


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
