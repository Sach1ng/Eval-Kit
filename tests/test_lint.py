from __future__ import annotations

import copy

import pytest

from evalkit.cli import main
from evalkit.dataset import load_dataset
from evalkit.lint import RULES, lint_dataset
from evalkit.util import write_json


def lint(make_dataset, config, worlds):
    return lint_dataset(load_dataset(make_dataset(config, worlds)))


def codes(findings, severity=None):
    return sorted({f.code for f in findings if severity in (None, f.severity)})


def variants(world, count, clean=0, holdout=0):
    """`count` distinct copies of the fixture world; the first `clean` are marked clean."""
    worlds = []
    for i in range(count):
        w = copy.deepcopy(world)
        w["id"] = f"refund-{i:03d}"
        w["task"] = f"{world['task']} (variant {i})"
        w["clean"] = i < clean
        w["split"] = "holdout" if i >= count - holdout else "dev"
        w["provenance"] = {"author": "a", "reviewer": "b"}
        worlds.append(w)
    return worlds


def test_every_rule_documents_why_it_exists():
    assert all(
        rule.why and rule.severity in ("error", "warning", "note") for rule in RULES.values()
    )


def test_a_sound_world_only_gets_notes(make_dataset, config, world):
    findings = lint(make_dataset, config, [world])
    assert codes(findings, "error") == []
    assert codes(findings, "warning") == []
    assert codes(findings, "note") == ["EK007", "EK010"]


def test_structure_errors_are_reported_per_file(make_dataset, config, world):
    world["checks"][0]["type"] = "sounds_right"
    findings = lint(make_dataset, config, [world])
    assert codes(findings, "error") == ["EK001"]
    assert findings[0].file == "worlds/refund-001.json"


def test_world_without_outcome_check(make_dataset, config, world):
    world["checks"] = [c for c in world["checks"] if c["type"] == "tool_called"]
    assert "EK002" in codes(lint(make_dataset, config, [world]), "error")


def test_acting_world_without_path_check(make_dataset, config, world):
    world["checks"] = [c for c in world["checks"] if c["type"] != "tool_called"]
    assert "EK003" in codes(lint(make_dataset, config, [world]), "error")
    config["acts"] = False
    assert "EK003" not in codes(lint(make_dataset, config, [world]))


def test_missing_reference(make_dataset, config, world):
    del world["reference"]
    findings = lint(make_dataset, config, [world])
    assert [f.message for f in findings if f.code == "EK004"] == ["no reference run"]


def test_reference_that_fails_its_own_checks(make_dataset, config, world):
    world["reference"]["tool_calls"] = []
    (finding,) = [f for f in lint(make_dataset, config, [world]) if f.code == "EK004"]
    assert finding.message.startswith("the reference run is dirty: checked_refund_history")


def test_duplicate_worlds_under_new_ids(make_dataset, config, world):
    copied = copy.deepcopy(world)
    copied["id"] = "refund-002"
    for check in copied["checks"]:
        check["id"] += "_copy"
    (finding,) = [f for f in lint(make_dataset, config, [world, copied]) if f.code == "EK005"]
    assert finding.message == "refund-001, refund-002 share a task, environment, and checks"


def test_sentence_long_text_checks(make_dataset, config, world):
    world["checks"][1]["values"] = ["Do not refund a second time and cite the prior refund"]
    findings = lint(make_dataset, config, [world])
    assert "EK006" in codes(findings, "warning")
    assert "EK004" in codes(findings, "error")


@pytest.mark.parametrize(("clean", "flagged"), [(0, True), (2, False), (6, True)])
def test_clean_share(make_dataset, config, world, clean, flagged):
    findings = lint(make_dataset, config, variants(world, 10, clean=clean, holdout=2))
    assert ("EK007" in codes(findings, "warning")) is flagged


def test_holdout(make_dataset, config, world):
    assert "EK008" in codes(lint(make_dataset, config, variants(world, 10, clean=2)), "warning")
    assert "EK008" not in codes(lint(make_dataset, config, variants(world, 10, 2, holdout=2)))


@pytest.mark.parametrize(
    ("value", "flagged"),
    [
        ("maya.chen@gmail.com", True),
        ("maya@example.com", False),
        ("card 4539 1488 0343 6467 on file", True),
        ("card 4242 4242 4242 4242 on file", False),
        ("ssn 123-45-6789", True),
        ("order total 129.99, placed 2025-11-03", False),
    ],
)
def test_personal_data_in_fixtures(make_dataset, config, world, value, flagged):
    world["environment"]["order"]["note"] = value
    assert ("EK009" in codes(lint(make_dataset, config, [world]), "error")) is flagged


def test_author_reviewing_their_own_world(make_dataset, config, world):
    world["provenance"] = {"author": "Sam", "reviewer": "sam"}
    assert "EK010" in codes(lint(make_dataset, config, [world]), "warning")


def test_drafts_and_uncovered_pathways(make_dataset, config, world):
    config["pathways"].append({"id": "must_escalate"})
    draft = {"id": "must_escalate-01", "status": "draft", "pathway": "must_escalate"}
    findings = lint(make_dataset, config, [world, draft])
    assert "EK011" in codes(findings, "note")
    (coverage,) = [f for f in findings if f.code == "EK012"]
    assert coverage.message == "pathway 'must_escalate' has no ready worlds (1 in draft)"


def test_lint_command_exit_codes(make_dataset, config, world, capsys):
    root = make_dataset(config, [world])
    assert main(["lint", str(root)]) == 0
    assert "0 errors, 0 warnings, 2 notes." in capsys.readouterr().out
    world["checks"][1]["values"] = ["refund was already issued for A-1001, so I"]
    write_json(root / "worlds" / "refund-001.json", world)
    assert main(["lint", str(root)]) == 0
    assert main(["lint", str(root), "--strict"]) == 1
    del world["reference"]
    write_json(root / "worlds" / "refund-001.json", world)
    assert main(["lint", str(root)]) == 1
