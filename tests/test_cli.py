import time
from pathlib import Path

import cv2

from lasthit import cli

FIX = Path(__file__).parent / "fixtures"


class FakeCapture:
    closed = False

    def __init__(self, frame):
        self.frame, self.stopped = frame, False

    def get(self, timeout=0.2):
        return time.monotonic(), self.frame

    def stop(self):
        self.stopped = True


def patch_game(monkeypatch, frame, found=True, minimized=False):
    cap = FakeCapture(frame)
    monkeypatch.setattr(cli.win, "find_dota", lambda: 77 if found else None)
    monkeypatch.setattr(cli.win, "client_rect", lambda h: None if minimized else {"left": 0, "top": 0, "width": 1440, "height": 900})
    monkeypatch.setattr(cli, "open_capture", lambda h: cap)
    return cap


def test_detect_finds_own_hero_and_side(monkeypatch):
    cap = patch_game(monkeypatch, cv2.imread(str(FIX / "frame_a.jpg")))
    out = cli.detect()
    assert out["ok"] and out["me"] == "Earth Spirit" and out["me_team"] == "radiant"
    assert [h["name"] for h in out["radiant"]] == ["Earth Spirit"] and out["dire"] == []
    assert cap.stopped                                   # the capture is always released


def test_detect_explains_when_game_is_missing_or_minimised(monkeypatch):
    patch_game(monkeypatch, None, found=False)
    assert not cli.detect()["ok"] and "не найдено" in cli.detect()["error"]
    patch_game(monkeypatch, None, minimized=True)
    assert "свёрнуто" in cli.detect()["error"]


def test_settings_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.settings, "PATH", tmp_path / "s.json")
    monkeypatch.setattr(cli.settings, "load", lambda path=tmp_path / "s.json": cli.settings.clean(__import__("json").loads(path.read_text()) if path.exists() else None))
    got = cli.settings_get()
    assert got["ok"] and got["values"]["melee_hp"] == 550 and "melee_hp" in got["limits"]
    bad = cli.settings_set("{not json")
    assert not bad["ok"] and "Не удалось" in bad["error"]
