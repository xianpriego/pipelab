"""Scenario 2: one initial tile, two added while running, one removed and one restarted."""

from _exported import after, load

exported = load()
loop = exported.GLib.MainLoop()
pipeline = exported.SlotsPipeline()


def ids() -> str:
    return ",".join(instance["id"] for instance in pipeline.list_tiles())


def add() -> None:
    print("ADDED", pipeline.add_tile(pattern="snow"), pipeline.add_tile(), flush=True)


def remove() -> None:
    print("LIST", ids(), flush=True)
    pipeline.remove_tile("tile1")
    print("LIST", ids(), flush=True)


def restart() -> None:
    print("RESTART", pipeline.restart_tile("tile2"), flush=True)


def finish() -> None:
    state = pipeline.pipeline.get_state(0)[1].value_nick
    pads = ",".join(pad.get_name() for pad in pipeline.elements["mix"].sinkpads)
    print("FINAL", ids(), state, flush=True)
    print("PADS", pads, flush=True)
    loop.quit()


pipeline.start()
for ms, action in ((500, add), (1200, remove), (1700, restart), (2500, finish)):
    after(exported, ms, action)
loop.run()
print("EXIT", pipeline.exit_code)
pipeline.stop()
