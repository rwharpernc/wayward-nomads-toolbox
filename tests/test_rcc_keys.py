"""The Raven Colonial keys (rcc_keys.py): one per commander, saved, never shared."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugin import rcc_keys  # noqa: E402


class KeyTests(unittest.TestCase):
    def test_keys_are_per_commander_and_survive_a_reload(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = rcc_keys.RccKeys(folder)
            store.set("Alice", " key-a ")
            store.set("Bob", "key-b")
            again = rcc_keys.RccKeys(folder)
            self.assertEqual(again.get("alice"), "key-a")
            self.assertEqual(again.get("Bob"), "key-b")
            self.assertEqual(again.get("Carol"), "")
            self.assertFalse(any("alice" in name.lower() for name in os.listdir(folder)))

    def test_an_empty_key_forgets_and_no_commander_saves_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = rcc_keys.RccKeys(folder)
            store.set("Alice", "k")
            store.set("Alice", "")
            store.set("", "orphan")
            self.assertEqual(store.get("Alice"), "")
            self.assertEqual(store.get(""), "")


if __name__ == "__main__":
    unittest.main()
