"""Metrics over trial results.

The world is the unit of analysis; trials are repeated runs of the same world.
For one world with n trials and c successes, the unbiased estimators are:

    pass@k = 1 - C(n - c, k) / C(n, k)    at least one of k runs succeeds   (Chen et al., 2021)
    pass^k = C(c, k) / C(n, k)            every one of k runs succeeds      (Yao et al., 2024)

A dataset's value is the mean over worlds. pass@k measures whether the agent can
do the task; pass^k measures whether it does it every time.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from math import comb, floor
from typing import Any, Callable

from evalkit.scoring import CELLS, TrialResult


def pass_at_k(n: int, c: int, k: int) -> float:
    _require(n, c, k)
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    _require(n, c, k)
    return comb(c, k) / comb(n, k)


def _require(n: int, c: int, k: int) -> None:
    if not 0 <= c <= n:
        raise ValueError(f"need 0 <= c <= n, got c={c}, n={n}")
    if not 1 <= k <= n:
        raise ValueError(f"need 1 <= k <= n, got k={k}, n={n}")


def percentile(values: list[float], q: float) -> float:
    """Linear interpolation between closest ranks (numpy's default method)."""
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = floor(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize(results: list[TrialResult], k: int | None = None) -> dict[str, Any]:
    """Summarize one agent's trials. `k` defaults to the fewest trials any world has."""
    if not results:
        raise ValueError("no trials to summarize")
    by_world: dict[str, list[TrialResult]] = defaultdict(list)
    for result in results:
        by_world[result.world_id].append(result)
    fewest = min(len(trials) for trials in by_world.values())
    k = fewest if k is None else k
    if not 1 <= k <= fewest:
        thin = min(by_world, key=lambda w: len(by_world[w]))
        raise ValueError(f"k={k} needs {k} trials of every world; {thin!r} has {fewest}")

    def mean_over_worlds(estimator: Callable[[int, int, int], float], success: str) -> float:
        values = [
            estimator(len(trials), sum(getattr(t, success) for t in trials), k)
            for trials in by_world.values()
        ]
        return sum(values) / len(values)

    cells = Counter(r.cell for r in results)
    total = len(results)
    summary: dict[str, Any] = {
        "worlds": len(by_world),
        "trials": total,
        "trials_per_world": {"min": fewest, "max": max(len(t) for t in by_world.values())},
        "k": k,
        "cells": {cell: cells.get(cell, 0) for cell in CELLS},
        "errors": sum(1 for r in results if r.error),
        "outcome_rate": sum(r.outcome for r in results) / total,
        "clean_rate": cells["clean"] / total,
        "dirty_pass_rate": rate(cells["dirty"], cells["clean"] + cells["dirty"]),
        "outcome_pass_at_k": mean_over_worlds(pass_at_k, "outcome"),
        "outcome_pass_hat_k": mean_over_worlds(pass_hat_k, "outcome"),
        "clean_pass_at_k": mean_over_worlds(pass_at_k, "clean"),
        "clean_pass_hat_k": mean_over_worlds(pass_hat_k, "clean"),
    }
    summary.update(_flag_metrics(results))
    summary["latency_ms"] = _spread([r.latency_ms for r in results if r.latency_ms is not None])
    costs = [r.cost_usd for r in results if r.cost_usd is not None]
    summary["cost_usd"] = (
        {"total": sum(costs), "per_trial": sum(costs) / len(costs)} if costs else None
    )
    summary["by_pathway"] = _by_pathway(results)
    return summary


def _flag_metrics(results: list[TrialResult]) -> dict[str, float | None]:
    """Precision and completeness of raised flags, pooled over trials of flag worlds."""
    found = false_alarms = missed = 0
    graded = False
    for result in results:
        if result.expected_flags is None:
            continue
        graded = True
        expected, raised = set(result.expected_flags), set(result.flags)
        found += len(expected & raised)
        false_alarms += len(raised - expected)
        missed += len(expected - raised)
    if not graded:
        return {"precision": None, "completeness": None}
    return {
        "precision": rate(found, found + false_alarms),
        "completeness": rate(found, found + missed),
    }


def _spread(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {"p50": percentile(values, 0.5), "p95": percentile(values, 0.95)}


def _by_pathway(results: list[TrialResult]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[TrialResult]] = defaultdict(list)
    for result in results:
        groups[result.pathway or "(none)"].append(result)
    return {
        pathway: {
            "worlds": len({r.world_id for r in trials}),
            "trials": len(trials),
            "outcome_rate": sum(r.outcome for r in trials) / len(trials),
            "clean_rate": sum(r.clean for r in trials) / len(trials),
        }
        for pathway, trials in sorted(groups.items())
    }
