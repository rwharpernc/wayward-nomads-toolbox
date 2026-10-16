"""Overlay transport: draws text/shapes on top of the game window via a
separate, optional helper app (EDMCModernOverlay) that
listens on a local TCP socket and renders whatever it's sent. WNTB never
installs or launches that app itself — it's the user's own tool to have
running; this module just knows how to talk to it if it is.

Protocol: connect, send one JSON object + "\n", e.g.
`{"id": "x", "text": "hi", "color": "red", "x": 200, "y": 100, "ttl": 4}`.
No response is read back — sends are fire-and-forget.

IMPORTANT — the connection must stay open for as long as its graphics
should stay visible. Observed behavior: each TCP connection gets a client
id, and every graphic sent over it is tagged with that id; the `ttl` field
*does* control expiry independently, but the server additionally wipes *all*
graphics owned by a client the instant that connection disconnects —
regardless of their ttl. `OverlayClient` holds one
persistent connection open for its whole lifetime instead of one per send,
reconnecting lazily if it drops.

Kept generic (not feature-specific) so every mode's own module can reuse
one shared client/connection rather than each opening its own socket.
"""

from __future__ import annotations

import json
import logging
import math
import os
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_CFG_HOST = "wntb_overlay_host"
_CFG_PORT = "wntb_overlay_port"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "5010"

# Short — this is a local-loopback connection to an app that's either
# running (near-instant) or not (fails fast); a long timeout would stall
# journal processing waiting on a helper app that isn't there.
CONNECT_TIMEOUT_S = 1.0

# After a failed connection the client stays quiet for this long and fails
# new sends immediately, so a user with no overlay program installed costs
# almost nothing (no thread waiting on a connection per pickup, per
# screenshot, or once a second for Mining's stats). A Settings "Test" button
# builds its own fresh client, so it always tries for real.
COOLOFF_S = 30.0


@dataclass
class OverlayConfig:
    host: str = DEFAULT_HOST
    port: str = DEFAULT_PORT


def load_config() -> OverlayConfig:
    return OverlayConfig(
        host=config.get_str(_CFG_HOST) or DEFAULT_HOST,
        port=config.get_str(_CFG_PORT) or DEFAULT_PORT,
    )


def save_config(cfg: OverlayConfig) -> None:
    config.set(_CFG_HOST, cfg.host)
    config.set(_CFG_PORT, cfg.port)


def register_modern_overlay_groups(groups: Iterable[Tuple[str, str]]) -> None:
    """EDMCModernOverlay has a "Plugin Group"
    concept: per its own wiki (Concepts.md), groups exist so a feature's
    several shape/text ids scale/anchor together as one unit instead of
    each being anchored from its own tiny individual bounding box.

    `groups` is `(group_name, id_prefix)` pairs — each mode/feature module
    that wants its own overlay ids grouped contributes its own pair here;
    this module deliberately doesn't hardcode any feature's name, so
    load.py assembles the full list from whichever modes are active.

    Why every card registers a group: a background rect's *fill* renders
    invisible under EDMCModernOverlay when it is NOT part of a registered
    group, and grouping it fixes that. So every card-style overlay in this
    project (Landing, Inventory, Discovery, Interdiction, Mining,
    Screenshots) registers a group, including single-card features with no
    other shapes to scale/anchor alongside. (A blanket rule against
    grouping a single rect was tried and was wrong.) If overlay rendering
    seems wrong, verify via EDMCModernOverlay's own payload-log/debug log
    before assuming a rule.

    `overlay_plugin.overlay_api` is EDMCModernOverlay's own module, only
    importable when it's installed as a sibling EDMC plugin - a plain
    ImportError means no overlay plugin at all, which this is a silent no-op for. Safe to call on every
    plugin_start3."""
    groups = list(groups)
    from . import overlay_native
    overlay_native.set_groups(groups)          # the built-in overlay places each display as one piece too
    try:
        from overlay_plugin.overlay_api import define_plugin_group  # type: ignore[import-not-found]
    except ImportError:
        return

    all_prefixes = [prefix for _, prefix in groups]
    for group_name, prefix in groups:
        try:
            define_plugin_group(
                plugin_name="WNTB",
                plugin_matching_prefixes=all_prefixes,
                plugin_group_name=group_name,
                plugin_group_prefixes=[prefix],
            )
        except Exception:
            # Registration is a cosmetic best-effort nicety, not something
            # that should ever be able to break plugin startup or overlay
            # sends.
            logger.debug("Could not register EDMCModernOverlay plugin group %r", group_name, exc_info=True)


