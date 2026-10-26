"""Committed examples lint clean and score to pinned numbers."""

from __future__ import annotations

import json

from evalkit.cli import main
from evalkit.dataset import load_dataset
from evalkit.lint import lint_dataset
from evalkit.util import example_dir, example_names


def test_both_examples_are_present():
    assert example_names() == ["apex-task4", "support-refund"]


def test_examples_lint_without_errors():
    for name in example_names():
        findings = lint_dataset(load_dataset(example_dir(name)))
        errors = [f for f in findings if f.severity == "error"]
        assert errors == [], errors


def test_score_support_refund():
    root = example_dir("support-refund")
    assert main(["score", str(root)]) == 0
    noisy = json.loads((root / "results" / "report.json").read_text())["agents"]["noisy"]
    assert noisy["clean_pass_at_k"] == 1.0
    assert noisy["clean_pass_hat_k"] == 0.0


def test_score_apex_cells():
    root = example_dir("apex-task4")
    assert main(["score", str(root)]) == 0
    agents = json.loads((root / "results" / "report.json").read_text())["agents"]
    assert agents["gold_expert"]["cells"]["clean"] == 1
    assert agents["dirty_guess"]["cells"]["dirty"] == 1
    assert agents["wrong_amount"]["cells"]["outcome_fail"] == 1
    assert agents["dirty_extra_post"]["cells"]["dirty"] == 1
    assert sum(a["outcome_rate"] for a in agents.values()) == 3.0
