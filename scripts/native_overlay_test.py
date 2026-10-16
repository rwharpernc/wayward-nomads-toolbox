"""A test of WNTB drawing its own overlay, with no EDMCModernOverlay: a transparent, click-through window laid over Elite, drawing real WNTB cards.

This is a throwaway experiment to answer whether a built-in overlay would be good enough, not part of the plugin. Windows only. Run it from the repository, with Elite in borderless
or windowed mode (a fullscreen game owns the screen and nothing can draw over it):

    python scripts/native_overlay_test.py            # lay the cards over Elite (or the primary screen when Elite is not running)
    python scripts/native_overlay_test.py --screen   # cover the primary screen, whatever Elite is doing
    python scripts/native_overlay_test.py --always   # stay up even when Elite is not the window you are in

Press Ctrl+C in the console to stop. It needs Pillow (`pip install pillow`) for the drawing; the window is plain Win32 through ctypes. What to look at: whether the text edges are as clean as
the overlay's, whether the panels show the game through them (90% opaque), whether it follows Elite when you move or resize the game window, whether clicks and keys reach the game, whether it
hides when you alt-tab away, and whether the game stutters. It prints how long each redraw takes.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time
import types
from ctypes import wintypes
from unittest import mock

if sys.platform != "win32":
    sys.exit("This test is for Windows only.")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
for _name in ("myNotebook", "ttkHyperlinkLabel", "theme", "monitor", "plug", "l10n", "requests"):
    sys.modules.setdefault(_name, mock.MagicMock())
if "config" not in sys.modules:
    _config = types.ModuleType("config")
    _config.appname = "EDMarketConnector"
    _config.config = mock.MagicMock()
    sys.modules["config"] = _config

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from plugin import body_info_overlay, exobiology_overlay, expedition_log, expedition_log_overlay  # noqa: E402
from plugin import overlay_style  # noqa: E402
from plugin.overlay_card import CARD_PAD_X, CARD_PAD_Y  # noqa: E402

user32, gdi32, kernel32 = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.kernel32
LRESULT, WPARAM, LPARAM = ctypes.c_ssize_t, ctypes.c_size_t, ctypes.c_ssize_t

WS_POPUP = 0x80000000
WS_EX_TOPMOST, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_LAYERED, WS_EX_NOACTIVATE = 0x8, 0x20, 0x80, 0x80000, 0x8000000
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
ULW_ALPHA, AC_SRC_OVER, AC_SRC_ALPHA = 2, 0, 1
PM_REMOVE = 1
ELITE_CLASS = "FrontierDevelopmentsAppWinClass"


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte), ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.FindWindowW.restype = wintypes.HWND
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi32.SelectObject.restype = wintypes.HANDLE
user32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT), ctypes.POINTER(wintypes.SIZE), wintypes.HDC,
                                       ctypes.POINTER(wintypes.POINT), wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]


# --- the game window ---------------------------------------------------------------------------------------------------

def elite_window() -> int:
    return user32.FindWindowW(ELITE_CLASS, None) or 0


def client_rect(hwnd: int):
    """(x, y, width, height) of a window's drawing area on the screen."""
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    return origin.x, origin.y, rect.right - rect.left, rect.bottom - rect.top


def primary_screen():
    return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


# --- drawing -----------------------------------------------------------------------------------------------------------

def parse_color(text: str):
    """(r, g, b, a) for "#RRGGBB" or "#AARRGGBB"."""
    value = text.lstrip("#")
    if len(value) == 8:
        a, r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4, 6))
        return r, g, b, a
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return r, g, b, 255


def find_font() -> str:
    folder = os.path.join(os.environ.get("LOCALAPPDATA", ""), "EDMarketConnector", "plugins", "EDMCModernOverlay", "overlay_client", "fonts")
    for name in ("SourceSans3-Regular.ttf",):
        path = os.path.join(folder, name)
        if os.path.exists(path):
            return path
    return os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeui.ttf")


FONT_PATH = find_font()
_fonts = {}


def font(px: int) -> ImageFont.FreeTypeFont:
    px = max(8, px)
    if px not in _fonts:
        _fonts[px] = ImageFont.truetype(FONT_PATH, px)
    return _fonts[px]


def sample_cards(look):
    """(layout, card, anchor) for four real WNTB cards. `anchor` places a card: how far across (0 left, 0.5 centered, 1 right) and down the window it sits."""
    run = expedition_log_overlay.sample_run()
    ex = exobiology_overlay
    view = ex.sample_view()
    return [
        (ex.LAYOUT_STATUS, ex.build_status_card(view, "Sample System"), (0.5, 0.0)),
        (ex.LAYOUT_LIST, ex.build_list_card(view, "Sample System"), (0.0, 0.72)),
        (expedition_log_overlay.LAYOUT, expedition_log_overlay.build_card(run, expedition_log.parse_time("2026-10-16T10:14:00Z")), (0.0, 0.03)),
        (body_info_overlay.LAYOUT, body_info_overlay.build_card(body_info_overlay.sample_body()) if hasattr(body_info_overlay, "sample_body") else None, (1.0, 0.3)),
    ]


