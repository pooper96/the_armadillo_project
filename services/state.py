# services/state.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

from models.armadillo import Armadillo
from models.habitat import Habitat
from models.breeding import BreedingJob, hatch_result
from services.economy import Economy, clamp


@dataclass
class GameState:
    """
    Process-wide singleton holding all mutable game data and rules.

    Use GameState.instance() to access the single shared instance.
    Observers can subscribe to state changes via add_observer().
    """
    coins: int = 0
    inventory: Dict[str, int] = field(default_factory=dict)
    armadillos: List[Armadillo] = field(default_factory=list)
    habitats: List[Habitat] = field(default_factory=list)
    breeding_queue: List[BreedingJob] = field(default_factory=list)
    dex_colors: Set[str] = field(default_factory=set)
    selected_id: Optional[str] = None
    meta: Dict[str, object] = field(default_factory=dict)
    _observers: List[Callable[[], None]] = field(default_factory=list, repr=False)

    # --- Singleton plumbing ---
    _singleton: Optional["GameState"] = field(default=None, init=False, repr=False)

    @staticmethod
    def instance() -> "GameState":
        """Return the single shared GameState instance, creating it if needed."""
        if GameState._singleton is None:
            GameState._singleton = GameState()
        return GameState._singleton

    # --- Observers ---
    def add_observer(self, cb: Callable[[], None]) -> None:
        """Register a no-arg callback invoked after successful mutations."""
        if cb not in self._observers:
            self._observers.append(cb)

    def _notify(self) -> None:
        """Invoke all registered observers (exceptions are ignored)."""
        for cb in list(self._observers):
            try:
                cb()
            except Exception:
                continue

    # --- Queries ---
    def get_selected(self) -> Optional[Armadillo]:
        """Return the currently selected Armadillo, if any."""
        return self.get_by_id(self.selected_id) if self.selected_id else None

    def get_by_id(self, did: Optional[str]) -> Optional[Armadillo]:
        """Lookup an Armadillo by id."""
        if did is None:
            return None
        for d in self.armadillos:
            if d.id == did:
                return d
        return None

    # --- Mutations ---
    def seed_starters(self) -> None:
        """
        Initialize a fresh save with 3 armadillos, 3 habitats, 100 coins,
        starter inventory, empty breeding queue, and dex from starters.
        """
        self.coins = 100
        self.inventory = {"food": 3, "toy": 1}
        self.breeding_queue.clear()
        self.selected_id = None

        # Starters (distinct colors to seed Dex)
        self.armadillos = [
            Armadillo(id="d1", name="Pebble", sex="M", age_days=14,
                      hunger=70, happiness=70, genes={"color": "Aa"}, color="Brown"),
            Armadillo(id="d2", name="Mochi", sex="F", age_days=14,
                      hunger=65, happiness=75, genes={"color": "aa"}, color="Albino"),
            Armadillo(id="d3", name="Blu", sex="M", age_days=14,
                      hunger=80, happiness=60, genes={"color": "AB"}, color="Blue"),
        ]
        self.dex_colors = {d.color for d in self.armadillos}

        # Habitats (empty to start)
        self.habitats = [
            Habitat(id="h1", name="Grassland", capacity=2, level=1, occupants=[]),
            Habitat(id="h2", name="Desert", capacity=2, level=1, occupants=[]),
            Habitat(id="h3", name="Forest", capacity=2, level=1, occupants=[]),
        ]
        self._notify()

    def select(self, did: Optional[str]) -> None:
        """Select an armadillo by id, or clear selection with None."""
        if did is not None and self.get_by_id(did) is None:
            raise ValueError("Cannot select unknown armadillo id.")
        self.selected_id = did
        self._notify()

    def add_coins(self, amt: int) -> None:
        """Adjust coins by amt; result cannot be negative."""
        if not isinstance(amt, int):
            raise ValueError("amt must be int.")
        self.coins = max(0, self.coins + amt)
        self._notify()

    def buy(self, item: str, cost: int) -> bool:
        """Buy an item if enough coins; increments inventory on success."""
        if cost < 0:
            raise ValueError("cost must be >= 0.")
        if self.coins < cost:
            return False
        self.coins -= cost
        self.inventory[item] = self.inventory.get(item, 0) + 1
        self._notify()
        return True

    def upgrade_habitat(self, hid: str, cost: int, capacity_delta: int) -> bool:
        """Spend coins to upgrade a habitat's capacity and level."""
        hab = next((h for h in self.habitats if h.id == hid), None)
        if hab is None or cost < 0 or capacity_delta <= 0 or self.coins < cost:
            return False
        self.coins -= cost
        hab.capacity += capacity_delta
        hab.level += 1
        self._notify()
        return True

    def _care_reward_if_earned(self, d: Armadillo) -> None:
        """Award a care reward if both hunger and happiness exceed 80."""
        if d.hunger > 80 and d.happiness > 80:
            self.coins += Economy.REWARD_CARE

    def feed_selected(self) -> bool:
        """
        Feed the selected armadillo (+20 hunger) consuming one 'food'.
        Awards care reward if thresholds are met post-action.
        """
        d = self.get_selected()
        if d is None or self.inventory.get("food", 0) <= 0:
            return False
        d.feed(20)
        d.hunger = clamp(d.hunger, 0, 100)
        self.inventory["food"] -= 1
        self._care_reward_if_earned(d)
        self._notify()
        return True

    def pet_selected(self) -> bool:
        """
        Pet the selected armadillo (+15 happiness).
        Awards care reward if thresholds are met post-action.
        """
        d = self.get_selected()
        if d is None:
            return False
        d.pet(15)
        d.happiness = clamp(d.happiness, 0, 100)
        self._care_reward_if_earned(d)
        self._notify()
        return True

    def move_selected_to_habitat(self, hid: str) -> bool:
        """
        Move the selected armadillo to the specified habitat if capacity allows.
        Removes it from any previous habitat and avoids duplicate entries.
        """
        d = self.get_selected()
        target = next((h for h in self.habitats if h.id == hid), None)
        if d is None or target is None:
            return False
        # Remove from any habitat first
        for h in self.habitats:
            if d.id in getattr(h, "occupants", []):
                h.occupants = [x for x in h.occupants if x != d.id]
        # Capacity/enforce no-dup
        if len(target.occupants) >= target.capacity:
            return False
        if d.id not in target.occupants:
            target.occupants.append(d.id)
        self._notify()
        return True

    def adults(self) -> List[Armadillo]:
        """Return all adult armadillos (age_days >= 14)."""
        return [d for d in self.armadillos if d.age_days >= 14]

    def start_breeding(self, dad_id: str, mom_id: str, duration_s: int) -> Optional[BreedingJob]:
        """
        Queue a breeding job for valid adult M/F parents with distinct ids.
        Duration < 1 uses Economy.DEFAULT_INCUBATION_S.
        """
        if dad_id == mom_id:
            return None
        dad = self.get_by_id(dad_id)
        mom = self.get_by_id(mom_id)
        if not dad or not mom or dad.sex != "M" or mom.sex != "F":
            return None
        if not dad.is_adult or not mom.is_adult:
            return None
        dur = duration_s if duration_s >= 1 else Economy.DEFAULT_INCUBATION_S
        job = BreedingJob(
            id=f"b{len(self.breeding_queue)+1}",
            parent_m_id=dad_id,
            parent_f_id=mom_id,
            start_ts=self.meta.get("now_ts", 0.0) if isinstance(self.meta.get("now_ts"), float) else 0.0,
            duration_s=dur,
            status="incubating",
            result=None,
        )
        self.breeding_queue.append(job)
        self._notify()
        return job

    def breeding_tick(self, now: float) -> List[Armadillo]:
        """
        Progress breeding timers and hatch completed jobs.

        Returns a list of newborn Armadillo objects created this tick.
        Babies are added to mom's habitat if space is available.
        """
        self.meta["now_ts"] = float(now)
        newborns: List[Armadillo] = []
        remaining_jobs: List[BreedingJob] = []
        for job in self.breeding_queue:
            if job.start_ts == 0.0:
                job.start_ts = float(now)  # initialize start on first tick
            if job.is_done(now):
                dad = self.get_by_id(job.parent_m_id)
                mom = self.get_by_id(job.parent_f_id)
                if dad and mom:
                    baby_dict = hatch_result(dad, mom, mutation_chance=0.05)
                    job.status = "done"
                    job.result = baby_dict
                    baby = Armadillo.from_dict(baby_dict)
                    self.armadillos.append(baby)
                    self.dex_colors.add(baby.color)
                    # place in mom's habitat if space
                    mom_hab = next((h for h in self.habitats if mom.id in getattr(h, "occupants", [])), None)
                    if mom_hab and len(mom_hab.occupants) < mom_hab.capacity and baby.id not in mom_hab.occupants:
                        mom_hab.occupants.append(baby.id)
                    newborns.append(baby)
            else:
                remaining_jobs.append(job)
        self.breeding_queue = remaining_jobs
        if newborns:
            self._notify()
        return newborns

    # --- Serialization ---
    def to_dict(self) -> Dict[str, object]:
        """Serialize the entire game state to a JSON-friendly dict."""
        return {
            "coins": self.coins,
            "inventory": dict(self.inventory),
            "armadillos": [d.to_dict() for d in self.armadillos],
            "habitats": [h.to_dict() for h in self.habitats],
            "breeding_queue": [j.to_dict() for j in self.breeding_queue],
            "dex_colors": sorted(self.dex_colors),
            "selected_id": self.selected_id,
            "meta": dict(self.meta),
        }

    def from_dict(self, d: Dict[str, object]) -> None:
        """
        Load state from a dict produced by to_dict().

        Life-stage flags are recomputed by Armadillo.__post_init__.
        """
        self.coins = int(d.get("coins", 0))
        self.inventory = {str(k): int(v) for k, v in dict(d.get("inventory", {})).items()}
        self.armadillos = [Armadillo.from_dict(x) for x in list(d.get("armadillos", []))]
        self.habitats = [Habitat.from_dict(x) for x in list(d.get("habitats", []))]
        self.breeding_queue = [BreedingJob.from_dict(x) for x in list(d.get("breeding_queue", []))]
        self.dex_colors = set(map(str, d.get("dex_colors", [])))
        self.selected_id = d.get("selected_id") if d.get("selected_id") in {a.id for a in self.armadillos} else None
        self.meta = dict(d.get("meta", {}))
        # De-duplicate occupants and enforce capacity safety
        all_ids = {a.id for a in self.armadillos}
        for h in self.habitats:
            unique: List[str] = []
            for aid in getattr(h, "occupants", []):
                if aid in all_ids and aid not in unique:
                    unique.append(aid)
            h.occupants = unique[: max(0, h.capacity)]
        self._notify()
