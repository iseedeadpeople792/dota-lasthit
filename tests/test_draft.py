from pathlib import Path

import cv2
import numpy as np
import pytest

from lasthit import draft

FIX = Path(__file__).parent / "fixtures"


def fake_slot(icon, rng):
    """What the game roughly does to an icon: zoom in, shift, health strip on top, ability badge."""
    ih, iw = icon.shape[:2]
    z = rng.choice([1.15, 1.3, 1.45])
    cw, ch = int(iw / z), int(ih / z)
    x0 = int((iw - cw) / 2 + rng.integers(-4, 5))
    y0 = int((ih - ch) / 2 + rng.integers(-3, 4))
    part = icon[max(y0, 0):max(y0, 0) + ch, max(x0, 0):max(x0, 0) + cw]
    out = cv2.resize(part, (48, 27), interpolation=cv2.INTER_AREA).astype(np.float32)
    out *= rng.uniform(0.85, 1.15)                                   # brightness
    out[:3] = (170, 90, 20)                                          # blue health strip
    out[14:, :14] = rng.integers(0, 255, 3)                          # ability badge
    out = cv2.GaussianBlur(out, (3, 3), 0.7)
    out += rng.normal(0, 3, out.shape)
    out = np.clip(out, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def test_methods_tells_all_heroes_apart_on_synthetic_slots():
    keys = draft._load()[0]
    rng = np.random.default_rng(7)
    right = wrong = rejected = 0
    wrong_list = []
    for key in keys:
        icon = cv2.imread(str(draft.DATA / "heroicons" / f"{key}.png"))
        got, best, second = draft.classify(fake_slot(icon, rng))
        accepted = best >= draft.MIN_SCORE and best - second >= draft.MIN_GAP
        if not accepted:
            rejected += 1
        elif got == key:
            right += 1
        else:
            wrong += 1
            wrong_list.append((key, got))
    n = len(keys)
    print(f"\nsynthetic slots: {n} heroes, right {right}, wrong {wrong}, rejected as unsure {rejected}", wrong_list[:5])
    assert wrong <= 1                    # a wrong name is worse than 'unsure'
    assert right >= 0.9 * n


def test_real_frames_find_the_own_hero_and_ignore_empty_slots():
    for name in ("frame_a.jpg", "frame_b.jpg"):
        res = draft.detect(cv2.imread(str(FIX / name)))
        assert [h["key"] for h in res["radiant"]] == ["earth_spirit"]
        assert res["dire"] == [] and res["unsure"] == 0


def test_empty_slot_is_never_a_hero():
    frame = cv2.imread(str(FIX / "frame_a.jpg"))
    slots = {(s.team, s.index): s for s in draft.read_slots(frame)}
    assert all(slots[("dire", i)].hero_key is None for i in range(5))


def test_rejects_plain_noise():
    rng = np.random.default_rng(1)
    junk = rng.integers(0, 255, (27, 48, 3), dtype=np.uint8)
    _, best, second = draft.classify(junk)
    assert not (best >= draft.MIN_SCORE and best - second >= draft.MIN_GAP)
