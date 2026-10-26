"""The eval is not done when init returns.

A launch-quality golden set is weeks to months: talk to the people who see the
failures, rebuild the environment, write checks, confirm metrics, and have
someone else verify. This module writes that remaining work into PROCESS.md
and `evalkit status`.
"""

from __future__ import annotations

from pathlib import Path

from evalkit.dataset import Dataset
from evalkit.propose import load_plan
from evalkit.util import plural

STAGES = (
    ("Frame the job", "You + experts, customers, PRD", "`evalkit init`"),
    ("Collect real misses", "Transcripts, tickets, issues you already have", "`evalkit ingest`"),
    ("Plant and write checks", "You", "edit worlds/*.json"),
    ("Prove the world is solvable", "You", "reference run; `evalkit lint`"),
    ("Propose metrics", "Job, harm, PRD — then you confirm", "`evalkit metrics`"),
    ("Pre-prod against gold", "Your adapter + code checks", "`evalkit preprod`"),
    ("Ship bar", "Confirmed gates, prefer holdout", "`evalkit ship`"),
    ("Post-prod", "Unlabeled live traces", "`evalkit prod`"),
    ("Grow gold", "Confirmed live misses", "`evalkit ingest` / `prod --ingest`"),
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
    plan = load_plan(dataset.root)
    if plan is None or not plan.get("confirmed"):
        todo.append(
            "Metric plan is still a proposal. Confirm it with `evalkit metrics` before ship."
        )
    elif not dataset.gates:
        todo.append("Metrics confirmed but no launch bar. Set a gate, then `evalkit ship`.")
    if not dataset.agents:
        todo.append("No agent adapter in evalkit.json. Point agents at your system.")
    return todo


def render_process(dataset: Dataset) -> str:
    ready = len(dataset.ready_worlds())
    drafts = sum(1 for w in dataset.worlds if w.get("status") == "draft")
    plan = load_plan(dataset.root)
    if plan is None:
        metrics_state = "none yet"
    elif plan.get("confirmed"):
        metrics_state = "confirmed"
    else:
        metrics_state = "proposal"
    lines = [
        f"# {dataset.name} is not done",
        "",
        "Gold, then metrics you confirm, then pre-prod against that gold, then a ship",
        "check, then post-prod on unlabeled live traces. The kit helps create the worlds",
        "and the plan. It does not finish the months of interviews, environment work,",
        "or verification for you.",
        "",
        f"Ready worlds (scored): {ready}",
        f"Drafts (not gold yet): {drafts}",
        f"Metrics: {metrics_state}",
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
        lines.append("- Lint is clean, metrics are confirmed, a reviewer is recorded.")
        lines.append("  Keep adding real misses from prod.")
    lines += [
        "",
        "## Commands",
        "",
        "```bash",
        f"python3 -m evalkit ingest {dataset.root} --from ./inbox",
        f"python3 -m evalkit metrics {dataset.root}",
        f"python3 -m evalkit lint {dataset.root}",
        f"python3 -m evalkit status {dataset.root}",
        f"python3 -m evalkit preprod {dataset.root}",
        f"python3 -m evalkit ship {dataset.root}",
        f"python3 -m evalkit prod {dataset.root} --from ./prod-traces",
        "```",
        "",
    ]
    return "\n".join(lines)


def write_process(dataset: Dataset) -> Path:
    path = dataset.root / "PROCESS.md"
    path.write_text(render_process(dataset), encoding="utf-8")
    return path
