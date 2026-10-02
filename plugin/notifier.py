"""A tiny subscribe/notify helper, used where one module's data changes and
others need to redraw.

Callbacks run synchronously on the caller's thread, in the order they were
connected. A callback that raises is logged and skipped so one bad
subscriber can't stop the others from hearing about the change.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")


class Notifier:
    def __init__(self) -> None:
        self._subscribers: list[Callable[..., Any]] = []

    def connect(self, callback: Callable[..., Any]) -> None:
        self._subscribers.append(callback)

    def disconnect(self, callback: Callable[..., Any]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def notify(self, *args: Any) -> None:
        for callback in tuple(self._subscribers):
            try:
                callback(*args)
            except Exception:
                logger.exception("Subscriber %r failed", callback)
