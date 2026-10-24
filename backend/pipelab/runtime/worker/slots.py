"""Slots: N instances of a component added and removed while running (docs/DYNAMIC.md §2)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pipelab.components.models import Component
from pipelab.graph.dynamic import Slot, SlotLink
from pipelab.gst import GLib, Gst
from pipelab.runtime.worker.builder import apply_property
from pipelab.runtime.worker.links import get_pad
from pipelab.runtime.worker.probe_values import resolve

DRAIN_TIMEOUT_MS = 3000
_INDEX = re.compile(r"(\d+)$")


class SlotError(ValueError):
    pass


@dataclass
class _Instance:
    id: str
    index: int
    params: dict[str, Any]
    bin: Gst.Bin
    peers: list[tuple[SlotLink, Gst.Pad, Gst.Pad]] = field(default_factory=list)  # (link, ghost, peer)


class SlotManager:
    def __init__(
        self,
        slots: list[Slot],
        components: dict[str, Component],
        top: Any,
        pipeline: Gst.Pipeline,
        build_instance: Callable[[str, Component, dict[str, Any], str], Gst.Bin],
        on_instance: Callable[[str, bool], None],
        on_link: Callable[[str, Gst.Pad], None],
        emit: Callable[[dict[str, Any]], None],
    ) -> None:
        self._slots = {slot.id: slot for slot in slots}
        self._components = components
        self._top = top  # assembly.Scope of the static graph
        self._pipeline = pipeline
        self._build = build_instance
        self._on_instance = on_instance  # (runtime prefix, added?) → attach/detach probes and scripts
        self._on_link = on_link  # (global edge id, src pad) → stats and caps
        self._emit = emit
        self._instances: dict[str, dict[str, _Instance]] = {slot.id: {} for slot in slots}
        self.running = False

    @staticmethod
    def prefix(slot_id: str, instance_id: str) -> str:
        return f"{slot_id}.{instance_id}/"

    def slot(self, key: str) -> Slot:
        """A slot by id or by name."""
        slot = self._slots.get(key) or next((s for s in self._slots.values() if s.name == key), None)
        if slot is None:
            raise SlotError(f"unknown slot '{key}'")
        return slot

    def build_initial(self) -> None:
        for slot in self._slots.values():
            for initial in slot.initial:
                self.add(slot.id, initial.params, initial.id)

    def listing(self, slot_id: str) -> list[dict[str, Any]]:
        return [{"id": i.id, "params": i.params} for i in self._instances[self.slot(slot_id).id].values()]

    def _announce(self, slot: Slot) -> None:
        self._emit({"type": "instances", "slot": slot.id, "instances": self.listing(slot.id)})

    def _new_id(self, slot: Slot) -> str:
        taken = {i for instances in self._instances.values() for i in instances}
        index = 0
        while f"{slot.item}{index}" in taken:
            index += 1
        return f"{slot.item}{index}"

    def add(self, slot_id: str, params: dict[str, Any] | None = None, instance_id: str | None = None) -> str:
        slot = self.slot(slot_id)
        component = self._components.get(slot.component)
        if component is None:
            raise SlotError(f"component '{slot.component}' is not in the library")
        instances = self._instances[slot.id]
        if slot.max_instances is not None and len(instances) >= slot.max_instances:
            raise SlotError(f"slot '{slot.name}' is full ({slot.max_instances} instances)")
        instance_id = instance_id or self._new_id(slot)
        if any(instance_id in group for group in self._instances.values()):
            raise SlotError(f"instance '{instance_id}' already exists")
        match = _INDEX.search(instance_id)
        index = int(match.group(1)) if match else len(instances)
        params = {k: v for k, v in (params or {}).items() if v is not None}
        bin_ = self._build(instance_id, component, params, self.prefix(slot.id, instance_id))
        self._pipeline.add(bin_)
        instance = _Instance(instance_id, index, params, bin_)
        for link in slot.links:
            self._link(slot, instance, link)
        instances[instance_id] = instance
        self._on_instance(self.prefix(slot.id, instance_id), True)
        if self.running:
            bin_.sync_state_with_parent()
        self._announce(slot)
        return instance_id

    def _link(self, slot: Slot, instance: _Instance, link: SlotLink) -> None:
        target = self._top.elements.get(link.node_id)
        ghost = instance.bin.get_static_pad(link.port)
        if target is None or ghost is None:
            raise SlotError(f"cannot link {instance.id}.{link.port} to '{link.node_id}.{link.pad}'")
        peer = get_pad(target, link.pad)
        if peer is None:
            raise SlotError(f"'{link.pad}' is not a pad of the target element")
        env = {"index": instance.index, "id": instance.id, **instance.params}
        for name, value in link.pad_properties.items():
            apply_property(peer, name, resolve(value, env))
        src, sink = (ghost, peer) if ghost.get_direction() == Gst.PadDirection.SRC else (peer, ghost)
        if src.link(sink) != Gst.PadLinkReturn.OK:
            raise SlotError(f"cannot link {instance.id}.{link.port} → {link.node_id}.{peer.get_name()}")
        instance.peers.append((link, ghost, peer))
        self._on_link(f"{slot.id}.{instance.id}:{link.port}", src)

    def remove(self, slot_id: str, instance_id: str, then: Callable[[], None] | None = None) -> None:
        slot = self.slot(slot_id)
        instance = self._instances[slot.id].pop(str(instance_id), None)
        if instance is None:
            raise SlotError(f"no instance '{instance_id}' in slot '{slot.name}'")
        consumers = [p for p in instance.peers if p[1].get_direction() == Gst.PadDirection.SINK]
        if consumers and self.running:
            self._drain(slot, instance, consumers, then)
        else:
            self._dispose(slot, instance, then)

    def _drain(
        self, slot: Slot, instance: _Instance, consumers: list, then: Callable[[], None] | None
    ) -> None:
        """Consumers (recorders…) get EOS so they finalise before being removed."""
        sinks = [
            e
            for e in instance.bin.iterate_recurse()
            if not isinstance(e, Gst.Bin) and not list(e.iterate_src_pads())
        ]
        pending = {id(e) for e in sinks}
        finished = {"done": False}

        def finish() -> bool:
            if not finished["done"]:
                finished["done"] = True
                self._dispose(slot, instance, then)
            return GLib.SOURCE_REMOVE

        def on_eos(sink_element: Gst.Element) -> None:
            pending.discard(id(sink_element))
            if not pending:
                GLib.idle_add(finish)

        for element in sinks:
            for pad in element.iterate_sink_pads():
                pad.add_probe(Gst.PadProbeType.EVENT_DOWNSTREAM, _eos_watcher(on_eos, element))
        for _link, ghost, peer in consumers:
            peer.add_probe(Gst.PadProbeType.IDLE, _unlink_then_eos(peer, ghost))
        GLib.timeout_add(DRAIN_TIMEOUT_MS, finish)
        if not sinks:
            GLib.idle_add(finish)

    def _dispose(self, slot: Slot, instance: _Instance, then: Callable[[], None] | None) -> None:
        instance.bin.set_state(Gst.State.NULL)
        for _link, ghost, peer in instance.peers:
            if ghost.is_linked():
                (ghost.unlink(peer) if ghost.get_direction() == Gst.PadDirection.SRC else peer.unlink(ghost))
            template = peer.get_pad_template()
            if template is not None and template.presence == Gst.PadPresence.REQUEST:
                peer.get_parent_element().release_request_pad(peer)
        self._pipeline.remove(instance.bin)
        self._on_instance(self.prefix(slot.id, instance.id), False)
        self._announce(slot)
        if then is not None:
            then()

    def restart(self, slot_id: str, instance_id: str) -> str:
        slot = self.slot(slot_id)
        instance = self._instances[slot.id].get(str(instance_id))
        if instance is None:
            raise SlotError(f"no instance '{instance_id}' in slot '{slot.name}'")
        params = dict(instance.params)
        self.remove(slot.id, instance.id, then=lambda: self.add(slot.id, params, instance.id))
        return instance.id


def _eos_watcher(on_eos: Callable[[Gst.Element], None], element: Gst.Element) -> Callable:
    def probe(_pad: Gst.Pad, info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
        if info.get_event().type == Gst.EventType.EOS:
            on_eos(element)
        return Gst.PadProbeReturn.OK

    return probe


def _unlink_then_eos(peer: Gst.Pad, ghost: Gst.Pad) -> Callable:
    def probe(_pad: Gst.Pad, _info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
        if peer.is_linked():
            peer.unlink(ghost)
            ghost.send_event(Gst.Event.new_eos())
        return Gst.PadProbeReturn.REMOVE

    return probe
