"""Stapeljagd rules, independent of networking."""

import random
import secrets

from common import RuleError

JOKER = 0  # the joker, wild for any value
HAND_SIZE = 5
BUILD_PILES = 4
DISCARD_PILES = 4
MIN_PLAYERS, MAX_PLAYERS = 2, 6
STOCK_SIZES = (0, 5, 10, 15, 20, 25, 30)


def new_deck() -> list[int]:
    deck = [value for value in range(1, 13) for _ in range(12)] + [JOKER] * 18
    random.shuffle(deck)
    return deck


class Player:
    def __init__(self, name: str, is_bot: bool = False):
        self.id = secrets.token_hex(4)
        self.name = name
        self.is_bot = is_bot
        self.stock: list[int] = []
        self.hand: list[int] = []
        self.discards: list[list[int]] = [[] for _ in range(DISCARD_PILES)]

    def reset(self) -> None:
        self.stock, self.hand = [], []
        self.discards = [[] for _ in range(DISCARD_PILES)]


class Game:
    KIND = "stapeljagd"

    def __init__(self, code: str, stock_size: int = 0):
        self.code = code
        self.players: list[Player] = []
        self.host_id: str | None = None
        self.state = "lobby"  # lobby | playing | finished
        self.stock_size = stock_size  # 0 = by player count (30, or 20 with 5+ players)
        self.deck: list[int] = []
        self.building: list[list[int]] = [[] for _ in range(BUILD_PILES)]
        self.completed: list[int] = []
        self.turn = 0
        self.winner: str | None = None
        self.log: list[str] = []
        self.passes = 0  # consecutive turns passed without any card played

    # -- shared interface --------------------------------------------------
    def new_player(self, name: str, is_bot: bool = False) -> Player:
        return Player(name, is_bot)

    def configure(self, settings: dict) -> None:
        stock = int(settings.get("stock") or 0)
        self.stock_size = stock if stock in STOCK_SIZES else 0

    def act(self, player_id: str, msg: dict, is_host: bool) -> None:
        kind = msg.get("t")
        if kind == "play":
            self.play(player_id, str(msg.get("src")), int(msg.get("index", 0)), int(msg.get("pile", -1)))
        elif kind == "discard":
            self.discard(player_id, int(msg.get("index", -1)), int(msg.get("pile", -1)))
        elif kind == "pass":
            self.pass_turn(player_id)
        else:
            raise RuleError("Unbekannte Aktion")

    def pending_bots(self) -> list:
        current = self.current
        return [current] if current and current.is_bot else []

    def bot_step(self, bot: Player) -> None:
        move = bot_moves(self, bot)[0]
        if move[0] == "play":
            self.play(bot.id, *move[1:])
        elif move[0] == "discard":
            self.discard(bot.id, *move[1:])
        else:
            self.pass_turn(bot.id)

    # -- helpers -----------------------------------------------------------
    def player(self, player_id: str) -> Player | None:
        return next((p for p in self.players if p.id == player_id), None)

    @property
    def current(self) -> Player | None:
        return self.players[self.turn] if self.state == "playing" and self.players else None

    def note(self, text: str) -> None:
        self.log.append(text)
        del self.log[:-30]

    # -- lobby -------------------------------------------------------------
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
        index = self.players.index(player)
        self.players.remove(player)
        if self.host_id == player_id:
            self.host_id = next((p.id for p in self.players if not p.is_bot), None)
        if self.state == "playing":
            if len(self.players) < 2:
                self.finish(self.players[0] if self.players else None)
                return
            if index < self.turn:
                self.turn -= 1
            self.turn %= len(self.players)
            self.note(f"{player.name} hat das Spiel verlassen")
            self.start_turn()

    # -- game flow ---------------------------------------------------------
    def start(self) -> None:
        if len(self.players) < 2:
            raise RuleError("Mindestens 2 Spieler nötig")
        self.deck = new_deck()
        self.building = [[] for _ in range(BUILD_PILES)]
        self.completed = []
        self.winner = None
        self.log = []
        self.passes = 0
        size = self.stock_size or (20 if len(self.players) >= 5 else 30)
        for player in self.players:
            player.reset()
            player.stock = [self.deck.pop() for _ in range(size)]
        self.state = "playing"
        self.turn = random.randrange(len(self.players))
        self.note(f"Neues Spiel mit {size} Karten pro Stapel")
        self.start_turn()

    def draw(self, player: Player, count: int) -> None:
        for _ in range(count):
            if not self.deck:
                if not self.completed:
                    return
                self.deck = self.completed
                self.completed = []
                random.shuffle(self.deck)
                self.note("Fertige Stapel wurden neu gemischt")
            player.hand.append(self.deck.pop())

    def start_turn(self) -> None:
        player = self.current
        if player:
            self.draw(player, HAND_SIZE - len(player.hand))
            self.note(f"{player.name} ist dran")

    def next_turn(self) -> None:
        self.turn = (self.turn + 1) % len(self.players)
        self.start_turn()

    def finish(self, winner: Player | None) -> None:
        self.state = "finished"
        self.winner = winner.name if winner else None
        if winner:
            self.note(f"🏆 {winner.name} gewinnt!")

    # -- moves -------------------------------------------------------------
    def _require_turn(self, player_id: str) -> Player:
        player = self.current
        if self.state != "playing" or not player or player.id != player_id:
            raise RuleError("Du bist nicht am Zug")
        return player

    @staticmethod
    def fits(card: int, pile: list[int]) -> bool:
        return len(pile) < 12 and (card == JOKER or card == len(pile) + 1)

    def play(self, player_id: str, source: str, index: int, pile: int) -> None:
        player = self._require_turn(player_id)
        if not 0 <= pile < BUILD_PILES:
            raise RuleError("Ungültiger Stapel")
        if source == "hand":
            if not 0 <= index < len(player.hand):
                raise RuleError("Ungültige Karte")
            card = player.hand[index]
        elif source == "stock":
            if not player.stock:
                raise RuleError("Dein Stapel ist leer")
            card = player.stock[-1]
        elif source == "discard":
            if not 0 <= index < DISCARD_PILES or not player.discards[index]:
                raise RuleError("Dieser Ablagestapel ist leer")
            card = player.discards[index][-1]
        else:
            raise RuleError("Ungültige Quelle")

        target = self.building[pile]
        if not self.fits(card, target):
            need = len(target) + 1
            raise RuleError(f"Hier passt nur eine {need} oder ein Joker")

        if source == "hand":
            player.hand.pop(index)
        elif source == "stock":
            player.stock.pop()
        else:
            player.discards[index].pop()
        target.append(card)
        self.passes = 0

        if len(target) == 12:
            self.completed.extend(target)
            self.building[pile] = []
            self.note(f"{player.name} hat einen Stapel bis 12 gebaut")
        if source == "stock" and not player.stock:
            self.finish(player)
            return
        if not player.hand:
            self.draw(player, HAND_SIZE)

    def discard(self, player_id: str, index: int, pile: int) -> None:
        player = self._require_turn(player_id)
        if not 0 <= index < len(player.hand):
            raise RuleError("Ungültige Karte")
        if not 0 <= pile < DISCARD_PILES:
            raise RuleError("Ungültiger Ablagestapel")
        player.discards[pile].append(player.hand.pop(index))
        self.next_turn()

    def pass_turn(self, player_id: str) -> None:
        """Only possible without hand cards (deck and finished piles exhausted)."""
        player = self._require_turn(player_id)
        if player.hand:
            raise RuleError("Lege zum Beenden eine Handkarte auf einen deiner Ablagestapel")
        self.passes += 1
        if self.passes >= 2 * len(self.players):
            # Nobody can play any more: fewest cards left on the stock pile wins.
            self.note("Keiner kann mehr legen")
            self.finish(min(self.players, key=lambda p: len(p.stock)))
            return
        self.note(f"{player.name} kann nicht legen und passt")
        self.next_turn()

    # -- views -------------------------------------------------------------
    def view_for(self, viewer_id: str | None) -> dict:
        def public(p: Player) -> dict:
            info = {
                "id": p.id, "name": p.name, "bot": p.is_bot,
                "stock_count": len(p.stock), "stock_top": p.stock[-1] if p.stock else None,
                "discards": p.discards, "hand_count": len(p.hand),
            }
            if p.id == viewer_id:
                info["hand"] = p.hand
            return info

        current = self.current
        return {
            "kind": self.KIND, "code": self.code, "state": self.state, "host": self.host_id,
            "settings": {"stock": self.stock_size}, "stock_size": self.stock_size,
            "players": [public(p) for p in self.players],
            "turn": current.id if current else None,
            "building": self.building,
            "deck_count": len(self.deck), "completed_count": len(self.completed),
            "winner": self.winner, "log": self.log[-8:],
        }


