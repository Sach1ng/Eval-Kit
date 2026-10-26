"""Load an Eval Kit dataset from disk and validate its shape.

A dataset is a directory:

    evalkit.json        what is evaluated, trials per world, launch gates
    worlds/**/*.json    one world per file
    traces/**/*.json    agent runs to score, written by `evalkit run` or by your harness

The formats are also published as JSON Schemas in `schemas/`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evalkit.checks import validate_check
from evalkit.util import is_int, is_number

CONFIG_FILE = "evalkit.json"
WORLD_DIR = "worlds"
TRACE_DIR = "traces"
RESULTS_DIR = "results"

SPLITS = ("dev", "holdout")
STATUSES = ("ready", "draft")
GATE_METRICS = (
    "clean_rate",
    "outcome_rate",
    "dirty_pass_rate",
    "clean_pass_at_k",
    "clean_pass_hat_k",
    "outcome_pass_at_k",
    "outcome_pass_hat_k",
    "precision",
    "completeness",
)
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class DatasetError(ValueError):
    """A dataset file is missing, unreadable, or has the wrong shape."""


@dataclass
class Dataset:
    root: Path
    config: dict[str, Any]
    worlds: list[dict[str, Any]] = field(default_factory=list)
    world_paths: list[Path] = field(default_factory=list)

    @property
    def name(self) -> str:
        return str(self.config.get("name") or self.root.resolve().name)

    @property
    def trials(self) -> int:
        return int(self.config.get("trials", 1))

    @property
    def acts(self) -> bool:
        return bool(self.config.get("acts", False))

    @property
    def gates(self) -> list[dict[str, Any]]:
        return list(self.config.get("gates", []))

    @property
    def agents(self) -> dict[str, str]:
        return dict(self.config.get("agents", {}))

    @property
    def pathway_ids(self) -> list[str]:
        return [
            p["id"]
            for p in self.config.get("pathways", [])
            if isinstance(p, dict) and isinstance(p.get("id"), str)
        ]

    def world_acts(self, world: dict[str, Any]) -> bool:
        return bool(world.get("acts", self.acts))

    def ready_worlds(self, split: str | None = None) -> list[dict[str, Any]]:
        return [
            w
            for w in self.worlds
            if w.get("status", "ready") == "ready"
            and (split is None or w.get("split", "dev") == split)
        ]

    def world_by_id(self) -> dict[str, dict[str, Any]]:
        return {w["id"]: w for w in self.worlds if isinstance(w.get("id"), str)}

    def problems(self) -> list[tuple[Path, str]]:
        """Every structural problem in the config and the worlds, as (file, message)."""
        found = [(self.root / CONFIG_FILE, p) for p in validate_config(self.config)]
        declared = set(self.pathway_ids) or None
        first_seen: dict[str, Path] = {}
        for path, world in zip(self.world_paths, self.worlds):
            found.extend((path, p) for p in validate_world(world, declared))
            world_id = world.get("id")
            if not isinstance(world_id, str):
                continue
            if world_id in first_seen:
                found.append(
                    (path, f"world id {world_id!r} is also used by {first_seen[world_id]}")
                )
            else:
                first_seen[world_id] = path
        return found

    def require_valid(self) -> None:
        problems = self.problems()
        if not problems:
            return
        shown = "\n".join(f"  {self.relative(p)}: {m}" for p, m in problems[:10])
        more = f"\n  ... and {len(problems) - 10} more" if len(problems) > 10 else ""
        raise DatasetError(
            f"{self.root} has {len(problems)} problem(s). "
            f"Run `evalkit lint {self.root}` for details.\n{shown}{more}"
        )

    def relative(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetError(f"{path}: invalid JSON ({exc.msg} at line {exc.lineno})") from exc
    except OSError as exc:
        raise DatasetError(f"{path}: {exc.strerror or exc}") from exc


def load_dataset(root: str | Path) -> Dataset:
    root = Path(root)
    config_path = root / CONFIG_FILE
    if not config_path.is_file():
        raise DatasetError(f"{root}: no {CONFIG_FILE} (create one with `evalkit init {root}`)")
    config = read_json(config_path)
    if not isinstance(config, dict):
        raise DatasetError(f"{config_path}: expected a JSON object")
    dataset = Dataset(root=root, config=config)
    for path in sorted((root / WORLD_DIR).rglob("*.json")):
        world = read_json(path)
        if not isinstance(world, dict):
            raise DatasetError(f"{path}: expected a JSON object")
        dataset.worlds.append(world)
        dataset.world_paths.append(path)
    return dataset


def load_traces(path: str | Path, *, need_world_id: bool = True) -> list[dict[str, Any]]:
    """Load traces from one file or a directory tree. A file holds one trace or a list.

    Production traces often have no world_id. Pass need_world_id=False for those.
    """
    path = Path(path)
    if path.is_dir():
        files = sorted(path.rglob("*.json"))
    elif path.is_file():
        files = [path]
    else:
        raise DatasetError(f"{path}: no traces found")
    traces = []
    for file in files:
        data = read_json(file)
        items = data if isinstance(data, list) else [data]
        for index, item in enumerate(items):
            problems = validate_trace(item, need_world_id)
            if problems:
                where = f"{file}[{index}]" if isinstance(data, list) else str(file)
                raise DatasetError(f"{where}: {'; '.join(problems)}")
            traces.append(normalize_trace(item))
    return traces


def normalize_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with defaults filled in and tool calls and flags in one shape."""
    calls = [
        {"name": c, "args": {}}
        if isinstance(c, str)
        else {"name": c["name"], "args": dict(c.get("args") or {})}
        for c in trace.get("tool_calls") or []
    ]
    flags = [f if isinstance(f, str) else f["id"] for f in trace.get("flags") or []]
    return {
        **trace,
        "agent": trace.get("agent") or "agent",
        "trial": trace.get("trial", 1),
        "final_output": trace.get("final_output") or "",
        "tool_calls": calls,
        "flags": flags,
        "final_state": trace.get("final_state"),
    }


