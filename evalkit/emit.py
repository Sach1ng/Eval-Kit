from pathlib import Path
import json


def emit_pack(out_dir, task, plan, outcome_criteria, process_criteria):
    out = Path(out_dir)
    (out / "rubrics").mkdir(parents=True, exist_ok=True)
    (out / "judges").mkdir(parents=True, exist_ok=True)
    (out / "dataset").mkdir(parents=True, exist_ok=True)

    (out / "README.md").write_text(_readme(plan, task), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    (out / "dataset" / "task.json").write_text(json.dumps({
        "task_id": task.get("task_id"),
        "task_name": task.get("task_name"),
        "prompt": task.get("prompt"),
        "gold_output": task.get("gold_output"),
        "note": "Gold is the 100% worked example. Judges do not see it.",
    }, indent=2), encoding="utf-8")

    (out / "rubrics" / "outcome.md").write_text(_rubric_md("Outcome", outcome_criteria), encoding="utf-8")
    (out / "rubrics" / "process.md").write_text(_rubric_md("Process", process_criteria), encoding="utf-8")

    for c in outcome_criteria:
        _write_judge(out / "judges" / f"outcome_{c['id'][:12]}.md", c, sees_trace=False)
    for c in process_criteria:
        _write_judge(out / "judges" / f"process_{c['id']}.md", c, sees_trace=True)

    (out / "metrics" / "definitions.md").parent.mkdir(parents=True, exist_ok=True)
    (out / "metrics" / "definitions.md").write_text(_metrics_md(plan), encoding="utf-8")
    return out


def _readme(plan, task):
    return (
        f"# Eval pack: {task.get('task_name', 'task')}\n\n"
        f"**Architecture:** {plan['label']}\n\n"
        + "\n".join(f"- {r}" for r in plan["rationale"])
        + "\n\nGold is not passed to the judge. Each judge file grades one criterion.\n"
    )


def _rubric_md(title, criteria):
    lines = [f"# {title} criteria\n"]
    if not criteria:
        lines.append("None for this architecture.\n")
        return "".join(lines)
    for c in criteria:
        lines.append(f"## {c['id']}\n\n{c['description']}\n\n_{c.get('source', '')}_\n\n")
    return "".join(lines)


def _write_judge(path, criterion, sees_trace):
    extras = (
        "You also receive the observable trace: files opened, writes, tool names.\n"
        "Do not grade hidden chain-of-thought. Grade the trace.\n"
        if sees_trace
        else "You receive the task prompt, this criterion, and the final answer only.\n"
        "Do not use gold. Do not use the trace.\n"
    )
    path.write_text(
        f"# Judge: {criterion['id']}\n\n"
        f"## Question\n{criterion['description']}\n\n"
        f"## What you see\n{extras}\n"
        "## Pass\nThe criterion is clearly met.\n\n"
        "## Fail\nThe criterion is not met.\n\n"
        "## Unknown\nThe provided evidence is not enough to decide.\n\n"
        "## Output\n"
        "```json\n"
        '{"verdict": "PASS | FAIL | UNKNOWN", "evidence": "", "reason": ""}\n'
        "```\n",
        encoding="utf-8",
    )


def _metrics_md(plan):
    lines = ["# Metrics\n\n"]
    for m in plan["metrics"]:
        lines.append(f"- {m}\n")
    lines.append(
        "\nClean pass = all outcome criteria AND all process gates on the same run.\n"
        "Dirty pass = outcome passes and at least one process gate fails.\n"
    )
    return "".join(lines)
