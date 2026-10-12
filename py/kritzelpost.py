"""Kritzelpost: a drawing game of whispers. Write a sentence, draw what you get, describe the
drawing you get – and at the end watch how each story changed along the way (rules, no networking).

Every player starts one album. In every step each player works on the next album in the circle,
alternating between writing and drawing, until each album has passed through every player."""

import math
import random
import re
import secrets
import time

from common import RuleError

MIN_PLAYERS, MAX_PLAYERS = 3, 10
MAX_TEXT = 120
CANVAS_W, CANVAS_H = 1000, 750
MAX_STROKES = 3000
MAX_COORDS = 160_000
GRACE = 4  # seconds after the visible timer before missing work is filled in
# (seconds for writing, seconds for drawing); 0 = no time limit
TEMPOS = {1: (35, 70), 2: (50, 100), 3: (70, 160), 0: (0, 0)}
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

PROMPTS = [
    "Ein Pinguin im Urlaub auf Mallorca", "Oma fährt Skateboard", "Ein Hai beim Zahnarzt",
    "Die Katze regiert die Welt", "Ein Astronaut verliert seinen Schlüssel", "Pizza mit Ananas vor Gericht",
    "Ein Dino lernt Klavier", "Der Toaster hat Gefühle", "Ein Schneemann in der Sauna",
    "Ein Hund macht die Steuererklärung", "Die Sonne hat Sonnenbrand", "Ein Roboter verliebt sich in eine Waschmaschine",
    "Eine Kuh auf dem Mond", "Ein Baum, der Fußball spielt", "Ein Fisch fährt Fahrrad",
    "Der Weihnachtsmann im Sommerurlaub", "Ein Einhorn im Stau", "Ein Geist, der Angst vor dem Dunkeln hat",
    "Ein Huhn überquert die Autobahn", "Die Blume trinkt Kaffee", "Ein Vampir beim Blutspenden",
    "Ein Haus auf Hühnerbeinen", "Ein Bär, der Honig verkauft", "Ein Auto mit Flügeln",
    "Ein Ritter kämpft gegen eine Mücke", "Eine Giraffe im Aufzug", "Ein Koch, der vor seiner Suppe flieht",
    "Das Smartphone geht in Rente", "Eine Schildkröte gewinnt ein Rennen", "Ein Zauberer verliert seinen Hasen",
]
GUESSES = [
    "Ein Hund auf Rollschuhen?", "Irgendwas mit einem Ufo", "Eine sehr traurige Kartoffel",
    "Ein Monster beim Frühstück", "Moderne Kunst", "Ein Vogel im Regen", "Das ist bestimmt eine Katze",
    "Ein Haus mit Augen", "Ein Mann, der tanzt", "Eine explodierende Torte",
]


# -- doodles for computer players: strokes on the 1000 x 750 canvas ---------------------------
def _circle(cx, cy, r, ry=None, start=0.0, end=2 * math.pi, n=36):
    ry = r if ry is None else ry
    pts = []
    for i in range(n + 1):
        a = start + (end - start) * i / n
        pts += [round(cx + r * math.cos(a)), round(cy + ry * math.sin(a))]
    return pts


def _s(color, width, pts):
    return {"c": color, "w": width, "p": pts}


