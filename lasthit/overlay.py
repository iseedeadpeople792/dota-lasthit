"""Transparent, click-through, always-on-top window glued to the Dota 2 window."""
import ctypes
import json
import os
import threading
import time

import cv2
from PyQt6 import QtCore, QtGui, QtWidgets

from . import status, win
from .capture import open_capture
from .config import Config
from .engine import analyze, read_damage, read_hero
from .track import Tracker

WDA_EXCLUDEFROMCAPTURE = 0x11
GREEN, YELLOW, WHITE, BLUE = (60, 230, 60), (255, 220, 0), (255, 255, 255), (80, 170, 255)
FRAME_MS = 16
DISPLAY_LEAD = 0.025   # s: Windows shows what we paint about this much later, so paint slightly ahead
# debug: leave the overlay visible to screen capture so it can be screenshotted
VISIBLE_TO_CAPTURE = os.environ.get("LASTHIT_VISIBLE") == "1"
# debug: append every painted frame (time + label positions) to this file
PAINT_LOG = os.environ.get("LASTHIT_LOG")


class Overlay(QtWidgets.QWidget):
    place = QtCore.pyqtSignal(int, int, int, int)      # physical px: left, top, width, height

    def __init__(self, ratio: float, tracker: Tracker):
        super().__init__()
        self._tracker = tracker
        self._ratio = ratio
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.place.connect(self._place)
        self._log = open(PAINT_LOG, "w", buffering=1) if PAINT_LOG else None
        self._timer = QtCore.QTimer(self, interval=FRAME_MS, timeout=self.update)

    def _place(self, left, top, width, height):
        r = self._ratio
        self.setGeometry(round(left / r), round(top / r), round(width / r), round(height / r))
        if not self.isVisible():
            self.show()
            if not VISIBLE_TO_CAPTURE:
                # keep our own drawing out of the screen grab, or it feeds back into detection
                ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), WDA_EXCLUDEFROMCAPTURE)
            self._timer.start()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setFont(QtGui.QFont("Segoe UI", 11, QtGui.QFont.Weight.Bold))
        k = 1 / self._ratio
        now = time.monotonic()
        drawn = self._tracker.snapshot(now + DISPLAY_LEAD)
        if self._log:
            self._log.write(json.dumps([now, [[d.x, d.y, d.label] for d in drawn]]) + "\n")
        for d in drawn:
            color = GREEN if d.green else YELLOW if d.yellow else BLUE if d.deny else WHITE
            x, y, w = d.x * k, d.y * k, d.width * k
            if d.green or d.yellow:
                p.setPen(QtGui.QPen(QtGui.QColor(*color), 2))
                p.setBrush(QtGui.QColor(*color, 140))
                p.drawRect(QtCore.QRectF(x, y - 1, w, 6 * k))
            text = ("D " if d.deny else "") + d.label
            rect = QtCore.QRectF(x, y - 24 * k, w, 20 * k)
            p.setPen(QtGui.QColor(0, 0, 0))
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                p.drawText(rect.translated(dx, dy), QtCore.Qt.AlignmentFlag.AlignCenter, text)
            p.setPen(QtGui.QColor(*color))
            p.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)


def run(cfg: Config | None = None, selftest: bool = False) -> int:
    cfg = cfg or Config()
    app = QtWidgets.QApplication([])
    tracker = Tracker()
    overlay = Overlay(app.primaryScreen().devicePixelRatio(), tracker)
    stop = threading.Event()

    seen = {"frame": None, "damage": None, "hero": None}

    def reader():
        """Text reading is slow (tens of ms), so it runs off the tracking loop."""
        damage_at = hero_at = -1e9
        while not stop.is_set():
            frame, now = seen["frame"], time.monotonic()
            if frame is not None and now - damage_at > 1.0:
                seen["damage"] = read_damage(frame, cfg) or seen["damage"]
                damage_at = now
            if frame is not None and now - hero_at > 5.0:
                seen["hero"] = read_hero(frame, cfg) or seen["hero"]
                hero_at = now
            time.sleep(0.1)

    reported_at = [0.0]

    def report(**fields):
        """Let the stats app see what we are doing (twice a second is plenty)."""
        now = time.monotonic()
        if now - reported_at[0] >= 0.5:
            reported_at[0] = now
            status.write(**fields)

    def worker():
        hwnd, cap, placed = None, None, None
        wlog = open(PAINT_LOG + ".work", "w", buffering=1) if PAINT_LOG else None
        try:
            while not stop.is_set():
                if hwnd is None or not win.u.IsWindow(hwnd):
                    hwnd = win.find_dota()
                    if cap:
                        cap.stop()
                        cap = None
                box = win.client_rect(hwnd) if hwnd else None
                if box is None or not win.is_foreground(hwnd):
                    tracker.update([], time.monotonic())     # not in game: show nothing
                    report(game_found=bool(box), in_game=False, hero=seen["hero"], damage=seen["damage"])
                    time.sleep(0.25)
                    continue
                if cap is None or cap.closed:
                    if cap:
                        cap.stop()
                    cap = open_capture(hwnd)
                if box != placed:                            # window moved or resized: follow it
                    overlay.place.emit(box["left"], box["top"], box["width"], box["height"])
                    placed = box
                got = cap.get(0.2)                           # next frame the game presents
                if got is None:
                    continue
                captured, frame = got                        # time the frame arrived
                grabbed = time.monotonic()
                seen["frame"] = frame
                if selftest and seen["damage"] is None:      # no reader thread: read once, inline
                    seen["damage"], seen["hero"] = read_damage(frame, cfg), read_hero(frame, cfg)
                damage = seen["damage"]
                hints = analyze(frame, damage, seen["hero"], cfg) if damage else []
                tracker.update(hints, captured, frame.shape[0])
                report(game_found=True, in_game=True, hero=seen["hero"], damage=damage, hints=len(hints),
                       capture=type(cap).__name__)
                if wlog:
                    done = time.monotonic()
                    wlog.write(json.dumps([captured, (grabbed - captured) * 1000, 0,
                                           (done - grabbed) * 1000, len(hints)]) + "\n")
                if selftest:
                    print(f"selftest ok: area {frame.shape[1]}x{frame.shape[0]}, "
                          f"hero={seen['hero']}, damage={damage}, hints={len(hints)}")
                    stop.set()
                    return
        finally:
            if cap:
                cap.stop()

    threading.Thread(target=worker, daemon=True).start()
    if not selftest:
        threading.Thread(target=reader, daemon=True).start()
    print("Overlay running (it follows the Dota 2 window). Close this console to stop.")
    code = app.exec()
    stop.set()
    status.clear()
    return code
