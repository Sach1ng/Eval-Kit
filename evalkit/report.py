"""Score a dataset's traces, check the launch gates, and render the report."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evalkit.dataset import Dataset, DatasetError
from evalkit.metrics import summarize
from evalkit.scoring import CELLS, TrialResult, score_trial
from evalkit.util import plural, write_json

FAILURES_SHOWN = 25
COMPARED = (
    "outcome_rate",
    "clean_rate",
    "clean_pass_at_k",
    "clean_pass_hat_k",
    "precision",
    "completeness",
)


def score_dataset(
    dataset: Dataset, traces: list[dict[str, Any]], split: str | None = None
) -> tuple[list[TrialResult], int]:
    """Grade every trace. Returns the results and how many traces were skipped.

    Traces for draft worlds, or for worlds outside `split`, are skipped. A trace
    for a world that does not exist, or a second trace for the same world, agent,
    and trial, is an error.
    """
    scored = {w["id"]: w for w in dataset.ready_worlds(split)}
    known = dataset.world_by_id()
    seen: set[tuple[str, str, int]] = set()
    results, skipped = [], 0
    for trace in traces:
        world_id, agent, trial = trace["world_id"], trace["agent"], trace["trial"]
        if world_id not in known:
            raise DatasetError(
                f"trace for unknown world {world_id!r} (agent {agent}, trial {trial})"
            )
        if world_id not in scored:
            skipped += 1
            continue
        key = (world_id, agent, trial)
        if key in seen:
            raise DatasetError(f"two traces for world {world_id!r}, agent {agent!r}, trial {trial}")
        seen.add(key)
        results.append(score_trial(scored[world_id], trace))
    return results, skipped


def evaluate_gates(summary: dict[str, Any], gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evaluated = []
    for gate in gates:
        value = summary.get(gate["metric"])
        bound = "min" if "min" in gate else "max"
        threshold = gate[bound]
        if value is None:
            passed = False
        else:
            passed = value >= threshold if bound == "min" else value <= threshold
        evaluated.append(
            {"metric": gate["metric"], bound: threshold, "value": value, "passed": passed}
        )
    return evaluated


def build_report(
    dataset: Dataset,
    results: list[TrialResult],
    *,
    k: int | None = None,
    split: str | None = None,
    skipped: int = 0,
) -> dict[str, Any]:
    if not results:
        raise DatasetError(f"{dataset.root}: no traces to score")
    ready = [w["id"] for w in dataset.ready_worlds(split)]
    by_agent: dict[str, list[TrialResult]] = defaultdict(list)
    for result in results:
        by_agent[result.agent].append(result)
    configured = [a for a in dataset.agents if a in by_agent]
    order = configured + sorted(a for a in by_agent if a not in configured)

    agents = {}
    for agent in order:
        trials = by_agent[agent]
        summary = summarize(trials, k)
        summary["gates"] = evaluate_gates(summary, dataset.gates)
        summary["missing_worlds"] = sorted(set(ready) - {r.world_id for r in trials})
        agents[agent] = summary

    return _rounded(
        {
            "dataset": dataset.name,
            "split": split or "all",
            "worlds": len(ready),
            "skipped_traces": skipped,
            "passed": all(g["passed"] for s in agents.values() for g in s["gates"]),
            "agents": agents,
            "worlds_by_agent": _world_rows(order, by_agent),
            "failures": _failures(results, order),
        }
    )


def _world_rows(order: list[str], by_agent: dict[str, list[TrialResult]]) -> list[dict[str, Any]]:
    rows = []
    for agent in order:
        by_world: dict[str, list[TrialResult]] = defaultdict(list)
        for result in by_agent[agent]:
            by_world[result.world_id].append(result)
        for world_id in sorted(by_world):
            trials = by_world[world_id]
            cells = Counter(t.cell for t in trials)
            rows.append(
                {
                    "agent": agent,
                    "world_id": world_id,
                    "pathway": trials[0].pathway,
                    "trials": len(trials),
                    "outcome": sum(t.outcome for t in trials),
                    "clean": cells["clean"],
                    "cells": {cell: cells.get(cell, 0) for cell in CELLS},
                }
            )
    return rows


def _failures(results: list[TrialResult], order: list[str]) -> list[dict[str, Any]]:
    rank = {agent: i for i, agent in enumerate(order)}
    failing = sorted(
        (r for r in results if not r.clean),
        key=lambda r: (rank[r.agent], r.world_id, r.trial),
    )
    return [
        {
            "agent": r.agent,
            "world_id": r.world_id,
            "trial": r.trial,
            "cell": r.cell,
            "error": r.error,
            "failed": [{"id": c.id, "layer": c.layer, "detail": c.detail} for c in r.failed],
        }
        for r in failing
    ]


def compare_reports(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Compare agents that appear in both reports, or the only agent in each."""
    pairs = [(a, a) for a in current["agents"] if a in baseline["agents"]]
    if not pairs and len(current["agents"]) == 1 and len(baseline["agents"]) == 1:
        pairs = [(next(iter(current["agents"])), next(iter(baseline["agents"])))]
    if not pairs:
        raise DatasetError("the baseline report has no agent in common with this run")

    before = {(r["agent"], r["world_id"]): r for r in baseline["worlds_by_agent"]}
    comparison = {}
    for agent, base_agent in pairs:
        metrics = {}
        for name in COMPARED:
            old, new = baseline["agents"][base_agent].get(name), current["agents"][agent].get(name)
            change = None if old is None or new is None else new - old
            metrics[name] = {"baseline": old, "current": new, "change": change}
        regressions, improvements = [], []
        for row in current["worlds_by_agent"]:
            old_row = before.get((base_agent, row["world_id"]))
            if row["agent"] != agent or old_row is None:
                continue
            old_rate, new_rate = old_row["clean"] / old_row["trials"], row["clean"] / row["trials"]
            entry = {"world_id": row["world_id"], "baseline": old_rate, "current": new_rate}
            if new_rate < old_rate:
                regressions.append(entry)
            elif new_rate > old_rate:
                improvements.append(entry)
        comparison[agent] = {
            "baseline_agent": base_agent,
            "metrics": metrics,
            "regressions": regressions,
            "improvements": improvements,
        }
    return _rounded(comparison)