def bot_moves(game: Game, player: Player) -> list[tuple]:
    """Next move for a simple bot: ("play", source, index, pile) or ("discard", index, pile)."""
    def playable(card):
        return [i for i, pile in enumerate(game.building) if game.fits(card, pile)]

    # 1. Stock card, the way to win
    if player.stock:
        top = player.stock[-1]
        piles = playable(top)
        if piles:
            return [("play", "stock", 0, piles[0])]
        # A joker from the hand can open the way for the stock card
        if top != JOKER and JOKER in player.hand:
            for i, pile in enumerate(game.building):
                if len(pile) + 2 == top:
                    return [("play", "hand", player.hand.index(JOKER), i)]
    # 2. Discard tops and hand cards that fit (no jokers)
    for d, stack in enumerate(player.discards):
        if stack and stack[-1] != JOKER:
            piles = playable(stack[-1])
            if piles:
                return [("play", "discard", d, piles[0])]
    for h, card in enumerate(player.hand):
        if card != JOKER:
            piles = playable(card)
            if piles:
                return [("play", "hand", h, piles[0])]
    # 3. Discard: prefer the highest non-joker; stack descending if possible
    if not player.hand:
        # Last resort before passing: jokers waiting on the discard piles
        for d, stack in enumerate(player.discards):
            if stack and stack[-1] == JOKER:
                piles = playable(JOKER)
                if piles:
                    return [("play", "discard", d, piles[0])]
        return [("pass",)]
    candidates = [h for h, c in enumerate(player.hand) if c != JOKER] or list(range(len(player.hand)))
    h = max(candidates, key=lambda i: player.hand[i])
    card = player.hand[h]
    for d, stack in enumerate(player.discards):
        if stack and stack[-1] == card + 1:
            return [("discard", h, d)]
    for d, stack in enumerate(player.discards):
        if not stack:
            return [("discard", h, d)]
    d = max(range(DISCARD_PILES), key=lambda i: player.discards[i][-1] if player.discards[i][-1] else 13)
    return [("discard", h, d)]
