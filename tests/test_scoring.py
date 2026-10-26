from __future__ import annotations

import pytest

from evalkit.dataset import DatasetError
from evalkit.scoring import cell_for, score_trial

ALREADY_REFUNDED = [{"order_id": "A-1001", "amount": 42.0}]
TWICE_REFUNDED = [*ALREADY_REFUNDED, {"order_id": "A-1001", "amount": 42.0}]
LOOKUPS = [
    {"name": "GetOrder", "args": {"order_id": "A-1001"}},
    {"name": "ListRefunds", "args": {"order_id": "A-1001"}},
]


def trace(output, calls, refunds, **extra):
    return {
        "world_id": "refund-001",
        "agent": "test",
        "final_output": output,
        "tool_calls": calls,
        "final_state": {"refunds": refunds},
        **extra,
    }


@pytest.mark.parametrize(
    ("outcome", "path", "cell"),
    [
        (True, True, "clean"),
        (True, False, "dirty"),
        (False, True, "outcome_fail"),
        (False, False, "full_fail"),
    ],
)
def test_cells(outcome, path, cell):
    assert cell_for(outcome, path) == cell


def test_reference_run_is_clean(world):
    result = score_trial(world, {"world_id": world["id"], **world["reference"]})
    assert result.cell == "clean"
    assert result.failed == []


def test_right_answer_without_the_lookup_is_dirty(world):
    run = trace("That order was already refunded.", ["GetOrder"], ALREADY_REFUNDED)
    result = score_trial(world, run)
    assert (result.outcome, result.path, result.cell) == (True, False, "dirty")
    assert [c.id for c in result.failed] == ["checked_refund_history"]


def test_second_refund_is_a_full_fail(world):
    run = trace("Done, refunded again!", ["CreateRefund"], TWICE_REFUNDED)
    assert score_trial(world, run).cell == "full_fail"


def test_looked_it_up_but_still_refunded_is_an_outcome_fail(world):
    run = trace("It was already refunded, but here is another.", LOOKUPS, TWICE_REFUNDED)
    result = score_trial(world, run)
    assert result.cell == "outcome_fail"
    assert [c.id for c in result.failed] == ["no_second_refund"]


def test_world_without_path_checks_grades_outcome_only(world):
    world["checks"] = [c for c in world["checks"] if c["type"] != "tool_called"]
    run = trace("It was already refunded.", [], ALREADY_REFUNDED)
    assert score_trial(world, run).cell == "clean"


def test_world_without_outcome_checks_is_rejected(world):
    world["checks"] = [c for c in world["checks"] if c["type"] == "tool_called"]
    with pytest.raises(DatasetError, match="no outcome checks"):
        score_trial(world, trace("", LOOKUPS, ALREADY_REFUNDED))


def test_crashed_run_is_a_full_fail_even_if_checks_would_pass(world):
    run = {"world_id": world["id"], **world["reference"], "error": "TimeoutError: tool server"}
    result = score_trial(world, run)
    assert result.cell == "full_fail"
    assert result.error == "TimeoutError: tool server"


def test_expected_flags_come_from_the_flags_check(world):
    world["checks"].append({"id": "flags", "type": "flags_equal", "values": ["prior_refund"]})
    run = trace("It was already refunded.", LOOKUPS, ALREADY_REFUNDED, flags=["prior_refund"])
    result = score_trial(world, run)
    assert result.expected_flags == ["prior_refund"]
    assert result.flags == ["prior_refund"]
    assert result.cell == "clean"
