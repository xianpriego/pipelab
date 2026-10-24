"""Scenario 3: the `configure` API function sets a property and posts a message."""

from _exported import after, load

exported = load()
loop = exported.GLib.MainLoop()
pipeline = exported.FunctionsPipeline()


def on_message(name, fields, source):
    print("MESSAGE", name, fields["pattern"], source, flush=True)


def call() -> None:
    pipeline.configure(pattern="snow")
    print("PATTERN", pipeline.elements["src"].get_property("pattern").value_nick, flush=True)


pipeline.on_message(on_message)
pipeline.start()
after(exported, 500, call)
after(exported, 1200, loop.quit)
loop.run()
pipeline.stop()
