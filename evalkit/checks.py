"""Check types. A check is a small JSON object in a world file that grades one trace.

Outcome checks read what a run produced: the final reply, the final state of the
environment, and any structured flags. Path checks read how it got there: the
tool calls.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable

from evalkit.util import is_int

LAYERS = ("outcome", "path")
_MISSING = object()


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


@dataclass(frozen=True)
class CheckResult:
    id: str
    type: str
    layer: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def layer_of(check: dict[str, Any]) -> str:
    return check.get("layer") or CHECK_TYPES[check["type"]].layer


def evaluate(check: dict[str, Any], trace: dict[str, Any]) -> CheckResult:
    """Grade one normalized trace against one valid check."""
    passed, detail = _EVALUATORS[check["type"]](check, trace)
    return CheckResult(check["id"], check["type"], layer_of(check), passed, detail)


def resolve(state: Any, path: str) -> Any:
    """Follow a dotted path such as `refunds.0.amount` through objects and lists."""
    current = state
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return _MISSING
    return current


def same_json(a: Any, b: Any) -> bool:
    """JSON equality that does not treat true as 1 or false as 0."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same_json(a[key], b[key]) for key in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same_json(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


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


Outcome = tuple[bool, str]


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _quote(values: list[str]) -> str:
    return ", ".join(repr(v) for v in values)


def _short(value: Any, limit: int = 120) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _found(check: dict[str, Any], trace: dict[str, Any]) -> list[str]:
    text = _norm(trace["final_output"])
    return [v for v in check["values"] if _norm(v) in text]


def _contains_all(check: dict[str, Any], trace: dict[str, Any]) -> Outcome:
    found = _found(check, trace)
    missing = [v for v in check["values"] if v not in found]
    return not missing, f"missing {_quote(missing)}" if missing else "all present"


def _contains_any(check: dict[str, Any], trace: dict[str, Any]) -> Outcome:
    found = _found(check, trace)
    return bool(found), f"found {found[0]!r}" if found else f"none of {_quote(check['values'])}"


def _not_contains(check: dict[str, Any], trace: dict[str, Any]) -> Outcome:
    found = _found(check, trace)
    return not found, f"found {_quote(found)}" if found else "none present"


def _regex(check: dict[str, Any], trace: dict[str, Any]) -> Outcome:
    count = sum(1 for _ in re.finditer(check["pattern"], trace["final_output"], re.IGNORECASE))
    low, high = check.get("min", 1), check.get("max")
    passed = count >= low and (high is None or count <= high)
    if high is None:
        expected = f"at least {low}"
    elif high == low:
        expected = str(low)
    else:
        expected = f"{low} to {high}"
    return passed, f"{count} match(es) for /{check['pattern']}/, expected {expected}"


def _calls(check: dict[str, Any], trace: dict[str, Any]) -> int:
    want = check.get("args", {})
    return sum(
        1
        for call in trace["tool_calls"]
        if call["name"] == check["tool"]
        and all(same_json(call["args"].get(k, _MISSING), v) for k, v in want.items())
    )


def _call_label(check: dict[str, Any]) -> str:
    args = check.get("args")
    if not args:
        return check["tool"]
    return f"{check['tool']}({', '.join(f'{k}={v!r}' for k, v in args.items())})"


def _tool_called(check: dict[str, Any], trace: dict[str, Any]) -> Outcome:
    count, low = _calls(check, trace), check.get("min", 1)
    return count >= low, f"{_call_label(check)} called {count} time(s), expected >= {low}"


def _tool_not_called(check: dict[str, Any], trace: dict[str, Any]) -> Outcome:
    count = _calls(check, trace)
    return count == 0, f"{_call_label(check)} called {count} time(s), expected 0"


def _state_equals(check: dict[str, Any], trace: dict[str, Any]) -> Outcome:
    state = trace.get("final_state")
    if state is None:
        return False, "trace has no final_state"
    actual = resolve(state, check["path"])
    if actual is _MISSING:
        return False, f"{check['path']} is missing from final_state"
    if same_json(actual, check["value"]):
        return True, f"{check['path']} matches"
    return False, f"{check['path']}: expected {_short(check['value'])}, got {_short(actual)}"


def _flags_equal(check: dict[str, Any], trace: dict[str, Any]) -> Outcome:
    expected, raised = set(check["values"]), set(trace["flags"])
    missed, extra = sorted(expected - raised), sorted(raised - expected)
    if not missed and not extra:
        return True, "flags match" if expected else "no flags, as expected"
    parts = [f"missed {_quote(missed)}"] if missed else []
    parts += [f"extra {_quote(extra)}"] if extra else []
    return False, "; ".join(parts)


_EVALUATORS: dict[str, Callable[[dict[str, Any], dict[str, Any]], Outcome]] = {
    "contains_all": _contains_all,
    "contains_any": _contains_any,
    "not_contains": _not_contains,
    "regex": _regex,
    "state_equals": _state_equals,
    "flags_equal": _flags_equal,
    "tool_called": _tool_called,
    "tool_not_called": _tool_not_called,
}
