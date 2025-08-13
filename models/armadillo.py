# models/armadillo.py
from dataclasses import dataclass, field
from typing import Dict


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    """Clamp an integer to the inclusive range [lo, hi]."""
    if not isinstance(value, int):
        raise ValueError("Value must be an integer.")
    if lo > hi:
        raise ValueError("Lower bound cannot exceed upper bound.")
    return max(lo, min(hi, value))


@dataclass
class Armadillo:
    """
    Immutable-ish game model for an Armadillo creature.

    Fields:
        id: Unique identifier.
        name: Display name.
        sex: Biological sex, "M" or "F" only.
        age_days: Age in whole days (must be non-negative).
        hunger: Fullness meter, 0–100 (higher = fuller).
        happiness: Mood meter, 0–100.
        genes: Simple Mendelian genotype map, e.g., {"color": "Aa"}.
        color: Phenotype label derived elsewhere, e.g., "Brown".
        is_baby: Life-stage flag (auto-derived; True if age < 14).
        is_adult: Life-stage flag (auto-derived; True if age >= 14).
    """
    id: str
    name: str
    sex: str
    age_days: int
    hunger: int
    happiness: int
    genes: Dict[str, str] = field(default_factory=dict)
    color: str = "Brown"
    is_baby: bool = field(init=False, repr=False)
    is_adult: bool = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate and normalize fields; derive life-stage flags."""
        if self.sex not in {"M", "F"}:
            raise ValueError('sex must be "M" or "F".')
        if not isinstance(self.age_days, int) or self.age_days < 0:
            raise ValueError("age_days must be a non-negative integer.")
        self.hunger = _clamp(self.hunger)
        self.happiness = _clamp(self.happiness)

        if not isinstance(self.genes, dict):
            raise ValueError("genes must be a dict[str, str].")
        for k, v in self.genes.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValueError("genes keys and values must be strings.")

        self.is_adult = self.age_days >= 14
        self.is_baby = not self.is_adult

    def to_dict(self) -> Dict[str, object]:
        """Serialize to a plain dict suitable for JSON storage."""
        return {
            "id": self.id,
            "name": self.name,
            "sex": self.sex,
            "age_days": self.age_days,
            "hunger": self.hunger,
            "happiness": self.happiness,
            "genes": dict(self.genes),
            "color": self.color,
            "is_baby": self.is_baby,
            "is_adult": self.is_adult,
        }

    @staticmethod
    def from_dict(d: Dict[str, object]) -> "Armadillo":
        """
        Deserialize from a dict produced by to_dict().

        Round-trip safe: Armadillo.from_dict(x.to_dict()) preserves values.
        Life-stage flags are recomputed from age_days.
        """
        required = {
            "id", "name", "sex", "age_days", "hunger",
            "happiness", "genes", "color"
        }
        missing = required - d.keys()
        if missing:
            raise ValueError(f"Missing fields: {sorted(missing)}")
        return Armadillo(
            id=str(d["id"]),
            name=str(d["name"]),
            sex=str(d["sex"]),
            age_days=int(d["age_days"]),
            hunger=int(d["hunger"]),
            happiness=int(d["happiness"]),
            genes=dict(d["genes"]),  # type: ignore[arg-type]
            color=str(d["color"]),
        )

    def feed(self, amount: int) -> None:
        """
        Increase hunger (fullness) by amount; clamp to [0, 100].

        Args:
            amount: Non-negative integer to add.
        """
        if not isinstance(amount, int) or amount < 0:
            raise ValueError("amount must be a non-negative integer.")
        self.hunger = _clamp(self.hunger + amount)

    def pet(self, amount: int) -> None:
        """
        Increase happiness by amount; clamp to [0, 100].

        Args:
            amount: Non-negative integer to add.
        """
        if not isinstance(amount, int) or amount < 0:
            raise ValueError("amount must be a non-negative integer.")
        self.happiness = _clamp(self.happiness + amount)

    def age_up(self, days: int) -> None:
        """
        Advance age by a non-negative number of days and recompute life-stage.

        Args:
            days: Non-negative integer number of days to add.
        """
        if not isinstance(days, int) or days < 0:
            raise ValueError("days must be a non-negative integer.")
        self.age_days += days
        self.is_adult = self.age_days >= 14
        self.is_baby = not self.is_adult
