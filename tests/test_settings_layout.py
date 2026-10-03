"""
Guards the Settings-tab construction rule that broke the whole WNTB tab once:

EDMC's `myNotebook.Frame` (`nb.Frame`) cannot have children managed by `pack`
("cannot use geometry manager pack inside ... which already has slaves managed by
grid"): its constructor puts a gridded spacer frame inside every instance. A widget that is packed must live in a plain `tk.Frame`. Building the tab
raises, EDMC logs `Failed for Plugin "WNTB"`, and the entire Settings tab goes
missing. Stand-in widgets in a unit test can't reproduce the error, so this checks
the source instead.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import ast
import glob
import os
import unittest

PLUGIN = os.path.join(os.path.dirname(__file__), "..", "plugin")


def _is_nb_frame_call(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Frame"
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "nb")


def _violations(path: str) -> list[str]:
    tree = ast.parse(open(path, encoding="utf-8").read())
    found: list[str] = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        nb_frames: set[str] = set()
        for node in ast.walk(func):
            if isinstance(node, ast.Assign) and _is_nb_frame_call(node.value):
                nb_frames.update(t.id for t in node.targets if isinstance(t, ast.Name))
        if not nb_frames:
            continue
        packed_in_nb: set[str] = set()  # widgets created inside an nb.Frame, remembered by variable name
        for node in ast.walk(func):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and node.value.args:
                first = node.value.args[0]
                if isinstance(first, ast.Name) and first.id in nb_frames:
                    packed_in_nb.update(t.id for t in node.targets if isinstance(t, ast.Name))
        for node in ast.walk(func):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "pack"):
                continue
            target = node.func.value
            if isinstance(target, ast.Call) and target.args and isinstance(target.args[0], ast.Name) \
                    and target.args[0].id in nb_frames:
                found.append(f"{os.path.basename(path)}:{node.lineno} packs a widget into nb.Frame {target.args[0].id!r}")
            elif isinstance(target, ast.Name) and target.id in packed_in_nb:
                found.append(f"{os.path.basename(path)}:{node.lineno} packs {target.id!r}, which lives in an nb.Frame")
    return found


class SettingsLayoutTests(unittest.TestCase):
    def test_nothing_is_packed_into_an_nb_frame(self) -> None:
        problems: list[str] = []
        for path in sorted(glob.glob(os.path.join(PLUGIN, "*.py"))):
            problems.extend(_violations(path))
        self.assertEqual(problems, [], "pack() inside an nb.Frame breaks EDMC's Settings tab; use tk.Frame or grid")

    def test_the_checker_catches_the_bug_it_exists_for(self) -> None:
        import tempfile

        bad = (
            "import myNotebook as nb\n"
            "def build(tabs):\n"
            "    frame = nb.Frame(tabs)\n"
            "    intro = nb.Frame(frame)\n"
            "    nb.Label(intro, text='x').pack()\n"
        )
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "bad.py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(bad)
            self.assertEqual(len(_violations(path)), 1)


if __name__ == "__main__":
    unittest.main()
