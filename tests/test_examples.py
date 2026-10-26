"""Committed examples lint clean, and `evalkit demo` runs them end to end."""

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


def test_demo_support_refund(capsys):
    assert main(["demo", "--example", "support-refund"]) == 0
    out = capsys.readouterr().out
    assert "policy" in out
    assert "eager" in out
    assert "noisy" in out
    noisy = json.loads((example_dir("support-refund") / "results" / "report.json").read_text())[
        "agents"
    ]["noisy"]
    assert noisy["clean_pass_at_k"] == 1.0
    assert noisy["clean_pass_hat_k"] == 0.0


def test_demo_apex_cells(capsys):
    assert main(["demo", "--example", "apex-task4"]) == 0
    assert "gold_expert" in capsys.readouterr().out
    agents = json.loads((example_dir("apex-task4") / "results" / "report.json").read_text())[
        "agents"
    ]
    assert agents["gold_expert"]["cells"] == {
        "clean": 1,
        "dirty": 0,
        "outcome_fail": 0,
        "full_fail": 0,
    }
    assert agents["dirty_guess"]["cells"]["dirty"] == 1
    assert agents["wrong_amount"]["cells"]["outcome_fail"] == 1
    assert agents["dirty_extra_post"]["cells"]["dirty"] == 1
    assert sum(a["outcome_rate"] for a in agents.values()) == 3.0
