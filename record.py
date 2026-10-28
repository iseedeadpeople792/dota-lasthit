"""Record a short burst of the Dota 2 client area into data/rec/ (for offline tuning)."""
import ctypes
import ctypes.wintypes as wt
import sys
import time
from pathlib import Path

import cv2
import mss
import numpy as np

u = ctypes.windll.user32


def find(title):
    out = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _):
        b = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(h, b, 256)
        if u.IsWindowVisible(h) and b.value.strip().lower() == title:
            out.append(h)
        return True
    u.EnumWindows(cb, 0)
    return out[0] if out else None


def client_rect(hwnd):
    r = wt.RECT()
    u.GetClientRect(hwnd, ctypes.byref(r))
    p = wt.POINT(0, 0)
    u.ClientToScreen(hwnd, ctypes.byref(p))
    return {"left": p.x, "top": p.y, "width": r.right, "height": r.bottom}


def focus(hwnd):
    u.keybd_event(0x12, 0, 0, 0)            # tap ALT: lets SetForegroundWindow succeed
    u.ShowWindow(hwnd, 9)
    u.SetForegroundWindow(hwnd)
    u.keybd_event(0x12, 0, 2, 0)


if __name__ == "__main__":
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 6
    dota = find("dota 2")
    me = u.GetForegroundWindow()
    if not dota:
        sys.exit("Dota 2 window not found")
    focus(dota)
    time.sleep(0.8)
    box = client_rect(dota)
    print("client area:", box, "foreground is dota:", u.GetForegroundWindow() == dota)
    frames = []
    with mss.MSS() as sct:
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < seconds:
            t = time.perf_counter() - t0
            frames.append((t, np.ascontiguousarray(np.asarray(sct.grab(box))[..., :3])))
    focus(me)                               # hand the screen back to the terminal
    out = Path("data/rec")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.jpg"):
        old.unlink()
    for i, (t, f) in enumerate(frames):
        cv2.imwrite(str(out / f"{i:04d}_{int(t*1000):05d}.jpg"), f, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"{len(frames)} frames in {seconds}s = {len(frames)/seconds:.1f} fps capture, saved to {out}")
