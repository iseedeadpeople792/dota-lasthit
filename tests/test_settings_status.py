import json

from lasthit import settings, status
from lasthit.config import Config


def test_clean_clamps_and_fills_defaults():
    v = settings.clean({"melee_hp": 99999, "ranged_hp": "abc", "deny_below": 0.0, "junk": 1})
    assert v["melee_hp"] == 3000.0                       # clamped
    assert v["ranged_hp"] == 300.0                       # not a number -> default
    assert v["deny_below"] == 0.1
    assert "junk" not in v and set(v) == set(settings.LIMITS)


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    saved = settings.save({"melee_hp": 600, "melee_armor": 3}, p)
    assert settings.load(p) == saved
    assert settings.load(p)["melee_hp"] == 600
    assert not list(tmp_path.glob("*.tmp"))              # temp file replaced, not left behind


def test_load_missing_or_broken_file_gives_defaults(tmp_path):
    assert settings.load(tmp_path / "none.json") == settings.clean(None)
    bad = tmp_path / "bad.json"; bad.write_text("{not json")
    assert settings.load(bad) == settings.clean(None)


def test_apply_changes_creep_types():
    cfg = settings.apply(Config(), {"melee_hp": 700, "ranged_armor": 1})
    by = {c.name: c for c in cfg.creep_types}
    assert by["melee"].max_hp == 700 and by["ranged"].armor == 1


def test_status_running_flag_goes_stale(tmp_path):
    p = tmp_path / "st.json"
    p.write_text(json.dumps({"t": 1000.0, "hero": "Axe"}))
    assert status.read(p, now=1001.0)["running"] is True
    assert status.read(p, now=1010.0)["running"] is False
    assert status.read(tmp_path / "missing.json") == {"running": False}
