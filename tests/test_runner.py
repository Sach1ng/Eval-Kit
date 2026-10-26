from __future__ import annotations

import json
import textwrap

import pytest

from evalkit.cli import main
from evalkit.dataset import DatasetError, load_dataset, load_traces
from evalkit.report import score_dataset
from evalkit.runner import load_agent, run_agent, stable_seed

ADAPTERS = textwrap.dedent(
    """
    import random

    def careful(world, *, trial, seed):
        order = world["environment"]["order"]["id"]
        return {
            "final_output": f"A refund was already issued for {order}.",
            "tool_calls": [{"name": "ListRefunds", "args": {"order_id": order}}],
            "final_state": {"refunds": world["environment"]["refunds"]},
        }

    def coin(world, *, trial, seed):
        lucky = random.Random(seed).random() < 0.5
        return {"final_output": "already issued" if lucky else "refunded", "flags": []}

    def peek(world, *, trial, seed):
        return {"final_output": ",".join(sorted(world))}

    def crash(world, *, trial, seed):
        raise RuntimeError("tool server down")

    def text_only(world, *, trial, seed):
        return "already issued"
    """
)


@pytest.fixture
def dataset(make_dataset, config, world):
    config["agents"] = {"careful": "agents.py:careful"}
    root = make_dataset(config, [world])
    (root / "agents.py").write_text(ADAPTERS, encoding="utf-8")
    return load_dataset(root)


def run(dataset, name, trials=4):
    return run_agent(
        dataset, load_agent(f"agents.py:{name}", dataset.root), label=name, trials=trials
    )


def test_writes_one_trace_per_world_and_trial(dataset):
    result = run(dataset, "careful")
    files = sorted(p.name for p in result.out_dir.glob("*.json"))
    assert files == [f"refund-001.0{t}.json" for t in range(1, 5)]
    trace = json.loads((result.out_dir / "refund-001.03.json").read_text())
    assert (trace["world_id"], trace["agent"], trace["trial"]) == ("refund-001", "careful", 3)
    results, _ = score_dataset(dataset, load_traces(result.out_dir))
    assert {r.cell for r in results} == {"clean"}


def test_agent_sees_the_task_and_environment_only(dataset):
    trace = run(dataset, "peek", trials=1).traces[0]
    assert trace["final_output"] == "environment,id,task"


def test_seeds_are_stable_so_reruns_match(dataset):
    first = [t["final_output"] for t in run(dataset, "coin", trials=8).traces]
    second = [t["final_output"] for t in run(dataset, "coin", trials=8).traces]
    assert first == second
    assert len(set(first)) == 2
    assert stable_seed("refund-001", 1) == stable_seed("refund-001", 1)
    assert stable_seed("refund-001", 1) != stable_seed("refund-001", 2)


@pytest.mark.parametrize(
    ("adapter", "error"),
    [
        ("crash", "RuntimeError: tool server down"),
        ("text_only", "TypeError: returned str, expected a dict of trace fields"),
    ],
)
def test_a_failing_adapter_is_a_failed_trial(dataset, adapter, error):
    result = run(dataset, adapter, trials=2)
    assert result.errors == 2
    assert result.traces[0]["error"] == error
    results, _ = score_dataset(dataset, load_traces(result.out_dir))
    assert {r.cell for r in results} == {"full_fail"}


def test_rerun_replaces_stale_traces(dataset):
    run(dataset, "careful", trials=4)
    result = run(dataset, "careful", trials=2)
    assert len(list(result.out_dir.glob("*.json"))) == 2


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ("agents.py", "expected 'file.py:function'"),
        ("missing.py:careful", "not found"),
        ("agents.py:nope", "no function 'nope'"),
        ("no_such_module_xyz:run", "cannot import"),
    ],
)
def test_load_agent_errors(dataset, spec, message):
    with pytest.raises(DatasetError, match=message):
        load_agent(spec, dataset.root)


def test_load_agent_from_an_importable_module():
    assert callable(load_agent("json:dumps"))


def test_run_then_score_from_the_command_line(dataset, capsys):
    assert main(["run", str(dataset.root)]) == 0
    assert "careful: 4 trials over 1 world -> traces/careful" in capsys.readouterr().out
    assert main(["score", str(dataset.root)]) == 0


def test_run_an_unlisted_adapter_with_a_label(dataset):
    args = ["run", str(dataset.root), "--agent", "agents.py:coin", "--label", "coin-v2"]
    assert main([*args, "--trials", "3"]) == 0
    assert len(list((dataset.root / "traces" / "coin-v2").glob("*.json"))) == 3
