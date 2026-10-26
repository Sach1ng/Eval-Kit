from __future__ import annotations

from itertools import combinations

import pytest

from evalkit.metrics import pass_at_k, pass_hat_k, percentile, summarize
from evalkit.scoring import TrialResult, cell_for


def brute_force(n: int, c: int, k: int) -> tuple[float, float]:
    """Average over every size-k subset of n trials, c of which succeeded."""
    trials = [True] * c + [False] * (n - c)
    subsets = list(combinations(trials, k))
    at_least_one = sum(any(s) for s in subsets) / len(subsets)
    every_one = sum(all(s) for s in subsets) / len(subsets)
    return at_least_one, every_one


@pytest.mark.parametrize("n", range(1, 9))
def test_estimators_match_enumerating_every_subset(n):
    for c in range(n + 1):
        for k in range(1, n + 1):
            at_least_one, every_one = brute_force(n, c, k)
            assert pass_at_k(n, c, k) == pytest.approx(at_least_one)
            assert pass_hat_k(n, c, k) == pytest.approx(every_one)


def test_known_values():
    assert pass_at_k(4, 3, 2) == 1.0
    assert pass_hat_k(4, 3, 2) == 0.5
    assert pass_hat_k(8, 7, 8) == 0.0
    assert pass_at_k(8, 1, 8) == 1.0
    assert pass_at_k(10, 0, 3) == 0.0
    assert pass_hat_k(10, 10, 3) == 1.0


@pytest.mark.parametrize(("n", "c", "k"), [(4, 5, 1), (4, 2, 0), (4, 2, 5), (3, -1, 1)])
def test_estimators_reject_impossible_inputs(n, c, k):
    with pytest.raises(ValueError):
        pass_at_k(n, c, k)
    with pytest.raises(ValueError):
        pass_hat_k(n, c, k)


def test_percentile_interpolates():
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert percentile([10.0], 0.95) == 10.0
    assert percentile([0.0, 100.0], 0.95) == pytest.approx(95.0)


def trial(world, n, outcome, path, pathway="p", **extra):
    return TrialResult(
        world_id=world,
        agent="a",
        trial=n,
        pathway=pathway,
        split="dev",
        clean_world=False,
        outcome=outcome,
        path=path,
        cell=cell_for(outcome, path),
        checks=[],
        **extra,
    )


def test_summary_separates_looking_right_from_being_right():
    results = [
        trial("w1", 1, True, True),
        trial("w1", 2, True, False),
        trial("w1", 3, True, True),
        trial("w1", 4, True, True),
        trial("w2", 1, True, True),
        trial("w2", 2, False, True),
        trial("w2", 3, False, False),
        trial("w2", 4, True, True),
    ]
    summary = summarize(results, k=2)
    assert summary["worlds"] == 2
    assert summary["cells"] == {"clean": 5, "dirty": 1, "outcome_fail": 1, "full_fail": 1}
    assert summary["outcome_rate"] == 6 / 8
    assert summary["clean_rate"] == 5 / 8
    assert summary["dirty_pass_rate"] == 1 / 6
    assert summary["outcome_pass_hat_k"] == pytest.approx((1.0 + 1 / 6) / 2)
    assert summary["clean_pass_hat_k"] == pytest.approx((3 / 6 + 1 / 6) / 2)
    assert summary["clean_pass_at_k"] == pytest.approx((1.0 + 5 / 6) / 2)


def test_k_defaults_to_the_fewest_trials_and_cannot_exceed_them():
    results = [trial("w1", 1, True, True), trial("w1", 2, True, True), trial("w2", 1, True, True)]
    assert summarize(results)["k"] == 1
    with pytest.raises(ValueError, match="'w2' has 1"):
        summarize(results, k=2)


def test_flag_precision_and_completeness_pool_over_trials():
    results = [
        trial("w1", 1, True, True, expected_flags=["a", "b"], flags=["a", "b"]),
        trial("w2", 1, False, True, expected_flags=["c"], flags=["x"]),
        trial("w3", 1, False, True, expected_flags=[], flags=["y"]),
    ]
    summary = summarize(results)
    assert summary["precision"] == pytest.approx(2 / 4)
    assert summary["completeness"] == pytest.approx(2 / 3)


def test_flag_metrics_are_absent_without_flag_worlds():
    summary = summarize([trial("w1", 1, True, True)])
    assert summary["precision"] is None
    assert summary["completeness"] is None


def test_latency_cost_and_pathways_are_summarized():
    results = [
        trial("w1", 1, True, True, pathway="refund", latency_ms=100.0, cost_usd=0.01),
        trial("w2", 1, False, True, pathway="escalate", latency_ms=300.0, cost_usd=0.03),
    ]
    summary = summarize(results)
    assert summary["latency_ms"] == {"p50": 200.0, "p95": 290.0}
    assert summary["cost_usd"]["total"] == pytest.approx(0.04)
    assert summary["by_pathway"]["refund"]["clean_rate"] == 1.0
    assert summary["by_pathway"]["escalate"]["clean_rate"] == 0.0
