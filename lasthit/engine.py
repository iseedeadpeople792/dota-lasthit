"""Turn a captured frame into per-bar hints."""
import re
from dataclasses import dataclass

from . import calc
from .config import Config
from .detect import Bar, find_bars
from .heroes import half_range, match_hero
from .ocr import read_text

_DMG = re.compile(r"(\d+)\s*(?:\+\s*(\d+))?")


@dataclass(frozen=True)
class Hint:
    bar: Bar
    hits: tuple          # hits needed per creep type, same order as config
    green: bool          # guaranteed one-hit kill for every creep type
    yellow: bool         # one-hit kill possible for at least one creep type / roll
    deny: bool           # allied creep (can only be denied)

    @property
    def label(self) -> str:
        lo, hi = min(self.hits), max(self.hits)
        return str(lo) if lo == hi else f"{lo}-{hi}"


def _crop(frame, box):
    h, w = frame.shape[:2]
    s = h / 900
    x0, y0, x1, y1 = box
    return frame[int(h + y0 * s):int(h + y1 * s), int(w / 2 + x0 * s):int(w / 2 + x1 * s)]


def read_damage(frame, cfg: Config) -> int | None:
    box = _crop(frame, cfg.dmg_box)
    if box.size == 0:
        return None
    m = _DMG.search(read_text(box))
    return int(m.group(1)) + int(m.group(2) or 0) if m else None


def read_hero(frame, cfg: Config) -> str | None:
    box = _crop(frame, cfg.name_box)
    return match_hero(read_text(box)) if box.size else None


def analyze(frame, damage: float, hero: str | None, cfg: Config) -> list[Hint]:
    # The HUD shows the average hit; a real hit lands within +-half the hero's base range of it.
    swing = half_range(hero)
    lo, hi = damage - swing, damage + swing
    out = []
    for bar in find_bars(frame):
        if bar.ally and bar.ratio >= cfg.deny_below:
            continue
        verdicts = [calc.evaluate(bar.ratio * t.max_hp, lo, hi, t.armor) for t in cfg.creep_types]
        out.append(Hint(
            bar,
            tuple(v.hits for v in verdicts),
            all(v.one_shot for v in verdicts),
            any(v.maybe_one_shot for v in verdicts),
            bar.ally,
        ))
    return out
