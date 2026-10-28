from pathlib import Path

import cv2
import pytest

from lasthit.detect import find_bars

FIX = Path(__file__).parent / "fixtures"

# (x, y) of every creep bar in each hand-checked 1440x900 frame
EXPECTED = {
    "frame_a.jpg": [(944, 271), (708, 374), (709, 408), (764, 415), (729, 441),
                    (788, 447), (773, 483), (549, 574)],
    "frame_b.jpg": [(687, 283), (644, 315), (462, 432), (497, 451), (484, 494), (244, 593)],
}


@pytest.mark.parametrize("name", EXPECTED)
def test_finds_every_bar_and_nothing_else(name):
    bars = find_bars(cv2.imread(str(FIX / name)))
    got = sorted((b.x, b.y) for b in bars)
    want = sorted(EXPECTED[name])
    assert len(got) == len(want)
    for (gx, gy), (wx, wy) in zip(got, want):
        assert abs(gx - wx) <= 3 and abs(gy - wy) <= 3


def test_fill_ratio_of_known_bars():
    bars = {(b.x // 10, b.y // 10): b for b in find_bars(cv2.imread(str(FIX / "frame_a.jpg")))}
    assert bars[(76, 41)].ratio == pytest.approx(0.23, abs=0.04)   # enemy at 23%
