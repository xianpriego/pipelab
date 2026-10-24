"""Encoding and streaming best practices."""

from __future__ import annotations

from pipelab.catalog.models import ElementInfo
from pipelab.graph.models import Issue, Node
from pipelab.graph.rules.base import RuleContext, issue
from pipelab.graph.suggest import set_property_suggestion

NETWORK_SINKS = {
    "udpsink",
    "multiudpsink",
    "tcpserversink",
    "rtspclientsink",
    "srtsink",
    "ristsink",
    "rtmpsink",
    "rtmp2sink",
    "webrtcsink",
    "whipclientsink",
    "whipsink",
    "rtpsink",
}
NETWORK_SOURCES = {
    "udpsrc",
    "tcpclientsrc",
    "tcpserversrc",
    "srtsrc",
    "ristsrc",
    "rtmpsrc",
    "rtmp2src",
    "rtspsrc",
    "whepsrc",
    "whepclientsrc",
    "webrtcsrc",
    "souphttpsrc",
}
LOW_LATENCY_ENCODERS = {"x264enc": ("tune", "zerolatency"), "x265enc": ("tune", "zerolatency")}
PAYLOADERS_WITH_CONFIG = {"rtph264pay", "rtph265pay"}
FINALIZED_MUXERS = {"mp4mux", "qtmux", "isomp4mux"}


def _streams_over_network(ctx: RuleContext) -> bool:
    return any(node.factory in NETWORK_SINKS for node in ctx.graph.nodes)


def encoder_latency(ctx: RuleContext) -> list[Issue]:
    if not _streams_over_network(ctx):
        return []
    issues = []
    for node, _element in ctx.nodes_with(lambda n, _e: n.factory in LOW_LATENCY_ENCODERS):
        name, value = LOW_LATENCY_ENCODERS[node.factory]
        if value not in str(node.properties.get(name, "")):
            issues.append(
                issue(
                    "encoder-latency",
                    "info",
                    f"{node.name} feeds a network stream: {name}={value} avoids frame look-ahead and "
                    "B-frames that add seconds of latency.",
                    [node],
                    suggestions=[set_property_suggestion(node.id, name, value, "Low latency encoding.")],
                )
            )
    return issues


def payloader_config(ctx: RuleContext) -> list[Issue]:
    issues = []
    for node, _element in ctx.nodes_with(lambda n, _e: n.factory in PAYLOADERS_WITH_CONFIG):
        if "config-interval" not in node.properties:
            issues.append(
                issue(
                    "rtp-config-interval",
                    "info",
                    f"{node.name}: config-interval=-1 sends SPS/PPS with every key frame so receivers can "
                    "join the stream at any time.",
                    [node],
                    suggestions=[
                        set_property_suggestion(node.id, "config-interval", -1, "Repeat codec headers.")
                    ],
                )
            )
    return issues


def _needs_eos(node: Node, element: ElementInfo) -> bool:
    return node.factory in FINALIZED_MUXERS and not node.properties.get("fragment-duration")


def muxer_finalization(ctx: RuleContext) -> list[Issue]:
    return [
        issue(
            "muxer-eos",
            "info",
            f"{node.name} writes its index when it receives EOS: stop the pipeline with Stop (sends EOS), "
            "not Kill, or set fragment-duration to get a playable file even after a crash.",
            [node],
            suggestions=[
                set_property_suggestion(node.id, "fragment-duration", 1000, "Fragmented MP4 (1 s).")
            ],
        )
        for node, _element in ctx.nodes_with(_needs_eos)
    ]


def _async_enabled(node: Node) -> bool:
    return str(node.properties.get("async", True)).lower() not in ("false", "0", "no")


def loopback_async(ctx: RuleContext) -> list[Issue]:
    """A pipeline that sends to the network and receives in the same pipeline deadlocks while prerolling."""
    if not any(node.factory in NETWORK_SOURCES for node in ctx.graph.nodes):
        return []
    return [
        issue(
            "loopback-async",
            "warning",
            f"{node.name} sends to the network while this same pipeline also receives from it: the "
            "receiving sinks cannot preroll until the sender plays, and the sender waits for them. "
            "Set async=false on the network sink (or split sender and receiver into two pipelines).",
            [node],
            suggestions=[set_property_suggestion(node.id, "async", False, "Do not wait for preroll.")],
        )
        for node, _element in ctx.nodes_with(lambda n, _e: n.factory in NETWORK_SINKS)
        if _async_enabled(node)
    ]
