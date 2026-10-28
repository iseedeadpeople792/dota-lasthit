"""Last-hit math: how many hits a creep needs, and whether one hit finishes it."""
import math
from dataclasses import dataclass

ARMOR_FACTOR = 0.06


def physical_multiplier(armor: float) -> float:
    """Damage taken multiplier for physical damage (Dota 2 armor formula)."""
    return 1 - ARMOR_FACTOR * armor / (1 + ARMOR_FACTOR * abs(armor))


@dataclass(frozen=True)
class Verdict:
    hits: int          # hits needed even on the lowest damage roll
    one_shot: bool     # the next hit kills on the lowest roll (show green)
    maybe_one_shot: bool  # kills only on a high roll (show yellow)


def evaluate(hp: float, dmg_min: float, dmg_max: float, armor: float = 0.0) -> Verdict:
    if hp <= 0:
        return Verdict(0, True, True)
    mult = physical_multiplier(armor)
    low = dmg_min * mult
    high = dmg_max * mult
    if low <= 0:
        raise ValueError("damage must be positive")
    hits = math.ceil(hp / low)
    return Verdict(hits, hp <= low, hp <= high)
