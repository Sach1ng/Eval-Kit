from __future__ import annotations

import json

from evalkit.cli import main
from evalkit.dataset import load_dataset
from evalkit.lint import lint_dataset


def test_init_writes_a_runnable_dataset(tmp_path, capsys):
    dest = tmp_path / "my-eval"
    assert main(["init", str(dest), "--pack", "chatbot", "--yes"]) == 0
    out = capsys.readouterr().out
    assert "Wrote golden set" in out
    assert "already-refunded" in out
    dataset = load_dataset(dest)
    errors = [f for f in lint_dataset(dataset) if f.severity == "error"]
    assert errors == []
    assert {w["id"] for w in dataset.ready_worlds()} == {"already-refunded"}
    assert any(w.get("status") == "draft" for w in dataset.worlds)
    assert main(["run", str(dest)]) == 0
    assert main(["score", str(dest)]) == 0


def test_init_refuses_to_overwrite(tmp_path):
    dest = tmp_path / "my-eval"
    assert main(["init", str(dest), "--pack", "coding", "--yes"]) == 0
    assert main(["init", str(dest), "--pack", "coding", "--yes"]) == 2
    assert main(["init", str(dest), "--pack", "coding", "--yes", "--force"]) == 0


def test_demo_writes_a_golden_set_then_scores_it(tmp_path, capsys):
    dest = tmp_path / "demo"
    assert main(["demo", "--out", str(dest), "--pack", "chatbot"]) == 0
    out = capsys.readouterr().out
    assert "Wrote golden set" in out
    assert "already-refunded" in out
    assert "must_escalate-01" in out
    report = json.loads((dest / "results" / "report.json").read_text())
    assert report["agents"]["stub"]["clean_rate"] == 1.0