def render_frame(width: int, height: int, look, cards, stamp: str) -> Image.Image:
    """The whole overlay as one RGBA picture, one logical pixel of a card being `scale` real pixels (the window is judged against 1080 lines)."""
    scale = height / 1080.0
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width - 1, height - 1), outline=(255, 0, 255, 160))            # the edge of the window the overlay thinks it has
    draw.text((8, height - 22), stamp, font=font(14), fill=(255, 0, 255, 220))
    pad_x, pad_y = look.pad_x(CARD_PAD_X), look.pad_y(CARD_PAD_Y)
    for layout, card, (ax, ay) in cards:
        if card is None or not card:
            continue
        shapes, texts, card_w, card_h = layout.plan(card, look)
        sw, sh = card_w * scale, card_h * scale
        left = (width - sw) * ax
        top = height * ay
        ox, oy = left + pad_x * scale - layout.x * scale, top + pad_y * scale
        draw.rectangle((left, top, left + sw, top + sh), fill=parse_color(look.color("fill")))
        for kind, color, fill, x, y, w, h in shapes:
            if kind == "circle":
                cx, cy = ox + x * scale, oy + y * scale
                box = (cx, cy, cx + w * scale, cy + h * scale)
                fill_rgba = parse_color(fill)
                draw.ellipse(box, fill=fill_rgba if fill_rgba[3] else None, outline=parse_color(color), width=2)
            else:
                draw.rectangle((ox + x * scale, oy + y * scale, ox + (x + w) * scale, oy + (y + h) * scale), fill=parse_color(fill))
        for text, role, x, y, size in texts:
            px = round(overlay_style.LINE_PX.get(size, 16) * 0.8 * scale)
            draw.text((ox + x * scale, oy + y * scale), text, font=font(px), fill=parse_color(look.color(role)))
    return image


# --- the window --------------------------------------------------------------------------------------------------------

class Overlay:
    def __init__(self) -> None:
        self._proc = WNDPROC(lambda hwnd, msg, wp, lp: user32.DefWindowProcW(hwnd, msg, wp, lp))      # kept alive: Windows calls it
        hinst = kernel32.GetModuleHandleW(None)
        cls = WNDCLASSW()
        cls.lpfnWndProc, cls.hInstance, cls.lpszClassName = self._proc, hinst, "WNTBOverlayTest"
        user32.RegisterClassW(ctypes.byref(cls))
        style = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self.hwnd = user32.CreateWindowExW(style, "WNTBOverlayTest", "WNTB overlay test", WS_POPUP, 0, 0, 16, 16, None, None, hinst, None)
        self.shown = False
        self.screen_dc = user32.GetDC(None)
        self.mem_dc = gdi32.CreateCompatibleDC(self.screen_dc)
        self._bitmap = None
        self._size = (0, 0)
        self._bits = ctypes.c_void_p()

    def _ensure_bitmap(self, width: int, height: int) -> None:
        if self._size == (width, height):
            return
        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, width * height * 4, 0, 0, 0, 0)
        bitmap = gdi32.CreateDIBSection(self.mem_dc, ctypes.byref(header), 0, ctypes.byref(self._bits), None, 0)
        gdi32.SelectObject(self.mem_dc, bitmap)
        if self._bitmap:
            gdi32.DeleteObject(self._bitmap)
        self._bitmap, self._size = bitmap, (width, height)

    def show(self, visible: bool) -> None:
        if visible != self.shown:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE if visible else SW_HIDE)
            self.shown = visible

    def draw(self, rect, image: Image.Image) -> None:
        x, y, width, height = rect
        self._ensure_bitmap(width, height)
        ctypes.memmove(self._bits, image.convert("RGBa").tobytes("raw", "BGRa"), width * height * 4)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(self.hwnd, self.screen_dc, ctypes.byref(wintypes.POINT(x, y)), ctypes.byref(wintypes.SIZE(width, height)), self.mem_dc,
                                   ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA)

    def pump(self) -> None:
        msg = wintypes.MSG()
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--screen", action="store_true", help="cover the primary screen instead of following Elite")
    parser.add_argument("--always", action="store_true", help="stay visible when Elite is not the window you are in")
    parser.add_argument("--fps", type=float, default=5.0, help="redraws per second (the picture only changes when the window does or once a second)")
    args = parser.parse_args()

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)        # real pixels, so the window matches the game's size exactly
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()

    look = overlay_style.DEFAULT
    cards = sample_cards(look)
    overlay = Overlay()
    last_rect, last_draw, last_report = None, 0.0, 0.0
    frames, spent = 0, 0.0
    print(f"Font: {FONT_PATH}\nDrawing {sum(1 for c in cards if c[1])} cards. Ctrl+C stops.", flush=True)
    try:
        while True:
            overlay.pump()
            elite = 0 if args.screen else elite_window()
            rect = client_rect(elite) if elite else primary_screen()
            foreground = user32.GetForegroundWindow()
            visible = args.always or args.screen or not elite or foreground in (elite, overlay.hwnd)
            if not elite and not args.screen and last_rect is None:
                print("Elite's window was not found; covering the primary screen. Start Elite (borderless or windowed) and this follows it.")
            overlay.show(visible and rect[2] > 0 and rect[3] > 0)
            now = time.perf_counter()
            if visible and rect[2] > 0 and rect[3] > 0 and (rect != last_rect or now - last_draw >= 1.0):
                stamp = f"WNTB overlay test  {time.strftime('%H:%M:%S')}  window {rect[2]}x{rect[3]} at {rect[0]},{rect[1]}"
                start = time.perf_counter()
                overlay.draw(rect, render_frame(rect[2], rect[3], look, cards, stamp))
                spent += time.perf_counter() - start
                frames += 1
                last_rect, last_draw = rect, now
            if now - last_report >= 10 and frames:
                print(f"{frames} redraws, {spent / frames * 1000:.0f} ms each; window {last_rect}; visible={overlay.shown}")
                last_report, frames, spent = now, 0, 0.0
            time.sleep(1.0 / args.fps)
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        user32.DestroyWindow(overlay.hwnd)


if __name__ == "__main__":
    main()
