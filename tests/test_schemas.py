"""The published JSON Schemas and the Python validator must agree."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from evalkit.dataset import validate_config, validate_trace, validate_world

SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"


def schema(name: str) -> Draft202012Validator:
    data = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(data)
    return Draft202012Validator(data)


def test_fixtures_are_valid_under_both(world, config):
    assert not list(schema("world").iter_errors(world))
    assert not list(schema("config").iter_errors(config))
    trace = {"world_id": world["id"], **world["reference"]}
    assert not list(schema("trace").iter_errors(trace))
    assert validate_world(world) == []
    assert validate_config(config) == []
    assert validate_trace(trace) == []


@pytest.mark.parametrize(
    "change",
    [
        {"id": "has space"},
        {"split": "test"},
        {"status": "done"},
        {"checks": [{"id": "a", "type": "sounds_right"}]},
        {"checks": [{"id": "a", "type": "contains_any"}]},
        {"checks": [{"id": "a", "type": "tool_called"}]},
        {"checks": [{"id": "a", "type": "state_equals", "path": "x"}]},
    ],
)
def test_invalid_worlds_are_rejected_by_both(world, change):
    world.update(change)
    assert list(schema("world").iter_errors(world))
    assert validate_world(world)


@pytest.mark.parametrize(
    "trace",
    [
        {},
        {"world_id": "w", "trial": 0},
        {"world_id": "w", "tool_calls": [{"args": {}}]},
        {"world_id": "w", "final_state": []},
        {"world_id": "w", "latency_ms": -1},
    ],
)
def test_invalid_traces_are_rejected_by_both(trace):
    assert list(schema("trace").iter_errors(trace))
    assert validate_trace(trace)
