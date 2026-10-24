"""Loads the generated module given on the command line."""

import importlib.util
import sys


def load():
    spec = importlib.util.spec_from_file_location("exported", sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.Gst.init(None)
    return module
