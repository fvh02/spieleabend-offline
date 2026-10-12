"""Schnellmaler: one player draws a word, everyone else guesses it on their phone (rules, no networking).

One device in the room can become the "Host" screen (e.g. a TV): it shows the live drawing, the
word hint, the timer and the scores, but neither draws nor guesses."""

import random
import re
import secrets
import time
import unicodedata

from common import RuleError

MIN_PLAYERS, MAX_PLAYERS = 2, 12   # players who draw and guess; the screen comes on top
CANVAS_W, CANVAS_H = 1000, 750
MAX_COORDS = 200_000
CHOOSE_SECONDS = 15
REVEAL_SECONDS = 6
ROUNDS = (1, 2, 3)
TIMES = (60, 80, 100, 120)
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

WORDS = """
Apfel Banane Birne Erdbeere Kirsche Ananas Zitrone Karotte Kartoffel Tomate Gurke Pizza Burger Pommes Brezel
Eis Torte Kuchen Keks Schokolade Kaffee Tee Milch Käse Ei Brot Nudeln Suppe Honig Popcorn
Hund Katze Maus Pferd Kuh Schwein Schaf Ziege Hase Igel Fuchs Bär Wolf Löwe Tiger Elefant Giraffe Zebra Affe
Pinguin Eule Adler Ente Huhn Hahn Fisch Hai Wal Delfin Krake Krebs Schnecke Spinne Biene Schmetterling Frosch
Schlange Krokodil Dino Einhorn Drache Kamel Känguru Koala Papagei Flamingo
Haus Schloss Burg Kirche Turm Brücke Leuchtturm Zelt Iglu Garage Zaun Tür Fenster Treppe Dach Kamin
Auto Bus Zug Fahrrad Motorrad Flugzeug Hubschrauber Rakete Schiff Boot Uboot Traktor Bagger Feuerwehr Krankenwagen
Ampel Straße Tankstelle Parkplatz Anker Segelboot Heißluftballon Skateboard Roller
Sonne Mond Stern Wolke Regen Schnee Blitz Regenbogen Vulkan Berg Insel Strand Wüste Wald Baum Blume Kaktus
Pilz Blatt Gras Welle Fluss See Höhle Wasserfall Tornado Schneemann Lagerfeuer
Ball Fußball Tor Tennis Basketball Schwimmen Ski Schlitten Angel Pokal Medaille Würfel Puzzle Drachen Schaukel Rutsche
Gitarre Klavier Trommel Geige Trompete Mikrofon Kopfhörer Radio Fernseher Handy Laptop Computer Kamera Uhr Wecker
Lampe Kerze Glühbirne Schlüssel Schloss Brille Hut Mütze Schal Handschuh Schuh Stiefel Socke Hose Kleid Krone Ring
Rucksack Koffer Regenschirm Geschenk Luftballon Schere Hammer Säge Nagel Schraube Pinsel Stift Buch Brief Zeitung
Tasse Teller Gabel Löffel Messer Topf Pfanne Kühlschrank Waschmaschine Toaster Staubsauger Bett Sofa Stuhl Tisch
Badewanne Dusche Toilette Zahnbürste Spiegel Kamm Seife Besen Eimer Gießkanne Schubkarre Leiter
Pirat Ritter Prinzessin Zauberer Hexe Geist Vampir Roboter Astronaut Außerirdischer Ufo Clown Koch Polizist Arzt
Superheld Mumie Zombie Meerjungfrau Weihnachtsmann Osterhase Engel Teufel Ninja Cowboy
Herz Smiley Pfeil Fragezeichen Schatz Karte Kompass Lupe Magnet Batterie Glocke Fahne Briefkasten Sanduhr
Geburtstag Hochzeit Picknick Zirkus Karussell Achterbahn Kino Zahnarzt Friseur Weihnachtsbaum Ostereier Feuerwerk
""".split()
WORDS = list(dict.fromkeys(WORDS))