def validate_config(config: dict[str, Any]) -> list[str]:
    problems = []
    if "name" in config and not isinstance(config["name"], str):
        problems.append("name must be a string")
    trials = config.get("trials", 1)
    if not is_int(trials) or trials < 1:
        problems.append("trials must be a whole number of at least 1")
    if not isinstance(config.get("acts", False), bool):
        problems.append("acts must be true or false")

    pathways = config.get("pathways", [])
    if not isinstance(pathways, list):
        problems.append("pathways must be a list")
    else:
        seen = set()
        for index, pathway in enumerate(pathways):
            pid = pathway.get("id") if isinstance(pathway, dict) else None
            if not isinstance(pid, str) or not ID_PATTERN.match(pid):
                problems.append(
                    f"pathways[{index}] needs an id of letters, digits, '.', '_' or '-'"
                )
            elif pid in seen:
                problems.append(f"pathway {pid!r} is declared twice")
            else:
                seen.add(pid)

    gates = config.get("gates", [])
    if not isinstance(gates, list):
        problems.append("gates must be a list")
    else:
        for index, gate in enumerate(gates):
            problems.extend(f"gates[{index}]: {p}" for p in validate_gate(gate))

    agents = config.get("agents", {})
    if not isinstance(agents, dict) or not all(
        isinstance(spec, str) and ":" in spec for spec in agents.values()
    ):
        problems.append("agents must map a name to 'file.py:function' or 'module:function'")

    dimensions = config.get("dimensions", {})
    if not isinstance(dimensions, dict) or not all(
        isinstance(values, list) and values and all(isinstance(v, str) for v in values)
        for values in dimensions.values()
    ):
        problems.append("dimensions must map a name to a non-empty list of strings")
    return problems


def validate_gate(gate: Any) -> list[str]:
    if not isinstance(gate, dict):
        return ['must be an object such as {"metric": "clean_pass_hat_k", "min": 0.8}']
    problems = []
    if gate.get("metric") not in GATE_METRICS:
        problems.append(f"metric must be one of: {', '.join(GATE_METRICS)}")
    bounds = [key for key in ("min", "max") if key in gate]
    if len(bounds) != 1:
        problems.append("set exactly one of min or max")
    elif not is_number(gate[bounds[0]]) or not 0 <= gate[bounds[0]] <= 1:
        problems.append(f"{bounds[0]} must be a number from 0 to 1")
    return problems


