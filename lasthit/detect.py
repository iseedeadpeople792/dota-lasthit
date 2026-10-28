"""Find creep health bars on a captured frame (BGR numpy array).

A creep bar is a thin horizontal strip: dark border row, three rows of
fill + empty (dark) pixels, dark border row. Matching on that shape (not on
colour alone) keeps creep bodies and terrain from producing false hits.
"""
from dataclasses import dataclass

import cv2
import numpy as np

REF_HEIGHT = 900          # screenshots were taken at 1440x900
REF_BAR_WIDTH = 65        # creep bar width at REF_HEIGHT, caps included
WIDTH_TOLERANCE = 0.12
HUD_TOP_FRACTION = 0.78    # rows below this are the game HUD, never creep bars
SCOREBOARD_FRACTION = 0.045  # rows above this are the top scoreboard
MAX_CANDIDATE_ROWS = 250   # safety cap on rows sent to the full analysis
MIN_FILL_PX = 3            # thinner fills are indistinguishable from dark terrain


@dataclass(frozen=True)
class Bar:
    x: int
    y: int          # y of the first fill row
    width: int
    fill: int       # filled pixels
    ally: bool

    @property
    def ratio(self) -> float:
        return self.fill / self.width


def _masks(frame: np.ndarray):
    b, g, r = cv2.split(frame)
    dark = cv2.max(cv2.max(b, g), r) < 46
    # cv2.subtract saturates at 0, so (g - r) > 20 reads as "g exceeds r by more than 20"
    ally = (g >= 95) & (cv2.subtract(g, r) > 20) & (cv2.subtract(g, b) > 30) & (r < 125)
    enemy = (r >= 90) & (cv2.subtract(r, g) > 25) & (cv2.subtract(g, b) > 6)
    return dark, ally, enemy