def norm(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"^(der|die|das|ein|eine|einen)\s+", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


def distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class Player:
    def __init__(self, name: str, is_bot: bool = False):
        self.id = secrets.token_hex(4)
        self.name = name
        self.is_bot = is_bot
        self.screen = False
        self.score = 0
        self.gained = 0     # points in the current turn


class Game:
    KIND = "schnellmaler"
    NO_BOTS = True

    def __init__(self, code: str):
        self.code = code
        self.players: list[Player] = []
        self.host_id: str | None = None
        self.state = "lobby"      # lobby | playing | finished
        self.phase = "choose"     # choose | draw | reveal
        self.rounds = 2
        self.seconds = 80
        self.order: list[str] = []
        self.turn_index = -1
        self.drawer: str | None = None
        self.choices: list[str] = []
        self.word = ""
        self.revealed: set[int] = set()  # letter positions shown as hint
        self.guessed: list[str] = []     # player ids in the order they guessed
        self.strokes: list[dict] = []
        self.coords = 0
        self.feed: list[dict] = []
        self.turn_end = 0.0
        self.deadline: float | None = None
        self.used: set[str] = set()
        self.log: list[str] = []

    # -- shared interface ----------------------------------------------------
    def new_player(self, name: str, is_bot: bool = False) -> Player:
        return Player(name, is_bot)

    def player(self, player_id):
        return next((p for p in self.players if p.id == player_id), None)

    def note(self, text: str) -> None:
        self.log.append(text)
        del self.log[:-30]

    @property
    def screen(self):
        return next((p for p in self.players if p.screen), None)

    @property
    def artists(self) -> list[Player]:
        return [p for p in self.players if not p.screen]

    def configure(self, settings: dict) -> None:
        rounds, seconds = int(settings.get("rounds") or 2), int(settings.get("seconds") or 80)
        self.rounds = rounds if rounds in ROUNDS else 2
        self.seconds = seconds if seconds in TIMES else 80

    def add_player(self, player: Player) -> None:
        if player.is_bot:
            raise RuleError("In diesem Spiel gibt es keine Computer-Spieler")
        if self.state != "lobby":
            raise RuleError("Das Spiel läuft bereits")
        if len(self.artists) >= MAX_PLAYERS:
            raise RuleError(f"Maximal {MAX_PLAYERS} Spieler")
        self.players.append(player)
        if self.host_id is None:
            self.host_id = player.id

    def remove_player(self, player_id: str) -> None:
        player = self.player(player_id)
        if not player:
            return
        self.players.remove(player)
        if self.host_id == player_id:
            self.host_id = next((p.id for p in self.players if not p.is_bot), None)

    def start(self) -> None:
        if len(self.artists) < MIN_PLAYERS:
            raise RuleError(f"Mindestens {MIN_PLAYERS} Spieler (ohne den Host-Bildschirm) nötig")
        for p in self.players:
            p.score = p.gained = 0
        ids = [p.id for p in self.artists]
        random.shuffle(ids)
        self.order = ids * self.rounds
        self.turn_index = -1
        self.used = set()
        self.log = []
        self.feed = []
        self.state = "playing"
        self.note("Das Spiel beginnt!")
        self._next_turn()

    # -- turns ---------------------------------------------------------------
    def _next_turn(self) -> None:
        while True:
            self.turn_index += 1
            if self.turn_index >= len(self.order):
                self.finish()
                return
            drawer = self.player(self.order[self.turn_index])
            if drawer and not drawer.screen and not drawer.is_bot:
                break
        self.drawer = drawer.id
        pool = [w for w in WORDS if w not in self.used] or WORDS
        self.choices = random.sample(pool, 3)
        self.word = ""
        self.revealed = set()
        self.guessed = []
        self.strokes = []
        self.coords = 0
        for p in self.players:
            p.gained = 0
        self.phase = "choose"
        self.turn_end = time.time() + CHOOSE_SECONDS
        self.deadline = self.turn_end
        self.feed.append({"kind": "info", "text": f"{drawer.name} ist dran"})
        del self.feed[:-40]

    def _start_drawing(self, word: str) -> None:
        self.word = word
        self.used.add(word)
        self.phase = "draw"
        self.turn_end = time.time() + self.seconds
        self._schedule_hint()

    def _schedule_hint(self) -> None:
        # Letters are revealed after half and after three quarters of the time.
        now, start = time.time(), self.turn_end - self.seconds
        hints = [start + self.seconds * f for f in (.5, .75)]
        upcoming = [t for t in hints if t > now + .2]
        self.deadline = upcoming[0] if upcoming else self.turn_end

    def _reveal_letter(self) -> None:
        hidden = [i for i, ch in enumerate(self.word) if ch != " " and i not in self.revealed]
        if len(hidden) > 2:
            self.revealed.add(random.choice(hidden))

    def _end_turn(self, reason: str) -> None:
        drawer = self.player(self.drawer)
        if drawer and self.guessed:
            gain = min(150, 25 * len(self.guessed))
            drawer.score += gain
            drawer.gained = gain
        self.phase = "reveal"
        self.feed.append({"kind": "word", "text": f"Das Wort war: {self.word}"})
        self.note(reason)
        self.turn_end = time.time() + REVEAL_SECONDS
        self.deadline = self.turn_end

    def on_deadline(self) -> None:
        if self.state != "playing":
            return
        if self.phase == "choose":
            self._start_drawing(random.choice(self.choices))
        elif self.phase == "draw":
            if time.time() >= self.turn_end - .2:
                self._end_turn("Die Zeit ist um")
            else:
                self._reveal_letter()
                self._schedule_hint()
        else:
            self._next_turn()

    def finish(self) -> None:
        self.state = "finished"
        self.deadline = None
        self.phase = "reveal"
        best = max(self.artists, key=lambda p: p.score, default=None)
        if best:
            self.note(f"🏆 {best.name} gewinnt mit {best.score} Punkten!")

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool):
        kind = msg.get("t")
        player = self.player(player_id)
        if not player:
            raise RuleError("Gerade nicht möglich")
        if kind == "screen":
            if self.state != "lobby":
                raise RuleError("Der Host-Bildschirm wird vor dem Start gewählt")
            current = self.screen
            if current and current is not player:
                raise RuleError(f"{current.name} ist schon Host")
            player.screen = not player.screen
            return None
        if self.state != "playing":
            raise RuleError("Gerade nicht möglich")
        if player.screen:
            raise RuleError("Der Host-Bildschirm zeigt nur an")

        if kind == "choose":
            if self.phase != "choose" or player.id != self.drawer:
                raise RuleError("Du wählst gerade kein Wort")
            word = msg.get("word")
            if word not in self.choices:
                raise RuleError("Dieses Wort steht nicht zur Wahl")
            self._start_drawing(word)
            return None
        if kind == "draw":
            if self.phase != "draw" or player.id != self.drawer:
                raise RuleError("Du zeichnest gerade nicht")
            return self._draw(msg)
        if kind == "skip":
            if player.id != self.drawer or self.phase not in ("choose", "draw"):
                raise RuleError("Gerade nicht möglich")
            if not self.word:
                self.word = random.choice(self.choices)
            self._end_turn(f"{player.name} hat aufgegeben")
            return None
        if kind == "guess":
            return self._guess(player, str(msg.get("text", "")))
        raise RuleError("Unbekannte Aktion")

    def _draw(self, msg: dict) -> dict:
        op = msg.get("op")
        if op == "begin":
            color, width, pts = msg.get("c"), msg.get("w"), msg.get("p")
            if not isinstance(color, str) or not COLOR.match(color):
                raise RuleError("Ungültige Farbe")
            stroke = {"c": color.lower(), "w": max(1, min(80, int(width or 8))), "p": self._points(pts)[:2]}
            if len(stroke["p"]) < 2:
                raise RuleError("Ungültige Zeichnung")
            self.strokes.append(stroke)
            return {"t": "live", "op": "begin", "s": stroke, "by": self.drawer}
        if op == "pts":
            if not self.strokes:
                raise RuleError("Ungültige Zeichnung")
            pts = self._points(msg.get("p"))
            self.strokes[-1]["p"].extend(pts)
            return {"t": "live", "op": "pts", "p": pts, "by": self.drawer}
        if op == "undo":
            if self.strokes:
                self.coords -= len(self.strokes.pop()["p"])
            return {"t": "live", "op": "undo", "by": self.drawer}
        if op == "clear":
            self.strokes, self.coords = [], 0
            return {"t": "live", "op": "clear", "by": self.drawer}
        raise RuleError("Unbekannte Zeichenaktion")

    def _points(self, raw) -> list[int]:
        if not isinstance(raw, list) or len(raw) % 2 or len(raw) > 4000:
            raise RuleError("Ungültige Zeichnung")
        if self.coords + len(raw) > MAX_COORDS:
            raise RuleError("Die Zeichnung ist zu groß")
        out = []
        for i, v in enumerate(raw):
            if not isinstance(v, (int, float)):
                raise RuleError("Ungültige Zeichnung")
            out.append(max(0, min(CANVAS_W if i % 2 == 0 else CANVAS_H, round(v))))
        self.coords += len(out)
        return out

    def _guess(self, player: Player, text: str):
        text = " ".join(text.split())[:60]
        if not text:
            return None
        if self.phase != "draw":
            raise RuleError("Gerade wird nicht geraten")
        if player.id == self.drawer:
            raise RuleError("Du zeichnest – du darfst nicht raten")
        if player.id in self.guessed:
            raise RuleError("Du hast es schon erraten")
        guess, word = norm(text), norm(self.word)
        if guess == word:
            remaining = max(0.0, self.turn_end - time.time())
            gain = max(20, round(100 * remaining / self.seconds)) + max(0, 30 - 10 * len(self.guessed))
            player.score += gain
            player.gained = gain
            self.guessed.append(player.id)
            self.feed.append({"kind": "correct", "text": f"{player.name} hat es erraten! (+{gain})", "by": player.id})
            if len(self.guessed) >= len([p for p in self.artists if p.id != self.drawer and not p.is_bot]):
                self._end_turn("Alle haben es erraten!")
            return None
        close = len(word) >= 4 and distance(guess, word) <= 1
        self.feed.append({"kind": "guess", "text": text, "by": player.id, "name": player.name, "close": close})
        del self.feed[:-40]
        return None

    # -- bots (only players who left during a game) ---------------------------
    def pending_bots(self) -> list:
        drawer = self.player(self.drawer) if self.state == "playing" and self.phase in ("choose", "draw") else None
        return [drawer] if drawer and drawer.is_bot else []

    def bot_step(self, bot: Player) -> None:
        if not self.word:
            self.word = random.choice(self.choices)
        self._end_turn(f"{bot.name} ist nicht mehr da – nächste Runde")

    # -- view ----------------------------------------------------------------
    def hint(self) -> str:
        return " ".join(ch if ch == " " or i in self.revealed else "_" for i, ch in enumerate(self.word))

    def view_for(self, viewer_id) -> dict:
        me = self.player(viewer_id)
        show_word = self.phase == "reveal" or self.state == "finished" or (me and me.id == self.drawer)
        feed = []
        for item in self.feed[-14:]:
            item = dict(item)
            # "Close" is a private hint for whoever guessed.
            if item.get("close") and item.get("by") != viewer_id:
                item["close"] = False
            feed.append(item)
        return {
            "kind": self.KIND, "code": self.code, "state": self.state, "phase": self.phase,
            "host": self.host_id, "settings": {"rounds": self.rounds, "seconds": self.seconds},
            "players": [{"id": p.id, "name": p.name, "bot": p.is_bot, "screen": p.screen, "score": p.score,
                         "gained": p.gained, "guessed": p.id in self.guessed} for p in self.players],
            "screen": self.screen.id if self.screen else None,
            "drawer": self.drawer,
            "turn": self.turn_index + 1, "turns": len(self.order),
            "choices": self.choices if me and me.id == self.drawer and self.phase == "choose" else [],
            "word": self.word if show_word else None,
            "hint": self.hint() if self.word else "",
            "letters": len(self.word.replace(" ", "")),
            "strokes": self.strokes,
            "remaining": max(0, round(self.turn_end - time.time(), 1)) if self.state == "playing" else None,
            "seconds": CHOOSE_SECONDS if self.phase == "choose" else REVEAL_SECONDS if self.phase == "reveal" else self.seconds,
            "feed": feed, "log": self.log[-6:],
        }
