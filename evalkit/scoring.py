"""Grade one trace against one world.

Outcome asks whether the run produced the right result. Path asks whether it got
there the right way. Together they put each trial in one of four cells:

    clean         right outcome, right path
    dirty         right outcome, wrong path    (looks like a pass; is not one)
    outcome_fail  wrong outcome, right path
    full_fail     wrong outcome, wrong path
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evalkit.checks import CheckResult, evaluate
from evalkit.dataset import DatasetError, normalize_trace

CELLS = ("clean", "dirty", "outcome_fail", "full_fail")


def cell_for(outcome: bool, path: bool) -> str:
    if outcome:
        return "clean" if path else "dirty"
    return "outcome_fail" if path else "full_fail"


@dataclass
class TrialResult:
    world_id: str
    agent: str
    trial: int
    pathway: str | None
    split: str
    clean_world: bool
    outcome: bool
    path: bool
    cell: str
    checks: list[CheckResult]
    expected_flags: list[str] | None = None
    flags: list[str] = field(default_factory=list)
    latency_ms: float | None = None
    cost_usd: float | None = None
    error: str | None = None

    @property
    def clean(self) -> bool:
        return self.cell == "clean"

    @property
    def failed(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "agent": self.agent,
            "trial": self.trial,
            "pathway": self.pathway,
            "split": self.split,
            "outcome": self.outcome,
            "path": self.path,
            "cell": self.cell,
            "checks": [c.to_dict() for c in self.checks],
            "error": self.error,
        }


def score_trial(world: dict[str, Any], trace: dict[str, Any]) -> TrialResult:
    """Run every check in `world` against `trace`. The world must be valid."""
    trace = normalize_trace(trace)
    results = [evaluate(check, trace) for check in world.get("checks", [])]
    outcome_results = [r for r in results if r.layer == "outcome"]
    if not outcome_results:
        raise DatasetError(
            f"world {world.get('id')!r} has no outcome checks, so no run can pass it. "
            "Run `evalkit lint` on the dataset."
        )
    error = trace.get("error")
    outcome = not error and all(r.passed for r in outcome_results)
    path = not error and all(r.passed for r in results if r.layer == "path")
    expected_flags = next(
        (list(c["values"]) for c in world["checks"] if c["type"] == "flags_equal"), None
    )
    return TrialResult(
        world_id=world["id"],
        agent=trace["agent"],
        trial=trace["trial"],
        pathway=world.get("pathway"),
        split=world.get("split", "dev"),
        clean_world=bool(world.get("clean", False)),
        outcome=outcome,
        path=path,
        cell=cell_for(outcome, path),
        checks=results,
        expected_flags=expected_flags,
        flags=list(trace["flags"]),
        latency_ms=trace.get("latency_ms"),
        cost_usd=trace.get("cost_usd"),
        error=error,
    )
