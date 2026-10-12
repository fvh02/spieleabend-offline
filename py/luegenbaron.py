"""Lügenbaron: a true but strange fact with a gap. Everyone invents a believable fake answer,
then everyone has to find the truth among all answers – and gets points for fooling the others."""

import random

from common import RuleError
from party import PartyGame, clean, normalize

# (sentence with ___, true answer, other spellings that also count as the truth)
FACTS = [
    ("Das schottische Nationaltier ist das ___.", "Einhorn", []),
    ("Bananen sind botanisch gesehen ___.", "Beeren", ["Beere"]),
    ("Wombats hinterlassen ___ Kot.", "würfelförmigen", ["würfelförmig", "eckigen", "Würfel"]),
    ("Die Mona Lisa hat keine ___.", "Augenbrauen", []),
    ("Der Name „Bluetooth“ stammt von einem ___ König.", "dänischen", ["Wikinger"]),
    ("Das Wort „Roboter“ stammt aus dem ___.", "Tschechischen", ["Tschechisch"]),
    ("Ketchup wurde im 19. Jahrhundert als ___ verkauft.", "Medizin", ["Arznei", "Heilmittel"]),
    ("Australien ist breiter als der ___.", "Mond", []),
    ("In der Schweiz ist es verboten, nur ein einzelnes ___ zu halten.", "Meerschweinchen", []),
    ("Der Erfinder der Pringles-Dose wurde in einer ___ beerdigt.", "Pringles-Dose", ["Pringlesdose", "Pringles Dose"]),
    ("Faultiere können bis zu ___ Minuten die Luft anhalten.", "40", ["vierzig"]),
    ("Ein Tag auf der Venus dauert länger als ein ___ auf der Venus.", "Jahr", []),
    ("Die erste Webcam der Welt war auf eine ___ gerichtet.", "Kaffeemaschine", []),
    ("Das Gehirn eines Straußes ist kleiner als sein ___.", "Auge", ["Augen"]),
    ("Schmetterlinge schmecken mit ihren ___.", "Füßen", ["Füsse", "Beinen"]),
    ("Kängurus können nicht ___ hüpfen.", "rückwärts", []),
    ("Karotten waren ursprünglich nicht orange, sondern ___.", "lila", ["violett", "purpur"]),
    ("Ein Golfball hat meist zwischen 300 und 500 ___.", "Dellen", ["Dellen", "Vertiefungen", "Mulden"]),
    ("Die Freiheitsstatue war ursprünglich ___.", "kupferbraun", ["kupferfarben", "braun", "kupfer"]),
    ("Auf dem Markusplatz in Venedig ist es verboten, ___ zu füttern.", "Tauben", []),
    ("Das Lied „Happy Birthday“ war bis 2016 urheberrechtlich ___.", "geschützt", []),
    ("Eine Gruppe Flamingos heißt auf Englisch „a ___“.", "flamboyance", []),
    ("Eine Gruppe Krähen heißt auf Englisch „a ___ of crows“.", "murder", []),
    ("Das Spiel Monopoly sollte ursprünglich vor ___ warnen.", "Monopolen", ["Großgrundbesitzern", "Großgrundbesitz", "Kapitalismus"]),
    ("Haie gab es schon vor den ___.", "Bäumen", ["Bäume"]),
    ("Der kürzeste Linienflug der Welt dauert etwa ___ Minuten.", "zwei", ["2"]),
    ("Ein Krokodil kann seine ___ nicht herausstrecken.", "Zunge", []),
    ("Bei Seepferdchen bekommen die ___ die Babys.", "Männchen", ["Männer", "Väter"]),
    ("Die Kiwi-Frucht wurde nach einem ___ benannt.", "Vogel", []),
    ("Laut einer Uni-Studie gibt es im Schottischen über 400 Wörter für ___.", "Schnee", []),
    ("Der Fallschirm wurde vor dem ___ erfunden.", "Flugzeug", []),
    ("Kleopatra lebte zeitlich näher an der Mondlandung als am Bau der ___.", "Cheops-Pyramide", ["Pyramiden", "Pyramide", "Cheopspyramide"]),
    ("Die Universität Oxford ist älter als das Reich der ___.", "Azteken", []),
    ("1897 sollte im US-Staat Indiana die Zahl Pi per ___ festgelegt werden.", "Gesetz", []),
    ("Die Nationalhymne Spaniens hat keinen ___.", "Text", []),
    ("Nach Stückzahl ist LEGO der größte ___-Hersteller der Welt.", "Reifen", []),
    ("Eselspinguine schenken ihrem Partner zum Werben einen ___.", "Kieselstein", ["Stein", "Kiesel"]),
    ("Honig aus ägyptischen Gräbern war nach Jahrtausenden noch ___.", "essbar", ["genießbar"]),
    ("Der Eiffelturm wird im Sommer durch die Hitze bis zu 15 Zentimeter ___.", "höher", ["größer", "länger"]),
    ("Flamingos sind rosa, weil sie ___ fressen.", "Krebstierchen", ["Krebse", "Garnelen", "Algen", "Krebstiere"]),
    ("Seeotter halten sich beim Schlafen an den ___.", "Händen", ["Pfoten", "Händchen"]),
    ("Elefanten können nicht ___.", "springen", []),
    ("Napoleon wurde bei einer Jagd einmal von einer Horde ___ angegriffen.", "Kaninchen", ["Hasen"]),
    ("Kühe haben nachweislich beste ___.", "Freunde", ["Freundinnen"]),
    ("Ein Oktopus hat ___ Herzen.", "drei", ["3"]),
    ("Die Hauptstadt von Australien heißt ___.", "Canberra", []),
    ("Honigbienen können menschliche ___ wiedererkennen.", "Gesichter", []),
    ("Ein Blauwalherz ist etwa so groß wie ein ___.", "Kleinwagen", ["Auto"]),
    ("Ein Teelöffel Materie eines Neutronensterns wiegt rund eine ___ Tonnen.", "Milliarde", []),
    ("Der Britisch-Sansibarische Krieg 1896 dauerte nur etwa ___ Minuten.", "38", ["achtunddreißig"]),
    ("In Frankreich wurde erst 2013 ein Verbot offiziell aufgehoben, nach dem Frauen keine ___ tragen durften.", "Hosen", ["Hose"]),
]


