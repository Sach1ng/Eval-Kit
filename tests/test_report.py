from __future__ import annotations

import copy

import pytest

from evalkit.dataset import DatasetError, load_dataset
from evalkit.report import (
    build_report,
    compare_reports,
    evaluate_gates,
    render_markdown,
    render_summary,
    score_dataset,
)

TWICE = [{"order_id": "A-1001", "amount": 42.0}, {"order_id": "A-1001", "amount": 42.0}]


def runs(world, agent, trials, broken=()):
    """Reference runs for `agent`; trials listed in `broken` refund a second time."""
    traces = []
    for trial in range(1, trials + 1):
        trace = {"world_id": world["id"], "agent": agent, "trial": trial, **world["reference"]}
        if trial in broken:
            trace = copy.deepcopy(trace)
            trace["final_state"] = {"refunds": TWICE}
        traces.append(trace)
    return traces


@pytest.fixture
def dataset(make_dataset, config, world):
    config["gates"] = [{"metric": "clean_pass_hat_k", "min": 0.9}]
    config["agents"] = {"steady": "agents.py:steady", "shaky": "agents.py:shaky"}
    draft = {"id": "draft-01", "status": "draft", "pathway": "double_refund", "checks": []}
    return load_dataset(make_dataset(config, [world, draft]))


def test_score_dataset_skips_drafts_and_rejects_unknown_worlds(dataset, world):
    draft_run = {**runs(world, "steady", 1)[0], "world_id": "draft-01"}
    traces = [*runs(world, "steady", 2), draft_run]
    results, skipped = score_dataset(dataset, traces)
    assert (len(results), skipped) == (2, 1)
    with pytest.raises(DatasetError, match="unknown world 'nope'"):
        score_dataset(dataset, [{**traces[0], "world_id": "nope"}])


def test_score_dataset_rejects_duplicate_trials(dataset, world):
    trace = runs(world, "steady", 1)[0]
    with pytest.raises(DatasetError, match="two traces"):
        score_dataset(dataset, [trace, trace])


def test_report_gates_each_agent_and_lists_failures(dataset, world):
    traces = runs(world, "shaky", 4, broken={2}) + runs(world, "steady", 4)
    results, _ = score_dataset(dataset, traces)
    report = build_report(dataset, results)
    assert list(report["agents"]) == ["steady", "shaky"]
    steady, shaky = report["agents"]["steady"], report["agents"]["shaky"]
    assert steady["clean_pass_hat_k"] == 1.0
    assert steady["gates"][0]["passed"] is True
    assert shaky["clean_rate"] == 0.75
    assert shaky["clean_pass_hat_k"] == 0.0
    assert shaky["gates"][0]["passed"] is False
    assert report["passed"] is False
    (failure,) = report["failures"]
    assert (failure["agent"], failure["trial"], failure["cell"]) == ("shaky", 2, "outcome_fail")
    assert [c["id"] for c in failure["failed"]] == ["no_second_refund"]
    assert failure["failed"][0]["detail"].startswith("refunds: expected")


def test_gates_with_no_value_fail():
    summary = {"precision": None, "dirty_pass_rate": 0.02}
    gates = [{"metric": "precision", "min": 0.8}, {"metric": "dirty_pass_rate", "max": 0.05}]
    assert [g["passed"] for g in evaluate_gates(summary, gates)] == [False, True]


def test_comparison_finds_regressions(dataset, world):
    before = build_report(dataset, score_dataset(dataset, runs(world, "steady", 4))[0])
    after = build_report(dataset, score_dataset(dataset, runs(world, "steady", 4, {1, 3}))[0])
    comparison = compare_reports(before, after)["steady"]
    assert comparison["metrics"]["clean_rate"] == {"baseline": 1.0, "current": 0.5, "change": -0.5}
    assert comparison["regressions"] == [
        {"world_id": "refund-001", "baseline": 1.0, "current": 0.5}
    ]


def test_comparison_pairs_single_agents_with_different_names(dataset, world):
    before = build_report(dataset, score_dataset(dataset, runs(world, "v1", 2))[0])
    after = build_report(dataset, score_dataset(dataset, runs(world, "v2", 2))[0])
    assert compare_reports(before, after)["v2"]["baseline_agent"] == "v1"


def test_markdown_and_terminal_output(dataset, world):
    traces = runs(world, "shaky", 4, broken={2}) + runs(world, "steady", 4)
    report = build_report(dataset, score_dataset(dataset, traces)[0])
    markdown = render_markdown(report)
    assert "# Eval report: refunds" in markdown
    assert "| steady | 4 | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | pass |" in markdown
    assert (
        "| shaky | refund-001 | 2 | outcome_fail | `no_second_refund`: refunds: expected"
        in markdown
    )
    terminal = render_summary(report)
    assert "refunds: 1 world, k = 4" in terminal
    assert "FAIL: clean_pass_hat_k 0.0% (needs >= 90.0%)" in terminal