def validate_world(world: dict[str, Any], pathways: set[str] | None = None) -> list[str]:
    """Return every structural problem with one world."""
    problems = []
    world_id = world.get("id")
    if not isinstance(world_id, str) or not ID_PATTERN.match(world_id):
        problems.append("id must be letters, digits, '.', '_' or '-'")

    status = world.get("status", "ready")
    if status not in STATUSES:
        problems.append(f"status must be one of: {', '.join(STATUSES)}")
    if world.get("split", "dev") not in SPLITS:
        problems.append(f"split must be one of: {', '.join(SPLITS)}")
    for key in ("clean", "acts"):
        if key in world and not isinstance(world[key], bool):
            problems.append(f"{key} must be true or false")

    pathway = world.get("pathway")
    if pathway is not None and not isinstance(pathway, str):
        problems.append("pathway must be a string")
    elif pathways and pathway is None:
        problems.append("pathway is required because evalkit.json declares pathways")
    elif pathways and pathway not in pathways:
        problems.append(f"pathway {pathway!r} is not declared in evalkit.json")

    task = world.get("task", "")
    if not isinstance(task, str):
        problems.append("task must be a string")
    elif status == "ready" and not task.strip():
        problems.append("task is empty")
    for key in ("environment", "dimensions", "provenance"):
        if key in world and not isinstance(world[key], dict):
            problems.append(f"{key} must be an object")

    check_list = world.get("checks", [])
    if not isinstance(check_list, list):
        problems.append("checks must be a list")
    else:
        if status == "ready" and not check_list:
            problems.append("a ready world needs at least one check")
        seen = set()
        for index, check in enumerate(check_list):
            cid = check.get("id") if isinstance(check, dict) else None
            label = cid if isinstance(cid, str) and cid else f"checks[{index}]"
            problems.extend(f"check {label}: {p}" for p in validate_check(check))
            if isinstance(cid, str) and cid:
                if cid in seen:
                    problems.append(f"check id {cid!r} is used twice")
                seen.add(cid)

    if "reference" in world:
        problems.extend(f"reference: {p}" for p in validate_trace(world["reference"], False))
    return problems


def validate_trace(trace: Any, need_world_id: bool = True) -> list[str]:
    if not isinstance(trace, dict):
        return ["a trace must be a JSON object"]
    problems = []
    if need_world_id and not isinstance(trace.get("world_id"), str):
        problems.append("world_id is required")
    if "agent" in trace and not isinstance(trace["agent"], str):
        problems.append("agent must be a string")
    trial = trace.get("trial", 1)
    if not is_int(trial) or trial < 1:
        problems.append("trial must be a whole number of at least 1")
    if not isinstance(trace.get("final_output", ""), str):
        problems.append("final_output must be a string")

    calls = trace.get("tool_calls", [])
    if not isinstance(calls, list):
        problems.append("tool_calls must be a list")
    else:
        for index, call in enumerate(calls):
            if isinstance(call, str):
                continue
            if not isinstance(call, dict) or not isinstance(call.get("name"), str):
                problems.append(f"tool_calls[{index}] needs a name")
            elif not isinstance(call.get("args", {}), dict):
                problems.append(f"tool_calls[{index}].args must be an object")

    state = trace.get("final_state")
    if state is not None and not isinstance(state, dict):
        problems.append("final_state must be an object")
    flags = trace.get("flags", [])
    if not isinstance(flags, list) or not all(
        isinstance(f, str) or (isinstance(f, dict) and isinstance(f.get("id"), str)) for f in flags
    ):
        problems.append("flags must be a list of ids, or of objects with an id")
    for key in ("latency_ms", "cost_usd"):
        if key in trace and (not is_number(trace[key]) or trace[key] < 0):
            problems.append(f"{key} must be a number of at least 0")
    if trace.get("error") is not None and not isinstance(trace["error"], str):
        problems.append("error must be a string")
    return problems
