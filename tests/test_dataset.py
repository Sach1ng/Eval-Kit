from __future__ import annotations

import pytest

from evalkit.dataset import (
    DatasetError,
    load_dataset,
    load_traces,
    normalize_trace,
    validate_config,
    validate_world,
)
from evalkit.util import write_json


def test_loads_config_and_worlds(make_dataset, config, world):
    dataset = load_dataset(make_dataset(config, [world]))
    assert dataset.name == "refunds"
    assert dataset.trials == 4
    assert dataset.acts is True
    assert [w["id"] for w in dataset.ready_worlds()] == ["refund-001"]
    assert dataset.problems() == []


def test_missing_config_points_to_init(tmp_path):
    with pytest.raises(DatasetError, match="evalkit init"):
        load_dataset(tmp_path)


def test_invalid_json_names_the_file(make_dataset, config, world):
    root = make_dataset(config, [world])
    (root / "worlds" / "broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(DatasetError, match=r"broken\.json: invalid JSON"):
        load_dataset(root)


def test_valid_world_has_no_problems(world):
    assert validate_world(world, {"double_refund"}) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"id": "bad id"}, "id must be"),
        ({"status": "done"}, "status must be"),
        ({"split": "test"}, "split must be"),
        ({"clean": "no"}, "clean must be true or false"),
        ({"pathway": "unknown"}, "not declared"),
        ({"task": "  "}, "task is empty"),
        ({"checks": []}, "needs at least one check"),
        ({"environment": []}, "environment must be an object"),
    ],
)
def test_world_problems_are_specific(world, change, expected):
    world.update(change)
    problems = validate_world(world, {"double_refund"})
    assert any(expected in p for p in problems), problems


@pytest.mark.parametrize(
    ("check", "expected"),
    [
        ({"id": "a", "type": "sounds_right"}, "type must be one of"),
        ({"id": "a", "type": "contains_any"}, "needs 'values'"),
        ({"id": "a", "type": "contains_any", "values": []}, "must not be empty"),
        ({"id": "a", "type": "regex", "pattern": "("}, "does not compile"),
        ({"id": "a", "type": "contains_all", "values": ["x"], "min": 1}, "only applies"),
        ({"id": "a", "type": "tool_called", "tool": "X", "args": "y"}, "args must be an object"),
        ({"id": "a", "type": "regex", "pattern": "x", "min": 3, "max": 1}, "min is larger"),
        ({"id": "a", "type": "state_equals", "path": "x"}, "needs 'value'"),
        ({"type": "contains_any", "values": ["x"]}, "needs an id"),
    ],
)
def test_check_problems_are_specific(world, check, expected):
    world["checks"].append(check)
    problems = validate_world(world, {"double_refund"})
    assert any(expected in p for p in problems), problems


def test_duplicate_check_ids_are_reported(world):
    world["checks"].append(dict(world["checks"][0]))
    assert any("used twice" in p for p in validate_world(world))


def test_draft_worlds_may_be_unfinished():
    draft = {"id": "double_refund-03", "status": "draft", "task": "", "checks": []}
    assert validate_world(draft) == []


def test_duplicate_world_ids_are_reported(make_dataset, config, world):
    root = make_dataset(config, [world])
    write_json(root / "worlds" / "copy.json", world)
    problems = load_dataset(root).problems()
    assert any("also used by" in message for _, message in problems)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"trials": 0}, "trials must be"),
        ({"acts": "yes"}, "acts must be"),
        ({"gates": [{"metric": "vibes", "min": 0.9}]}, "metric must be one of"),
        ({"gates": [{"metric": "clean_rate", "min": 0.9, "max": 1}]}, "exactly one of min or max"),
        ({"gates": [{"metric": "clean_rate", "min": 90}]}, "from 0 to 1"),
        ({"agents": {"mine": "agent.py"}}, "agents must map"),
        ({"pathways": [{"id": "a"}, {"id": "a"}]}, "declared twice"),
        ({"dimensions": {"tone": []}}, "dimensions must map"),
    ],
)
def test_config_problems_are_specific(config, change, expected):
    config.update(change)
    problems = validate_config(config)
    assert any(expected in p for p in problems), problems


def test_normalize_trace_puts_calls_and_flags_in_one_shape():
    trace = normalize_trace(
        {
            "world_id": "w",
            "tool_calls": ["GetOrder", {"name": "ListRefunds"}],
            "flags": [{"id": "f1"}],
        }
    )
    assert trace["tool_calls"] == [
        {"name": "GetOrder", "args": {}},
        {"name": "ListRefunds", "args": {}},
    ]
    assert trace["flags"] == ["f1"]
    assert trace["agent"] == "agent"
    assert trace["trial"] == 1
    assert trace["final_output"] == ""


def test_load_traces_reads_single_traces_and_lists(tmp_path):
    write_json(tmp_path / "a.json", {"world_id": "w1", "agent": "x"})
    write_json(tmp_path / "nested" / "b.json", [{"world_id": "w2"}, {"world_id": "w3", "trial": 2}])
    traces = load_traces(tmp_path)
    assert [t["world_id"] for t in traces] == ["w1", "w2", "w3"]


def test_invalid_trace_names_the_file_and_entry(tmp_path):
    write_json(tmp_path / "runs.json", [{"world_id": "w1"}, {"world_id": "w2", "trial": 0}])
    with pytest.raises(DatasetError, match=r"runs\.json\[1\]: trial must be"):
        load_traces(tmp_path)
