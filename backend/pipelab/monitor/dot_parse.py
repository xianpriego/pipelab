"""Parse the GraphViz ``.dot`` that GStreamer writes for a live pipeline.

``gst_debug_bin_to_dot_data`` (and the ``GST_DEBUG_DUMP_DOT_DIR`` dumps) serialise a running
``GstBin`` to GraphViz: one ``cluster`` per element, pad nodes inside per-direction subclusters,
and one edge per linked pad with the negotiated caps in its label. This module turns that text
back into a structured description we can map onto Pipelab's own graph model, so a pipeline we did
not build can be inspected as a graph.

It is deliberately pure and defensive: the dump comes from arbitrary third-party processes and
GStreamer versions, so anything unrecognised is skipped rather than raising.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ``subgraph cluster_node_<name>_0x<addr>`` — the trailing ``_sink`` / ``_src`` marks a pad group,
# not an element. ``<name>`` may itself contain ``_`` and digits, so the hex address is the anchor.
_CLUSTER = re.compile(r"cluster_node_(?P<name>.+)_0x(?P<addr>[0-9a-fA-F]+)(?P<pad>_sink|_src)?\s*\{")
# A pad node: ``node_<el>_0x<addr>_node_<pad>_0x<addr> [ ... ]``. ``_node_`` separates the two.
_PAD = re.compile(r"^(?P<id>node_.+_node_.+?_0x[0-9a-fA-F]+)\s*\[")
# A link between two pad nodes.
_LINK = re.compile(r"^(?P<src>node_.+?)\s*->\s*(?P<dst>node_.+?)\s*(?:\[(?P<attrs>.*)\])?\s*;?\s*$")
_LABEL = re.compile(r'label="(?P<label>.*?)"', re.DOTALL)
_PAD_ADDR = re.compile(r"_0x[0-9a-fA-F]+$")


@dataclass
class ParsedPad:
    name: str
    direction: str  # "sink" | "src" | "unknown"


@dataclass
class ParsedElement:
    addr: str
    name: str
    gtype: str  # GObject type name, e.g. "GstCapsFilter"
    state: str | None = None  # "null" | "ready" | "paused" | "playing" | None
    properties: dict[str, str] = field(default_factory=dict)
    parent: str | None = None  # addr of the enclosing bin, or None at the top
    pads: dict[str, ParsedPad] = field(default_factory=dict)  # pad addr -> pad


@dataclass
class ParsedLink:
    src_element: str  # element addr
    src_pad: str  # pad name
    dst_element: str
    dst_pad: str
    caps: str | None = None


@dataclass
class ParsedPipeline:
    name: str
    elements: dict[str, ParsedElement]  # addr -> element
    links: list[ParsedLink]


_STATE_GLYPHS = {"0": "null", "-": "ready", "=": "paused", ">": "playing", "~": "void-pending"}


def _unescape(text: str) -> str:
    return text.replace("\\l", "\n").replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


def _parse_element_label(label: str) -> tuple[str, str, str | None, dict[str, str]]:
    """Return ``(gtype, name, state, properties)`` from an element cluster label.

    Two layouts occur across GStreamer versions: ``GstTypeName\\nname\\n[state]`` on their own
    lines followed by ``property=value`` lines, or everything on one header line. The ``[state]``
    glyph and the ``GType`` / name header come first; the rest are properties.
    """
    lines = [ln.strip() for ln in _unescape(label).splitlines() if ln.strip()]
    gtype = name = ""
    state: str | None = None
    props: dict[str, str] = {}
    for line in lines:
        bare_state = re.fullmatch(r"\[(.)\]", line)
        if bare_state:
            state = _STATE_GLYPHS.get(bare_state.group(1))
            continue
        # A property line (value may contain '='; a leading '[' is a pad-state line, not a prop).
        if "=" in line and not line.startswith("["):
            key, _, value = line.partition("=")
            props[key.strip()] = value.strip()
            continue
        # A header line: optional trailing [state], then GType and maybe the element name.
        m_state = re.search(r"\[(.)\]\s*$", line)
        if m_state:
            state = _STATE_GLYPHS.get(m_state.group(1), state)
            line = line[: m_state.start()].strip()
        for token in line.split():
            if not gtype:
                gtype = token
            elif not name:
                name = token
    return gtype, name, state, props


def _split_pad_id(pad_node_id: str) -> tuple[str, str] | None:
    """``node_<el>_0x<a>_node_<pad>_0x<b>`` -> (element addr, pad addr). None if malformed."""
    body = pad_node_id[len("node_") :] if pad_node_id.startswith("node_") else pad_node_id
    el_part, sep, pad_part = body.rpartition("_node_")
    if not sep:
        return None
    el_addr = _addr_of(el_part)
    pad_addr = _addr_of(pad_part)
    if not el_addr or not pad_addr:
        return None
    return el_addr, pad_addr


def _addr_of(part: str) -> str | None:
    m = re.search(r"_0x([0-9a-fA-F]+)$", part)
    if m:
        return m.group(1).lower()
    m = re.match(r"0x([0-9a-fA-F]+)$", part)
    return m.group(1).lower() if m else None


def parse_dot(text: str) -> ParsedPipeline:
    """Parse one GStreamer ``.dot`` document into a :class:`ParsedPipeline`."""
    pipeline_name = "pipeline"
    # The graph-level label is the first ``label=`` in the document (before any subgraph).
    head = text.split("subgraph", 1)[0]
    m = _LABEL.search(head)
    if m:
        _, parsed_name, _, _ = _parse_element_label(m.group("label"))
        pipeline_name = parsed_name or pipeline_name

    elements: dict[str, ParsedElement] = {}
    links: list[ParsedLink] = []
    pad_owner: dict[str, str] = {}  # pad addr -> element addr

    # Stack of (brace_depth, addr) for the enclosing *element* clusters only. Pad subclusters push
    # brace depth too, tracked separately so pads attach to the right element and direction.
    element_stack: list[tuple[int, str]] = []
    pad_group: tuple[int, str, str] | None = None  # (brace_depth, element addr, direction)
    depth = 0

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        cluster = _CLUSTER.search(stripped)
        if cluster and stripped.startswith("subgraph"):
            addr = cluster.group("addr").lower()
            if cluster.group("pad"):
                pad_group = (depth, addr, cluster.group("pad").lstrip("_"))
            else:
                parent = element_stack[-1][1] if element_stack else None
                # The label may span several physical lines until the closing quote.
                label_text, consumed = _collect_label(lines, i)
                gtype, name, state, props = _parse_element_label(label_text)
                elements[addr] = ParsedElement(
                    addr=addr,
                    name=name or cluster.group("name"),
                    gtype=gtype,
                    state=state,
                    properties=props,
                    parent=parent,
                )
                element_stack.append((depth, addr))
                i += consumed
                depth += raw.count("{") - raw.count("}")
                i += 1
                continue

        pad = _PAD.match(stripped)
        if pad and pad_group is not None:
            parts = _split_pad_id(pad.group("id"))
            if parts:
                el_addr, pad_addr = parts
                owner = element_stack[-1][1] if element_stack else el_addr
                lbl = _LABEL.search(stripped)
                pad_name = _unescape(lbl.group("label")).split("[")[0].strip() if lbl else pad_addr
                if owner in elements:
                    elements[owner].pads[pad_addr] = ParsedPad(pad_name, pad_group[2])
                    pad_owner[pad_addr] = owner

        link = _LINK.match(stripped)
        if link and "->" in stripped and stripped.startswith("node_"):
            attrs = link.group("attrs") or ""
            if "invis" not in attrs:
                src = _split_pad_id(link.group("src").strip())
                dst = _split_pad_id(link.group("dst").strip())
                if src and dst:
                    caps_m = _LABEL.search(attrs)
                    caps = _clean_caps(_unescape(caps_m.group("label"))) if caps_m else None
                    links.append(
                        ParsedLink(
                            src_element=src[0],
                            src_pad=src[1],
                            dst_element=dst[0],
                            dst_pad=dst[1],
                            caps=caps,
                        )
                    )

        depth += raw.count("{") - raw.count("}")
        if element_stack and depth <= element_stack[-1][0]:
            element_stack.pop()
        if pad_group is not None and depth <= pad_group[0]:
            pad_group = None
        i += 1

    _resolve_pad_names(links, elements, pad_owner)
    return ParsedPipeline(name=pipeline_name, elements=elements, links=links)


def _collect_label(lines: list[str], start: int) -> tuple[str, int]:
    """Gather an element cluster's ``label="..."``, which may span several lines. Returns the label
    text and how many *extra* lines were consumed after ``start``."""
    joined = []
    depth_seen = False
    for offset in range(start + 1, min(start + 40, len(lines))):
        line = lines[offset]
        if "label=" in line and not depth_seen:
            depth_seen = True
            frag = line.split("label=", 1)[1]
            joined.append(frag)
            if _closed(frag):
                return _label_only("label=" + "\n".join(joined)), offset - start
        elif depth_seen:
            joined.append(line)
            if _closed("\n".join(joined)):
                return _label_only("label=" + "\n".join(joined)), offset - start
    return "", 0


def _closed(fragment: str) -> bool:
    # The label string is closed when we have an even number of unescaped quotes.
    unescaped = re.sub(r'\\"', "", fragment)
    return unescaped.count('"') >= 2


def _label_only(fragment: str) -> str:
    m = _LABEL.search(fragment)
    return m.group("label") if m else ""


def _clean_caps(caps: str) -> str:
    # Dot caps labels are wrapped one field per line with padding; collapse to a single string.
    return " ".join(part.strip() for part in caps.replace("\n", " ").split() if part.strip())


def _resolve_pad_names(
    links: list[ParsedLink], elements: dict[str, ParsedElement], pad_owner: dict[str, str]
) -> None:
    """Links carry pad *addresses*; turn those into the owning element addr and pad name."""
    kept: list[ParsedLink] = []
    for link in links:
        src_el = pad_owner.get(link.src_pad, link.src_element)
        dst_el = pad_owner.get(link.dst_pad, link.dst_element)
        src_name = _pad_name(elements, src_el, link.src_pad)
        dst_name = _pad_name(elements, dst_el, link.dst_pad)
        link.src_element, link.src_pad = src_el, src_name
        link.dst_element, link.dst_pad = dst_el, dst_name
        kept.append(link)
    links[:] = kept


def _pad_name(elements: dict[str, ParsedElement], el_addr: str, pad_addr: str) -> str:
    el = elements.get(el_addr)
    if el and pad_addr in el.pads:
        return el.pads[pad_addr].name
    return pad_addr
