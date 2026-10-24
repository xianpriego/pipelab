"""Loads the generated module given on the command line (shared by the scenario drivers)."""

import importlib.util
import sys


def load():
    spec = importlib.util.spec_from_file_location("exported", sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.Gst.init(None)
    return module


def after(module, ms: int, action) -> None:
    """Run ``action`` once on the main loop after ``ms`` milliseconds."""
    module.GLib.timeout_add(ms, lambda: action() and False)