_applied_offsets: Dict[str, float] = {}   # the group offsets last sent to EDMCModernOverlay, so unchanged ones are not rewritten


def group_offsets_available() -> bool:
    """Whether EDMCModernOverlay's plugin API is there to offset a group (it is only importable when that plugin is installed)."""
    try:
        from overlay_plugin.overlay_api import define_plugin_group  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return False
    return True


def set_group_offsets(offsets: Mapping[str, float], plugin: str = "WNTB") -> bool:
    """Has EDMCModernOverlay move each registered group `offsets[group_name]` canvas units to the right. The overlay applies a
    group's offset after it clamps a shape to the canvas, which is what lets a display sit against the right-hand edge (see
    overlay_layout.py). This is the overlay's own plugin API, the same setting its Overlay Controller edits; it is written to
    the overlay's groupings file by the overlay itself. Returns True when every group was set (or was already set), False
    when the API is missing or a call failed; callers fall back to drawing where the clamp allows. Safe to call often:
    only offsets that changed are sent."""
    try:
        from overlay_plugin.overlay_api import define_plugin_group  # type: ignore[import-not-found]
    except ImportError:
        return False
    ok = True
    for group_name, value in offsets.items():
        value = round(float(value), 3)
        if _applied_offsets.get(group_name) == value:
            continue
        try:
            define_plugin_group(plugin_name=plugin, plugin_group_name=group_name, plugin_group_offset_x=value)
            _applied_offsets[group_name] = value
        except Exception:
            ok = False
            logger.debug("Could not set the EDMCModernOverlay offset of group %r", group_name, exc_info=True)
    return ok


# --- hiding every overlay for a while --------------------------------------------------------------------------------
# Everything WNTB draws goes through `OverlayClient._send`, so one switch here hides it all. While hidden, nothing is sent; what each display last drew is kept (with
# when) so it can be put back with the time it had left, which also brings back the displays that are drawn once and left up (Colonization lasts an hour). Hiding sends
# a clear for everything drawn so far, so the screen empties at once instead of as each display expires. The state is not saved: overlays are shown when EDMC starts.

_vis_lock = threading.Lock()
_hidden = False
_last: Dict[str, Tuple[Dict[str, Any], float]] = {}          # id -> (the payload last drawn, when)
_listeners: List[Callable[[bool], None]] = []
_MAX_REMEMBERED = 2000


def _clear_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """A payload that removes what `payload` drew (the overlay lets a short ttl and nothing to draw replace it)."""
    ident = payload["id"]
    if "text" in payload:
        return {"id": ident, "text": "", "color": "white", "x": payload.get("x", 0), "y": payload.get("y", 0), "ttl": 1, "size": payload.get("size", "normal")}
    shape = payload.get("shape", "rect")
    if shape == "vect":
        return {"id": ident, "shape": "vect", "color": payload.get("color", ""), "vector": [], "ttl": 1}
    if shape == "circle":
        return {**payload, "color": "", "fill": "", "ttl": 1}
    return {"id": ident, "shape": shape, "color": "", "fill": "", "x": payload.get("x", 0), "y": payload.get("y", 0), "w": 0, "h": 0, "ttl": 1}


def _remember(payload: Mapping[str, Any]) -> bool:
    """Notes what was drawn; True when everything is hidden, so it is not sent."""
    ident = payload.get("id")
    with _vis_lock:
        if ident:
            if (payload.get("ttl") or 0) > 1:
                _last[ident] = (dict(payload), time.monotonic())
            else:
                _last.pop(ident, None)               # a clear
            if len(_last) > _MAX_REMEMBERED:
                now = time.monotonic()
                for key in [k for k, (p, t) in _last.items() if now - t >= (p.get("ttl") or 0)]:
                    del _last[key]
        return _hidden


def all_hidden() -> bool:
    return _hidden


def on_visibility_change(callback: Callable[[bool], None]) -> None:
    """`callback(hidden)` runs, on whichever thread changed it, each time overlays are hidden or shown."""
    _listeners.append(callback)


