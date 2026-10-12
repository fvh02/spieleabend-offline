"""Galgenraten: guess the word letter by letter before the gallows is complete (rules, no networking).

One player thinks of a word (or takes a random one), the others take turns guessing letters.
A right letter lets you go on, a wrong one passes the turn and adds a piece to the gallows."""

import random
import secrets
import time

import wortschatz
from common import RuleError

MIN_PLAYERS, MAX_PLAYERS = 1, 8
MAX_FAILS = 10
WORDS_PER_GAME = (3, 5, 8)
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ"
FREQ = "ENIRSTADHULGCMOBWFKZÄÜPVÖJYXQ"  # German letter frequency, for computer players
TURN_SECONDS = 40
CHOOSE_SECONDS = 75
BOT_THINK = (1.8, 3.5)


def clean(text: str) -> str:
    text = " ".join(str(text).split()).upper().replace("ß", "SS")
    return text


class Player:
    def __init__(self, name: str, is_bot: bool = False):
        self.id = secrets.token_hex(4)
        self.name = name
        self.is_bot = is_bot
        self.total = 0
        self.gained = 0


class Game:
    KIND = "galgenraten"

    def __init__(self, code: str):
        self.code = code
        self.players: list[Player] = []
        self.host_id: str | None = None
        self.state = "lobby"      # lobby | playing | finished
        self.phase = "choose"     # choose | guess | round_end
        self.source = 1           # 1 = players think of words, 0 = random words
        self.words = 5
        self.round = 0
        self.setter: str | None = None
        self.word = ""
        self.hint = ""
        self.guessed: list[str] = []
        self.wrong: list[str] = []
        self.fails = 0
        self.order: list[str] = []
        self.turn = 0
        self.turn_end = 0.0
        self.bot_at = 0.0
        self.solver: str | None = None
        self.used: set[str] = set()
        self.last: dict = {}
        self.seq = 0
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
        source = settings.get("source")
        self.source = 0 if source is not None and int(source) == 0 else 1
        words = int(settings.get("words") or 5)
        self.words = words if words in WORDS_PER_GAME else 5

    def add_player(self, player: Player) -> None:
        if self.state != "lobby":
            raise RuleError("Das Spiel läuft bereits")
        if len(self.players) >= MAX_PLAYERS:
            raise RuleError(f"Maximal {MAX_PLAYERS} Spieler")
        self.players.append(player)
        if self.host_id is None and not player.is_bot:
            self.host_id = player.id

    def remove_player(self, player_id: str) -> None:
        player = self.player(player_id)
        if not player:
            return
        self.players.remove(player)
        if self.host_id == player_id:
            self.host_id = next((p.id for p in self.players if not p.is_bot), None)
        if self.state == "playing":
            if player_id in self.order:
                index = self.order.index(player_id)
                self.order.remove(player_id)
                if index < self.turn:
                    self.turn -= 1
                if self.order:
                    self.turn %= len(self.order)
            if not self.order or player_id == self.setter:
                self._end_round(None)

    def start(self) -> None:
        if len(self.players) < MIN_PLAYERS:
            raise RuleError("Mindestens 1 Spieler nötig")
        for p in self.players:
            p.total = 0
        self.round = 0
        self.used = set()
        self.log = []
        self.state = "playing"
        self.start_round()

    # -- rounds --------------------------------------------------------------
    @property
    def player_words(self) -> bool:
        return self.source == 1 and len(self.players) >= 2

    def start_round(self) -> None:
        self.round += 1
        self.word, self.hint = "", ""
        self.guessed, self.wrong, self.fails = [], [], 0
        self.solver = None
        for p in self.players:
            p.gained = 0
        if self.player_words:
            setter = self.players[(self.round - 1) % len(self.players)]
            self.setter = setter.id
            self.phase = "choose"
            self.turn_end = time.time() + CHOOSE_SECONDS
            self.bot_at = time.time() + random.uniform(*BOT_THINK) if setter.is_bot else 0.0
            self.note(f"Wort {self.round}: {setter.name} denkt sich ein Wort aus")
        else:
            self.setter = None
            self._set_word(*self._random_word())

    def _random_word(self) -> tuple[str, str]:
        pool = [(w, c) for w, c in wortschatz.ALL if w not in self.used] or wortschatz.ALL
        word, cat = random.choice(pool)
        self.used.add(word)
        return word, cat

    def _set_word(self, word: str, hint: str) -> None:
        self.word, self.hint = clean(word), " ".join(str(hint).split())[:40]
        guessers = [p for p in self.players if p.id != self.setter]
        start = (self.round - 1) % len(guessers)
        self.order = [p.id for p in guessers[start:] + guessers[:start]]
        self.turn = 0
        self.phase = "guess"
        self._new_turn()
        self._event(kind="word")

    def _new_turn(self) -> None:
        self.turn_end = time.time() + TURN_SECONDS
        current = self.player(self.order[self.turn]) if self.order else None
        self.bot_at = time.time() + random.uniform(*BOT_THINK) if current and current.is_bot else 0.0

    def _next_turn(self) -> None:
        self.turn = (self.turn + 1) % len(self.order)
        self._new_turn()

    def letters(self) -> set[str]:
        return {ch for ch in self.word if ch in LETTERS}

    def solved(self) -> bool:
        return self.letters() <= set(self.guessed)

    def _end_round(self, solver: Player | None) -> None:
        setter = self.player(self.setter) if self.setter else None
        if solver:
            solver.total += 30
            solver.gained += 30
            self.solver = solver.id
            self.note(f"{solver.name} hat das Wort gelöst!")
        elif self.word and self.fails >= MAX_FAILS:
            if setter:
                setter.total += 40
                setter.gained += 40
            self.note("Der Galgen ist fertig – niemand hat es geschafft")
        self.phase = "round_end"
        self.turn_end = 0.0
        self.bot_at = 0.0
        if self.round >= self.words:
            self.finish()

    def finish(self) -> None:
        self.state = "finished"
        best = max(self.players, key=lambda p: p.total, default=None)
        if best:
            self.note(f"🏆 {best.name} gewinnt mit {best.total} Punkten!")

    def _event(self, **event) -> None:
        self.seq += 1
        self.last = dict(event, seq=self.seq)

    # -- timer (turn limits and computer players) ------------------------------
    @property
    def deadline(self) -> float | None:
        if self.state != "playing" or self.phase == "round_end":
            return None
        times = [t for t in (self.turn_end, self.bot_at) if t]
        return min(times) if times else None

    def on_deadline(self) -> None:
        if self.state != "playing":
            return
        now = time.time()
        if self.bot_at and self.bot_at <= now + .2:
            self.bot_at = 0.0
            self._bot_move()
            return
        if self.turn_end and self.turn_end <= now + .2:
            if self.phase == "choose":
                setter = self.player(self.setter)
                self.note(f"{setter.name if setter else 'Niemand'} war zu langsam – es gibt ein Zufallswort")
                self._set_word(*self._random_word())
            elif self.phase == "guess" and self.order:
                current = self.player(self.order[self.turn])
                self.note(f"{current.name} war zu langsam")
                self._next_turn()

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool) -> None:
        kind = msg.get("t")
        player = self.player(player_id)
        if not player or self.state != "playing":
            raise RuleError("Gerade nicht möglich")
        if kind == "next_round":
            if self.phase != "round_end":
                raise RuleError("Das Wort läuft noch")
            if not is_host:
                raise RuleError("Nur der Gastgeber startet das nächste Wort")
            self.start_round()
            return
        if kind in ("set_word", "random_word"):
            if self.phase != "choose" or player.id != self.setter:
                raise RuleError("Du bist gerade nicht dran, ein Wort auszudenken")
            if kind == "random_word":
                self._set_word(*self._random_word())
                return
            word = clean(msg.get("word", ""))
            if not 3 <= len(word) <= 30 or not any(ch in LETTERS for ch in word):
                raise RuleError("Bitte ein Wort mit 3 bis 30 Buchstaben")
            if any(ch not in LETTERS and ch not in " -" for ch in word):
                raise RuleError("Nur Buchstaben, Leerzeichen und Bindestriche")
            if len(self.letters_of(word)) < 2:
                raise RuleError("Das Wort ist zu einfach")
            self._set_word(word, msg.get("hint") or "")
            return
        if self.phase != "guess":
            raise RuleError("Gerade wird nicht geraten")
        if not self.order or self.order[self.turn] != player.id:
            raise RuleError("Du bist nicht dran")
        if kind == "letter":
            self._letter(player, clean(msg.get("letter", ""))[:1])
        elif kind == "solve":
            self._solve(player, clean(msg.get("word", "")))
        else:
            raise RuleError("Unbekannte Aktion")

    @staticmethod
    def letters_of(word: str) -> set[str]:
        return {ch for ch in word if ch in LETTERS}

    def _letter(self, player: Player, letter: str) -> None:
        if letter not in LETTERS:
            raise RuleError("Bitte einen Buchstaben wählen")
        if letter in self.guessed or letter in self.wrong:
            raise RuleError("Dieser Buchstabe war schon dran")
        count = self.word.count(letter)
        if count:
            self.guessed.append(letter)
            player.total += 10 * count
            player.gained += 10 * count
            self._event(kind="hit", by=player.id, letter=letter, n=count)
            if self.solved():
                self._end_round(player)
            else:
                self._new_turn()  # right letter: the same player goes on
        else:
            self.wrong.append(letter)
            self.fails += 1
            self._event(kind="miss", by=player.id, letter=letter)
            if self.fails >= MAX_FAILS:
                self._end_round(None)
            else:
                self._next_turn()

    def _solve(self, player: Player, word: str) -> None:
        if len(word) < 2:
            raise RuleError("Bitte das ganze Wort eingeben")
        if word.replace("-", " ") == self.word.replace("-", " "):
            missing = self.letters() - set(self.guessed)
            bonus = 10 * sum(self.word.count(ch) for ch in missing)
            player.total += bonus
            player.gained += bonus
            self.guessed += sorted(missing)
            self._event(kind="solved", by=player.id)
            self._end_round(player)
        else:
            self.fails = min(MAX_FAILS, self.fails + 2)
            self._event(kind="wrong_solve", by=player.id, word=word[:30])
            self.note(f"{player.name} tippt auf „{word[:30]}“ – falsch")
            if self.fails >= MAX_FAILS:
                self._end_round(None)
            else:
                self._next_turn()

    # -- bots ----------------------------------------------------------------
    def pending_bots(self) -> list:
        return []  # computer players move on the game's own timer (see on_deadline)

    def bot_step(self, bot: Player) -> None:
        pass

    def _bot_move(self) -> None:
        if self.phase == "choose":
            self._set_word(*self._random_word())
            return
        if self.phase != "guess" or not self.order:
            return
        bot = self.player(self.order[self.turn])
        if not bot or not bot.is_bot:
            return
        known = set(self.guessed)
        pattern = [ch if ch in known or ch not in LETTERS else None for ch in self.word]
        wrong = set(self.wrong)
        candidates = [clean(w) for w, _ in wortschatz.ALL]
        candidates = [w for w in candidates if len(w) == len(self.word)
                      and all(p is None and ch in LETTERS and ch not in known or p == ch for p, ch in zip(pattern, w))
                      and not (set(w) & wrong)]
        if len(candidates) == 1 and random.random() < .8:
            self._solve(bot, candidates[0])
            return
        counts: dict[str, int] = {}
        for w in candidates:
            for ch in set(w) - known:
                if ch in LETTERS:
                    counts[ch] = counts.get(ch, 0) + 1
        open_letters = [ch for ch in FREQ if ch not in known and ch not in wrong]
        if counts and random.random() < .75:
            letter = max(counts, key=lambda ch: (counts[ch], -FREQ.index(ch) if ch in FREQ else 0))
        else:
            letter = open_letters[min(len(open_letters) - 1, int(random.random() ** 2 * 6))]
        self._letter(bot, letter)

    # -- view ----------------------------------------------------------------
    def view_for(self, viewer_id) -> dict:
        reveal = self.phase == "round_end" or self.state == "finished" or viewer_id == self.setter
        known = set(self.guessed)
        return {
            "kind": self.KIND, "code": self.code, "state": self.state, "phase": self.phase,
            "host": self.host_id, "settings": {"source": self.source, "words": self.words},
            "round": self.round, "rounds": self.words, "setter": self.setter,
            "players": [{"id": p.id, "name": p.name, "bot": p.is_bot, "total": p.total, "gained": p.gained}
                        for p in self.players],
            "pattern": [ch if ch not in LETTERS or ch in known or reveal else None for ch in self.word],
            "missing": sorted(self.letters() - known) if reveal and self.phase == "round_end" else [],
            "hint": self.hint, "guessed": self.guessed, "wrong": self.wrong,
            "fails": self.fails, "max_fails": MAX_FAILS,
            "order": self.order, "turn": self.order[self.turn] if self.order and self.phase == "guess" else None,
            "remaining": max(0, round(self.turn_end - time.time(), 1)) if self.turn_end and self.phase != "round_end" else None,
            "solver": self.solver, "last": self.last, "log": self.log[-6:],
        }
