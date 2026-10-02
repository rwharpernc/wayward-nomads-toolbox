"""
Unit tests for plugin/overlay.py's connection handling: what happens when no
overlay program is running (fail fast, cool off, recover) and the settings
tab's connection check.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import socket
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# overlay.py imports EDMC's config and myNotebook at the top; stub them.
_config = types.ModuleType("config")
_config.appname = "EDMarketConnector"
_config.config = types.SimpleNamespace(get_str=lambda key: "", set=lambda *a, **k: None)
sys.modules.setdefault("config", _config)
sys.modules.setdefault("myNotebook", types.ModuleType("myNotebook"))

from plugin import overlay  # noqa: E402

# A refused loopback connection can take close to the full timeout on Windows; keep tests quick.
overlay.CONNECT_TIMEOUT_S = 0.3


def _closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _client(port: int) -> overlay.OverlayClient:
    return overlay.OverlayClient(overlay.OverlayConfig(host="127.0.0.1", port=str(port)))


class CheckConnectionTests(unittest.TestCase):
    def test_reports_a_listening_overlay(self) -> None:
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            ok, message = overlay.check_connection("127.0.0.1", str(server.getsockname()[1]))
        self.assertTrue(ok)
        self.assertIn("Connected", message)

    def test_reports_no_overlay(self) -> None:
        ok, message = overlay.check_connection("127.0.0.1", str(_closed_port()), timeout=0.3)
        self.assertFalse(ok)
        self.assertIn("No overlay found", message)

    def test_rejects_a_bad_port(self) -> None:
        ok, message = overlay.check_connection("127.0.0.1", "abc")
        self.assertFalse(ok)
        self.assertIn("valid port", message)


class CoolOffTests(unittest.TestCase):
    def test_second_send_fails_fast_without_trying_to_connect(self) -> None:
        client = _client(_closed_port())
        real_connect = socket.create_connection
        with mock.patch("plugin.overlay.socket.create_connection", side_effect=real_connect) as connect:
            with self.assertRaises(OSError):
                client.send_message("a", "hi", "white", 0, 0)
            self.assertEqual(connect.call_count, 1)
            with self.assertRaises(OSError):
                client.send_message("b", "hi", "white", 0, 0)
            self.assertEqual(connect.call_count, 1)  # cooled off: no second attempt

    def test_retry_now_tries_again(self) -> None:
        client = _client(_closed_port())
        real_connect = socket.create_connection
        with mock.patch("plugin.overlay.socket.create_connection", side_effect=real_connect) as connect:
            with self.assertRaises(OSError):
                client.send_message("a", "hi", "white", 0, 0)
            client.retry_now()
            with self.assertRaises(OSError):
                client.send_message("b", "hi", "white", 0, 0)
            self.assertEqual(connect.call_count, 2)

    def test_recovers_once_an_overlay_appears(self) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        client = _client(port)
        with self.assertRaises(OSError):
            client.send_message("a", "hi", "white", 0, 0)

        with socket.socket() as server:
            server.bind(("127.0.0.1", port))
            server.listen(1)
            client.retry_now()
            client.send_message("b", "hi", "white", 0, 0)  # connects and sends
            conn, _ = server.accept()
            self.assertIn(b'"id": "b"', conn.recv(1024))
            conn.close()
        client.close()

    def test_a_fresh_client_always_tries(self) -> None:
        # Settings "Test" buttons build their own client, so a cooling-off
        # shared client never makes a test report a false negative.
        port = _closed_port()
        first = _client(port)
        with self.assertRaises(OSError):
            first.send_message("a", "hi", "white", 0, 0)
        real_connect = socket.create_connection
        with mock.patch("plugin.overlay.socket.create_connection", side_effect=real_connect) as connect:
            with self.assertRaises(OSError):
                _client(port).send_message("a", "hi", "white", 0, 0)
            self.assertEqual(connect.call_count, 1)


if __name__ == "__main__":
    unittest.main()