DOODLES = {
    "sonne": lambda: [_s("#f59e0b", 14, _circle(500, 375, 120))]
    + [_s("#f59e0b", 12, [round(500 + 160 * math.cos(a)), round(375 + 160 * math.sin(a)),
                          round(500 + 240 * math.cos(a)), round(375 + 240 * math.sin(a))])
       for a in [i * math.pi / 4 for i in range(8)]],
    "haus": lambda: [_s("#b45309", 12, [300, 650, 300, 380, 700, 380, 700, 650, 300, 650]),
                     _s("#dc2626", 12, [260, 390, 500, 180, 740, 390]),
                     _s("#1e3a8a", 10, [460, 650, 460, 520, 540, 520, 540, 650]),
                     _s("#0ea5e9", 10, [350, 430, 430, 430, 430, 490, 350, 490, 350, 430])],
    "baum": lambda: [_s("#92400e", 30, [500, 680, 500, 420]), _s("#16a34a", 18, _circle(500, 300, 170, 150))],
    "katze": lambda: [_s("#334155", 12, _circle(500, 420, 180, 150)),
                      _s("#334155", 12, [360, 330, 380, 170, 450, 280]), _s("#334155", 12, [550, 280, 620, 170, 640, 330]),
                      _s("#16a34a", 16, _circle(430, 400, 12)), _s("#16a34a", 16, _circle(570, 400, 12)),
                      _s("#334155", 6, [300, 470, 450, 460]), _s("#334155", 6, [550, 460, 700, 470])],
    "fisch": lambda: [_s("#0284c7", 12, _circle(460, 375, 220, 120)),
                      _s("#0284c7", 12, [680, 375, 820, 260, 820, 490, 680, 375]),
                      _s("#0f172a", 18, _circle(340, 350, 10))],
    "smiley": lambda: [_s("#eab308", 14, _circle(500, 375, 220)), _s("#0f172a", 20, _circle(420, 310, 10)),
                       _s("#0f172a", 20, _circle(580, 310, 10)),
                       _s("#0f172a", 12, _circle(500, 380, 120, 100, 0.2 * math.pi, 0.8 * math.pi, 16))],
    "blume": lambda: [_s("#16a34a", 12, [500, 700, 500, 380])]
    + [_s("#ec4899", 10, _circle(round(500 + 70 * math.cos(a)), round(300 + 70 * math.sin(a)), 50))
       for a in [i * math.pi / 3 for i in range(6)]] + [_s("#eab308", 30, _circle(500, 300, 25))],
    "auto": lambda: [_s("#dc2626", 12, [200, 520, 200, 420, 330, 420, 400, 320, 620, 320, 700, 420, 820, 420, 820, 520, 200, 520]),
                     _s("#0f172a", 14, _circle(320, 540, 60)), _s("#0f172a", 14, _circle(700, 540, 60))],
    "schneemann": lambda: [_s("#64748b", 10, _circle(500, 580, 140)), _s("#64748b", 10, _circle(500, 340, 100)),
                           _s("#64748b", 10, _circle(500, 170, 70)), _s("#f97316", 12, [500, 175, 600, 190, 500, 200])],
}
SYNONYMS = {"pinguin": "fisch", "hai": "fisch", "fisch": "fisch", "sonne": "sonne", "haus": "haus", "baum": "baum",
            "katze": "katze", "hund": "katze", "bär": "katze", "blume": "blume", "auto": "auto", "schneemann": "schneemann",
            "weihnachtsmann": "schneemann", "lachen": "smiley", "glück": "smiley"}
DOODLE_NAMES = {"sonne": "Eine Sonne", "haus": "Ein Haus", "baum": "Ein Baum", "katze": "Eine Katze",
                "fisch": "Ein Fisch", "smiley": "Ein Smiley", "blume": "Eine Blume", "auto": "Ein Auto",
                "schneemann": "Ein Schneemann"}


def clean_strokes(raw) -> list[dict]:
    if not isinstance(raw, list) or len(raw) > MAX_STROKES:
        raise RuleError("Die Zeichnung ist zu groß")
    strokes, total = [], 0
    for s in raw:
        if not isinstance(s, dict):
            raise RuleError("Ungültige Zeichnung")
        color, width, pts = s.get("c"), s.get("w"), s.get("p")
        if not isinstance(color, str) or not COLOR.match(color) or not isinstance(pts, list) or len(pts) < 2 or len(pts) % 2:
            raise RuleError("Ungültige Zeichnung")
        total += len(pts)
        if total > MAX_COORDS:
            raise RuleError("Die Zeichnung ist zu groß")
        clean = []
        for i, v in enumerate(pts):
            if not isinstance(v, (int, float)):
                raise RuleError("Ungültige Zeichnung")
            clean.append(max(0, min(CANVAS_W if i % 2 == 0 else CANVAS_H, round(v))))
        strokes.append({"c": color.lower(), "w": max(1, min(80, int(width or 8))), "p": clean})
    return strokes


class Player:
    def __init__(self, name: str, is_bot: bool = False):
        self.id = secrets.token_hex(4)
        self.name = name
        self.is_bot = is_bot
        self.ideas: list[str] = []


