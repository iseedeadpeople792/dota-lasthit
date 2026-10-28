"""Follow creep bars across frames so overlay labels stay glued to them.

Detections are noisy (a few px) and arrive late (capture + analysis time). Each bar
becomes a track with a smoothed position and velocity; the overlay draws the track
extrapolated to "now", so it keeps moving with the camera between detections.
"""
import threading
import math
from collections import deque
from dataclasses import dataclass, field

from .engine import Hint

HOLD_SECONDS = 0.30        # keep a track alive this long after its bar was last seen
MAX_EXTRAPOLATION = 0.15   # never project further than this ahead of the last detection
MATCH_RADIUS = 40          # px at 900p, scaled by frame height
VOTES = 3                  # green/yellow need a majority of the last VOTES frames
# One-euro filter: heavy smoothing when a bar is still, light smoothing when it moves.
MIN_CUTOFF = 1.5           # Hz, smoothing of a still bar
BETA = 0.02                # cutoff gain per px/s of speed
D_CUTOFF = 1.0             # Hz, smoothing of the velocity estimate
MOVING_SPEED = 60.0        # px/s at 900p: slower than this is treated as standing still
OFFSET_TAU = 0.08          # s: a new measurement's correction is blended in over about this long


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


@dataclass
class Track:
    ally: bool
    x: float
    y: float
    width: float
    t: float
    vx: float = 0.0
    vy: float = 0.0
    tau: float = 0.0           # lag of the smoothed position behind the raw one, s
    moving: bool = False
    rx: float = 0.0            # last raw measurement, for the velocity estimate
    ry: float = 0.0
    hint: Hint | None = None
    seen: float = 0.0
    votes: deque = field(default_factory=lambda: deque(maxlen=VOTES))
    ox: float = 0.0            # correction still to be blended in, so the label never jumps
    oy: float = 0.0
    ot: float = 0.0

    def at(self, now: float) -> tuple[float, float]:
        if not self.moving:
            return self.x, self.y
        # project forward, and add back the lag the low-pass filter introduced
        dt = min(max(now - self.t, 0.0), MAX_EXTRAPOLATION) + self.tau
        return self.x + self.vx * dt, self.y + self.vy * dt

    def shown(self, now: float) -> tuple[float, float]:
        """Where the label is drawn: the estimate plus a correction that fades out."""
        x, y = self.at(now)
        fade = math.exp(-max(now - self.ot, 0.0) / OFFSET_TAU)
        return x + self.ox * fade, y + self.oy * fade


@dataclass(frozen=True)
class Drawable:
    x: float
    y: float
    width: float
    label: str
    green: bool
    yellow: bool
    deny: bool


class Tracker:
    def __init__(self):
        self._tracks: list[Track] = []
        self._lock = threading.Lock()

    def update(self, hints: list[Hint], now: float, frame_height: int = 900) -> None:
        radius = MATCH_RADIUS * frame_height / 900
        with self._lock:
            pairs = sorted(
                ((self._dist(t, h, now), ti, hi)
                 for ti, t in enumerate(self._tracks) for hi, h in enumerate(hints)
                 if t.ally == h.bar.ally),
                key=lambda p: p[0])
            used_t, used_h = set(), set()
            for d, ti, hi in pairs:
                if d > radius or ti in used_t or hi in used_h:
                    continue
                used_t.add(ti)
                used_h.add(hi)
                self._correct(self._tracks[ti], hints[hi], now, frame_height)
            for hi, h in enumerate(hints):
                if hi not in used_h:
                    t = Track(h.bar.ally, h.bar.x, h.bar.y, h.bar.width, now, seen=now,
                              rx=h.bar.x, ry=h.bar.y)
                    self._observe(t, h)
                    self._tracks.append(t)
            self._tracks = [t for t in self._tracks if now - t.seen <= HOLD_SECONDS]

    @staticmethod
    def _dist(t: Track, h: Hint, now: float) -> float:
        px, py = t.at(now)
        return ((px - h.bar.x) ** 2 + (py - h.bar.y) ** 2) ** 0.5

    @staticmethod
    def _observe(t: Track, h: Hint) -> None:
        t.hint = h
        t.votes.append((h.green, h.yellow))

    def _correct(self, t: Track, h: Hint, now: float, frame_height: int) -> None:
        dt = max(now - t.t, 1e-3)
        k = frame_height / 900
        mx, my = h.bar.x, h.bar.y
        before = t.shown(now)                              # what the viewer sees right now
        # velocity from the raw measurement, smoothed
        ad = _alpha(D_CUTOFF, dt)
        t.vx += ad * ((mx - t.rx) / dt - t.vx)
        t.vy += ad * ((my - t.ry) / dt - t.vy)
        speed = (t.vx ** 2 + t.vy ** 2) ** 0.5 / k
        cutoff = MIN_CUTOFF + BETA * speed
        a = _alpha(cutoff, dt)
        t.x += a * (mx - t.x)
        t.y += a * (my - t.y)
        t.tau = 1.0 / (2 * math.pi * cutoff)
        t.moving = speed > MOVING_SPEED
        t.rx, t.ry = mx, my
        t.width, t.t, t.seen = h.bar.width, now, now
        t.ox, t.oy, t.ot = 0.0, 0.0, now
        after = t.at(now)
        t.ox, t.oy = before[0] - after[0], before[1] - after[1]   # glide from old to new
        self._observe(t, h)

    def snapshot(self, now: float) -> list[Drawable]:
        out = []
        with self._lock:
            for t in self._tracks:
                if t.hint is None or now - t.seen > HOLD_SECONDS:
                    continue
                x, y = t.shown(now)
                g = sum(v[0] for v in t.votes) * 2 > len(t.votes)
                yl = sum(v[1] for v in t.votes) * 2 > len(t.votes)
                out.append(Drawable(x, y, t.width, t.hint.label, g, yl or g, t.ally))
        return out
