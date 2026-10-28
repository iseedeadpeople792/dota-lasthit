"""Run the pipeline on a saved screenshot and write an annotated copy."""
import sys
import time

import cv2

from lasthit.config import Config
from lasthit.engine import analyze, read_damage, read_hero

GREEN, YELLOW, WHITE, BLUE = (60, 230, 60), (0, 220, 255), (255, 255, 255), (255, 170, 60)


def draw(frame, hints):
    for h in hints:
        b = h.bar
        color = GREEN if h.green else YELLOW if h.yellow else WHITE
        if h.deny and not (h.green or h.yellow):
            color = BLUE
        if h.green or h.yellow:
            cv2.rectangle(frame, (b.x - 1, b.y - 2), (b.x + b.width + 1, b.y + 4), color, 2)
        text = ("D" if h.deny else "") + h.label
        cv2.putText(frame, text, (b.x + b.width // 2 - 8, b.y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, text, (b.x + b.width // 2 - 8, b.y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)


if __name__ == "__main__":
    cfg = Config()
    for path in sys.argv[1:]:
        frame = cv2.imread(path)
        dmg = read_damage(frame, cfg)
        hero = read_hero(frame, cfg)
        t = time.perf_counter()
        hints = analyze(frame, dmg, hero, cfg)
        ms = (time.perf_counter() - t) * 1000
        print(f"{path}: hero={hero}, damage={dmg}, {len(hints)} hints, analyze {ms:.0f} ms")
        for h in hints:
            print("  ", "ally " if h.deny else "enemy", f"{h.bar.ratio:.0%}", "hits", h.label,
                  "GREEN" if h.green else "yellow" if h.yellow else "")
        draw(frame, hints)
        cv2.imwrite(path.rsplit(".", 1)[0].split("/")[-1].split("\\")[-1] + "_out.png", frame)
