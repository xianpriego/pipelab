"""Rust literals and small source-level checks shared by the Rust generators."""

from __future__ import annotations

import math
import re

from pipelab.export.plan import ParamKind


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


def value_literal(value: object) -> str:
    """``rt::Value`` expression for a JSON primitive."""
    if value is None:
        return "Value::Null"
    if isinstance(value, bool):
        return f"Value::Bool({'true' if value else 'false'})"
    if isinstance(value, int):
        return f"Value::Int({value})"
    if isinstance(value, float):
        return f"Value::Float({rust_float(value)})"
    return f"Value::from({rust_str(str(value))})"


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


_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')


def uses_name(name: str, lines: list[str]) -> bool:
    """Whether generated code (strings and comments aside) reads variable ``name``."""
    pattern = re.compile(rf"(?<![\w.]){name}\b")
    return any(pattern.search(_STRING.sub('""', line).split("//")[0]) for line in lines)
