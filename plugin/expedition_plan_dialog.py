"""The window behind the Expedition window's **Road to Riches** and **Exomastery** buttons: ask Spansh's route planner for a list of systems worth
visiting near a route, and hand the stops back to the Expedition window to become an expedition.

The commander picks where to start (the system they are in, filled in) and, if they like, where to end; the ship's jump range (the last `Loadout`'s
maximum, to change); how far from the route to look; how many results; how far from the arrival star; and the least a body or signal must be worth.
Nothing is sent until **Plot** is pressed, and then only those values (see `spansh_planners.py`); the answer can take a minute or two, so the search
runs on a worker thread and this window says whether Spansh has queued it or is working on it. **Cancel** stops waiting.

`plan_route` is a module-level name so tests can replace the network call."""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
import tkinter as tk
from typing import Any, Callable, List, Optional, Tuple

from config import appname

from . import spansh_planners, system_autocomplete
from .uikit import palette as P
from .uikit.shell import WindowShell
from .uikit import style
from .uikit.widgets import FlatButton

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

POLL_MS = 300
ANIMATE_MS = 60
BAR_HEIGHT = 10
BLOCK = 0.28       # the moving block's share of the bar's width
SIZE = (700, 560)
MIN_SIZE = (620, 500)

plan_route = spansh_planners.plan

_BLURBS = {
    spansh_planners.RICHES: ("Spansh's Road to Riches picks the bodies worth the most to scan (and, if you tick the box, to map) near a route "
                             "and puts them in a good order. The most credits for the fewest jumps."),
    spansh_planners.EXOBIOLOGY: ("Spansh's Expressway to Exomastery picks the planets with the most valuable biological signals near a route "
                                 "and puts them in a good order."),
    spansh_planners.NEUTRON: ("Spansh's neutron plotter finds the fastest way between two systems for your ship's jump range, supercharging "
                              "at neutron stars on the way. Each system to jump to becomes a stop, marked when it is a neutron star."),
}
_VALUE_LABEL = {spansh_planners.RICHES: "Least a body is worth (credits)", spansh_planners.EXOBIOLOGY: "Least a planet's biology is worth (credits)"}
_NEUTRON_ROWS = ("start", "destination", "jump_range", "efficiency", "supercharge")


def open_dialog(parent: tk.Misc, kind: str, system: str, jump_range: Optional[float],
                on_done: Callable[[spansh_planners.PlanQuery, List[spansh_planners.PlannedStop]], None]) -> "PlanDialog":
    """Open the dialog. `on_done(query, stops)` is called on the main thread when Spansh has answered (with possibly no stops)."""
    return PlanDialog(parent, kind, system, jump_range, on_done)


