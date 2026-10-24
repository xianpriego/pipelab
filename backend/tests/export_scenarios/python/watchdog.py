"""Scenario 1: the source of the `cam` instance stops after 20 buffers; its watchdog
rule set posts "branch-down" with `$instance` once 500 ms pass without buffers."""

from _exported import after, load

exported = load()
loop = exported.GLib.MainLoop()
pipeline = exported.WatchdogPipeline()


def on_message(name, fields, source):
    print("MESSAGE", name, fields["input"], fields["idle_ms"], flush=True)


pipeline.on_message(on_message)
pipeline.start()
after(exported, 2500, loop.quit)
loop.run()
pipeline.stop()
