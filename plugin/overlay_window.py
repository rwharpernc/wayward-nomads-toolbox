"""WNTB's own overlay window (Windows): a transparent, click-through window laid over Elite that draws the scene.

It runs on a thread inside EDMC, so it lives and dies with EDMC: no overlay window can be left running behind to draw a second copy of every card. The thread owns the window and its message
loop, and every few hundredths of a second it finds Elite's window, follows its position and size, and redraws when the scene changed (`overlay_scene.py`, drawn by `overlay_raster.py`).
The window is topmost, layered (per-pixel alpha through `UpdateLayeredWindow`), transparent to the mouse and never takes focus, so clicks and keys reach the game. It shows only while Elite
is the window you are in (unless the player asks it to stay up, to take screenshots) and there is something to show, and it does not exist unless the player turns the built-in overlay on. Nothing here talks to the network.

The game has to run borderless or windowed: a fullscreen game owns the screen and nothing can be drawn over it.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
from ctypes import wintypes
from typing import Callable, Optional, Sequence, Tuple

from . import overlay_raster
from .overlay_scene import Scene

logger = logging.getLogger(__name__)

ELITE_CLASS = "FrontierDevelopmentsAppWinClass"
WINDOW_CLASS = "WNTBOverlayWindow"
TICK_S = 0.05

WS_POPUP = 0x80000000
WS_EX_TOPMOST, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_LAYERED, WS_EX_NOACTIVATE = 0x8, 0x20, 0x80, 0x80000, 0x8000000
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
ULW_ALPHA, AC_SRC_OVER, AC_SRC_ALPHA = 2, 0, 1
PM_REMOVE = 1
PER_MONITOR_AWARE_V2 = -4

Geometry = Tuple[int, int, int, int, float]        # x, y, width, height of the game's drawing area on the screen, and the display scaling (1.25 for 125%)


def supported() -> bool:
    return sys.platform == "win32"


if supported():
    LRESULT, WPARAM, LPARAM = ctypes.c_ssize_t, ctypes.c_size_t, ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)

    class BLENDFUNCTION(ctypes.Structure):
        _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte), ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
                    ("lpszClassName", wintypes.LPCWSTR)]

    user32, gdi32, kernel32 = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("gdi32", use_last_error=True), ctypes.WinDLL("kernel32", use_last_error=True)
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT), ctypes.POINTER(wintypes.SIZE), wintypes.HDC,
                                           ctypes.POINTER(wintypes.POINT), wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
    gdi32.SelectObject.restype = wintypes.HANDLE
    gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
    kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


def game_geometry(hwnd: int) -> Optional[Geometry]:
    """Where the game's drawing area is on the screen and the display scaling there, or None when the window is gone, minimized or empty."""
    if not hwnd or not user32.IsWindow(hwnd) or user32.IsIconic(hwnd):
        return None
    rect = wintypes.RECT()
    origin = wintypes.POINT(0, 0)
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)) or not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        return None
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return None
    try:
        ratio = user32.GetDpiForWindow(wintypes.HWND(hwnd)) / 96.0
    except (AttributeError, OSError):
        ratio = 1.0
    return origin.x, origin.y, width, height, ratio if ratio > 0 else 1.0


