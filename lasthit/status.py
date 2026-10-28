"""Tiny status file the overlay writes so other programs (the stats app) can show what it is doing."""
import json
import os
import tempfile
import time
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "status.json"
STALE_AFTER = 3.0          # seconds without an update = the overlay is not running


def write(**fields) -> None:
    data = {"pid": os.getpid(), "t": time.time(), **fields}
    try:
        fd, tmp = tempfile.mkstemp(dir=PATH.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf8") as f:
            json.dump(data, f)
        os.replace(tmp, PATH)
    except OSError:
        pass                                        # status is a nicety; never break the overlay


def read(path: Path = PATH, now: float | None = None) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return {"running": False}
    age = (now if now is not None else time.time()) - d.get("t", 0)
    d["running"] = age < STALE_AFTER
    d["age"] = round(age, 1)
    return d


def clear() -> None:
    try:
        PATH.unlink()
    except OSError:
        pass
