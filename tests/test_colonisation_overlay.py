"""The Colonization shopping-list overlay card: what it lists, and how it is drawn and cleared."""
from __future__ import annotations

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "config" not in sys.modules:
    _stub = types.ModuleType("config")
    _stub.appname = "EDMarketConnector"
    _stub.config = types.SimpleNamespace(get_str=lambda key: "", default_journal_dir="")
    sys.modules["config"] = _stub

from unittest import mock  # noqa: E402

sys.modules.setdefault("myNotebook", mock.MagicMock())   # overlay.py builds Settings with it; not needed here

from plugin import colonisation, colonisation_overlay as card  # noqa: E402


def site(complete: bool = False) -> colonisation.Site:
    entry = {"MarketID": 7, "ConstructionComplete": complete, "ResourcesRequired": [
        {"Name": "$steel_name;", "Name_Localised": "Steel", "RequiredAmount": 500, "ProvidedAmount": 100},
        {"Name": "$water_name;", "Name_Localised": "Water", "RequiredAmount": 50, "ProvidedAmount": 0},
        {"Name": "$copper_name;", "Name_Localised": "Copper", "RequiredAmount": 20, "ProvidedAmount": 20}]}
    return colonisation.apply_depot_event(entry, None, name="Depot One", system="Sol")


class FakeClient:
    def __init__(self) -> None:
        self.sent = []

    def send_shape(self, shape_id, shape, color, fill, x, y, w, h, ttl=8, thickness=None):
        self.sent.append(("shape", shape_id, w, h, ttl))

    def send_message(self, msg_id, text, color, x, y, ttl=8, size="normal"):
        self.sent.append(("msg", msg_id, text, ttl))


class CardLinesTests(unittest.TestCase):
    def test_lists_what_is_left_after_the_hold_biggest_first(self) -> None:
        lines = card.card_lines(site(), {"steel": 100}, {})
        self.assertEqual([text for text, _ in lines], ["To source: Depot One", "300 t  Steel", "50 t  Water"])

    def test_shows_stock_on_the_carrier(self) -> None:
        lines = card.card_lines(site(), {}, {"water": 40})
        self.assertIn("50 t  Water  (FC 40)", [text for text, _ in lines])

    def test_row_limit_is_summarized(self) -> None:
        lines = card.card_lines(site(), {}, {}, max_rows=1)
        self.assertEqual([text for text, _ in lines][-2:], ["400 t  Steel", "+1 more"])

    def test_nothing_to_draw(self) -> None:
        self.assertEqual(card.card_lines(None, {}, {}), [])
        self.assertEqual(card.card_lines(site(complete=True), {}, {}), [])
        self.assertEqual(card.card_lines(site(), {"steel": 400, "water": 50}, {}), [])


class RenderTests(unittest.TestCase):
    def test_draws_card_and_rows(self) -> None:
        client = FakeClient()
        rows = card.render(client, card.preview_lines(), 20, 300)
        self.assertEqual(rows, len(card.preview_lines()))
        self.assertEqual(client.sent[0][:2], ("shape", card.CARD_ID))
        self.assertEqual(sum(1 for item in client.sent if item[0] == "msg"), rows)

    def test_shorter_list_clears_leftover_rows(self) -> None:
        client = FakeClient()
        card.render(client, card.preview_lines()[:2], 20, 300, previous_rows=4)
        cleared = [item for item in client.sent if item[0] == "msg" and item[2] == ""]
        self.assertEqual(len(cleared), 2)

    def test_empty_clears_everything(self) -> None:
        client = FakeClient()
        self.assertEqual(card.render(client, [], 20, 300, previous_rows=3), 0)
        self.assertEqual(client.sent[0][1], card.CARD_ID)
        self.assertEqual(sum(1 for item in client.sent if item[0] == "msg"), 3)


if __name__ == "__main__":
    unittest.main()