class Game:
    KIND = "kritzelpost"

    def __init__(self, code: str):
        self.code = code
        self.players: list[Player] = []
        self.host_id: str | None = None
        self.state = "lobby"      # lobby | playing | finished
        self.phase = "play"       # play | reveal
        self.tempo = 2
        self.order: list[str] = []          # player ids in passing order
        self.albums: list[list[dict]] = []  # album i starts with order[i]
        self.step = 0
        self.done: set[str] = set()
        self.deadline: float | None = None  # when missing work is filled in (server clock)
        self.shown_album = 0
        self.shown_count = 0
        self.log: list[str] = []

    # -- shared interface ----------------------------------------------------
    def new_player(self, name: str, is_bot: bool = False) -> Player:
        return Player(name, is_bot)

    def player(self, player_id):
        return next((p for p in self.players if p.id == player_id), None)

    def note(self, text: str) -> None:
        self.log.append(text)
        del self.log[:-30]

    def configure(self, settings: dict) -> None:
        tempo = settings.get("tempo")
        tempo = int(tempo) if tempo is not None else 2
        self.tempo = tempo if tempo in TEMPOS else 2

    def add_player(self, player: Player) -> None:
        if self.state != "lobby":
            raise RuleError("Das Spiel läuft bereits")
        if len(self.players) >= MAX_PLAYERS:
            raise RuleError(f"Maximal {MAX_PLAYERS} Spieler")
        self.players.append(player)
        if self.host_id is None and not player.is_bot:
            self.host_id = player.id

    def remove_player(self, player_id: str) -> None:
        # The server only removes players outside a running game; a leaver in a game becomes a bot.
        player = self.player(player_id)
        if not player:
            return
        self.players.remove(player)
        if self.host_id == player_id:
            self.host_id = next((p.id for p in self.players if not p.is_bot), None)

    def start(self) -> None:
        if len(self.players) < MIN_PLAYERS:
            raise RuleError(f"Mindestens {MIN_PLAYERS} Spieler nötig")
        self.order = [p.id for p in self.players]
        random.shuffle(self.order)
        self.albums = [[] for _ in self.order]
        self.state, self.phase = "playing", "play"
        self.log = []
        self.shown_album = self.shown_count = 0
        for p in self.players:
            p.ideas = random.sample(PROMPTS, 3)
        self.note("Jeder schreibt einen Satz")
        self._begin_step(0)

    # -- steps ---------------------------------------------------------------
    @property
    def steps(self) -> int:
        return len(self.order)

    def step_kind(self, step: int | None = None) -> str:
        step = self.step if step is None else step
        return "write" if step == 0 else "draw" if step % 2 else "describe"

    def album_of(self, player_id: str, step: int | None = None) -> int:
        step = self.step if step is None else step
        return (self.order.index(player_id) - step) % self.steps

    def _begin_step(self, step: int) -> None:
        self.step = step
        self.done = set()
        seconds = TEMPOS[self.tempo][1 if self.step_kind() == "draw" else 0]
        self.deadline = time.time() + seconds + GRACE if seconds else None

    def _store(self, player: Player, entry: dict) -> None:
        album = self.albums[self.album_of(player.id)]
        entry.update(by=player.id, name=player.name.removesuffix(" (Bot)"))
        if len(album) > self.step:
            album[self.step] = entry
        else:
            album.append(entry)
        self.done.add(player.id)
        if len(self.done) == self.steps:
            self._advance()

    def _advance(self) -> None:
        if self.step + 1 < self.steps:
            self._begin_step(self.step + 1)
            self.note("Jetzt wird gezeichnet" if self.step_kind() == "draw" else "Jetzt wird beschrieben")
        else:
            self.phase = "reveal"
            self.deadline = None
            self.shown_album, self.shown_count = 0, 1
            self.note("Alle Alben sind fertig – jetzt wird aufgedeckt!")

    def on_deadline(self) -> None:
        """Time is up: fill in whatever is missing so the game goes on."""
        if self.state != "playing" or self.phase != "play":
            return
        step = self.step
        for pid in [p for p in self.order if p not in self.done]:
            player = self.player(pid)
            if player:
                self._store(player, self._fallback(player))
            if self.phase != "play" or self.step != step:
                break

    def _fallback(self, player: Player) -> dict:
        kind = self.step_kind()
        if kind == "draw":
            return {"kind": "draw", "strokes": [], "late": True}
        if kind == "write":
            return {"kind": "text", "text": random.choice(player.ideas or PROMPTS), "late": True}
        return {"kind": "text", "text": "", "late": True}

    def task_for(self, player_id: str):
        """What the player gets to work on in this step: the previous entry of their album."""
        if self.step == 0:
            return None
        album = self.albums[self.album_of(player_id)]
        return album[self.step - 1] if len(album) >= self.step else None

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool) -> None:
        kind = msg.get("t")
        player = self.player(player_id)
        if not player or self.state != "playing":
            raise RuleError("Gerade nicht möglich")
        if self.phase == "reveal":
            if not is_host:
                raise RuleError("Der Gastgeber blättert die Alben um")
            if kind == "next":
                if self.shown_count < self.steps:
                    self.shown_count += 1
                elif self.shown_album + 1 < self.steps:
                    self.shown_album += 1
                    self.shown_count = 1
                else:
                    self.finish()
            elif kind == "back":
                if self.shown_count > 1:
                    self.shown_count -= 1
                elif self.shown_album > 0:
                    self.shown_album -= 1
                    self.shown_count = self.steps
            elif kind == "album_all":
                self.shown_count = self.steps
            else:
                raise RuleError("Unbekannte Aktion")
            return

        if kind == "edit":
            self.done.discard(player.id)
            return
        if kind != "submit":
            raise RuleError("Unbekannte Aktion")
        if player.id in self.done:
            raise RuleError("Du bist schon fertig")
        if self.step_kind() == "draw":
            strokes = clean_strokes(msg.get("strokes"))
            self._store(player, {"kind": "draw", "strokes": strokes})
        else:
            text = " ".join(str(msg.get("text", "")).split())[:MAX_TEXT]
            if not text:
                raise RuleError("Schreib zuerst etwas")
            self._store(player, {"kind": "text", "text": text})

    def finish(self) -> None:
        self.state = "finished"
        self.deadline = None
        self.note("Das waren alle Alben!")

    # -- bots ----------------------------------------------------------------
    def pending_bots(self) -> list:
        if self.state != "playing" or self.phase != "play":
            return []
        return [p for p in self.players if p.is_bot and p.id in self.order and p.id not in self.done]

    def bot_step(self, bot: Player) -> None:
        kind = self.step_kind()
        task = self.task_for(bot.id)
        if kind == "write":
            self.act(bot.id, {"t": "submit", "text": random.choice(PROMPTS)}, False)
        elif kind == "draw":
            text = (task or {}).get("text", "").lower()
            thing = next((v for k, v in SYNONYMS.items() if k in text), None) or random.choice(list(DOODLES))
            self._store(bot, {"kind": "draw", "strokes": DOODLES[thing](), "thing": thing})
        else:
            thing = (task or {}).get("thing")
            if thing and random.random() < .8:
                text = DOODLE_NAMES[thing] + random.choice(["", "!", " – ganz sicher", ", glaube ich", " beim Tanzen"])
            else:
                text = random.choice(GUESSES)
            self.act(bot.id, {"t": "submit", "text": text}, False)

    # -- view ----------------------------------------------------------------
    @staticmethod
    def _public(entry: dict | None):
        if not entry:
            return None
        out = {"kind": entry["kind"], "by": entry["by"], "name": entry["name"], "late": entry.get("late", False)}
        if entry["kind"] == "draw":
            out["strokes"] = entry["strokes"]
        else:
            out["text"] = entry["text"]
        return out

    def view_for(self, viewer_id) -> dict:
        view = {
            "kind": self.KIND, "code": self.code, "state": self.state, "phase": self.phase,
            "host": self.host_id, "settings": {"tempo": self.tempo},
            "players": [{"id": p.id, "name": p.name, "bot": p.is_bot, "done": p.id in self.done} for p in self.players],
            "step": self.step, "steps": self.steps, "log": self.log[-6:],
        }
        if self.state == "playing" and self.phase == "play":
            view["step_kind"] = self.step_kind()
            view["remaining"] = max(0, round(self.deadline - GRACE - time.time(), 1)) if self.deadline else None
            if viewer_id in self.order:
                view["album"] = self.album_of(viewer_id)
                view["task"] = self._public(self.task_for(viewer_id))
                me = self.player(viewer_id)
                view["ideas"] = me.ideas if me and self.step == 0 else []
        elif self.order and (self.phase == "reveal" or self.state == "finished"):
            album = self.albums[self.shown_album]
            owner = self.player(self.order[self.shown_album])
            view["reveal"] = {
                "album": self.shown_album, "albums": self.steps,
                "owner": album[0]["name"] if album else (owner.name if owner else "?"),
                "entries": [self._public(e) for e in album[: self.shown_count if self.state == "playing" else len(album)]],
                "count": self.shown_count, "total": len(album),
            }
        return view
