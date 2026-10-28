"""Find the Dota 2 window and its drawable area on the desktop (physical pixels)."""
import ctypes
import ctypes.wintypes as wt

u = ctypes.windll.user32
TITLE = "dota 2"


def _title(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    u.GetWindowTextW(hwnd, buf, 256)
    return buf.value.strip().lower()


def find_dota() -> int | None:
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def visit(hwnd, _):
        if u.IsWindowVisible(hwnd) and _title(hwnd) == TITLE:
            found.append(hwnd)
        return True

    u.EnumWindows(visit, 0)
    return found[0] if found else None


def client_rect(hwnd) -> dict | None:
    """Screen-space rectangle of the window's client area, or None if minimised."""
    if not u.IsWindow(hwnd) or u.IsIconic(hwnd):
        return None
    r = wt.RECT()
    u.GetClientRect(hwnd, ctypes.byref(r))
    p = wt.POINT(0, 0)
    u.ClientToScreen(hwnd, ctypes.byref(p))
    if r.right < 200 or r.bottom < 200:
        return None
    return {"left": p.x, "top": p.y, "width": r.right, "height": r.bottom}


def is_foreground(hwnd) -> bool:
    return u.GetForegroundWindow() == hwnd
