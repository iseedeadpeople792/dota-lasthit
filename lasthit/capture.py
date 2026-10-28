"""Frames of the Dota 2 game area.

Primary source is Windows Graphics Capture (the OS window-capture API OBS and Discord use):
it runs on the GPU, is fast, and works even when other windows cover the game. Nothing is
injected into or read from the game process. If it cannot start, plain screen grabbing is
used instead.
"""
import ctypes
import ctypes.wintypes as wt
import threading
import time

import cv2
import mss
import numpy as np

from . import win

DWMWA_EXTENDED_FRAME_BOUNDS = 9


def _visible_origin(hwnd) -> tuple[int, int]:
    r = wt.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wt.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r))
    return r.left, r.top


class WindowCapture:
    """Latest game-area frame, pushed by the OS each time the game presents one."""

    def __init__(self, hwnd: int):
        from windows_capture import WindowsCapture
        self.hwnd, self.closed = hwnd, False
        self._latest = None
        self._lock = threading.Lock()
        self._new = threading.Event()
        capture = WindowsCapture(cursor_capture=False, draw_border=False, window_hwnd=hwnd)

        @capture.event
        def on_frame_arrived(frame, control):
            self._on_frame(frame.frame_buffer)

        @capture.event
        def on_closed():
            self.closed = True

        self._control = capture.start_free_threaded()

    def _on_frame(self, buf: np.ndarray) -> None:
        stamp = time.monotonic()
        box = win.client_rect(self.hwnd)
        if box is None:
            return
        ox, oy = box["left"] - _visible_origin(self.hwnd)[0], box["top"] - _visible_origin(self.hwnd)[1]
        part = buf[oy:oy + box["height"], ox:ox + box["width"]]
        if part.shape[0] != box["height"] or part.shape[1] != box["width"]:
            return                                         # window mid-resize
        frame = cv2.cvtColor(part, cv2.COLOR_BGRA2BGR)     # a copy: the buffer is only valid here
        with self._lock:
            self._latest = (stamp, frame)
        self._new.set()

    def get(self, timeout: float = 0.2):
        """Block until a frame newer than the last one returned arrives; (time, frame) or None."""
        if not self._new.wait(timeout):
            return None
        self._new.clear()
        with self._lock:
            return self._latest

    def stop(self) -> None:
        try:
            self._control.stop()
        except Exception:
            pass


class ScreenGrabCapture:
    """Fallback: copy the game area off the desktop (needs the game to be on top)."""

    def __init__(self, hwnd: int):
        self.hwnd, self.closed = hwnd, False
        self._sct = mss.MSS()

    def get(self, timeout: float = 0.2):
        box = win.client_rect(self.hwnd)
        if box is None:
            time.sleep(timeout)
            return None
        stamp = time.monotonic()
        return stamp, cv2.cvtColor(np.asarray(self._sct.grab(box)), cv2.COLOR_BGRA2BGR)

    def stop(self) -> None:
        self._sct.close()


def open_capture(hwnd: int):
    try:
        return WindowCapture(hwnd)
    except Exception as exc:                               # no WGC support, bad handle, ...
        print(f"Window capture unavailable ({exc}); falling back to screen grabbing.")
        return ScreenGrabCapture(hwnd)
