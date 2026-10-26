from __future__ import annotations

from evalkit.propose import propose


def test_propose_does_not_invent_a_bar():
    plan = propose(job="resolve the ticket", harm="second refund", acts=True, reliability="both")
    assert plan["confirmed"] is False
    assert plan["offline"] == []
    assert any(v["id"] == "path" for v in plan["verifiers"])
    assert any(v["id"] == "outcome" for v in plan["verifiers"])


def test_propose_reads_precision_from_prd_not_conversion():
    prd = "Flag precision must stay at 90%. We also want conversion up."
    plan = propose(prd_text=prd, acts=True, reliability="every_time", gate=0.8)
    metrics = {g["metric"]: g for g in plan["offline"]}
    assert metrics["precision"]["min"] == 0.9
    assert metrics["clean_pass_hat_k"]["min"] == 0.8
    names = {e["name"] for e in plan["experiments"]}
    assert "conversion" in names
    assert all(g["metric"] != "conversion" for g in plan["offline"])
