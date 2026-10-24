"""Values in probe rules and API functions: ``$references``, comparisons, templates."""

from __future__ import annotations

import operator
import re
from collections.abc import Mapping
from typing import Any

_OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def resolve(value: Any, env: Mapping[str, Any]) -> Any:
    """``"$name"`` → ``env["name"]``; ``"$$x"`` → ``"$x"``; anything else as is."""
    if isinstance(value, str) and value.startswith("$"):
        return value[1:] if value.startswith("$$") else env.get(value[1:])
    return value


def resolve_all(values: Mapping[str, Any], env: Mapping[str, Any]) -> dict[str, Any]:
    return {key: resolve(value, env) for key, value in values.items()}


def _coerce(left: Any, right: Any) -> tuple[Any, Any]:
    if isinstance(left, bool) or isinstance(right, bool):
        return left, right
    try:
        return float(left), float(right)
    except (TypeError, ValueError):
        return ("" if left is None else str(left)), ("" if right is None else str(right))


def compare(left: Any, op: str | None, right: Any) -> bool:
    """Numbers compare numerically (also when given as text), the rest as text."""
    left, right = _coerce(left, right)
    try:
        return bool(_OPERATORS.get(op or "==", operator.eq)(left, right))
    except TypeError:
        return False


def expand(template: str, env: Mapping[str, Any]) -> str:
    """``"lost {count} buffers"`` with the variables/builtins of ``env``."""
    return _PLACEHOLDER.sub(lambda m: str(env[m.group(1)]) if m.group(1) in env else m.group(0), template)
