"""Run an agent adapter over a dataset: every ready world, k trials each.

An adapter is a plain Python function that runs your agent on one world:

    def my_agent(world: dict, *, trial: int, seed: int) -> dict:
        ...
        return {"final_output": "...", "tool_calls": [...], "final_state": {...}}

It receives only the world's id, task, and environment, never the checks or the
reference run. It returns trace fields; the runner adds world_id, agent, and
trial. Return latency_ms and cost_usd too if you have them. If the adapter
raises, the trial is recorded with the error and scored as a full failure.
"""

from __future__ import annotations

import copy
import importlib
import importlib.util
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from evalkit.dataset import ID_PATTERN, TRACE_DIR, Dataset, DatasetError, validate_trace
from evalkit.util import write_json

Agent = Callable[..., dict]


@dataclass
class Run:
    label: str
    out_dir: Path
    traces: list[dict[str, Any]]

    @property
    def errors(self) -> int:
        return sum(1 for t in self.traces if t.get("error"))


def load_agent(spec: str, base: Path | None = None) -> Agent:
    """Load `file.py:function` (relative to `base`) or `package.module:function`."""
    target, sep, name = spec.rpartition(":")
    if not sep or not target or not name:
        raise DatasetError(f"agent {spec!r}: expected 'file.py:function' or 'module:function'")
    if target.endswith(".py"):
        path = Path(target)
        if not path.is_absolute() and base is not None:
            path = base / path
        if not path.is_file():
            raise DatasetError(f"agent {spec!r}: {path} not found")
        module_name = f"evalkit_agent_{zlib.crc32(str(path.resolve()).encode()):08x}"
        module_spec = importlib.util.spec_from_file_location(module_name, path)
        if module_spec is None or module_spec.loader is None:
            raise DatasetError(f"agent {spec!r}: cannot load {path}")
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[module_name] = module
        module_spec.loader.exec_module(module)
    else:
        try:
            module = importlib.import_module(target)
        except ImportError as exc:
            raise DatasetError(f"agent {spec!r}: cannot import {target} ({exc})") from exc
    agent = getattr(module, name, None)
    if not callable(agent):
        raise DatasetError(f"agent {spec!r}: no function {name!r} in {target}")
    return agent


def stable_seed(world_id: str, trial: int) -> int:
    """The same world and trial get the same seed on every run and every machine."""
    return zlib.crc32(f"{world_id}:{trial}".encode())


def agent_view(world: dict[str, Any]) -> dict[str, Any]:
    """What the agent may see: the task and the environment."""
    return {
        "id": world["id"],
        "task": world.get("task", ""),
        "environment": copy.deepcopy(world.get("environment", {})),
    }


def run_agent(
    dataset: Dataset, agent: Agent, *, label: str, trials: int, split: str | None = None
) -> Run:
    """Run `agent` on every ready world `trials` times; write traces to traces/<label>/."""
    if not ID_PATTERN.match(label):
        raise DatasetError(f"agent label {label!r} must be letters, digits, '.', '_' or '-'")
    if trials < 1:
        raise DatasetError("trials must be at least 1")
    out_dir = dataset.root / TRACE_DIR / label
    if out_dir.is_dir():
        for stale in out_dir.glob("*.json"):
            stale.unlink()
    traces = []
    for world in dataset.ready_worlds(split):
        for trial in range(1, trials + 1):
            trace = _one_trial(agent, world, trial, label)
            write_json(out_dir / f"{world['id']}.{trial:02d}.json", trace)
            traces.append(trace)
    return Run(label, out_dir, traces)


def _one_trial(agent: Agent, world: dict[str, Any], trial: int, label: str) -> dict[str, Any]:
    error = None
    try:
        produced = agent(agent_view(world), trial=trial, seed=stable_seed(world["id"], trial))
        if not isinstance(produced, dict):
            raise TypeError(f"returned {type(produced).__name__}, expected a dict of trace fields")
        problems = validate_trace(produced, need_world_id=False)
        if problems:
            raise ValueError("; ".join(problems))
    except Exception as exc:
        produced, error = {}, f"{type(exc).__name__}: {exc}"
    trace = {
        "final_output": "",
        "tool_calls": [],
        **produced,
        "world_id": world["id"],
        "agent": label,
        "trial": trial,
    }
    if error:
        trace["error"] = error
    return trace