def write_report(report: dict[str, Any], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out_dir / "report.json", out_dir / "report.md"
    write_json(json_path, report)
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return [md_path, json_path]


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {key: _rounded(v) for key, v in value.items()}
    if isinstance(value, list):
        return [_rounded(v) for v in value]
    return value


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def _common_k(report: dict[str, Any]) -> int | None:
    ks = {s["k"] for s in report["agents"].values()}
    return ks.pop() if len(ks) == 1 else None


def _gate_text(gate: dict[str, Any]) -> str:
    bound = "min" if "min" in gate else "max"
    sign = ">=" if bound == "min" else "<="
    return f"{gate['metric']} {pct(gate['value'])} (needs {sign} {pct(gate[bound])})"


def _gate_cell(summary: dict[str, Any]) -> str:
    gates = summary["gates"]
    if not gates:
        return "none set"
    failed = [g for g in gates if not g["passed"]]
    return "pass" if not failed else "FAIL: " + "; ".join(_gate_text(g) for g in failed)


def _escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict[str, Any]) -> str:
    agents = report["agents"]
    k = _common_k(report)
    show_k = any(s["k"] > 1 for s in agents.values())
    lines = [f"# Eval report: {report['dataset']}", ""]
    scope = "all splits" if report["split"] == "all" else f"the {report['split']} split"
    lines.append(f"{plural(report['worlds'], 'ready world')}, {scope}.")
    if show_k:
        lines.append(
            f"pass@k and pass^k use k = {k} trials per world."
            if k
            else "pass@k and pass^k use each agent's own k, shown in brackets."
        )
    if report["skipped_traces"]:
        lines.append(
            f"{report['skipped_traces']} trace(s) for draft or out-of-split worlds were skipped."
        )
    lines.append("")

    header = ["Agent", "Trials", "Outcome pass", "Clean", "Dirty share of passes"]
    if show_k:
        header += [f"Clean pass@{k or 'k'}", f"Clean pass^{k or 'k'}"]
    header.append("Gates")
    lines += [_row(header), _row(["---"] + ["--:"] * (len(header) - 2) + ["---"])]
    for name, s in agents.items():
        cells = [
            name,
            str(s["trials"]),
            pct(s["outcome_rate"]),
            pct(s["clean_rate"]),
            pct(s["dirty_pass_rate"]),
        ]
        if show_k:
            suffix = "" if k else f" [{s['k']}]"
            cells += [pct(s["clean_pass_at_k"]) + suffix, pct(s["clean_pass_hat_k"]) + suffix]
        cells.append(_escape(_gate_cell(s)))
        lines.append(_row(cells))

    if any(s["precision"] is not None for s in agents.values()):
        lines += [
            "",
            _row(["Agent", "Flag precision", "Flag completeness"]),
            _row(["---", "--:", "--:"]),
        ]
        lines += [_row([n, pct(s["precision"]), pct(s["completeness"])]) for n, s in agents.items()]

    if any(s["latency_ms"] or s["cost_usd"] for s in agents.values()):
        lines += ["", _row(["Agent", "p50 latency", "p95 latency", "Cost per trial", "Total cost"])]
        lines.append(_row(["---", "--:", "--:", "--:", "--:"]))
        for name, s in agents.items():
            latency, cost = s["latency_ms"] or {}, s["cost_usd"] or {}
            lines.append(
                _row(
                    [
                        name,
                        _ms(latency.get("p50")),
                        _ms(latency.get("p95")),
                        _usd(cost.get("per_trial")),
                        _usd(cost.get("total")),
                    ]
                )
            )

    lines += [
        "",
        "## Cells",
        "",
        _row(["Agent", "Clean", "Dirty", "Outcome fail", "Full fail", "Errors"]),
    ]
    lines.append(_row(["---"] + ["--:"] * 5))
    for name, s in agents.items():
        counts = [str(s["cells"][cell]) for cell in CELLS]
        lines.append(_row([name, *counts, str(s["errors"])]))

    pathways = sorted({p for s in agents.values() for p in s["by_pathway"]})
    if len(pathways) > 1:
        lines += ["", "## Clean rate by pathway", "", _row(["Pathway", *agents])]
        lines.append(_row(["---"] + ["--:"] * len(agents)))
        for pathway in pathways:
            rates = [
                pct(s["by_pathway"].get(pathway, {}).get("clean_rate")) for s in agents.values()
            ]
            lines.append(_row([pathway, *rates]))

    missing = {n: s["missing_worlds"] for n, s in agents.items() if s["missing_worlds"]}
    if missing:
        lines += ["", "## Coverage", ""]
        for name, worlds in missing.items():
            lines.append(f"- {name} has no traces for {len(worlds)} world(s): {', '.join(worlds)}")

    if "comparison" in report:
        lines += ["", *_comparison_lines(report["comparison"])]

    failures = report["failures"]
    lines += ["", "## Trials that were not clean", ""]
    if not failures:
        lines.append("None.")
    else:
        if len(failures) > FAILURES_SHOWN:
            lines += [
                f"Showing {FAILURES_SHOWN} of {len(failures)}. The JSON report lists all.",
                "",
            ]
        lines += [
            _row(["Agent", "World", "Trial", "Cell", "What failed"]),
            _row(["---", "---", "--:", "---", "---"]),
        ]
        for f in failures[:FAILURES_SHOWN]:
            reasons = [f"error: {f['error']}"] if f["error"] else []
            reasons += [f"`{c['id']}`: {c['detail']}" for c in f["failed"]]
            lines.append(
                _row(
                    [
                        f["agent"],
                        f["world_id"],
                        str(f["trial"]),
                        f["cell"],
                        _escape("<br>".join(reasons)),
                    ]
                )
            )
    return "\n".join(lines) + "\n"


