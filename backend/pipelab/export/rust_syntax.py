"""Rust identifiers and literals for the Rust generator."""

from __future__ import annotations

import math

from pipelab.export.plan import ParamKind

# Rust keywords plus the names the generated code uses itself (renamed with a trailing "_").
RUST_KEYWORDS = frozenset(
    [
        *("as", "async", "await", "break", "const", "continue", "crate", "dyn", "else", "enum"),
        *("extern", "false", "fn", "for", "if", "impl", "in", "let", "loop", "match", "mod", "move"),
        *("mut", "pub", "ref", "return", "self", "static", "struct", "super", "trait", "true", "type"),
        *("unsafe", "use", "where", "while", "abstract", "become", "box", "do", "final", "macro"),
        *("override", "priv", "typeof", "unsized", "virtual", "yield", "try"),
        *("gst", "rt", "main", "container", "elements", "name", "params", "value"),
    ]
)


def rust_str(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{escaped}"'


def rust_float(value: float) -> str:
    if math.isnan(value):
        return "f64::NAN"
    if math.isinf(value):
        return "f64::INFINITY" if value > 0 else "f64::NEG_INFINITY"
    text = repr(float(value))
    return text if any(c in text for c in ".e") else f"{text}.0"


def typed_literal(kind: ParamKind, value: object) -> str | None:
    """Rust literal of ``value`` for a parameter of ``kind`` (``None`` if it does not convert)."""
    try:
        if kind == "string":
            text = ("true" if value else "false") if isinstance(value, bool) else str(value)
            return f"{rust_str(text)}.to_string()"
        if kind == "bool":
            if isinstance(value, str) and value.lower() in ("true", "false", "1", "0", "yes", "no"):
                value = value.lower() in ("true", "1", "yes")
            return ("true" if value else "false") if isinstance(value, bool | int) else None
        if isinstance(value, bool):
            return None
        if kind == "int":
            number = float(value)  # type: ignore[arg-type]
            return str(int(number)) if number.is_integer() else None
        return rust_float(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
