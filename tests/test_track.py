import random

from lasthit.detect import Bar
from lasthit.engine import Hint
from lasthit.track import Tracker


def hint(x, y, green=False, ally=False, hits=(3, 3)):
    return Hint(Bar(round(x), round(y), 66, 30, ally), hits, green, green, ally)


def test_label_follows_bar_between_detections():
    tr = Tracker()
    # bar scrolls right at 200 px/s, detected every 50 ms
    for k in range(10):
        tr.update([hint(100 + 200 * k * 0.05, 300)], now=k * 0.05)
    x_detected = 100 + 200 * 9 * 0.05
    d = tr.snapshot(now=9 * 0.05 + 0.05)[0]          # 50 ms after the last detection
    assert abs(d.x - (x_detected + 10)) < 4          # extrapolated, not stuck at the old spot


def test_jitter_is_smoothed():
    random.seed(1)
    tr = Tracker()
    xs = []
    for k in range(40):
        tr.update([hint(500 + random.choice((-3, -2, 2, 3)), 400)], now=k * 0.05)
        xs.append(tr.snapshot(now=k * 0.05)[0].x)
    swing = max(xs[10:]) - min(xs[10:])
    assert swing < 5                                  # raw input swings by 6


def test_track_survives_short_dropout_then_expires():
    tr = Tracker()
    tr.update([hint(100, 100)], now=0.0)
    tr.update([], now=0.1)
    assert len(tr.snapshot(now=0.1)) == 1
    tr.update([], now=0.5)
    assert tr.snapshot(now=0.5) == []


def test_two_bars_do_not_swap():
    tr = Tracker()
    for k in range(5):
        tr.update([hint(100, 100, hits=(2, 2)), hint(180, 100, hits=(7, 7))], now=k * 0.05)
    labels = {round(d.x, -1): d.label for d in tr.snapshot(now=0.2)}
    assert labels == {100: "2", 180: "7"}


def test_green_needs_majority_so_it_does_not_flicker():
    tr = Tracker()
    for k, g in enumerate([True, True, False, True]):
        tr.update([hint(100, 100, green=g)], now=k * 0.05)
    assert tr.snapshot(now=0.15)[0].green


def test_label_glides_instead_of_jumping_on_a_correction():
    tr = Tracker()
    for k in range(6):
        tr.update([hint(100, 100)], now=k * 0.05)
    before = tr.snapshot(now=0.25)[0].x
    tr.update([hint(140, 100)], now=0.25)            # bar really moved 40px
    right_after = tr.snapshot(now=0.25)[0].x
    later = tr.snapshot(now=0.5)[0].x
    assert abs(right_after - before) < 3             # no snap
    assert later > before + 25                       # but it does get there
