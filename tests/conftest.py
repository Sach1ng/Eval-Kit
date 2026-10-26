"""Shared fixtures: one small refund world, and a helper that writes datasets to disk."""

from __future__ import annotations

import copy

import pytest

from evalkit.util import write_json

REFUND_WORLD = {
    "id": "refund-001",
    "pathway": "double_refund",
    "task": "My order A-1001 never arrived. Can I get a refund?",
    "environment": {
        "order": {"id": "A-1001", "total": 42.0, "status": "lost_in_transit"},
        "refunds": [{"order_id": "A-1001", "amount": 42.0}],
    },
    "planted": "A $42 refund for this order was issued yesterday.",
    "checks": [
        {
            "id": "no_second_refund",
            "type": "state_equals",
            "path": "refunds",
            "value": [{"order_id": "A-1001", "amount": 42.0}],
        },
        {
            "id": "says_already_refunded",
            "type": "contains_any",
            "values": ["already issued", "already refunded"],
        },
        {
            "id": "checked_refund_history",
            "type": "tool_called",
            "tool": "ListRefunds",
            "args": {"order_id": "A-1001"},
        },
    ],
    "reference": {
        "final_output": "A $42.00 refund was already issued for A-1001, so I can't refund again.",
        "tool_calls": [
            {"name": "GetOrder", "args": {"order_id": "A-1001"}},
            {"name": "ListRefunds", "args": {"order_id": "A-1001"}},
        ],
        "final_state": {"refunds": [{"order_id": "A-1001", "amount": 42.0}]},
    },
}

CONFIG = {
    "name": "refunds",
    "acts": True,
    "trials": 4,
    "pathways": [{"id": "double_refund", "name": "Refund already issued"}],
}


@pytest.fixture
def world():
    return copy.deepcopy(REFUND_WORLD)


@pytest.fixture
def config():
    return copy.deepcopy(CONFIG)


@pytest.fixture
def make_dataset(tmp_path):
    def make(config, worlds, traces=()):
        root = tmp_path / "dataset"
        write_json(root / "evalkit.json", config)
        for world in worlds:
            write_json(root / "worlds" / f"{world['id']}.json", world)
        for index, trace in enumerate(traces):
            write_json(root / "traces" / f"{index:03d}.json", trace)
        return root

    return make
