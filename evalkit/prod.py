"""Post-prod: live traces have no gold label.

Traces that still name a ready world_id are scored against gold (regression).
Everything else gets policy checks only: crashes, empty replies, and personal
data. Confirmed misses become draft worlds — they are not gold until checks
and a reference run exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evalkit.dataset import WORLD_DIR, Dataset, DatasetError, load_dataset, load_traces
from evalkit.inbox import draft_world
from evalkit.lint import personal_data_hits
from evalkit.process import write_process
from evalkit.report import build_report, score_dataset
from evalkit.util import write_json

PROD_DIR = "prod"


def policy_hits(trace: dict[str, Any], forbidden_tools: list[str]) -> list[str]:
    hits = []
    error = trace.get("error")
    if error:
        hits.append(f"error: {error}")
    output = trace.get("final_output") or ""
    calls = trace.get("tool_calls") or []
    if not str(output).strip() and not calls:
        hits.append("empty reply and no tools")
    for _location, kind in personal_data_hits({"final_output": output, "tool_calls": calls}):
        hits.append(f"possible {kind} in the reply")
    names = {
        c if isinstance(c, str) else c.get("name")
        for c in calls
        if isinstance(c, (str, dict))
    }
    for tool in forbidden_tools:
        if tool in names:
            hits.append(f"forbidden tool {tool}")
    return hits


def forbidden_tools_of(dataset: Dataset) -> list[str]:
    extra = dataset.config.get("prod") or {}
    listed = extra.get("forbidden_tools") if isinstance(extra, dict) else None
    if not isinstance(listed, list):
        return []
    return [t for t in listed if isinstance(t, str) and t]


def evaluate_prod(
    dataset: Dataset,
    traces: list[dict[str, Any]],
    *,
    ingest_misses: bool = False,
) -> dict[str, Any]:
    if not traces:
        raise DatasetError(f"{dataset.root}: no production traces")
    ready = {w["id"]: w for w in dataset.ready_worlds()}
    labeled, unlabeled = [], []
    for trace in traces:
        world_id = trace.get("world_id")
        if isinstance(world_id, str) and world_id in ready:
            labeled.append(trace)
        else:
            unlabeled.append(trace)

    gold: dict[str, Any] | None = None
    if labeled:
        results, skipped = score_dataset(dataset, labeled)
        gold = build_report(dataset, results, skipped=skipped)

    forbidden = forbidden_tools_of(dataset)
    queue = []
    for index, trace in enumerate(unlabeled, start=1):
        hits = policy_hits(trace, forbidden)
        if hits:
            queue.append({"id": f"miss-{index:04d}", "hits": hits, "trace": trace})

    drafts = []
    if ingest_misses and queue:
        drafts = _ingest_queue(dataset, queue)
        dataset = load_dataset(dataset.root)
        write_process(dataset)

    report = {
        "dataset": dataset.name,
        "traces": len(traces),
        "labeled": len(labeled),
        "unlabeled": len(unlabeled),
        "queue": len(queue),
        "drafts_written": [d["id"] for d in drafts],
        "gold": gold,
        "misses": [{"id": m["id"], "hits": m["hits"]} for m in queue],
    }
    return {"report": report, "queue": queue, "gold": gold}


def write_prod(dataset: Dataset, payload: dict[str, Any]) -> list[Path]:
    root = dataset.root / PROD_DIR
    report = payload["report"]
    write_json(root / "report.json", report)
    md = root / "report.md"
    md.write_text(_render(report), encoding="utf-8")
    written = [root / "report.json", md]
    qdir = root / "queue"
    if qdir.exists():
        for old in qdir.glob("*.json"):
            old.unlink()
    for item in payload["queue"]:
        path = qdir / f"{item['id']}.json"
        write_json(path, item)
        written.append(path)
    return written


def load_prod_traces(source: Path) -> list[dict[str, Any]]:
    return load_traces(source, need_world_id=False)


def _ingest_queue(dataset: Dataset, queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    used = {w["id"] for w in dataset.worlds if isinstance(w.get("id"), str)}
    declared = list(dataset.pathway_ids)
    written = []
    for item in queue:
        trace = item["trace"]
        text = (
            trace.get("final_output")
            or trace.get("error")
            or " ".join(item["hits"])
            or "unlabeled production miss"
        )
        stem = item["id"]
        world = draft_world(
            Path(stem),
            str(text),
            used_ids=used,
            pathway_ids=declared,
        )
        pid = f"prod_{item['id']}"
        n = 2
        while pid in used:
            pid = f"prod_{item['id']}-{n}"
            n += 1
        world["id"] = pid
        world["provenance"] = {"source": "prod", "author": "prod"}
        world["planted"] = (
            "From an unlabeled production trace. Confirm the failure before "
            "marking this world ready."
        )
        used.add(world["id"])
        write_json(dataset.root / WORLD_DIR / "from_prod" / f"{world['id']}.json", world)
        written.append(world)
    return written


def _render(report: dict[str, Any]) -> str:
    lines = [
        f"# Production watch: {report['dataset']}",
        "",
        "Live traces have no gold label unless they still name a ready world.",
        "Unlabeled traces get policy checks only (crash, empty reply, personal data).",
        "Confirmed misses should become draft worlds, not instant gold.",
        "",
        f"- Traces: {report['traces']}",
        f"- Scored against gold: {report['labeled']}",
        f"- Unlabeled: {report['unlabeled']}",
        f"- Policy misses queued: {report['queue']}",
        "",
    ]
    gold = report.get("gold")
    if gold:
        lines += ["## Gold regression", ""]
        for agent, row in (gold.get("agents") or {}).items():
            lines.append(
                f"- {agent}: clean {row.get('clean_rate')}  "
                f"dirty_pass {row.get('dirty_pass_rate')}"
            )
        lines.append("")
    misses = report.get("misses") or []
    if misses:
        lines += ["## Queue", ""]
        for miss in misses[:50]:
            lines.append(f"- {miss['id']}: {'; '.join(miss['hits'])}")
        lines.append("")
    drafts = report.get("drafts_written") or []
    if drafts:
        lines += ["## Drafts from misses", ""]
        lines.extend(f"- {i}" for i in drafts)
        lines.append("")
    return "\n".join(lines)
