from __future__ import annotations

from evalkit.cli import main
from evalkit.dataset import load_dataset
from evalkit.lint import lint_dataset


def test_init_writes_a_runnable_dataset(tmp_path, capsys):
    dest = tmp_path / "my-eval"
    assert main(["init", str(dest), "--pack", "chatbot", "--yes"]) == 0
    assert "Wrote dataset" in capsys.readouterr().out
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


def test_unknown_example(capsys):
    assert main(["demo", "--example", "nope"]) == 2
    assert "Available: apex-task4, support-refund" in capsys.readouterr().err