def set_all_hidden(hidden: bool) -> None:
    """Hides every WNTB overlay (clearing what is on screen), or shows them again (putting back what had not run out)."""
    global _hidden
    with _vis_lock:
        if hidden == _hidden:
            return
        _hidden = hidden
        items = list(_last.items())
    now = time.monotonic()
    sender = OverlayClient()
    try:
        for ident, (payload, when) in items:
            if hidden:
                sender._send_raw(_clear_payload(payload))
            else:
                left = (payload.get("ttl") or 0) - (now - when)
                if left >= 1:
                    sender._send_raw({**payload, "ttl": math.ceil(left)})
    except OSError:
        logger.debug("Could not reach the overlay to %s it", "hide" if hidden else "show", exc_info=True)
    finally:
        sender.close()
    for callback in list(_listeners):
        try:
            callback(hidden)
        except Exception:
            logger.debug("An overlay visibility listener failed", exc_info=True)


def toggle_all_hidden() -> bool:
    """Flips between hidden and shown; returns whether they are now hidden."""
    set_all_hidden(not _hidden)
    return _hidden


class OverlayClient:
    """Holds one persistent connection open for the client's whole lifetime
    (see the module docstring for why this is required, not just an
    optimization) rather than one per send. Config is only actually
    re-read when a (re)connect is needed — normally just once, on the
    first send — since re-reading it on every already-connected send would
    have no effect anyway (a live host/port change can't migrate an
    already-open socket); a Settings change to host/port takes effect on
    this client's *next* reconnect.

    Sends are serialized with a lock: one shared `OverlayClient` instance
    is used across every mode, and each fires its render from its own
    background thread, so concurrent sends on the same socket are a real
    possibility, not just a theoretical one."""

    def __init__(self, cfg: Optional[OverlayConfig] = None) -> None:
        self._cfg = cfg
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._unavailable_until = 0.0  # time.monotonic() before which sends fail fast
        self._reported_unavailable = False  # log "no overlay found" once per outage

    def _connect_locked(self) -> socket.socket:
        cfg = self._cfg or load_config()
        try:
            port = int(cfg.port)
        except ValueError:
            port = int(DEFAULT_PORT)
        try:
            sock = socket.create_connection((cfg.host, port), timeout=CONNECT_TIMEOUT_S)
        except OSError:
            self._unavailable_until = time.monotonic() + COOLOFF_S
            if not self._reported_unavailable:
                self._reported_unavailable = True
                logger.info(
                    "No overlay found at %s:%s. On-screen features stay quiet until one is running "
                    "(see docs/OVERLAY_SETUP.md); will try again in %d seconds.",
                    cfg.host, port, int(COOLOFF_S))
            raise
        self._unavailable_until = 0.0
        self._reported_unavailable = False
        self._sock = sock
        return sock

    def retry_now(self) -> None:
        """Forget any recent failure so the next send tries to connect straight
        away (used when the host/port setting changes)."""
        with self._lock:
            self._unavailable_until = 0.0

    def _send(self, payload: dict) -> None:
        if _remember(payload):
            return                                   # every overlay is hidden: kept, not drawn
        self._send_raw(payload)

    def _send_raw(self, payload: dict) -> None:
        from . import overlay_native
        if overlay_native.accepting():          # WNTB's own overlay draws: no socket, no EDMCModernOverlay
            overlay_native.scene.apply(payload)
            return
        """Raises OSError (e.g. the overlay isn't running, or the socket
        was reset) after trying once to reconnect - a single reconnect
        attempt covers "the overlay wasn't running yet" and "the overlay
        was restarted since our last send" without silently retrying
        forever on a send that's genuinely never going to land."""
        data = json.dumps(payload).encode("utf-8") + b"\n"
        with self._lock:
            sock = self._sock
            if sock is None:
                if time.monotonic() < self._unavailable_until:
                    raise ConnectionRefusedError("no overlay found (cooling off before the next attempt)")
                sock = self._connect_locked()
            try:
                sock.sendall(data)
                return
            except OSError:
                self._close_locked()
            sock = self._connect_locked()
            sock.sendall(data)

    def _close_locked(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def close(self) -> None:
        """Drops the connection (if any) so the next send reconnects fresh.
        Safe to call whether or not a connection is currently open."""
        with self._lock:
            self._close_locked()

    def send_message(
        self, msg_id: str, text: str, color: str, x: int, y: int, ttl: int = 8, size: str = "normal",
    ) -> None:
        """Raises on failure (e.g. the overlay isn't running) — callers
        decide whether that should be swallowed (live feature paths) or
        surfaced (a Settings "Test" button)."""
        self._send({"id": msg_id, "text": text, "color": color, "x": x, "y": y, "ttl": ttl, "size": size})

    def send_shape(
        self, shape_id: str, shape: str, color: str, fill: str, x: int, y: int, w: int, h: int, ttl: int = 8,
        thickness: Optional[int] = None,
    ) -> None:
        """`fill`/`color` accept "#AARRGGBB" (alpha channel first). `thickness` (border
        width) is included only when given."""
        payload = {
            "id": shape_id, "shape": shape, "color": color, "fill": fill, "x": x, "y": y, "w": w, "h": h, "ttl": ttl,
        }
        if thickness is not None:
            payload["thickness"] = thickness
        self._send(payload)

    def send_circle(
        self, shape_id: str, color: str, fill: str, x: int, y: int, radius: int, ttl: int = 8, thickness: Optional[int] = None,
    ) -> None:
        """A "circle" shape centered on (x, y). A radius under 1 is dropped by the overlay, so a caller clears a circle by sending it with a
        short ttl and an empty color instead."""
        payload = {"id": shape_id, "shape": "circle", "color": color, "fill": fill, "x": int(x), "y": int(y), "radius": max(1, int(radius)), "ttl": ttl}
        if thickness is not None:
            payload["thickness"] = thickness
        self._send(payload)

    def send_vector(
        self, shape_id: str, points: list, color: str, ttl: int = 8,
    ) -> None:
        """A "vect" shape: connected line segments through `points` (each a
        dict with "x"/"y", and optionally "color"/"marker"/"text" for a
        per-point decoration - "marker" is "cross" or "circle"). A
        single-point list draws just that point's marker/text with no
        line. An empty list draws nothing (used to clear a previously-sent
        id before its ttl naturally expires)."""
        vector = [
            {
                "x": int(round(p["x"])),
                "y": int(round(p["y"])),
                **({"color": p["color"]} if p.get("color") else {}),
                **({"marker": p["marker"]} if p.get("marker") else {}),
                **({"text": p["text"]} if p.get("text") else {}),
            }
            for p in points
        ]
        self._send({"id": shape_id, "shape": "vect", "color": color, "vector": vector, "ttl": ttl})


def check_connection(host: str, port: str, timeout: float = CONNECT_TIMEOUT_S) -> Tuple[bool, str]:
    """Whether something is listening at host:port, and a plain-language result.
    Connects and immediately closes; sends nothing."""
    try:
        number = int(port)
    except (TypeError, ValueError):
        return False, f"'{port}' isn't a valid port number."
    try:
        socket.create_connection((host, number), timeout=timeout).close()
    except OSError:
        return False, (f"No overlay found at {host}:{number}. Start your overlay program first "
                       f"(see docs/OVERLAY_SETUP.md).")
    return True, f"Connected: an overlay is listening at {host}:{number}."


# --- Settings tab: the one shared host/port pair every overlay-drawing
# feature (Interdiction/Landing/Discovery) reuses, rather than each of them
# duplicating the same two fields on their own tab. ------------------------

_host_var: Optional[tk.StringVar] = None
_port_var: Optional[tk.StringVar] = None
_backend_var: Optional[tk.StringVar] = None
_keep_var: Optional[tk.BooleanVar] = None
_BACKEND_LABELS = {"modern": "EDMCModernOverlay (a separate app)", "builtin": "WNTB built-in overlay (Windows)"}


def _build_backend_choice(frame: tk.Misc) -> None:
    """Which overlay draws: EDMCModernOverlay, or WNTB's own window (Windows only; off until chosen)."""
    global _backend_var, _keep_var
    from . import overlay_native
    if not overlay_native.supported():
        _backend_var = None
        return
    box = tk.LabelFrame(frame, text="Which overlay draws")
    box.grid(row=5, column=0, sticky=tk.W + tk.E, padx=10, pady=(8, 10))
    _backend_var = tk.StringVar(value=_BACKEND_LABELS[overlay_native.selected()])
    nb.Label(box, text=("WNTB can draw its overlays itself, in a transparent window it lays over Elite (borderless or windowed only), instead of through EDMCModernOverlay. "
                        "It is new: try it, and switch back here if anything is off. Pick one; the host and port above are for EDMCModernOverlay. "
                        "Takes effect when you press OK."),
             wraplength=440, justify=tk.LEFT).grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=6, pady=(4, 6))
    nb.Label(box, text="Overlay:").grid(row=1, column=0, sticky=tk.W, padx=6, pady=2)
    tk.OptionMenu(box, _backend_var, *_BACKEND_LABELS.values()).grid(row=1, column=1, sticky=tk.W, pady=2)
    _keep_var = tk.BooleanVar(value=overlay_native.keep_showing())
    nb.Checkbutton(box, text="Keep showing when Elite is not the window in front (to take screenshots with another tool)", variable=_keep_var).grid(
        row=2, column=0, columnspan=2, sticky=tk.W, padx=6, pady=2)
    status = tk.StringVar(value=overlay_native.status_text())
    nb.Label(box, textvariable=status, wraplength=440, justify=tk.LEFT).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=6, pady=(2, 6))


