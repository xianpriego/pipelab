"""Registry of graph validation rules, run in order by ``graph.validate``."""

from pipelab.graph.rules import connectivity, elements, negotiation, streaming, threading
from pipelab.graph.rules.base import Rule, RuleContext

RULES: list[Rule] = [
    elements.missing_elements,
    elements.duplicate_names,
    elements.properties,
    elements.required_properties,
    connectivity.endpoints,
    connectivity.unlinked_pads,
    connectivity.links,
    threading.tee_branches,
    threading.demuxer_branches,
    threading.aggregator_inputs,
    threading.live_sources,
    negotiation.source_caps,
    streaming.encoder_latency,
    streaming.payloader_config,
    streaming.muxer_finalization,
    streaming.loopback_async,
]

__all__ = ["RULES", "Rule", "RuleContext"]
