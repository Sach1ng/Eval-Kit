"""The eval is not done when init returns.

A launch-quality golden set is weeks to months: talk to the people who see the
failures, rebuild the environment, write checks, and have someone else verify.
This module writes that remaining work into PROCESS.md and `evalkit status`.
"""

from __future__ import annotations

from pathlib import Path

from evalkit.dataset import Dataset
from evalkit.util import plural

STAGES = (
    ("Frame", "You + experts or customers", "`evalkit init` interview"),
    ("Collect real misses", "Tickets, chats, traces you already have", "`evalkit ingest`"),
    ("Plant and write checks", "You", "edit worlds/*.json"),
    ("Prove the world is solvable", "You", "reference run; `evalkit lint`"),
    ("Second pair of eyes", "Someone who did not plant the world", "provenance.reviewer"),
    ("Holdout", "You", 'mark about a fifth `"split": "holdout"`'),
    ("Run the agent", "Your adapter", "`evalkit run` / `evalkit score`"),
    ("Grow", "New production misses", "`evalkit ingest` again"),
)


def remaining(dataset: Dataset) -> list[str]:
    ready = dataset.ready_worlds()
    drafts = [w for w in dataset.worlds if w.get("status") == "draft"]
    todo = []
    if not ready:
        todo.append("No ready worlds yet. Finish at least one draft: checks + a reference run.")
    if drafts:
        todo.append(
            f"{plural(len(drafts), 'draft')} still need checks and a known-good reference "
            "before they are gold."
        )
    unreviewed = [
        w["id"]
        for w in ready
        if not str((w.get("provenance") or {}).get("reviewer") or "").strip()
        or str((w.get("provenance") or {}).get("reviewer")) == "fixture"
    ]
    if unreviewed:
        verb = "needs" if len(unreviewed) == 1 else "need"
        todo.append(
            f"{plural(len(unreviewed), 'ready world')} still {verb} a reviewer "
            "who did not plant them."
        )
    if len(ready) < 20:
        todo.append(
            f"{len(ready)} ready world(s). Anthropic's starting range is 20-50 from real "
            "failures, not a generated grid."
        )
    if ready and not any(w.get("split") == "holdout" for w in ready) and len(ready) >= 10:
        todo.append("No holdout split yet. Do not tune on every world.")
    if not dataset.agents:
        todo.append("No agent adapter in evalkit.json. Point agents at your system.")
    return todo


def render_process(dataset: Dataset) -> str:
    ready = len(dataset.ready_worlds())
    drafts = sum(1 for w in dataset.worlds if w.get("status") == "draft")
    lines = [
        f"# {dataset.name} is not done",
        "",
        "A launch-quality eval is weeks to months of interviews, environment setup, and",
        "verification. This folder is the start of that loop. The kit helps you create",
        "worlds from interviews and from transcripts or tickets that already happened.",
        "It does not finish the set for you.",
        "",
        f"Ready worlds (scored): {ready}",
        f"Drafts (not gold yet): {drafts}",
        "",
        "| Stage | Who | This kit |",
        "|-------|-----|----------|",
    ]
    for name, who, kit in STAGES:
        lines.append(f"| {name} | {who} | {kit} |")
    lines += ["", "## Still on you", ""]
    todo = remaining(dataset)
    if todo:
        lines.extend(f"- {item}" for item in todo)
    else:
        lines.append("- Lint is clean and a reviewer is recorded. Keep adding real misses.")
    lines += [
        "",
        "## Commands",
        "",
        "```bash",
        f"python3 -m evalkit ingest {dataset.root} --from ./inbox",
        f"python3 -m evalkit lint {dataset.root}",
        f"python3 -m evalkit status {dataset.root}",
        f"python3 -m evalkit run {dataset.root}",
        f"python3 -m evalkit score {dataset.root}",
        "```",
        "",
    ]
    return "\n".join(lines)


def write_process(dataset: Dataset) -> Path:
    path = dataset.root / "PROCESS.md"
    path.write_text(render_process(dataset), encoding="utf-8")
    return path
