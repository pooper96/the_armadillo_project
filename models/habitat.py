# models/habitat.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Habitat:
    """
    Represents a habitat/pen that can hold a limited number of armadillos.

    Enforces:
      - level >= 1
      - capacity >= 0
      - 0 <= hatch_boost_pct <= 100
      - Occupant IDs are unique (order preserved)
    """
    id: str
    name: str
    level: int
    capacity: int
    occupants: List[str] = field(default_factory=list)
    hatch_boost_pct: int = 0

    def __post_init__(self) -> None:
        """Validate invariants and normalize occupants to be unique in order."""
        if self.level < 1:
            raise ValueError("level must be >= 1")
        if self.capacity < 0:
            raise ValueError("capacity must be >= 0")
        if not (0 <= self.hatch_boost_pct <= 100):
            raise ValueError("hatch_boost_pct must be in [0, 100]")

        # Deduplicate occupants while preserving order.
        seen = set()
        unique: List[str] = []
        for oid in self.occupants:
            if oid not in seen:
                unique.append(oid)
                seen.add(oid)
        self.occupants = unique

        # Capacity can be smaller than current occupants only if explicitly set so.
        # Disallow impossible state: more occupants than capacity.
        if len(self.occupants) > self.capacity:
            raise ValueError("occupants exceed capacity")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this habitat into a plain dict (round-trip safe)."""
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "capacity": self.capacity,
            "occupants": list(self.occupants),  # preserve order
            "hatch_boost_pct": self.hatch_boost_pct,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Habitat":
        """
        Deserialize a Habitat from a dict produced by `to_dict`.

        Missing optional fields default to sensible values; required fields must exist.
        """
        try:
            id_ = d["id"]
            name = d["name"]
            level = int(d["level"])
            capacity = int(d["capacity"])
        except KeyError as e:
            raise KeyError(f"Missing required field: {e.args[0]}") from e

        occupants_raw = d.get("occupants", [])
        if not isinstance(occupants_raw, list):
            raise TypeError("occupants must be a list of str")
        occupants = [str(x) for x in occupants_raw]

        hatch_boost = int(d.get("hatch_boost_pct", 0))
        return Habitat(
            id=id_,
            name=name,
            level=level,
            capacity=capacity,
            occupants=occupants,
            hatch_boost_pct=hatch_boost,
        )

    def has_space(self) -> bool:
        """Return True if there is capacity to add another occupant."""
        return len(self.occupants) < self.capacity

    def add(self, armadillo_id: str) -> bool:
        """
        Add an armadillo by ID if space remains and it isn't already present.

        Returns:
            True if added, False otherwise.
        """
        if not self.has_space():
            return False
        if armadillo_id in self.occupants:
            return False
        self.occupants.append(armadillo_id)
        return True

    def remove(self, armadillo_id: str) -> None:
        """Remove an armadillo by ID if present; no error if absent."""
        try:
            self.occupants.remove(armadillo_id)
        except ValueError:
            pass

    def upgrade(self, capacity_delta: int, level_delta: int = 1) -> None:
        """
        Upgrade the habitat's level and capacity.

        Raises:
            ValueError: if resulting level < 1, capacity < 0, or
                        capacity < current occupants.
        """
        new_level = self.level + int(level_delta)
        new_capacity = self.capacity + int(capacity_delta)
        if new_level < 1:
            raise ValueError("resulting level must be >= 1")
        if new_capacity < 0:
            raise ValueError("resulting capacity must be >= 0")
        if new_capacity < len(self.occupants):
            raise ValueError("resulting capacity cannot be less than occupants")
        self.level = new_level
        self.capacity = new_capacity