def build_settings(notebook: nb.Notebook) -> None:
    global _host_var, _port_var

    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Overlay Connection")

    cfg = load_config()

    nb.Label(
        frame,
        text=(
            "Connection to EDMCModernOverlay (Windows and Linux). It is a separate, optional helper app that WNTB does not "
            "install or launch itself, used by the on-screen features. Every feature works without one."
        ),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 8))

    _build_backend_choice(frame)

    host_row = tk.Frame(frame)
    host_row.grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)
    nb.Label(host_row, text="Host:").pack(side=tk.LEFT)
    _host_var = tk.StringVar(value=cfg.host)
    nb.EntryMenu(host_row, textvariable=_host_var, width=12).pack(side=tk.LEFT, padx=(4, 0))
    nb.Label(host_row, text="   Port:").pack(side=tk.LEFT)
    _port_var = tk.StringVar(value=cfg.port)
    nb.EntryMenu(host_row, textvariable=_port_var, width=6).pack(side=tk.LEFT, padx=(4, 0))

    status_var = tk.StringVar(value="")

    def _check() -> None:
        host = _host_var.get().strip() or DEFAULT_HOST
        port = (_port_var.get().strip() if _port_var is not None else "") or DEFAULT_PORT
        status_var.set("Checking...")

        def worker() -> None:
            from . import overlay_native
            if overlay_native.accepting():
                ok, message = True, overlay_native.status_text()
            else:
                ok, message = check_connection(host, port)
            if ok:
                from . import overlay_processes
                extra = overlay_processes.warning(overlay_processes.running_windows())
                message = f"{message} {extra}".strip()
            try:
                frame.after(0, lambda: status_var.set(message))
            except tk.TclError:
                pass  # the settings window was closed while checking

        threading.Thread(target=worker, name="WNTB-overlay-check", daemon=True).start()

    check_row = tk.Frame(frame)
    check_row.grid(row=2, column=0, sticky=tk.W, padx=10, pady=(8, 2))
    tk.Button(check_row, text="Check connection", command=_check).pack(side=tk.LEFT)
    nb.Label(frame, textvariable=status_var, wraplength=440, justify=tk.LEFT).grid(
        row=3, column=0, sticky=tk.W, padx=10, pady=(2, 8))


def save_settings() -> None:
    if _backend_var is not None:
        from . import overlay_native, overlay_placement
        before = overlay_native.selected()
        overlay_native.save_choice("builtin" if _backend_var.get() == _BACKEND_LABELS["builtin"] else "modern")
        if _keep_var is not None:
            overlay_native.save_keep_showing(bool(_keep_var.get()))
        if overlay_native.selected() != before:
            overlay_native.apply_choice()
            overlay_placement.refresh()
    if _host_var is None:
        return
    save_config(
        OverlayConfig(
            host=(_host_var.get().strip() or DEFAULT_HOST),
            port=((_port_var.get().strip() if _port_var is not None else "") or DEFAULT_PORT),
        )
    )
