"""EDMCOverlay transport: draws text/shapes on top of the game window via a
separate, optional helper app (https://github.com/inorton/EDMCOverlay) that
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
import os
import socket
import threading
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

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
    """EDMCModernOverlay (unlike classic EDMCOverlay) has a "Plugin Group"
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
    ImportError means either classic EDMCOverlay or no overlay plugin at
    all, both of which this is a silent no-op for. Safe to call on every
    plugin_start3."""
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

    def _connect_locked(self) -> socket.socket:
        cfg = self._cfg or load_config()
        try:
            port = int(cfg.port)
        except ValueError:
            port = int(DEFAULT_PORT)
        sock = socket.create_connection((cfg.host, port), timeout=CONNECT_TIMEOUT_S)
        self._sock = sock
        return sock

    def _send(self, payload: dict) -> None:
        """Raises OSError (e.g. EDMCOverlay isn't running, or the socket
        was reset) after trying once to reconnect - a single reconnect
        attempt covers "EDMCOverlay wasn't running yet" and "EDMCOverlay
        was restarted since our last send" without silently retrying
        forever on a send that's genuinely never going to land."""
        data = json.dumps(payload).encode("utf-8") + b"\n"
        with self._lock:
            sock = self._sock
            if sock is None:
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
        """Raises on failure (e.g. EDMCOverlay isn't running) — callers
        decide whether that should be swallowed (live feature paths) or
        surfaced (a Settings "Test" button)."""
        self._send({"id": msg_id, "text": text, "color": color, "x": x, "y": y, "ttl": ttl, "size": size})

    def send_shape(
        self, shape_id: str, shape: str, color: str, fill: str, x: int, y: int, w: int, h: int, ttl: int = 8,
        thickness: Optional[int] = None,
    ) -> None:
        """`fill`/`color` accept "#AARRGGBB" (alpha channel first) on both
        classic EDMCOverlay and EDMCModernOverlay. `thickness` (border
        width) is an EDMCModernOverlay-only extension - included only when
        given, and harmless on classic EDMCOverlay (an unknown JSON field,
        silently ignored by its Newtonsoft.Json deserializer)."""
        payload = {
            "id": shape_id, "shape": shape, "color": color, "fill": fill, "x": x, "y": y, "w": w, "h": h, "ttl": ttl,
        }
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


# --- Settings tab: the one shared host/port pair every overlay-drawing
# feature (Interdiction/Landing/Discovery) reuses, rather than each of them
# duplicating the same two fields on their own tab. ------------------------

_host_var: Optional[tk.StringVar] = None
_port_var: Optional[tk.StringVar] = None


def build_settings(notebook: nb.Notebook) -> None:
    global _host_var, _port_var

    frame = nb.Frame(notebook)
    frame.columnconfigure(0, weight=1)
    notebook.add(frame, text="Overlay Connection")

    cfg = load_config()

    nb.Label(
        frame,
        text=(
            "Connection to EDMCOverlay, a separate, optional helper app WNTB does not install or "
            "launch itself — used by Interdiction Warning, Landing, and Discovery Alerts below."
        ),
        wraplength=440, justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 8))

    host_row = tk.Frame(frame)
    host_row.grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)
    nb.Label(host_row, text="Host:").pack(side=tk.LEFT)
    _host_var = tk.StringVar(value=cfg.host)
    nb.EntryMenu(host_row, textvariable=_host_var, width=12).pack(side=tk.LEFT, padx=(4, 0))
    nb.Label(host_row, text="   Port:").pack(side=tk.LEFT)
    _port_var = tk.StringVar(value=cfg.port)
    nb.EntryMenu(host_row, textvariable=_port_var, width=6).pack(side=tk.LEFT, padx=(4, 0))


def save_settings() -> None:
    if _host_var is None:
        return
    save_config(
        OverlayConfig(
            host=(_host_var.get().strip() or DEFAULT_HOST),
            port=((_port_var.get().strip() if _port_var is not None else "") or DEFAULT_PORT),
        )
    )
