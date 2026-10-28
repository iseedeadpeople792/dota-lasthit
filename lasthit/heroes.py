"""Hero attack-damage spread, keyed by the name shown on the HUD."""
import difflib
import json
import re
from pathlib import Path

_DATA = json.loads(Path(__file__).resolve().parent.parent.joinpath("data", "heroes.json")
                   .read_text(encoding="utf8"))
_BY_KEY = {re.sub(r"[^a-z]", "", n.lower()): n for n in _DATA}
DEFAULT_HALF_RANGE = 3.0      # median across all heroes


def match_hero(ocr_text: str) -> str | None:
    key = re.sub(r"[^a-z]", "", ocr_text.lower())
    if len(key) < 3:
        return None
    hit = difflib.get_close_matches(key, _BY_KEY, n=1, cutoff=0.75)
    return _BY_KEY[hit[0]] if hit else None


def half_range(name: str | None) -> float:
    """Half of the min..max base attack range: the roll swing around the HUD number."""
    h = _DATA.get(name or "")
    return (h["max"] - h["min"]) / 2 if h else DEFAULT_HALF_RANGE
