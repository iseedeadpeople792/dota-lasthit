import os
import sys

from lasthit import settings
from lasthit.config import Config
from lasthit.overlay import run

if __name__ == "__main__":
    cfg = settings.apply(Config())                    # creep stats from settings.json, if any
    if os.environ.get("LASTHIT_SHOW_ALL") == "1":     # debug: label every bar, even full-HP allies
        cfg.deny_below = 1.1
    sys.exit(run(cfg, selftest="--selftest" in sys.argv))