class PlanDialog:
    def __init__(self, parent: tk.Misc, kind: str, system: str, jump_range: Optional[float],
                 on_done: Callable[[spansh_planners.PlanQuery, List[spansh_planners.PlannedStop]], None]) -> None:
        self._kind = kind
        self._on_done = on_done
        self._results: "queue.Queue[Tuple[Optional[spansh_planners.PlanQuery], Any]]" = queue.Queue()
        self._cancel: Optional[threading.Event] = None
        self._busy = False
        self._started = 0.0
        self._phase = 0.0
        self._spansh_note = ""
        title = spansh_planners.TITLES[kind]
        self._shell = WindowShell(parent, title, "Plan a route of places worth visiting", size=SIZE, min_size=MIN_SIZE)
        self._shell.window.protocol("WM_DELETE_WINDOW", self.close)
        self._plot_button = self._shell.add_action("Plot", self._plot, accent=True)
        self._shell.add_action("Cancel", self._cancel_or_close)

        body = self._shell.body
        tk.Label(body, text=_BLURBS[kind], fg=P.MUTED, bg=P.BG, justify="left", anchor="w", wraplength=620).pack(fill="x", pady=(0, P.PAD))
        form = tk.Frame(body, bg=P.PANE, padx=P.PAD, pady=P.PAD)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        self._vars = {
            "start": tk.StringVar(value=system), "destination": tk.StringVar(),
            "jump_range": tk.StringVar(value=f"{jump_range:g}" if jump_range else f"{spansh_planners.DEFAULT_JUMP_RANGE_LY:g}"),
            "radius": tk.StringVar(value=str(spansh_planners.DEFAULT_RADIUS_LY)),
            "max_results": tk.StringVar(value=str(spansh_planners.DEFAULT_MAX_RESULTS)),
            "max_distance": tk.StringVar(value=str(spansh_planners.DEFAULT_MAX_ARRIVAL_LS)),
            "min_value": tk.StringVar(value=str(spansh_planners.DEFAULT_MIN_VALUE.get(kind, 1))),
            "efficiency": tk.StringVar(value=str(spansh_planners.DEFAULT_EFFICIENCY)),
            "supercharge": tk.StringVar(value="4"),
        }
        rows = (("Start from", "start", "The system the route begins in. Filled in with the one you are in."),
                ("End at (optional)", "destination", "Leave empty for a route that just goes where the best places are."),
                ("Jump range (ly)", "jump_range", "Your ship's. Filled in from your last loadout when WNTB has seen one."),
                ("Look this far from the route (ly)", "radius", "How far off the route a place may be."),
                ("Most results", "max_results", "Up to 100."),
                ("Furthest from the arrival star (ls)", "max_distance", "Leaves out bodies that are a long way from where you arrive."),
                (_VALUE_LABEL.get(kind, ""), "min_value", "Fewer, better places with a higher number."),
                ("Efficiency (percent)", "efficiency", "Spansh's own starting value is 60."),
                ("Supercharge multiplier", "supercharge", "4 for most ships; 6 only if your ship overcharges at neutron stars."))
        if kind == spansh_planners.NEUTRON:
            rows = tuple(r for r in rows if r[1] in _NEUTRON_ROWS)
            rows = tuple((("End at", key, "The system the route goes to (required).") if key == "destination" else (label, key, hint))
                         for label, key, hint in rows)
        else:
            rows = tuple(r for r in rows if r[1] not in ("efficiency", "supercharge"))
        self._entries = {}
        for row, (label, key, hint) in enumerate(rows):
            tk.Label(form, text=label, fg=P.MUTED, bg=P.PANE, anchor="w").grid(row=row * 2, column=0, sticky="w", pady=(4, 0))
            entry = tk.Entry(form, textvariable=self._vars[key], width=36 if key in ("start", "destination") else 14)
            entry.grid(row=row * 2, column=1, sticky="w", padx=P.PAD_SM, pady=(4, 0))
            if key in ("start", "destination"):
                system_autocomplete.attach(entry, self._vars[key])
            entry.bind("<Return>", lambda _e: self._plot())
            self._entries[key] = entry
            tk.Label(form, text=hint, fg=P.MUTED, bg=P.PANE, anchor="w", wraplength=460, justify="left").grid(
                row=row * 2 + 1, column=1, sticky="w", padx=P.PAD_SM)
        self._flags = {"avoid_thargoids": tk.BooleanVar(value=True), "loop": tk.BooleanVar(value=False),
                       "use_mapping_value": tk.BooleanVar(value=False)}
        checks = [("Avoid systems the Thargoids control", "avoid_thargoids"), ("Come back to the start", "loop")]
        if kind == spansh_planners.NEUTRON:
            checks = []
        if kind == spansh_planners.RICHES:
            checks.insert(0, ("Count what mapping pays as well as the first scan", "use_mapping_value"))
        flags = tk.Frame(body, bg=P.BG)
        flags.pack(fill="x", pady=(P.PAD, 0))
        for text, key in checks:
            tk.Checkbutton(flags, text=text, variable=self._flags[key], fg=P.TEXT, bg=P.BG, selectcolor=P.PANE, activebackground=P.BG,
                           activeforeground=P.TEXT, anchor="w").pack(fill="x", anchor="w")
        tk.Label(body, text=("Pressing Plot sends Spansh the system names above and these numbers, nothing else. "
                             "The result becomes a new expedition you can edit, reorder and start."),
                 fg=P.MUTED, bg=P.BG, justify="left", anchor="w", wraplength=620).pack(fill="x", pady=(P.PAD, 0))
        # Shown while Spansh works, which can take a couple of minutes: a moving bar and the time waited, so it never looks stuck.
        self._activity = tk.Label(body, text="", fg=P.ACCENT, bg=P.BG, anchor="w", font=style.font(P.FONT_BOLD))
        self._activity.pack(fill="x", pady=(P.PAD, 2))
        self._bar = tk.Canvas(body, height=BAR_HEIGHT, bg=P.PANE, highlightthickness=0, bd=0)
        self._bar.pack(fill="x")
        self._shell.set_status("Check the numbers and press Plot.")
        self._entries["start"].focus_set()

    # --- the window ---------------------------------------------------------------------------------------------------

    @property
    def alive(self) -> bool:
        return self._shell.alive

    def lift(self) -> None:
        self._shell.window.lift()

    def close(self) -> None:
        if self._cancel is not None:
            self._cancel.set()
        self._shell.close()

    def _say(self, text: str) -> None:
        self._shell.set_status(text)

    def _cancel_or_close(self) -> None:
        if self._busy and self._cancel is not None:
            self._cancel.set()
            self._spansh_note = "Cancelling"
            self._say("Cancelling...")
        else:
            self.close()

    # --- the search -----------------------------------------------------------------------------------------------------

    def _number(self, key: str, label: str, whole: bool = True) -> Optional[float]:
        text = self._vars[key].get().strip().replace(",", "").replace("_", "")
        try:
            value = float(text)
        except ValueError:
            self._say(f"{label} should be a number.")
            self._entries[key].focus_set()
            return None
        if value <= 0:
            self._say(f"{label} should be more than 0.")
            self._entries[key].focus_set()
            return None
        return float(int(value)) if whole else value

    def _query(self) -> Optional[spansh_planners.PlanQuery]:
        start = " ".join(self._vars["start"].get().split())
        if not start:
            self._say("Type the system to start from.")
            self._entries["start"].focus_set()
            return None
        if self._kind == spansh_planners.NEUTRON:
            destination = " ".join(self._vars["destination"].get().split())
            if not destination:
                self._say("Type the system to end at.")
                self._entries["destination"].focus_set()
                return None
            reach, efficiency = self._number("jump_range", "Jump range", False), self._number("efficiency", "Efficiency")
            if reach is None or efficiency is None:
                return None
            boost = self._number("supercharge", "The supercharge multiplier")
            if boost is None:
                return None
            if int(boost) not in spansh_planners.SUPERCHARGE_CHOICES:
                self._say("The supercharge multiplier is 4 or 6.")
                self._entries["supercharge"].focus_set()
                return None
            return spansh_planners.PlanQuery(self._kind, start, reach, destination, efficiency=int(efficiency), supercharge=int(boost))
        numbers = {}
        for key, label, whole in (("jump_range", "Jump range", False), ("radius", "The distance from the route", True),
                                  ("max_results", "Most results", True), ("max_distance", "The distance from the arrival star", True),
                                  ("min_value", "The least worth", True)):
            number = self._number(key, label, whole)
            if number is None:
                return None
            numbers[key] = number
        return spansh_planners.PlanQuery(
            self._kind, start, numbers["jump_range"], " ".join(self._vars["destination"].get().split()), int(numbers["radius"]),
            int(numbers["max_results"]), int(numbers["max_distance"]), int(numbers["min_value"]),
            self._flags["use_mapping_value"].get() and self._kind == spansh_planners.RICHES, self._flags["avoid_thargoids"].get(),
            self._flags["loop"].get())

    def _plot(self) -> None:
        if self._busy:
            return
        query = self._query()
        if query is None:
            return
        self._busy = True
        self._started, self._phase, self._spansh_note = time.monotonic(), 0.0, ""
        self._cancel = threading.Event()
        self._plot_button.configure(text="Plotting...")
        self._plot_button.set_enabled(False)
        self._say("Sent to Spansh. It can take a minute or two. You can cancel at any time.")
        self._animate()
        threading.Thread(target=self._worker, args=(query, self._cancel), daemon=True).start()
        self._shell.window.after(POLL_MS, self._poll)

    def _animate(self) -> None:
        """Runs on the main thread via after(): a block sliding along the bar, and the time waited, until the search ends."""
        if not self.alive:
            return
        if not self._busy:
            self._bar.delete("all")
            return
        seconds = int(time.monotonic() - self._started)
        waited = f"{seconds // 60}:{seconds % 60:02d}"
        dots = "." * (1 + int(self._phase * 10) % 3)
        self._activity.configure(text=f"Plotting{dots}  {waited} waited" + (f"  ·  {self._spansh_note}" if self._spansh_note else ""), fg=P.ACCENT)
        width = max(self._bar.winfo_width(), 1)
        block = width * BLOCK
        left = (width + block) * (self._phase % 1.0) - block
        self._bar.delete("all")
        self._bar.create_rectangle(max(left, 0), 0, min(left + block, width), BAR_HEIGHT, fill=P.ACCENT, outline="")
        self._phase += ANIMATE_MS / 1600.0
        self._shell.window.after(ANIMATE_MS, self._animate)

    def _finished(self, message: str = "") -> None:
        """Back to the idle look; `message` (an error or a refusal) is shown where the progress was."""
        self._busy = False
        self._plot_button.configure(text="Plot")
        self._plot_button.set_enabled(True)
        self._bar.delete("all")
        self._activity.configure(text=message, fg=P.DANGER if message else P.ACCENT)

    def _worker(self, query: spansh_planners.PlanQuery, cancel: threading.Event) -> None:
        """Runs off the main thread: it must not touch any Tk widget. Progress goes through the queue."""
        def tell(text: str) -> None:
            if text:
                self._results.put((None, text))
        try:
            stops = plan_route(query, cancel, tell)
        except spansh_planners.RouteSearchError as err:
            self._results.put((query, str(err)))
        except Exception:
            logger.exception("Spansh route planner failed")
            self._results.put((query, "Could not reach Spansh. Check your connection and try again."))
        else:
            self._results.put((query, stops))

    def _poll(self) -> None:
        """Runs on the main thread via after(): safe to touch widgets."""
        done = None
        while True:
            try:
                query, payload = self._results.get_nowait()
            except queue.Empty:
                break
            if query is None:
                self._spansh_note = str(payload).rstrip(".")      # Spansh's queued/working word, shown beside the timer
            else:
                done = (query, payload)
        if done is None:
            if self.alive and self._busy:
                self._shell.window.after(POLL_MS, self._poll)
            return
        if not self.alive:
            self._busy = False
            return
        query, payload = done
        if isinstance(payload, str):
            self._finished(payload)
            self._say("Not plotted. Fix what it says, or try again.")
            return
        self._finished()
        self._on_done(query, payload)
        self.close()
