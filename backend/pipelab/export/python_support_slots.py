"""Embedded Python support: slots of component instances."""

SLOTS = '''

class SlotManager:
    """N instances of a component linked to the static graph, added and removed while running."""

    def __init__(self, owner, item: str, builder, links: list, max_instances=None) -> None:
        self.owner, self.item, self.builder = owner, item, builder
        self.links, self.max_instances = links, max_instances
        self.instances: dict = {}
        self.draining: dict = {}

    def _next_id(self) -> str:
        index = 0
        while f"{self.item}{index}" in self.instances or f"{self.item}{index}" in self.draining:
            index += 1
        return f"{self.item}{index}"

    def _resolve(self, value, instance_id: str, index: int, params: dict):
        if isinstance(value, str) and value.startswith("$$"):
            return value[1:]
        if isinstance(value, str) and value.startswith("$"):
            return {"index": index, "id": instance_id}.get(value[1:], params.get(value[1:]))
        return value

    def add(self, params: dict, instance_id: str | None = None) -> str:
        if self.max_instances is not None and len(self.instances) >= self.max_instances:
            raise RuntimeError(f"at most {self.max_instances} {self.item} instances")
        instance_id = instance_id or self._next_id()
        suffix = instance_id[len(self.item):]
        index = int(suffix) if suffix.isdigit() else len(self.instances)
        pipeline = self.owner.pipeline
        container = self.builder(instance_id, self.owner.host, **params)
        pipeline.add(container)
        peers = []
        for port, direction, element, pad, props in self.links:
            peer, requested = pad_of(self.owner.elements[element], pad)
            for key, value in props.items():
                resolved = self._resolve(value, instance_id, index, params)
                apply_value(self.owner.elements[element], key, resolved, peer.get_name())
            peers.append((port, direction, element, peer, requested))
            self._connect(container, port, direction, peer)
        if pipeline.get_state(0)[1] != Gst.State.NULL:
            container.sync_state_with_parent()
        self.instances[instance_id] = {"bin": container, "params": dict(params), "peers": peers}
        return instance_id

    @staticmethod
    def _connect(container: Gst.Bin, port: str, direction: str, peer: Gst.Pad) -> None:
        def connect(ghost: Gst.Pad) -> None:
            result = ghost.link(peer) if direction == "src" else peer.link(ghost)
            if result != Gst.PadLinkReturn.OK:
                print(f"could not link {container.get_name()}.{port}: {result.value_nick}", file=sys.stderr)

        ghost = container.get_static_pad(port)
        if ghost is not None:
            connect(ghost)
        else:  # the port appears with a sometimes pad
            container.connect("pad-added", lambda _b, pad: pad.get_name() == port and connect(pad))

    def list(self) -> list:
        return [{"id": key, "params": dict(value["params"])} for key, value in self.instances.items()]

    def remove(self, instance_id: str, then=None) -> None:
        record = self.instances.pop(instance_id, None)
        if record is None:
            raise KeyError(f"no {self.item} '{instance_id}'")
        upstream = [p for p in record["peers"] if p[1] == "sink"]
        if not upstream:
            self._finish(record, then)
            return
        self.draining[instance_id] = (record, then)
        for port, _direction, _element, peer, _requested in upstream:
            ghost = record["bin"].get_static_pad(port)
            peer.add_probe(Gst.PadProbeType.IDLE, self._drain, ghost)
        GLib.timeout_add(3000, self._timeout, instance_id)

    @staticmethod
    def _drain(peer: Gst.Pad, _info: Gst.PadProbeInfo, ghost: Gst.Pad) -> Gst.PadProbeReturn:
        if ghost is not None:
            peer.unlink(ghost)
            ghost.send_event(Gst.Event.new_eos())
        return Gst.PadProbeReturn.REMOVE

    def forwarded_eos(self, source: Gst.Object) -> None:
        for instance_id, (record, then) in list(self.draining.items()):
            if source == record["bin"] or source.has_as_ancestor(record["bin"]):
                del self.draining[instance_id]
                GLib.idle_add(lambda r=record, t=then: self._finish(r, t) or GLib.SOURCE_REMOVE)

    def _timeout(self, instance_id: str) -> bool:
        if instance_id in self.draining:
            record, then = self.draining.pop(instance_id)
            self._finish(record, then)
        return GLib.SOURCE_REMOVE

    def _finish(self, record: dict, then) -> None:
        container = record["bin"]
        container.set_state(Gst.State.NULL)
        for port, direction, element, peer, requested in record["peers"]:
            ghost = container.get_static_pad(port)
            if ghost is not None and ghost.is_linked():
                ghost.unlink(peer) if direction == "src" else peer.unlink(ghost)
            if requested:
                self.owner.elements[element].release_request_pad(peer)
        self.owner.pipeline.remove(container)
        prefix = container.get_name() + "/"
        for probe_id in [key for key in self.owner.host.rule_sets if key.startswith(prefix)]:
            self.owner.host.rule_sets.pop(probe_id).remove()
        if then is not None:
            then()

    def restart(self, instance_id: str) -> str:
        record = self.instances.get(instance_id)
        if record is None:
            raise KeyError(f"no {self.item} '{instance_id}'")
        params = dict(record["params"])
        self.remove(instance_id, then=lambda: self.add(params, instance_id))
        return instance_id
'''
