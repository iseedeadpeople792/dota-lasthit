"""Command-line helpers other programs can call: python -m lasthit.cli detect"""
import json
import sys
import time

from . import draft, settings, win
from .capture import open_capture
from .config import Config
from .engine import read_hero


def detect() -> dict:
    hwnd = win.find_dota()
    if not hwnd:
        return {"ok": False, "error": "Окно Dota 2 не найдено. Запусти игру и войди в матч."}
    if win.client_rect(hwnd) is None:
        return {"ok": False, "error": "Окно Dota 2 свёрнуто. Разверни игру."}
    cap = open_capture(hwnd)
    try:
        got = None
        for _ in range(10):
            got = cap.get(0.5)
            if got:
                break
            time.sleep(0.1)
        if not got:
            return {"ok": False, "error": "Не удалось получить кадр игры."}
        frame = got[1]
        res = draft.detect(frame)
        me = read_hero(frame, Config())            # our own hero, to tell allies from enemies
    finally:
        cap.stop()
    me_team = None
    if me:
        for team in ("radiant", "dire"):
            if any(h["name"] == me for h in res[team]):
                me_team = team
    return {"ok": True, "me": me, "me_team": me_team, **res}


def settings_get() -> dict:
    return {"ok": True, "values": settings.load(), "limits": {k: list(v) for k, v in settings.LIMITS.items()}}


def settings_set(raw: str) -> dict:
    try:
        return {"ok": True, "values": settings.save(json.loads(raw))}
    except (ValueError, OSError) as exc:
        return {"ok": False, "error": f"Не удалось сохранить настройки: {exc}"}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "detect":
        out = detect()
    elif cmd == "settings-get":
        out = settings_get()
    elif cmd == "settings-set":
        out = settings_set(sys.argv[2] if len(sys.argv) > 2 else "{}")
    else:
        out = {"ok": False, "error": f"unknown command {cmd!r}"}
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))
