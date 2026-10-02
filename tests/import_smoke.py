"""Imports every plugin module the way EDMC would, with EDMC's own modules (and the
third-party libraries it bundles) replaced by stand-ins, and exits non-zero if any
import fails or if plugin.ui is not the main-panel module. Run by
test_import_smoke.py in a subprocess so the stand-ins never leak into other tests."""
import glob
import importlib
import os
import sys
import types
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))


class _Anything(types.ModuleType):
    """A stand-in module: any attribute is a harmless mock."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return mock.MagicMock(name=f"{self.__name__}.{name}")


STANDINS = (
    # EDMC's own modules
    "config", "theme", "myNotebook", "monitor", "ttkHyperlinkLabel", "edmc_data", "plug", "companion",
    "EDMCLogging", "l10n", "timeout_session", "protocol", "prefs", "killswitch", "Tooltips", "ttkDefaults",
    # libraries EDMC bundles
    "requests", "win32api", "win32con", "win32gui", "win32process", "win32clipboard", "pywintypes", "psutil",
)
for name in STANDINS:
    sys.modules[name] = _Anything(name)
sys.modules["config"].appname = "EDMarketConnector"
sys.modules["config"].appversion = lambda: "5.13.0"

failures = []
imported = 0
for path in sorted(glob.glob(os.path.join(HERE, "..", "plugin", "*.py"))):
    module = os.path.basename(path)[:-3]
    if module == "__init__":
        continue
    try:
        importlib.import_module(f"plugin.{module}")
        imported += 1
    except Exception as exc:  # noqa: BLE001 - report every failure, not just the first
        failures.append((module, f"{type(exc).__name__}: {exc}"))

print("imported OK:", imported)
for module, error in failures:
    print("FAIL", module, "-", error)

panel_module = sys.modules.get("plugin.ui")
has_panel_builder = hasattr(panel_module, "create_plugin_app")
print("plugin.ui is the main-panel module:", has_panel_builder)
sys.exit(1 if failures or not has_panel_builder else 0)
