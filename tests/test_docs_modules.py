"""Every module shipped in plugin/ (and plugin/uikit/) has a row in docs/MODULES.md."""
import os
import re
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _modules():
    for folder, prefix in (("plugin", ""), (os.path.join("plugin", "uikit"), "uikit/")):
        for name in sorted(os.listdir(os.path.join(_ROOT, folder))):
            if name.endswith(".py"):
                yield prefix + name


class ModuleIndexTest(unittest.TestCase):
    def test_every_module_is_listed(self):
        with open(os.path.join(_ROOT, "docs", "MODULES.md"), encoding="utf-8") as handle:
            listed = set(re.findall(r"^\| `([^`]+\.py)` \|", handle.read(), re.MULTILINE))
        missing = [name for name in _modules() if name not in listed]
        self.assertEqual(missing, [], "add these modules to docs/MODULES.md")

    def test_no_row_for_a_module_that_is_gone(self):
        with open(os.path.join(_ROOT, "docs", "MODULES.md"), encoding="utf-8") as handle:
            listed = set(re.findall(r"^\| `([^`]+\.py)` \|", handle.read(), re.MULTILINE))
        self.assertEqual(sorted(listed - set(_modules())), [], "remove these rows from docs/MODULES.md")


if __name__ == "__main__":
    unittest.main()
