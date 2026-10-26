from __future__ import annotations

import pytest

from evalkit.checks import evaluate, layer_of, resolve
from evalkit.dataset import normalize_trace


def grade(check, **trace):
    return evaluate({"id": "c", **check}, normalize_trace({"world_id": "w", **trace}))


@pytest.mark.parametrize(
    ("check", "output", "passed"),
    [
        ({"type": "contains_all", "values": ["$42", "A-1001"]}, "Refunded $42 on A-1001.", True),
        ({"type": "contains_all", "values": ["$42", "A-1001"]}, "Refunded $42.", False),
        ({"type": "contains_any", "values": ["already issued", "prior"]}, "ALREADY  issued", True),
        ({"type": "contains_any", "values": ["already issued"]}, "Refund sent!", False),
        ({"type": "not_contains", "values": ["you're all set"]}, "Refund declined.", True),
        ({"type": "not_contains", "values": ["you're all set"]}, "You're all set.", False),
    ],
)
def test_text_checks_ignore_case_and_spacing(check, output, passed):
    assert grade(check, final_output=output).passed is passed


def test_text_failures_say_what_is_missing():
    result = grade({"type": "contains_all", "values": ["$42", "A-1001"]}, final_output="$42")
    assert result.detail == "missing 'A-1001'"


@pytest.mark.parametrize(
    ("bounds", "output", "passed"),
    [
        ({}, "Proposed JE ...", True),
        ({}, "nothing here", False),
        ({"min": 0, "max": 1}, "Proposed JE ... Proposed JE", False),
        ({"min": 0, "max": 1}, "no entries", True),
        ({"min": 2}, "Proposed JE / Proposed JE", True),
    ],
)
def test_regex_counts_matches(bounds, output, passed):
    check = {"type": "regex", "pattern": r"\bproposed je\b", **bounds}
    assert grade(check, final_output=output).passed is passed


def test_tool_called_matches_a_subset_of_args():
    calls = [{"name": "ListRefunds", "args": {"order_id": "A-1001", "limit": 10}}]
    check = {"type": "tool_called", "tool": "ListRefunds", "args": {"order_id": "A-1001"}}
    assert grade(check, tool_calls=calls).passed
    check["args"] = {"order_id": "B-2207"}
    result = grade(check, tool_calls=calls)
    assert not result.passed
    assert result.detail == "ListRefunds(order_id='B-2207') called 0 time(s), expected >= 1"


def test_tool_called_respects_min():
    check = {"type": "tool_called", "tool": "RunTests", "min": 2}
    assert not grade(check, tool_calls=["RunTests"]).passed
    assert grade(check, tool_calls=["RunTests", "Edit", "RunTests"]).passed


def test_tool_not_called():
    check = {"type": "tool_not_called", "tool": "CreateRefund"}
    assert grade(check, tool_calls=["GetOrder"]).passed
    assert not grade(check, tool_calls=["GetOrder", "CreateRefund"]).passed


def test_state_equals_follows_dotted_paths():
    state = {"refunds": [{"order_id": "A-1001", "amount": 42.0}]}
    check = {"type": "state_equals", "path": "refunds.0.amount", "value": 42}
    assert grade(check, final_state=state).passed
    check["value"] = 84
    result = grade(check, final_state=state)
    assert not result.passed
    assert result.detail == "refunds.0.amount: expected 84, got 42.0"


@pytest.mark.parametrize(
    ("state", "detail"),
    [
        (None, "trace has no final_state"),
        ({"refunds": []}, "refunds.0 is missing from final_state"),
    ],
)
def test_state_equals_fails_when_the_value_is_absent(state, detail):
    result = grade({"type": "state_equals", "path": "refunds.0", "value": {}}, final_state=state)
    assert not result.passed
    assert result.detail == detail


def test_state_equals_does_not_treat_true_as_one():
    check = {"type": "state_equals", "path": "posted", "value": 1}
    assert not grade(check, final_state={"posted": True}).passed


@pytest.mark.parametrize(
    ("expected", "raised", "passed", "detail"),
    [
        (["payroll_missing:Q4"], ["payroll_missing:Q4"], True, "flags match"),
        ([], [], True, "no flags, as expected"),
        (["payroll_missing:Q4"], [], False, "missed 'payroll_missing:Q4'"),
        ([], ["suspicious_memo:T-9"], False, "extra 'suspicious_memo:T-9'"),
    ],
)
def test_flags_equal(expected, raised, passed, detail):
    result = grade({"type": "flags_equal", "values": expected}, flags=raised)
    assert (result.passed, result.detail) == (passed, detail)


def test_layers_default_by_type_and_can_be_overridden():
    assert layer_of({"type": "tool_called", "tool": "X"}) == "path"
    assert layer_of({"type": "state_equals", "path": "x", "value": 1}) == "outcome"
    assert layer_of({"type": "contains_any", "values": ["x"], "layer": "path"}) == "path"


def test_resolve_handles_objects_and_lists():
    state = {"a": {"b": [10, {"c": "x"}]}}
    assert resolve(state, "a.b.1.c") == "x"
    assert resolve(state, "a.b.0") == 10
