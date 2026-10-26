from __future__ import annotations

import json

import pytest

from evalkit import __version__
from evalkit.cli import main


def reference_runs(world, agent, trials):
    return [
        {"world_id": world["id"], "agent": agent, "trial": t, **world["reference"]}
        for t in range(1, trials + 1)
    ]


@pytest.fixture
def scored(make_dataset, config, world):
    config["gates"] = [{"metric": "clean_pass_hat_k", "min": 0.9}]
    return make_dataset(config, [world], reference_runs(world, "steady", 4))


def test_version(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out.strip() == f"evalkit {__version__}"


def test_score_writes_reports_and_passes_the_gate(scored, capsys):
    assert main(["score", str(scored)]) == 0
    report = json.loads((scored / "results" / "report.json").read_text())
    assert report["passed"] is True
    assert (scored / "results" / "report.md").read_text().startswith("# Eval report: refunds")
    assert "steady" in capsys.readouterr().out


def test_score_exits_1_when_a_gate_fails(scored, world, capsys):
    run = reference_runs(world, "steady", 1)[0]
    run["final_output"] = "Refunded again."
    (scored / "traces" / "000.json").write_text(json.dumps(run))
    assert main(["score", str(scored)]) == 1
    assert "A launch gate failed." in capsys.readouterr().err
    assert main(["score", str(scored), "--no-gate"]) == 0


def test_score_compares_with_a_baseline(scored, tmp_path):
    assert main(["score", str(scored), "--out", str(tmp_path / "before")]) == 0
    baseline = tmp_path / "before" / "report.json"
    assert main(["score", str(scored), "--baseline", str(baseline)]) == 0
    report = json.loads((scored / "results" / "report.json").read_text())
    assert report["comparison"]["steady"]["regressions"] == []


def test_invalid_dataset_exits_2_with_a_pointer_to_lint(scored, capsys):
    world_file = scored / "worlds" / "refund-001.json"
    world = json.loads(world_file.read_text())
    world["checks"][0]["type"] = "sounds_right"
    world_file.write_text(json.dumps(world))
    assert main(["score", str(scored)]) == 2
    assert "evalkit lint" in capsys.readouterr().err


def test_k_larger_than_the_trials_is_a_usage_error(scored, capsys):
    assert main(["score", str(scored), "--k", "9"]) == 2
    assert "k=9 needs 9 trials" in capsys.readouterr().err