class OverlayWindow:
    """Owns the window thread. `geometry` is where the game is as of the last look (None when it is not running), for placement."""

    def __init__(self, scene: Scene, font_path: Callable[[], str] = overlay_raster.default_font_path, keep_showing: Callable[[], bool] = lambda: False,
                 groups: Callable[[], Sequence[str]] = lambda: ()) -> None:
        self.scene = scene
        self._font_path = font_path
        self._keep_showing = keep_showing
        self._groups = groups
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._hidden = False
        self.geometry: Optional[Geometry] = None
        self.error = ""

    # control ---------------------------------------------------------------------------------------------------------
    def start(self) -> None:
        if not supported() or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="WNTB-overlay-window", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=2.0)

    def set_hidden(self, hidden: bool) -> None:
        self._hidden = hidden

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # the thread ------------------------------------------------------------------------------------------------------
    def _run(self) -> None:
        try:
            self._loop()
        except Exception:
            self.error = "The built-in overlay stopped after an error; see EDMC's log."
            logger.exception("The built-in overlay window failed")

    def _loop(self) -> None:
        try:
            user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(PER_MONITOR_AWARE_V2))      # real pixels for this thread's window and for the game's
        except (AttributeError, OSError):
            pass
        hinst = kernel32.GetModuleHandleW(None)
        proc = WNDPROC(lambda hwnd, msg, wp, lp: user32.DefWindowProcW(hwnd, msg, wp, lp))     # kept referenced: Windows calls it
        wndclass = WNDCLASSW()
        wndclass.lpfnWndProc, wndclass.hInstance, wndclass.lpszClassName = proc, hinst, WINDOW_CLASS
        user32.RegisterClassW(ctypes.byref(wndclass))                                          # fails harmlessly if a restart left the class registered
        style = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        hwnd = user32.CreateWindowExW(style, WINDOW_CLASS, "WNTB overlay", WS_POPUP, 0, 0, 16, 16, None, None, hinst, None)
        if not hwnd:
            self.error = "Could not create the built-in overlay window."
            logger.error("%s (error %s)", self.error, ctypes.get_last_error())
            return
        screen_dc = user32.GetDC(None)
        mem_dc = gdi32.CreateCompatibleDC(screen_dc)
        canvas = _Canvas(mem_dc)
        fonts = overlay_raster.Fonts(self._font_path())
        elite = 0
        shown, last = False, None
        try:
            while not self._stop.is_set():
                self._pump()
                if not elite or not user32.IsWindow(elite):
                    elite = user32.FindWindowW(ELITE_CLASS, None) or 0
                geometry = game_geometry(elite)
                self.geometry = geometry
                foreground = user32.GetForegroundWindow()
                items = self.scene.items()
                in_front = foreground in (elite, hwnd) or self._keep_showing()          # a screenshot tool or another window in front is not the game
                want = bool(geometry and items and not self._hidden and in_front)
                if want:
                    key = (geometry, self.scene.version)
                    if key != last or not shown:
                        x, y, width, height, ratio = geometry
                        image = overlay_raster.render(items, width, height, ratio, fonts, self._groups())
                        canvas.paint(hwnd, screen_dc, x, y, image)
                        last = key
                    if not shown:
                        user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
                        shown = True
                elif shown:
                    user32.ShowWindow(hwnd, SW_HIDE)
                    shown, last = False, None
                self._stop.wait(TICK_S)
        finally:
            user32.DestroyWindow(hwnd)
            canvas.close()
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(None, screen_dc)

    @staticmethod
    def _pump() -> None:
        msg = wintypes.MSG()
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


class _Canvas:
    """The 32-bit bitmap a frame is copied into before it is handed to the window, remade when the window changes size."""

    def __init__(self, mem_dc) -> None:
        self._dc = mem_dc
        self._bitmap = None
        self._size = (0, 0)
        self._bits = ctypes.c_void_p()

    def _ensure(self, width: int, height: int) -> None:
        if self._size == (width, height):
            return
        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, width * height * 4, 0, 0, 0, 0)
        bitmap = gdi32.CreateDIBSection(self._dc, ctypes.byref(header), 0, ctypes.byref(self._bits), None, 0)
        gdi32.SelectObject(self._dc, bitmap)
        if self._bitmap:
            gdi32.DeleteObject(self._bitmap)
        self._bitmap, self._size = bitmap, (width, height)

    def paint(self, hwnd, screen_dc, x: int, y: int, image) -> None:
        width, height = image.size
        self._ensure(width, height)
        ctypes.memmove(self._bits, image.convert("RGBa").tobytes("raw", "BGRa"), width * height * 4)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(hwnd, screen_dc, ctypes.byref(wintypes.POINT(x, y)), ctypes.byref(wintypes.SIZE(width, height)), self._dc,
                                   ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA)

    def close(self) -> None:
        if self._bitmap:
            gdi32.DeleteObject(self._bitmap)
            self._bitmap = None