def _comparison_lines(comparison: dict[str, Any]) -> list[str]:
    lines = ["## Compared with baseline", ""]
    for agent, c in comparison.items():
        label = (
            agent if c["baseline_agent"] == agent else f"{agent} (baseline: {c['baseline_agent']})"
        )
        lines += [
            f"**{label}**",
            "",
            _row(["Metric", "Baseline", "Now", "Change"]),
            _row(["---", "--:", "--:", "--:"]),
        ]
        for name, m in c["metrics"].items():
            if m["baseline"] is None and m["current"] is None:
                continue
            change = "n/a" if m["change"] is None else f"{100 * m['change']:+.1f} pts"
            lines.append(_row([name, pct(m["baseline"]), pct(m["current"]), change]))
        for title, rows in (("Regressions", c["regressions"]), ("Improvements", c["improvements"])):
            if rows:
                lines += ["", f"{title} (clean rate per world):", ""]
                lines += [
                    f"- {r['world_id']}: {pct(r['baseline'])} -> {pct(r['current'])}" for r in rows
                ]
        lines.append("")
    return lines


def render_summary(report: dict[str, Any]) -> str:
    """A compact plain-text table for the terminal."""
    agents = report["agents"]
    k = _common_k(report)
    show_k = any(s["k"] > 1 for s in agents.values())
    show_flags = any(s["precision"] is not None for s in agents.values())
    header = ["agent", "trials", "outcome", "clean", "dirty/passes"]
    if show_k:
        header += [f"pass@{k or 'k'}", f"pass^{k or 'k'}"]
    if show_flags:
        header += ["precision", "completeness"]
    header.append("gates")
    rows = [header]
    for name, s in agents.items():
        row = [
            name,
            str(s["trials"]),
            pct(s["outcome_rate"]),
            pct(s["clean_rate"]),
            pct(s["dirty_pass_rate"]),
        ]
        if show_k:
            row += [pct(s["clean_pass_at_k"]), pct(s["clean_pass_hat_k"])]
        if show_flags:
            row += [pct(s["precision"]), pct(s["completeness"])]
        row.append(_gate_cell(s))
        rows.append(row)
    widths = [max(len(r[i]) for r in rows) for i in range(len(header) - 1)]
    title = f"{report['dataset']}: {plural(report['worlds'], 'world')}"
    lines = [title + (f", k = {k}" if show_k and k else "")]
    for row in rows:
        cells = [row[0].ljust(widths[0])] + [c.rjust(w) for c, w in zip(row[1:-1], widths[1:])]
        lines.append("  " + "  ".join([*cells, row[-1]]))
    if show_k:
        lines.append("  (pass@k and pass^k count clean trials: right outcome, right path)")
    return "\n".join(lines)


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _ms(value: float | None) -> str:
    return "n/a" if value is None else f"{value:,.0f} ms"


def _usd(value: float | None) -> str:
    return "n/a" if value is None else f"${value:,.4f}"
