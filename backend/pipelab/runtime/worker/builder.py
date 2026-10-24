"""Creates the Gst.Pipeline elements of a graph (linking is done by ``links``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pipelab.graph.models import Node
from pipelab.gst import Gst
from pipelab.gst.values import to_launch_string
from pipelab.runtime.worker.encoder import Emit, FrameEncoder, PreviewSettings
from pipelab.runtime.worker.previews import preview_kind, preview_sink


@dataclass
class BuiltPipeline:
    pipeline: Gst.Pipeline
    elements: dict[str, Gst.Element] = field(default_factory=dict)  # global node id → element
    element_ids: dict[Gst.Element, str] = field(default_factory=dict)  # element → global node id
    scopes: list[Any] = field(default_factory=list)  # assembly.Scope, top level first
    errors: list[tuple[Node | None, str]] = field(default_factory=list)
    notes: list[tuple[Node, str]] = field(default_factory=list)
    encoders: list[FrameEncoder] = field(default_factory=list)

    def close_previews(self) -> None:
        for encoder in self.encoders:
            encoder.close()


def is_pad_property(target: Gst.Object, name: str) -> bool:
    pspec = target.find_property(name)
    return pspec is not None and pspec.value_type.is_a(Gst.Pad.__gtype__)


def apply_property(target: Gst.Object, name: str, value: str | int | float | bool) -> str | None:
    """Set a property the way gst-launch does; returns an error message.

    ``target`` is an element or a pad. GstPad-typed element properties take
    the name of one of the element's pads.
    """
    pspec = target.find_property(name)
    if pspec is None:
        return f"no property '{name}'"
    if isinstance(target, Gst.Element) and is_pad_property(target, name):
        pad = target.get_static_pad(str(value))
        if pad is None:
            return f"'{name}': pad '{value}' does not exist"
        target.set_property(name, pad)
        return None
    Gst.util_set_object_arg(target, name, to_launch_string(value))
    return None


def create_element(
    node: Node, settings: PreviewSettings, emit: Emit, built: BuiltPipeline
) -> Gst.Element | None:
    """The element for ``node``: the factory itself, or a browser preview for display sinks."""
    kind = preview_kind(node)
    if kind is None:
        return Gst.ElementFactory.make(node.factory, node.name)
    element, encoder = preview_sink(node, kind, settings, emit, emit)
    built.encoders.append(encoder)
    ignored = sorted(set(node.properties) - {"sync"})
    note = f"{node.factory} is shown in the Preview tab"
    built.notes.append((node, note + (f" (ignored: {', '.join(ignored)})" if ignored else "")))
    return element
