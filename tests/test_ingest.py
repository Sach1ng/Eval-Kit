from __future__ import annotations

import json

from evalkit.cli import main, normalize_argv
from evalkit.dataset import load_dataset


def test_no_args_starts_the_interview():
    assert normalize_argv([]) == ["init"]
    assert normalize_argv(["lint", "x"]) == ["lint", "x"]
    assert normalize_argv(["my-eval", "--yes"]) == ["init", "my-eval", "--yes"]


def test_ingest_turns_a_ticket_into_a_draft(tmp_path):
    dest = tmp_path / "eval"
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "second_refund.txt").write_text(
        "Customer: I already got a refund yesterday. The bot issued another $42 today.",
        encoding="utf-8",
    )
    assert main(["init", str(dest), "--pack", "chatbot", "--yes"]) == 0
    assert main(["ingest", str(dest), "--from", str(inbox)]) == 0
    dataset = load_dataset(dest)
    drafts = [w for w in dataset.worlds if w.get("status") == "draft"]
    from_inbox = [w for w in drafts if w["id"].startswith("from_")]
    assert from_inbox
    world = from_inbox[0]
    assert world["pathway"] == "double_refund"
    assert world["checks"] == []
    assert "already got a refund" in world["task"]
    assert (dest / "PROCESS.md").is_file()
    assert "not done" in (dest / "PROCESS.md").read_text().lower()


def test_ingest_reads_json_messages(tmp_path):
    dest = tmp_path / "eval"
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "thread.json").write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "user", "content": "This is fraud. I will file a chargeback tonight."},
                    {"role": "agent", "content": "I refunded you."},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert main(["init", str(dest), "--pack", "chatbot", "--yes"]) == 0
    assert main(["ingest", str(dest), "--from", str(inbox)]) == 0
    world = next(w for w in load_dataset(dest).worlds if w["id"].startswith("from_"))
    assert world["pathway"] == "must_escalate"
    assert "chargeback" in world["task"].lower()


def test_status_lists_remaining_work(tmp_path, capsys):
    dest = tmp_path / "eval"
    assert main(["init", str(dest), "--pack", "chatbot", "--yes"]) == 0
    assert main(["status", str(dest)]) == 0
    out = capsys.readouterr().out
    assert "Drafts (not gold yet)" in out
    assert "reviewer" in out.lower()


def test_ingest_skips_prd_files(tmp_path):
    dest = tmp_path / "eval"
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "prd.md").write_text("Flag precision must stay at 90%.\n", encoding="utf-8")
    (inbox / "ticket.txt").write_text(
        "Customer: I already got a refund yesterday. The bot issued another $42 today.",
        encoding="utf-8",
    )
    assert main(["init", str(dest), "--pack", "chatbot", "--yes"]) == 0
    assert main(["ingest", str(dest), "--from", str(inbox)]) == 0
    ids = [w["id"] for w in load_dataset(dest).worlds]
    assert any(i.startswith("from_ticket") for i in ids)
    assert not any(i.startswith("from_prd") for i in ids)


def test_init_with_inbox_ingests_when_source_is_both(tmp_path):
    dest = tmp_path / "eval"
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "lost_order.txt").write_text(
        "Please refund this order. I never got a refund confirmation.",
        encoding="utf-8",
    )
    assert main(["init", str(dest), "--pack", "chatbot", "--yes", "--inbox", str(inbox)]) == 0
    ids = [w["id"] for w in load_dataset(dest).worlds]
    assert any(i.startswith("from_") for i in ids)
