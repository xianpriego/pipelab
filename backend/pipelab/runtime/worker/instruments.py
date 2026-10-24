"""Instruments attached on demand to established links: taps and probes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from pipelab.gst import GLib, Gst
from pipelab.runtime.worker.encoder import PreviewSettings
from pipelab.runtime.worker.events import Emit
from pipelab.runtime.worker.probes import LinkProbe
from pipelab.runtime.worker.taps import LinkTap


class _Instrument(Protocol):
    def close(self) -> None: ...


class LinkInstruments:
    def __init__(self, preview: PreviewSettings, started: float, emit: Emit) -> None:
        self.pads: dict[str, Gst.Pad] = {}
        self._preview = preview
        self._started = started
        self._emit = emit
        self._taps: dict[str, LinkTap] = {}
        self._probes: dict[str, LinkProbe] = {}

    def register(self, edge_id: str, pad: Gst.Pad) -> None:
        self.pads[edge_id] = pad

    def _toggle(
        self, registry: dict[str, Any], edge_id: str, enabled: bool, create: Callable[[Gst.Pad], _Instrument]
    ) -> dict[str, Any]:
        if edge_id in registry:
            registry.pop(edge_id).close()
        if not enabled:
            return {"ok": True}
        pad = self.pads.get(edge_id)
        if pad is None:
            return {"ok": False, "error": "the link is not established"}
        try:
            registry[edge_id] = create(pad)
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True}

    def set_tap(self, edge_id: str, enabled: bool) -> dict[str, Any]:
        return self._toggle(
            self._taps,
            edge_id,
            enabled,
            lambda pad: LinkTap(edge_id, pad, self._preview, self._emit),
        )

    def set_probe(self, edge_id: str, enabled: bool) -> dict[str, Any]:
        return self._toggle(
            self._probes, edge_id, enabled, lambda pad: LinkProbe(edge_id, pad, self._started, self._emit)
        )

    def flush(self) -> bool:
        """GLib timeout callback sending the pending probe records."""
        for probe in list(self._probes.values()):
            probe.flush()
        return GLib.SOURCE_CONTINUE

    def close(self) -> None:
        for registry in (self._taps, self._probes):
            for instrument in registry.values():
                instrument.close()
            registry.clear()
