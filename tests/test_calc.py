import pytest
from lasthit.calc import evaluate, physical_multiplier


def test_zero_armor_is_full_damage():
    assert physical_multiplier(0) == 1


def test_two_armor_reduces_about_ten_percent():
    assert physical_multiplier(2) == pytest.approx(0.893, abs=0.001)


def test_negative_armor_increases_damage():
    assert physical_multiplier(-2) > 1


def test_one_shot_when_hp_below_min_damage():
    v = evaluate(hp=50, dmg_min=60, dmg_max=66)
    assert v.hits == 1 and v.one_shot


def test_maybe_when_only_high_roll_kills():
    v = evaluate(hp=63, dmg_min=60, dmg_max=66)
    assert not v.one_shot and v.maybe_one_shot and v.hits == 2


def test_hits_use_armor_reduction():
    # 550 hp, 50 dmg, armor 2 -> ~44.6 per hit -> 13 hits
    assert evaluate(550, 50, 50, armor=2).hits == 13


def test_dead_creep():
    assert evaluate(0, 50, 55).hits == 0


def test_invalid_damage():
    with pytest.raises(ValueError):
        evaluate(100, 0, 0)