class Game(PartyGame):
    KIND = "luegenbaron"
    MIN_PLAYERS, MAX_PLAYERS = 3, 12
    ROUNDS = (6, 4, 8, 10)
    TIMES = (75, 60, 120, 0)
    INPUT_PHASES = ("write", "pick")

    def __init__(self, code: str):
        super().__init__(code)
        self.fact = None
        self.options: list[dict] = []   # {"id", "text", "authors": [ids], "truth": bool}

    def setup_round(self) -> None:
        pool = [f for f in FACTS if f[0] not in self.used] or FACTS
        self.fact = random.choice(pool)
        self.used.add(self.fact[0])
        self.options = []
        self.begin("write")

    def phase_attr(self) -> str:
        return "answer" if self.phase == "write" else "pick"

    def is_truth(self, text: str) -> bool:
        norm = normalize(text)
        return norm in {normalize(t) for t in [self.fact[1], *self.fact[2]]}

    def play(self, player, msg: dict) -> None:
        kind = msg.get("t")
        if self.phase == "write" and kind == "write":
            text = clean(msg.get("text"), 40)
            if not normalize(text):
                raise RuleError("Bitte eine Antwort eingeben")
            if self.is_truth(text):
                raise RuleError("Psst – das ist die richtige Antwort! Denk dir eine falsche aus.")
            player.answer = text
            if self.done("answer"):
                self.advance()
        elif self.phase == "pick" and kind == "pick":
            option = next((o for o in self.options if o["id"] == msg.get("id")), None)
            if not option:
                raise RuleError("Diese Antwort gibt es nicht")
            if player.id in option["authors"]:
                raise RuleError("Deine eigene Antwort kannst du nicht wählen")
            player.pick = option["id"]
            if self.done("pick"):
                self.advance()
        else:
            raise RuleError("Gerade nicht möglich")

    def advance(self) -> None:
        if self.phase == "write":
            merged: dict[str, dict] = {}
            for p in self.gamers:
                if p.answer:
                    entry = merged.setdefault(normalize(p.answer), {"text": p.answer, "authors": [], "truth": False})
                    entry["authors"].append(p.id)
            options = list(merged.values()) + [{"text": self.fact[1], "authors": [], "truth": True}]
            random.shuffle(options)
            for n, o in enumerate(options):
                o["id"] = f"o{n}"
            self.options = options
            # Players whose only choice would be their own answer, or placeholders, skip the vote.
            for p in self.gamers:
                p.pick = "" if p.is_bot else None
            if len(options) == 1 or self.done("pick"):
                self.score_round()
            else:
                self.begin("pick")
        elif self.phase == "pick":
            self.score_round()

    def score_round(self) -> None:
        by_id = {o["id"]: o for o in self.options}
        for p in self.gamers:
            chosen = by_id.get(p.pick or "")
            if chosen and chosen["truth"]:
                p.gained += 2
            elif chosen:
                for author in chosen["authors"]:
                    fooled = self.player(author)
                    if fooled:
                        fooled.gained += 1
        for p in self.gamers:
            p.score += p.gained
        self.begin("reveal", timed=False)
        liars = sorted(self.gamers, key=lambda p: p.gained, reverse=True)
        if liars and liars[0].gained:
            self.note(f"{liars[0].name} holt {liars[0].gained} Punkte in dieser Runde")

    def extra_view(self, me) -> dict:
        sentence, truth, _ = self.fact or ("", "", [])
        reveal = self.phase == "reveal" or self.state == "finished"
        options = []
        if self.phase in ("pick", "reveal") or self.state == "finished":
            for o in self.options:
                item = {"id": o["id"], "text": o["text"], "mine": bool(me and me.id in o["authors"])}
                if reveal:
                    item.update(truth=o["truth"], authors=o["authors"],
                                pickers=[p.id for p in self.gamers if p.pick == o["id"]])
                options.append(item)
        return {
            "sentence": sentence, "truth": truth if reveal else None, "options": options,
            "my_answer": me.answer if me else None, "my_pick": me.pick if me else None,
        }


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
