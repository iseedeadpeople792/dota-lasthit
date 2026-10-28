"""Recognise which heroes are in the game from the top bar of a captured frame.

The bar shows each hero's portrait zoomed in a little (the Steam CDN '_sb' icon is the
uncropped version), with a health strip on top and an ability badge bottom-left. So we compare
only the face area, against several zoom/shift variants of every icon, and take the best.
Empty slots (no colour at all) and unsure matches are skipped rather than guessed.
Only pixels are read; nothing touches the game process.
"""
import itertools
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"
REF_HEIGHT = 900
# Top-bar geometry at 1440x900: left edge of the first slot, per team, and the slot pitch.
TEAMS = {"radiant": 374.0, "dire": 805.0}
SLOT_PITCH = 51.8
CONTENT = (2, 4, 48, 27)            # x offset, y, width, height of the portrait inside a slot
FACE_ROWS, FACE_COLS = (0.07, 0.74), (0.38, 0.99)   # face area, as fractions of the portrait
FEAT = (32, 18)                     # feature image size
ZOOMS = (1.0, 1.15, 1.3, 1.45, 1.6)
SHIFTS = (-6, -3, 0, 3, 6)          # px in the 59x33 icon
MIN_SCORE = 0.62                    # below this the slot is "not a hero we recognise"
MIN_GAP = 0.08                      # best must beat the runner-up (another hero) by this much
EMPTY_SAT, EMPTY_VAL = 25.0, 90.0   # empty slots: no colour and dim


@dataclass(frozen=True)
class Slot:
    team: str
    index: int            # 0 = leftmost slot of that team
    hero_key: str | None  # e.g. "earth_spirit"; None if empty or unsure
    score: float
    runner_up: float


def _feature(img: np.ndarray) -> np.ndarray:
    a = cv2.resize(img, FEAT, interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    a -= a.mean()
    n = np.linalg.norm(a)
    return a / n if n else a


def _face(part: np.ndarray) -> np.ndarray:
    h, w = part.shape[:2]
    return part[int(h * FACE_ROWS[0]):int(h * FACE_ROWS[1]), int(w * FACE_COLS[0]):int(w * FACE_COLS[1]) + 1]


_db = None


def _load():
    """(keys, owner index per template, template matrix, key -> (id, name))."""
    global _db
    if _db is None:
        keys, owners, rows = [], [], []
        for p in sorted((DATA / "heroicons").glob("*.png")):
            icon = cv2.imread(str(p))
            ih, iw = icon.shape[:2]
            keys.append(p.stem)
            for z, dx, dy in itertools.product(ZOOMS, SHIFTS, SHIFTS):
                cw, ch = int(iw / z), int(ih / z)
                x0, y0 = int((iw - cw) / 2 + dx), int((ih - ch) / 2 + dy)
                if x0 < 0 or y0 < 0 or x0 + cw > iw or y0 + ch > ih:
                    continue
                rows.append(_feature(_face(icon[y0:y0 + ch, x0:x0 + cw])))
                owners.append(len(keys) - 1)
        heroes = json.loads((DATA / "heroes.json").read_text(encoding="utf8"))
        info = {h["key"]: (h["id"], n) for n, h in heroes.items()}
        _db = (keys, np.array(owners), np.stack(rows), info)
    return _db


def _slot_image(frame: np.ndarray, team: str, i: int) -> np.ndarray | None:
    h, w = frame.shape[:2]
    s = h / REF_HEIGHT
    ox, y, cw, ch = CONTENT
    x = (TEAMS[team] + i * SLOT_PITCH + ox) * s
    xa, ya = round(x), round(y * s)
    part = frame[ya:ya + round(ch * s), xa:xa + round(cw * s)]
    return part if part.shape[0] >= 8 and part.shape[1] >= 8 else None


def _is_empty(part: np.ndarray) -> bool:
    hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
    return float(hsv[..., 1].mean()) < EMPTY_SAT and float(np.percentile(hsv[..., 2], 90)) < EMPTY_VAL


def classify(part: np.ndarray):
    """(best key, best score, runner-up score) for one portrait image."""
    keys, owners, mat, _ = _load()
    sims = mat @ _feature(_face(part))
    per_hero = np.full(len(keys), -1.0, np.float32)
    np.maximum.at(per_hero, owners, sims)
    order = np.argsort(per_hero)[::-1]
    return keys[order[0]], float(per_hero[order[0]]), float(per_hero[order[1]])


def read_slots(frame: np.ndarray) -> list[Slot]:
    out = []
    for team in TEAMS:
        for i in range(5):
            part = _slot_image(frame, team, i)
            if part is None or _is_empty(part):
                out.append(Slot(team, i, None, 0.0, 0.0))
                continue
            key, best, second = classify(part)
            ok = best >= MIN_SCORE and best - second >= MIN_GAP
            out.append(Slot(team, i, key if ok else None, best, second))
    return out


def detect(frame: np.ndarray) -> dict:
    """{'radiant': [{'id','name','key'}...], 'dire': [...], 'unsure': n} for recognised slots."""
    info = _load()[3]
    res = {"radiant": [], "dire": [], "unsure": 0}
    for s in read_slots(frame):
        if s.hero_key:
            hid, name = info[s.hero_key]
            res[s.team].append({"id": hid, "name": name, "key": s.hero_key})
        elif s.score > 0:
            res["unsure"] += 1             # something is there but we could not tell what
    return res
