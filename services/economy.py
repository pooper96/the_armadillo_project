# services/economy.py
"""
Economy configuration constants for the mobile game.

Provides fixed costs, rewards, and configuration values that define the
game's economic balance. This module is pure Python, dependency-free,
and intended to be imported wherever economic values are needed.
"""

from typing import Final


class Economy:
    """Namespace container for game economy constants. Not meant to be instantiated."""

    # Costs (in coins)
    COST_FOOD: Final[int] = 5               # Buy one food item
    COST_TOY: Final[int] = 8                 # Buy one toy
    COST_HABITAT_UPGRADE: Final[int] = 25    # Upgrade habitat capacity/level
    COST_STATION_UNLOCK: Final[int] = 80     # Unlock an extra breeding station

    # Rewards (in coins)
    REWARD_CARE: Final[int] = 3              # Bonus for feeding & petting to high stats
    REWARD_HATCH: Final[int] = 12            # Reward for successful hatching

    # Breeding configuration
    INCUBATION_MIN_S: Final[int] = 30        # Minimum incubation time (seconds)
    INCUBATION_MAX_S: Final[int] = 90        # Maximum incubation time (seconds)
    DEFAULT_INCUBATION_S: Final[int] = 30    # MVP fixed incubation time
    MUTATION_CHANCE: Final[float] = 0.06     # 6% chance of rare blue mutation

    # Habitat upgrades
    UPGRADE_CAPACITY_DELTA: Final[int] = 1   # Capacity increment per upgrade
    UPGRADE_LEVEL_DELTA: Final[int] = 1      # Level increment per upgrade

    def __new__(cls, *args, **kwargs):
        raise TypeError(f"{cls.__name__} is not instantiable")


def clamp(n: int, lo: int, hi: int) -> int:
    """
    Clamp an integer value between inclusive lower and upper bounds.

    Args:
        n: The value to clamp.
        lo: Minimum allowed value.
        hi: Maximum allowed value.

    Returns:
        int: n limited to the range [lo, hi].

    Examples:
        >>> clamp(120, 0, 100)
        100
        >>> clamp(-5, 0, 100)
        0
    """
    return max(lo, min(n, hi))