def _runs(valid: np.ndarray):
    """Yield (start, end_exclusive) of True-runs in a 1-D bool array."""
    padded = np.concatenate(([False], valid, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return zip(edges[::2], edges[1::2])


def _close(valid: np.ndarray, gap: int = 5) -> np.ndarray:
    """Bridge gaps of up to `gap` px caused by compression / anti-aliasing."""
    k = np.ones((1, gap), np.uint8)
    row = valid.astype(np.uint8)[None, :]
    return cv2.morphologyEx(row, cv2.MORPH_CLOSE, k)[0].astype(bool)


def _check(dark, fill, i, x0, x1):
    """Return fill pixel count if [x0,x1) at fill rows i+1..i+3 is a bar, else None."""
    top = dark[i, x0:x1].mean()                      # border rows y-1 and y+3
    bottom = dark[i + 4, x0:x1].mean()
    if (top + bottom) / 2 < 0.6 or min(top, bottom) < 0.35:
        return None
    cols = fill[i + 1:i + 4, x0:x1].any(axis=0)
    n = int(cols.sum())
    if n < MIN_FILL_PX or cols[: n + 4].sum() < n - 2:   # fill must be a left-aligned block
        return None
    per_row = fill[i + 1:i + 4, x0:x1].sum(axis=1)
    if per_row.min() < 0.3 * per_row.max():           # a real fill is a rectangle; a blob tapers to ~nothing
        return None
    if n < 0.2 * (x1 - x0):
        # Mostly-empty bars are indistinguishable from dark terrain by their insides, so
        # demand a sharp edge: just past both ends the background must not be dark too.
        rows = dark[i + 1:i + 4]
        sides = (rows[:, max(0, x0 - 4):max(0, x0 - 1)], rows[:, x1 + 1:x1 + 4])
        # judge each side on its own (a side past the screen edge is skipped)
        if any(side.size and 1 - side.mean() < 0.5 for side in sides) or min(top, bottom) < 0.75:
            return None
    return n


def find_bars(frame: np.ndarray) -> list[Bar]:
    h = frame.shape[0]
    scale = h / REF_HEIGHT
    ref = REF_BAR_WIDTH * scale
    wmin, wmax = ref * (1 - WIDTH_TOLERANCE), ref * (1 + WIDTH_TOLERANCE)
    top = int(h * SCOREBOARD_FRACTION)
    sub = frame[top:int(h * HUD_TOP_FRACTION) + 4]        # +4: bottom border row of the last bar

    dark_all, ally_all, enemy_all = _masks(sub)

    # Cheap scan: a bar is coloured fill squeezed between two dark border rows. Plain
    # terrain, grass and shadows rarely have that sandwich, so few rows survive.
    kernel_fill = np.ones((1, MIN_FILL_PX + 1), np.uint8)
    sandwich = dark_all[:-4] & dark_all[4:]
    rows_hit = np.zeros(sandwich.shape[0], bool)
    for m in (ally_all, enemy_all):
        votes = m[1:-3].astype(np.uint8) + m[2:-2] + m[3:-1]
        pat = (sandwich & (votes >= 2)).view(np.uint8)
        rows_hit |= cv2.morphologyEx(pat, cv2.MORPH_OPEN, kernel_fill).any(axis=1)
    cand = np.flatnonzero(rows_hit)[:MAX_CANDIDATE_ROWS]
    if not cand.size:
        return []

    k = len(cand)
    window = cand[:, None] + np.arange(5)                  # border, 3 fill rows, border
    dark, ally, enemy = dark_all[window], ally_all[window], enemy_all[window]
    kernel = np.ones((1, 5), np.uint8)
    dark_top = _prefix(dark[:, 0])
    dark_bottom = _prefix(dark[:, 4])
    found: list[Bar] = []
    for is_ally, fill in ((True, ally), (False, enemy)):
        cell = fill | dark
        band = (cell[:, 0].astype(np.uint8) + cell[:, 1] + cell[:, 2]) >= 2
        closed = cv2.morphologyEx(band.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
        pad = np.zeros((k, closed.shape[1] + 2), np.int8)
        pad[:, 1:-1] = closed
        edge = np.diff(pad, axis=1)
        rows, starts = np.nonzero(edge == 1)               # row-major, so starts/ends pair up
        _, ends = np.nonzero(edge == -1)
        keep = (ends - starts) >= wmin
        rows, starts, ends = rows[keep], starts[keep], ends[keep]
        if not rows.size:
            continue
        csum = _prefix(fill[:, 1] | fill[:, 2] | fill[:, 3])
        width = np.maximum(ends - starts, 1)
        top_dark = (dark_top[rows, ends] - dark_top[rows, starts]) / width
        bottom_dark = (dark_bottom[rows, ends] - dark_bottom[rows, starts]) / width
        ok = (csum[rows, ends] - csum[rows, starts] >= MIN_FILL_PX)   # some fill colour inside
        ok &= ((top_dark + bottom_dark) / 2 >= 0.6) & (np.minimum(top_dark, bottom_dark) >= 0.35)
        for j, x0, x1 in zip(rows[ok], starts[ok], ends[ok]):
            j, x0, x1 = int(j), int(x0), int(x1)
            if x1 - x0 > wmax:
                # run merged with dark surroundings: anchor on the fill's left edge
                cols = np.flatnonzero(fill[j, 1:4, x0:x1].any(axis=0))
                x0 += max(0, int(cols[0]) - 2)
                x1 = x0 + int(round(ref))
            n = _check(dark[j], fill[j], 0, x0, x1)
            if n is not None:
                found.append(Bar(x0, int(cand[j]) + 1 + top, x1 - x0, n, is_ally))
    return _dedupe(found)


def _prefix(mask: np.ndarray) -> np.ndarray:
    """Per-row running count along x, with a leading zero column: count in [a,b) = p[b]-p[a]."""
    out = np.zeros((mask.shape[0], mask.shape[1] + 1), np.int32)
    np.cumsum(mask, axis=1, dtype=np.int32, out=out[:, 1:])
    return out


def _dedupe(bars: list[Bar]) -> list[Bar]:
    out: list[Bar] = []
    for b in sorted(bars, key=lambda b: (b.y, b.x)):
        if any(abs(b.x - o.x) < 6 and abs(b.y - o.y) < 5 and b.ally == o.ally for o in out):
            continue
        out.append(b)
    return out
