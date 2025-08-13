# models/breeding.py
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import random
import time

from models.armadillo import Armadillo


ALLOWED_STATUS = {"incubating", "done"}
ALLOWED_ALLELES = {"A", "a", "B"}
_NAME_POOL = [
    "Pebble", "Sprocket", "Nugget", "Mochi", "Tango",
    "Pixel", "Bean", "Ziggy", "Clover", "Blu", "Amber",
]


def _validate_gene_string(g: str) -> None:
    if not isinstance(g, str) or len(g) != 2:
        raise ValueError("Gene string must be a 2-character string.")
    if any(ch not in ALLOWED_ALLELES for ch in g):
        raise ValueError("Gene string contains invalid alleles.")


def _phenotype_from_genes(g: str) -> str:
    if "B" in g:
        return "Blue"
    if "A" in g:
        return "Brown"
    return "Albino"


@dataclass
class BreedingJob:
    """
    Tracks a single breeding/incubation job between two parents.

    Fields:
        id: Unique job identifier.
        parent_m_id: Male parent ID.
        parent_f_id: Female parent ID.
        start_ts: Start time in epoch seconds.
        duration_s: Incubation duration in seconds (>= 1).
        status: "incubating" or "done".
        result: Newborn dict once hatched; otherwise None.
    """
    id: str
    parent_m_id: str
    parent_f_id: str
    start_ts: float
    duration_s: int
    status: str = "incubating"
    result: Optional[Dict[str, object]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.duration_s, int) or self.duration_s < 1:
            raise ValueError("duration_s must be an integer >= 1.")
        if self.status not in ALLOWED_STATUS:
            raise ValueError('status must be "incubating" or "done".')

    def to_dict(self) -> Dict[str, object]:
        """Serialize job to a plain dict suitable for JSON storage."""
        return {
            "id": self.id,
            "parent_m_id": self.parent_m_id,
            "parent_f_id": self.parent_f_id,
            "start_ts": float(self.start_ts),
            "duration_s": int(self.duration_s),
            "status": self.status,
            "result": self.result,
        }

    @staticmethod
    def from_dict(d: Dict[str, object]) -> "BreedingJob":
        """Deserialize from dict produced by to_dict()."""
        required = {
            "id", "parent_m_id", "parent_f_id", "start_ts", "duration_s", "status"
        }
        missing = required - set(d.keys())
        if missing:
            raise ValueError(f"Missing fields: {sorted(missing)}")
        return BreedingJob(
            id=str(d["id"]),
            parent_m_id=str(d["parent_m_id"]),
            parent_f_id=str(d["parent_f_id"]),
            start_ts=float(d["start_ts"]),
            duration_s=int(d["duration_s"]),
            status=str(d["status"]),
            result=d.get("result"),  # type: ignore[assignment]
        )

    def remaining(self, now: Optional[float] = None) -> int:
        """
        Seconds left until hatch, clamped to >= 0.

        Computed as: duration_s - (now - start_ts).
        """
        now_ts = time.time() if now is None else float(now)
        raw = self.duration_s - (now_ts - self.start_ts)
        return 0 if raw <= 0 else int(raw)

    def is_done(self, now: Optional[float] = None) -> bool:
        """
        True when countdown reached 0 and status is not already 'done'.
        """
        return self.status != "done" and self.remaining(now) == 0


def combine_genes(color_m: str, color_f: str, mutation_chance: float) -> Tuple[str, str]:
    """
    Combine parental color genes and apply optional mutation.

    Parents pass one allele each at random from their 2-char gene strings.
    With probability `mutation_chance` in [0,1], one random allele mutates to "B".
    Phenotype: if "B" in genes -> Blue; elif "A" in genes -> Brown; else Albino.
    Returns (child_genes, phenotype).
    """
    _validate_gene_string(color_m)
    _validate_gene_string(color_f)
    if not (0.0 <= mutation_chance <= 1.0):
        raise ValueError("mutation_chance must be between 0 and 1 inclusive.")

    allele_m = random.choice(list(color_m))
    allele_f = random.choice(list(color_f))
    child = [allele_m, allele_f]

    if random.random() < mutation_chance:
        idx = random.randrange(2)
        child[idx] = "B"

    child_genes = "".join(child)
    phenotype = _phenotype_from_genes(child_genes)
    return child_genes, phenotype


def make_baby_name() -> str:
    """Pick a newborn name from a small predefined pool."""
    return random.choice(_NAME_POOL)


def hatch_result(dad: Armadillo, mom: Armadillo, mutation_chance: float) -> Dict[str, object]:
    """
    Produce a newborn Armadillo dict from two parents and mutation chance.

    Newborn defaults: random sex, age_days=0, hunger=60, happiness=60,
    genes={"color": child_genes}, color=phenotype.
    """
    if dad.sex != "M" or mom.sex != "F":
        raise ValueError("Parent sexes must be dad='M' and mom='F'.")
    child_genes, phenotype = combine_genes(
        dad.genes.get("color", "Aa"), mom.genes.get("color", "Aa"), mutation_chance
    )
    baby = Armadillo(
        id=str(int(time.time() * 1000)),
        name=make_baby_name(),
        sex=random.choice(["M", "F"]),
        age_days=0,
        hunger=60,
        happiness=60,
        genes={"color": child_genes},
        color=phenotype,
    )
    return baby.to_dict()
