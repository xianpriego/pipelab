"""Scenario 4: an active-pad change is intercepted and applied on the next keyframe."""

import time

from _exported import after, load

exported = load()
loop = exported.GLib.MainLoop()
pipeline = exported.SwitchPipeline()
asked = {}


def active() -> str:
    return pipeline.elements["sel"].get_property("active-pad").get_name()


def on_message(name, fields, source):
    print("MESSAGE", name, fields["pad"], f"{time.monotonic() - asked['at']:.2f}", flush=True)


def switch() -> None:
    asked["at"] = time.monotonic()
    print("INTERCEPTED", pipeline.set_element_property("sel", "active-pad", "sink_1"), flush=True)
    print("ACTIVE", active(), flush=True)


def finish() -> None:
    print("ACTIVE", active(), flush=True)
    loop.quit()


pipeline.on_message(on_message)
pipeline.start()
after(exported, 1000, switch)
after(exported, 3000, finish)
loop.run()
pipeline.stop()
