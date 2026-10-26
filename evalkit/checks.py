"""Check types. A check is a small JSON object in a world file that grades one trace.

Outcome checks read what a run produced: the final reply, the final state of the
environment, and any structured flags. Path checks read how it got there: the
tool calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from evalkit.util import is_int

LAYERS = ("outcome", "path")


@dataclass(frozen=True)
class CheckType:
    layer: str
    params: dict[str, str]
    summary: str


CHECK_TYPES: dict[str, CheckType] = {
    "contains_all": CheckType(
        "outcome", {"values": "texts"}, "The final output contains every value."
    ),
    "contains_any": CheckType(
        "outcome", {"values": "texts"}, "The final output contains at least one value."
    ),
    "not_contains": CheckType(
        "outcome", {"values": "texts"}, "The final output contains none of the values."
    ),
    "regex": CheckType(
        "outcome",
        {"pattern": "pattern"},
        "The final output matches a pattern at least `min` (default 1) and at most `max` times.",
    ),
    "state_equals": CheckType(
        "outcome",
        {"path": "text", "value": "any"},
        "The value at a dotted path in the final environment state equals `value`.",
    ),
    "flags_equal": CheckType(
        "outcome",
        {"values": "texts_or_empty"},
        "The agent raised exactly these flags. An empty list means it should raise none.",
    ),
    "tool_called": CheckType(
        "path",
        {"tool": "text"},
        "A tool was called at least `min` (default 1) times, with matching `args` if given.",
    ),
    "tool_not_called": CheckType(
        "path", {"tool": "text"}, "A tool was never called with matching `args`."
    ),
}

TEXT_CHECKS = ("contains_all", "contains_any", "not_contains")
_COUNTED = ("regex", "tool_called")
_WITH_ARGS = ("tool_called", "tool_not_called")


def layer_of(check: dict[str, Any]) -> str:
    return check.get("layer") or CHECK_TYPES[check["type"]].layer


def validate_check(check: Any) -> list[str]:
    """Return every problem with one check. An empty list means it can be graded."""
    if not isinstance(check, dict):
        return ["must be an object"]
    problems = []
    if not isinstance(check.get("id"), str) or not check["id"].strip():
        problems.append("needs an id")
    kind = CHECK_TYPES.get(check.get("type"))
    if kind is None:
        return [*problems, f"type must be one of: {', '.join(CHECK_TYPES)}"]
    name = check["type"]

    if check.get("layer", kind.layer) not in LAYERS:
        problems.append("layer must be 'outcome' or 'path'")

    for param, form in kind.params.items():
        if param not in check:
            problems.append(f"{name} needs {param!r}")
            continue
        problems.extend(_param_problems(param, form, check[param]))

    for bound in ("min", "max"):
        if bound not in check:
            continue
        if name not in _COUNTED:
            problems.append(f"{bound!r} only applies to {' and '.join(_COUNTED)}")
        elif not is_int(check[bound]) or check[bound] < 0:
            problems.append(f"{bound} must be a whole number of at least 0")
    if is_int(check.get("min")) and is_int(check.get("max")) and check["min"] > check["max"]:
        problems.append("min is larger than max")

    if "args" in check:
        if name not in _WITH_ARGS:
            problems.append(f"'args' only applies to {' and '.join(_WITH_ARGS)}")
        elif not isinstance(check["args"], dict):
            problems.append("args must be an object")
    return problems


def _param_problems(param: str, form: str, value: Any) -> list[str]:
    if form == "text" and not (isinstance(value, str) and value.strip()):
        return [f"{param} must be a non-empty string"]
    if form in ("texts", "texts_or_empty"):
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            return [f"{param} must be a list of non-empty strings"]
        if form == "texts" and not value:
            return [f"{param} must not be empty"]
    if form == "pattern":
        if not (isinstance(value, str) and value):
            return [f"{param} must be a non-empty string"]
        try:
            re.compile(value)
        except re.error as exc:
            return [f"pattern does not compile: {exc}"]
    return []
