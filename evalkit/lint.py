"""Lint a golden dataset before trusting its scores.

Each rule has a code, a default severity, and the reason it exists. Errors make
`evalkit lint` exit 1. Warnings and notes are advice; `--strict` fails on
warnings too.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evalkit.checks import TEXT_CHECKS, layer_of
from evalkit.dataset import Dataset
from evalkit.scoring import score_trial

SET_RULES_MIN_WORLDS = 10
CLEAN_SHARE = (0.15, 0.5)
MAX_TEXT_WORDS = 6
SEVERITIES = ("error", "warning", "note")


@dataclass(frozen=True)
class Rule:
    code: str
    name: str
    severity: str
    why: str


RULES = {
    rule.code: rule
    for rule in (
        Rule("EK001", "structure", "error", "Files parse and match the published formats."),
        Rule(
            "EK002",
            "outcome-check",
            "error",
            "Every world checks the result, ideally the end state of the environment. "
            "Without one, no run can pass or fail.",
        ),
        Rule(
            "EK003",
            "path-check",
            "error",
            "If the agent can pay, post, or send, a right-looking result reached the wrong "
            "way is still a failure. Those worlds need a path check.",
        ),
        Rule(
            "EK004",
            "reference",
            "error",
            "Every world ships a known-good run, and that run passes every check. If it does "
            "not, the world or its checks are broken.",
        ),
        Rule(
            "EK005",
            "duplicate",
            "error",
            "Worlds with the same task, environment, and checks add rows without adding evidence.",
        ),
        Rule(
            "EK006",
            "brittle-text",
            "warning",
            f"Text checks look for short key facts (at most {MAX_TEXT_WORDS} words). A whole "
            "sentence fails correct answers that are worded differently.",
        ),
        Rule(
            "EK007",
            "balance",
            "warning",
            f"Between {CLEAN_SHARE[0]:.0%} and {CLEAN_SHARE[1]:.0%} of worlds are clean (nothing "
            "to fix), so an agent that always acts, or never acts, cannot score well.",
        ),
        Rule(
            "EK008",
            "holdout",
            "warning",
            "Some worlds are held out and never tuned against, so scores are not overfit to the "
            "worlds you watched.",
        ),
        Rule(
            "EK009",
            "pii",
            "error",
            "Fixtures contain no real personal data. Use reserved email domains (example.com) "
            "and published test card numbers.",
        ),
        Rule(
            "EK010",
            "review",
            "note",
            "A second person reviews each world (provenance.reviewer), and authors do not "
            "review their own.",
        ),
        Rule("EK011", "drafts", "note", "Draft worlds are not run or scored until finished."),
        Rule(
            "EK012", "coverage", "warning", "Every declared pathway has at least one ready world."
        ),
    )
}


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    file: str | None = None


def lint_dataset(dataset: Dataset) -> list[Finding]:
    findings = []
    broken: set[Path] = set()
    for path, message in dataset.problems():
        findings.append(Finding("EK001", "error", message, dataset.relative(path)))
        broken.add(path)

    entries = [(p, w) for p, w in zip(dataset.world_paths, dataset.worlds) if p not in broken]
    ready = [(p, w) for p, w in entries if w.get("status", "ready") == "ready"]
    drafts = [w for _, w in entries if w.get("status") == "draft"]

    unreviewed = []
    for path, world in ready:
        where = dataset.relative(path)
        findings += _world_findings(dataset, world, where)
        provenance = world.get("provenance") or {}
        author = str(provenance.get("author", "")).strip()
        reviewer = str(provenance.get("reviewer", "")).strip()
        if author and reviewer and author.casefold() == reviewer.casefold():
            findings.append(Finding("EK010", "warning", f"{author} wrote and reviewed this", where))
        elif not reviewer:
            unreviewed.append(world["id"])

    findings += _duplicates(ready)
    findings += _set_findings([w for _, w in ready])
    if unreviewed:
        findings.append(
            Finding("EK010", "note", f"{len(unreviewed)} ready world(s) have no reviewer recorded")
        )
    if drafts:
        findings.append(
            Finding("EK011", "note", f"{len(drafts)} draft world(s) are not run or scored yet")
        )
    covered = {w.get("pathway") for _, w in ready}
    for pathway in dataset.pathway_ids:
        if pathway not in covered:
            pending = sum(1 for w in drafts if w.get("pathway") == pathway)
            extra = f" ({pending} in draft)" if pending else ""
            message = f"pathway {pathway!r} has no ready worlds{extra}"
            findings.append(Finding("EK012", "warning", message, "evalkit.json"))
    rank = {severity: i for i, severity in enumerate(SEVERITIES)}
    return sorted(findings, key=lambda f: (rank[f.severity], f.file or "", f.code))


def _world_findings(dataset: Dataset, world: dict[str, Any], where: str) -> list[Finding]:
    findings = []
    layers = {layer_of(c) for c in world["checks"]}
    if "outcome" not in layers:
        findings.append(Finding("EK002", "error", "no outcome check", where))
    if dataset.world_acts(world) and "path" not in layers:
        message = "the agent can act here, but no check looks at how it got the result"
        findings.append(Finding("EK003", "error", message, where))

    reference = world.get("reference")
    if reference is None:
        findings.append(Finding("EK004", "error", "no reference run", where))
    elif "outcome" in layers:
        result = score_trial(world, {"world_id": world["id"], **reference})
        if not result.clean:
            reasons = "; ".join(f"{c.id}: {c.detail}" for c in result.failed) or result.error
            message = f"the reference run is {result.cell}: {reasons}"
            findings.append(Finding("EK004", "error", message, where))

    for check in world["checks"]:
        if check["type"] not in TEXT_CHECKS:
            continue
        for value in check["values"]:
            words = len(value.split())
            if words > MAX_TEXT_WORDS:
                message = f"check {check['id']}: {value!r} is {words} words; match a key fact"
                findings.append(Finding("EK006", "warning", message, where))

    fixture = {
        "task": world.get("task"),
        "environment": world.get("environment"),
        "reference": reference,
    }
    for location, kind in _personal_data(fixture):
        findings.append(Finding("EK009", "error", f"{location} looks like a real {kind}", where))
    return findings


def _duplicates(ready: list[tuple[Path, dict[str, Any]]]) -> list[Finding]:
    groups: dict[str, list[str]] = defaultdict(list)
    for _, world in ready:
        checks = [
            {k: v for k, v in check.items() if k not in ("id", "description")}
            for check in world["checks"]
        ]
        signature = {
            "task": " ".join(world.get("task", "").split()),
            "environment": world.get("environment", {}),
            "checks": checks,
        }
        groups[json.dumps(signature, sort_keys=True)].append(world["id"])
    return [
        Finding("EK005", "error", f"{', '.join(ids)} share a task, environment, and checks")
        for ids in groups.values()
        if len(ids) > 1
    ]


def _set_findings(ready: list[dict[str, Any]]) -> list[Finding]:
    if len(ready) < SET_RULES_MIN_WORLDS:
        message = (
            f"balance and holdout rules start at {SET_RULES_MIN_WORLDS} ready worlds; "
            f"this dataset has {len(ready)}"
        )
        return [Finding("EK007", "note", message)] if ready else []
    findings = []
    clean = sum(1 for w in ready if w.get("clean"))
    share = clean / len(ready)
    low, high = CLEAN_SHARE
    if share < low:
        consequence = f"below {low:.0%}, an agent that always acts scores well"
    elif share > high:
        consequence = f"above {high:.0%}, an agent that does nothing scores well"
    else:
        consequence = ""
    if consequence:
        message = f"{clean} of {len(ready)} ready worlds ({share:.0%}) are clean; {consequence}"
        findings.append(Finding("EK007", "warning", message))
    if not any(w.get("split") == "holdout" for w in ready):
        message = 'no holdout worlds; mark about a fifth "split": "holdout" and do not tune on them'
        findings.append(Finding("EK008", "warning", message))
    return findings


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
_SSN = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
_CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
_RESERVED_DOMAINS = ("example.com", "example.org", "example.net")
_RESERVED_SUFFIXES = (".example", ".test", ".invalid", ".localhost")
_TEST_CARDS = {
    "4242424242424242",
    "4111111111111111",
    "4000056655665556",
    "5555555555554444",
    "2223003122003222",
    "378282246310005",
    "6011111111111117",
    "3056930009020004",
    "3566002020360505",
}


def personal_data_hits(value: Any) -> list[tuple[str, str]]:
    """Locations in a fixture or trace that look like a real email, SSN, or card."""
    return list(_personal_data(value))


def _personal_data(value: Any) -> Iterator[tuple[str, str]]:
    for location, text in _strings(value, ""):
        for match in _EMAIL.finditer(text):
            domain = match.group(1).lower()
            reserved = domain in _RESERVED_DOMAINS or domain.endswith(
                tuple(f".{d}" for d in _RESERVED_DOMAINS) + _RESERVED_SUFFIXES
            )
            if not reserved:
                yield location, "email address"
        if _SSN.search(text):
            yield location, "social security number"
        for match in _CARD.finditer(text):
            digits = re.sub(r"\D", "", match.group())
            if digits not in _TEST_CARDS and _luhn(digits):
                yield location, "card number"


def _strings(value: Any, location: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield location, value
    elif isinstance(value, bool):
        return
    elif isinstance(value, int):
        yield location, str(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{location}.{key}" if location else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{location}.{index}")


def _luhn(digits: str) -> bool:
    total = 0
    for position, char in enumerate(reversed(digits)):
        digit = int(char)
        if position % 2 == 1:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return total % 10 == 0


def format_findings(dataset: Dataset, findings: list[Finding]) -> str:
    ready = len(dataset.ready_worlds())
    drafts = sum(1 for w in dataset.worlds if w.get("status") == "draft")
    lines = []
    for f in findings:
        where = f"{f.file}: " if f.file else ""
        lines.append(f"  {f.severity:<7} {f.code}  {where}{f.message}")
    counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITIES}
    tally = ", ".join(f"{n} {s}{'' if n == 1 else 's'}" for s, n in counts.items())
    lines.append(f"{dataset.root}: {ready} ready and {drafts} draft worlds. {tally}.")
    return "\n".join(lines)
