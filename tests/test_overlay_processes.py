"""overlay_processes: counting EDMCModernOverlay windows and the warning about a second one."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from plugin import overlay_processes as P  # noqa: E402

CMD = r"C:\x\.venv\Scripts\python.exe -m overlay_client.overlay_client"


class WindowsTests(unittest.TestCase):
    def test_a_launcher_and_its_child_are_one_window(self):
        entries = [(10, 1, CMD), (11, 10, CMD), (50, 1, "notepad.exe")]
        self.assertEqual(P.windows(entries), [10])

    def test_two_launcher_pairs_are_two_windows(self):
        entries = [(10, 1, CMD), (11, 10, CMD), (20, 1, CMD), (21, 20, CMD)]
        self.assertEqual(P.windows(entries), [10, 20])

    def test_a_child_whose_launcher_is_gone_is_a_window_of_its_own(self):
        self.assertEqual(P.windows([(11, 10, CMD), (20, 1, CMD)]), [11, 20])

    def test_nothing_running_is_no_windows(self):
        self.assertEqual(P.windows([(5, 1, "python other.py"), (6, 1, "")]), [])


class MessageTests(unittest.TestCase):
    def test_only_more_than_one_window_is_warned_about(self):
        self.assertEqual(P.warning([10]), "")
        self.assertEqual(P.warning([]), "")
        self.assertEqual(P.warning(None), "")
        text = P.warning([10, 20])
        self.assertIn("2 overlay windows", text)
        self.assertIn("10, 20", text)

    def test_the_diagnostics_line_says_how_many_or_that_it_is_unknown(self):
        self.assertEqual(P.summary(None), "Overlay windows running: unknown")
        self.assertEqual(P.summary([]), "Overlay windows running: 0")
        self.assertEqual(P.summary([10, 20]), "Overlay windows running: 2 (process 10, 20)")


if __name__ == "__main__":
    unittest.main()
