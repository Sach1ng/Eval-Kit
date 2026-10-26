from __future__ import annotations

import json

from evalkit.cli import main
from evalkit.dataset import load_dataset


def test_init_writes_an_unconfirmed_plan(tmp_path):
    dest = tmp_path / "eval"
    assert main(["init", str(dest), "--pack", "chatbot", "--yes"]) == 0
    plan = json.loads((dest / "metrics.json").read_text())
    assert plan["confirmed"] is False
    assert main(["status", str(dest)]) == 0


def test_metrics_confirm_writes_prd_gates(tmp_path):
    dest = tmp_path / "eval"
    assert main(["init", str(dest), "--pack", "backoffice", "--yes"]) == 0
    prd = tmp_path / "prd.md"
    prd.write_text("Flag precision 85%. Completeness 70%.\n", encoding="utf-8")
    assert main(["metrics", str(dest), "--prd", str(prd), "--confirm"]) == 0
    plan = json.loads((dest / "metrics.json").read_text())
    assert plan["confirmed"] is True
    config = json.loads((dest / "evalkit.json").read_text())
    metrics = {g["metric"]: g for g in config["gates"]}
    assert metrics["precision"]["min"] == 0.85
    assert metrics["completeness"]["min"] == 0.7


def test_ship_refuses_until_metrics_are_confirmed(tmp_path):
    dest = tmp_path / "eval"
    assert main(["init", str(dest), "--pack", "chatbot", "--yes"]) == 0
    assert main(["run", str(dest)]) == 0
    assert main(["ship", str(dest)]) == 2


def test_preprod_lints_runs_and_scores(tmp_path):
    dest = tmp_path / "eval"
    assert main(["init", str(dest), "--pack", "chatbot", "--yes"]) == 0
    assert main(["preprod", str(dest)]) == 0
    assert (dest / "results" / "report.json").is_file()


def test_ship_exits_1_when_a_confirmed_gate_fails(tmp_path, capsys):
    dest = tmp_path / "eval"
    assert main(["init", str(dest), "--pack", "chatbot", "--yes"]) == 0
    config = json.loads((dest / "evalkit.json").read_text())
    config["gates"] = [{"metric": "clean_pass_hat_k", "min": 0.99}]
    (dest / "evalkit.json").write_text(json.dumps(config), encoding="utf-8")
    plan = json.loads((dest / "metrics.json").read_text())
    plan["confirmed"] = True
    plan["offline"] = [{"metric": "clean_pass_hat_k", "min": 0.99, "source": "interview"}]
    (dest / "metrics.json").write_text(json.dumps(plan), encoding="utf-8")
    # Stub is clean; lower the trace after a run so the gate fails.
    assert main(["run", str(dest), "--trials", "1"]) == 0
    # Make the gate impossible by requiring 0.99 with a failing trace.
    world = json.loads((dest / "worlds" / "already-refunded.json").read_text())
    traces = dest / "traces"
    for path in traces.rglob("*.json"):
        data = json.loads(path.read_text())
        data["final_output"] = "Refunded again."
        data["tool_calls"] = [{"name": "CreateRefund", "args": {"order_id": "A-1001"}}]
        data["final_state"] = {
            "refunds": [
                *world["environment"]["refunds"],
                {"order_id": "A-1001", "amount": 42},
            ],
            "escalated": False,
        }
        path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["ship", str(dest)]) == 1
    assert "launch gate" in capsys.readouterr().err.lower()


def test_prod_queues_unlabeled_pii_and_ingests_a_draft(tmp_path):
    dest = tmp_path / "eval"
    assert main(["init", str(dest), "--pack", "chatbot", "--yes"]) == 0
    live = tmp_path / "live"
    live.mkdir()
    (live / "call.json").write_text(
        json.dumps(
            {
                "agent": "live",
                "trial": 1,
                "final_output": "I refunded alex@gmail.com another $42.",
                "tool_calls": [],
            }
        ),
        encoding="utf-8",
    )
    assert main(["prod", str(dest), "--from", str(live), "--ingest"]) == 1
    report = json.loads((dest / "prod" / "report.json").read_text())
    assert report["unlabeled"] == 1
    assert report["queue"] == 1
    assert report["labeled"] == 0
    dataset = load_dataset(dest)
    assert any(w["id"].startswith("prod_") for w in dataset.worlds)


def test_prod_scores_traces_that_still_name_a_world(tmp_path):
    dest = tmp_path / "eval"
    assert main(["init", str(dest), "--pack", "chatbot", "--yes"]) == 0
    assert main(["run", str(dest), "--trials", "1"]) == 0
    traces = next((dest / "traces").rglob("*.json"))
    live = tmp_path / "live"
    live.mkdir()
    (live / "labeled.json").write_text(traces.read_text(), encoding="utf-8")
    assert main(["prod", str(dest), "--from", str(live)]) == 0
    report = json.loads((dest / "prod" / "report.json").read_text())
    assert report["labeled"] == 1
    assert report["queue"] == 0
