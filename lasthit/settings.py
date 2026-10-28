"""User-editable assumptions, stored in settings.json next to main.py."""
import json
import os
import tempfile
from pathlib import Path

from .config import Config, CreepType

PATH = Path(__file__).resolve().parent.parent / "settings.json"

# key -> (default, min, max)
LIMITS = {
    "melee_hp": (550.0, 100.0, 3000.0),
    "melee_armor": (2.0, -5.0, 20.0),
    "ranged_hp": (300.0, 100.0, 3000.0),
    "ranged_armor": (0.0, -5.0, 20.0),
    "deny_below": (0.5, 0.1, 0.9),
}


def clean(raw: dict | None) -> dict:
    """Keep only known keys, coerce to numbers, clamp to sane ranges."""
    out = {}
    raw = raw or {}
    for key, (default, lo, hi) in LIMITS.items():
        try:
            v = float(raw.get(key, default))
        except (TypeError, ValueError):
            v = default
        out[key] = min(max(v, lo), hi)
    return out


def load(path: Path = PATH) -> dict:
    try:
        return clean(json.loads(path.read_text(encoding="utf8")))
    except (OSError, ValueError):
        return clean(None)


def save(values: dict, path: Path = PATH) -> dict:
    data = clean(values)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)                      # atomic: the overlay never reads a half-written file
    return data


def apply(cfg: Config, values: dict | None = None) -> Config:
    v = clean(values) if values is not None else load()
    cfg.creep_types = (CreepType("melee", v["melee_hp"], v["melee_armor"]),
                       CreepType("ranged", v["ranged_hp"], v["ranged_armor"]))
    cfg.deny_below = v["deny_below"]
    return cfg
