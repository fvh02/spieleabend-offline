"""Shared bits for all games."""


class RuleError(Exception):
    """An action the rules don't allow; the message is shown to the player."""
