"""How many EDMCModernOverlay windows are running, so Check connection and Copy diagnostics can say when there is more than one.

Each overlay window draws everything it is sent. A second one (left running by an EDMC that closed without stopping it, then reconnecting to the next session) draws a second copy of
every card; while both use the same font the copies sit on top of each other unseen, and once the font changes (or the two differ in size or position) the text looks doubled or
ghosted. WNTB does not start or stop the overlay, so it can only report this. On Windows the overlay is started through a launcher that runs the real window as its child, so a
"window" is a process matching the overlay's command line whose parent is not also one. Nothing here is sent anywhere.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

MARKER = "overlay_client.overlay_client"        # the overlay's command line is `python -m overlay_client.overlay_client`
Entry = Tuple[int, int, str]                    # (pid, parent pid, command line)


def windows(entries: Sequence[Entry]) -> List[int]:
    """The process ids of the overlay windows among `entries`: processes running the overlay whose parent is not also running it (a launcher and its child are one window)."""
    matching = {pid: ppid for pid, ppid, command in entries if MARKER in (command or "")}
    return sorted(pid for pid, ppid in matching.items() if ppid not in matching)


def _from_psutil() -> Optional[List[Entry]]:
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError:
        return None
    entries = []
    for proc in psutil.process_iter(["pid", "ppid", "cmdline"]):
        try:
            entries.append((int(proc.info["pid"]), int(proc.info["ppid"] or 0), " ".join(proc.info["cmdline"] or [])))
        except Exception:
            continue
    return entries


def _from_proc() -> Optional[List[Entry]]:
    if not os.path.isdir("/proc"):
        return None
    entries = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/cmdline", "rb") as handle:
                command = handle.read().replace(b"\0", b" ").decode("utf-8", "replace")
            with open(f"/proc/{name}/stat", "rb") as handle:
                stat = handle.read().decode("utf-8", "replace")
            ppid = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        entries.append((int(name), ppid, command))
    return entries


def _from_powershell() -> Optional[List[Entry]]:
    if sys.platform != "win32":
        return None
    script = ("Get-CimInstance Win32_Process -Filter \"CommandLine like '%overlay_client%'\" | "
              "Select-Object ProcessId, ParentProcessId, CommandLine | ConvertTo-Json -Compress")
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=10,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
        data = json.loads(result.stdout) if result.stdout.strip() else []
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if isinstance(data, dict):
        data = [data]
    return [(int(item.get("ProcessId") or 0), int(item.get("ParentProcessId") or 0), str(item.get("CommandLine") or "")) for item in data]


def running_windows() -> Optional[List[int]]:
    """The overlay windows running now, or None when the process list cannot be read here. Can take a second on Windows; call it from a worker thread."""
    for read in (_from_psutil, _from_proc, _from_powershell):
        try:
            entries = read()
        except Exception:
            logger.debug("Could not read the process list with %s", read.__name__, exc_info=True)
            continue
        if entries is not None:
            return windows(entries)
    return None


def warning(found: Optional[Sequence[int]]) -> str:
    """The sentence Check connection adds when there is more than one overlay window; "" when there is one, none, or it could not be told."""
    if not found or len(found) < 2:
        return ""
    ids = ", ".join(str(pid) for pid in found)
    return (f"{len(found)} overlay windows are running (process {ids}). Each draws every card, so text can look doubled or ghosted. Close the extra ones "
            "(Task Manager on Windows; look for `overlay_client`) or all of them and restart EDMC.")


def summary(found: Optional[Sequence[int]]) -> str:
    """One line for Copy diagnostics."""
    if found is None:
        return "Overlay windows running: unknown"
    return f"Overlay windows running: {len(found)}" + (f" (process {', '.join(str(p) for p in found)})" if found else "")
