"""Validation of a stored property value against its ``PropertyInfo``."""

from __future__ import annotations

import re

from pipelab.catalog.models import PropertyInfo, PropertyValue
from pipelab.gst import Gst
from pipelab.gst.caps import parse_structure
from pipelab.gst.values import FALSE_WORDS, TRUE_WORDS, parse_number

_INTEGER_TYPES = {"int", "uint", "int64", "uint64"}
_FLOAT_TYPES = {"float", "double"}
_FRACTION = re.compile(r"^\s*-?\d+\s*/\s*\d+\s*$|^\s*-?\d+\s*$")


def _check_range(prop: PropertyInfo, number: float) -> str | None:
    if prop.minimum is not None and number < prop.minimum:
        return f"{prop.name}={number} is below the minimum {prop.minimum}"
    if prop.maximum is not None and number > prop.maximum:
        return f"{prop.name}={number} is above the maximum {prop.maximum}"
    return None


def _enum_tokens(prop: PropertyInfo) -> set[str]:
    tokens = {v.nick for v in prop.enum_values} | {v.name for v in prop.enum_values}
    return tokens | {str(v.value) for v in prop.enum_values}


def check_value(prop: PropertyInfo, value: PropertyValue) -> str | None:
    """Error message when ``value`` cannot be applied to ``prop``, else ``None``."""
    kind = prop.type
    if kind == "boolean":
        if isinstance(value, bool) or str(value).strip().lower() in TRUE_WORDS | FALSE_WORDS:
            return None
        return f"{prop.name} expects true or false"
    if kind in _INTEGER_TYPES or kind in _FLOAT_TYPES:
        number = parse_number(value, kind in _INTEGER_TYPES)
        if number is None:
            return f"{prop.name} expects {'an integer' if kind in _INTEGER_TYPES else 'a number'}"
        return _check_range(prop, number)
    if kind == "enum" and prop.enum_values and str(value) not in _enum_tokens(prop):
        nicks = ", ".join(v.nick for v in prop.enum_values[:8])
        return f"{prop.name} must be one of: {nicks}"
    if kind == "flags" and prop.enum_values:
        unknown = [t for t in str(value).split("+") if t.strip() and t.strip() not in _enum_tokens(prop)]
        if unknown and not str(value).isdigit():
            return f"{prop.name}: unknown flag(s) {', '.join(unknown)}"
    if kind == "caps" and str(value).strip() and Gst.Caps.from_string(str(value)) is None:
        return f"{prop.name}: invalid caps '{value}'"
    if kind == "fraction" and not _FRACTION.match(str(value)):
        return f"{prop.name} expects a fraction like 30/1"
    if kind == "structure" and str(value).strip() and parse_structure(str(value)) is None:
        return f"{prop.name}: invalid structure '{value}'"
    return None
