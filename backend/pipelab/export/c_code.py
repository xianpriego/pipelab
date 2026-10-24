"""Single-file C program using the GStreamer API."""

from __future__ import annotations

from pipelab.catalog.store import Catalog
from pipelab.export.c_template import EPILOGUE, PRELUDE
from pipelab.export.common import ElementSpec, PipelineSpec, PropertySpec, build_spec, slug
from pipelab.export.gst_launch import render_description
from pipelab.export.script_notes import comment_block, script_notes
from pipelab.graph.models import Graph

C_KEYWORDS = frozenset(
    [
        "auto",
        "break",
        "case",
        "char",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extern",
        "float",
        "for",
        "goto",
        "if",
        "inline",
        "int",
        "long",
        "register",
        "restrict",
        "return",
        "short",
        "signed",
        "sizeof",
        "static",
        "struct",
        "switch",
        "typedef",
        "union",
        "unsigned",
        "void",
        "volatile",
        "while",
        "true",
        "false",
        "bool",
        "pipeline",
        "pad",
        "bus",
        "loop",
        "main",
        "make_element",
        "link_pads",
        "link_dynamic",
        "get_pad",
        "on_pad_added",
        "free_dynamic_link",
        "build_pipeline",
        "on_message",
        "on_sigint",
    ]
)


def c_string(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def c_value(spec: PropertySpec) -> str:
    value = spec.value
    if spec.kind == "bool":
        return "TRUE" if value else "FALSE"
    if spec.kind == "int":
        return f"(gint) {int(value)}"
    if spec.kind == "uint":
        return f"(guint) {int(value)}u"
    if spec.kind == "int64":
        return f"G_GINT64_CONSTANT ({int(value)})"
    if spec.kind == "uint64":
        return f"G_GUINT64_CONSTANT ({int(value)})"
    if spec.kind in ("float", "double"):
        return f"(gdouble) {float(value)!r}"
    return c_string(str(value))


def _set_properties(target: str, specs: tuple[PropertySpec, ...]) -> list[str]:
    lines = []
    typed = [s for s in specs if s.kind != "parse"]
    if typed:
        pairs = ", ".join(f"{c_string(s.name)}, {c_value(s)}" for s in typed)
        lines.append(f"  g_object_set ({target}, {pairs}, NULL);")
    for spec in specs:
        if spec.kind == "parse":
            args = f"G_OBJECT ({target}), {c_string(spec.name)}, {c_string(spec.text)}"
            lines.append(f"  gst_util_set_object_arg ({args});")
    return lines


def _element_lines(element: ElementSpec) -> list[str]:
    var = element.ident
    lines = [
        f"  {var} = make_element (pipeline, {c_string(element.factory)}, {c_string(element.name)});",
        f"  if ({var} == NULL)",
        "    goto failed;",
    ]
    return lines + _set_properties(var, element.properties)


def _after_link_lines(element: ElementSpec) -> list[str]:
    lines = []
    for pad, specs in element.pad_properties:
        lines += [
            f"  pad = get_pad ({element.ident}, {c_string(pad)});",
            "  if (pad == NULL)",
            "    goto failed;",
        ]
        lines += _set_properties("pad", specs)
        lines.append("  gst_object_unref (pad);")
    for ref in element.pad_refs:
        lines += [
            f"  pad = get_pad ({element.ident}, {c_string(str(ref.value))});",
            "  if (pad == NULL)",
            "    goto failed;",
            f"  g_object_set ({element.ident}, {c_string(ref.name)}, pad, NULL);",
            "  gst_object_unref (pad);",
        ]
    return lines


def _build_body(spec: PipelineSpec) -> list[str]:
    lines = [f"  GstElement *{e.ident};" for e in spec.elements]
    needs_pad = any(e.pad_properties or e.pad_refs for e in spec.elements)
    if needs_pad:
        lines.append("  GstPad *pad;")
    lines.append("")
    for element in spec.elements:
        lines += _element_lines(element)
    for link in spec.links:
        function = "link_dynamic" if link.dynamic else "link_pads"
        source = f"{link.source.ident}, {c_string(link.source_pad)}"
        args = f"{source}, {link.target.ident}, {c_string(link.target_pad)}"
        lines += [f"  if (!{function} ({args}))", "    goto failed;"]
    for element in spec.elements:
        lines += _after_link_lines(element)
    lines += ["  return pipeline;", "", "failed:", "  gst_object_unref (pipeline);", "  return NULL;", "}"]
    return lines


def render(graph: Graph, catalog: Catalog, name: str) -> str:
    spec = build_spec(graph, catalog, name, reserved=C_KEYWORDS)
    binary = slug(name)
    description = render_description(graph, catalog).replace("*/", "* /") or "(empty)"
    prelude = PRELUDE.format(
        name=name.replace("*/", "* /"),
        file=f"{binary}.c",
        binary=binary,
        description=description,
        pipeline_name=c_string(name),
    )
    notes = comment_block(script_notes(graph, "c"), "c")
    return prelude + "\n".join(_build_body(spec)) + "\n" + EPILOGUE + notes
