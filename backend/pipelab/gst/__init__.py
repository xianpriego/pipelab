"""Single entry point to the GStreamer bindings.

Every module imports ``Gst`` from here so initialisation happens exactly once.
"""

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GObject", "2.0")

from gi.repository import GLib, GObject, Gst

if not Gst.is_initialized():
    Gst.init(None)

__all__ = ["GLib", "GObject", "Gst"]
