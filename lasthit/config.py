"""Tunable assumptions. Creep stats are approximate: check them against your patch."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CreepType:
    name: str
    max_hp: float
    armor: float


@dataclass
class Config:
    # A bar shows only a fraction of max HP and melee/ranged bars look identical,
    # so every bar is evaluated against each type listed here.
    creep_types: tuple = (CreepType("melee", 550, 2.0), CreepType("ranged", 300, 0.0))
    # Allies can only be denied below this share of their max HP.
    deny_below: float = 0.5
    # Damage readout location, in a 1440x900 frame, as offsets from HUD anchor
    # (screen centre x, screen bottom y). Scaled by frame height / 900.
    dmg_box: tuple = (-284, -116, -220, -40)   # (x0, y0, x1, y1)
    # Hero name label, same convention as dmg_box.
    name_box: tuple = (-380, -148, -200, -110)
    scan_interval: float = 0.0
