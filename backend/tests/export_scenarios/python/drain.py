"""Sink-port slot: removing a consumer drains it (EOS forwarded by the pipeline) before
its request pad on the tee is released."""

from _exported import after, load

exported = load()
loop = exported.GLib.MainLoop()
pipeline = exported.SinkPipeline()


def state() -> str:
    ids = ",".join(instance["id"] for instance in pipeline.list_outputs())
    pads = ",".join(pad.get_name() for pad in pipeline.elements["split"].srcpads)
    return f"{ids} pads={pads}"


def add() -> None:
    print("ADDED", pipeline.add_output(), flush=True)
    print("STATE", state(), flush=True)


def remove() -> None:
    pipeline.remove_output("output0")
    print("REMOVING", state(), flush=True)


def finish() -> None:
    print("STATE", state(), flush=True)
    loop.quit()


pipeline.start()
for ms, action in ((400, add), (900, remove), (1500, finish)):
    after(exported, ms, action)
loop.run()
pipeline.stop()
