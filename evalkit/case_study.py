"""APEX gold → add variations → execute outcome-only then joint metrics."""

from pathlib import Path
import json

from evalkit.apex_task4 import DEMO_TRIALS, load_task, outcome_criteria, process_criteria
from evalkit.score import aggregate, trial_score


def score_trials(task, o_crit, p_crit, use_outcome, use_process):
    results = []
    for trial in DEMO_TRIALS:
        final = trial["final_output"] or task["gold_output"]
        scored = trial_score(
            final, trial["trace"], o_crit, p_crit, use_outcome, use_process
        )
        scored["name"] = trial["name"]
        scored["kind"] = trial.get("kind")
        scored["what_we_changed"] = trial.get("what_we_changed")
        results.append(scored)
    return results


def run_case_study(out_dir):
    task = load_task()
    o_crit = outcome_criteria(task)
    p_crit = process_criteria()

    print()
    print("=" * 64)
    print("CASE STUDY: APEX gold → variations → metrics")
    print("=" * 64)
    print()
    print("We did not invent a new accounting task. We took Mercor's published")
    print("World 9 Task 4 (prompt, gold, 2 outcome criteria) and added:")
    print("  1. Process gates APEX does not score")
    print("  2. Three labeled variations of how an agent might finish that task")
    print()

    print("PHASE A — APEX as published (outcome only)")
    print("  Gold + their two checklist lines. No trace. This is how they grade.")
    a_results = score_trials(task, o_crit, [], True, False)
    for t in a_results:
        print(f"  {t['name']:20}  outcome={'PASS' if t['O'] else 'fail':4}  {t['cell']}")
    a_sum = aggregate(a_results)
    print(
        f"  Outcome Pass@K={a_sum['outcome_pass_at_k']}  "
        f"Pass^K={a_sum['outcome_pass_hat_k']}  "
        f"mean={_pct(a_sum['mean_outcome'])}"
    )
    print("  (Three of four trials look successful. APEX would not split them.)")

    print()
    print("PHASE B — variations we added")
    for trial in DEMO_TRIALS:
        tag = "GOLD" if trial.get("kind") == "published_gold" else "VAR "
        print(f"  [{tag}] {trial['name']}")
        print(f"         {trial.get('what_we_changed')}")

    print()
    print("PHASE C — same trials, joint metrics (outcome + process)")
    c_results = score_trials(task, o_crit, p_crit, True, True)
    for t in c_results:
        print(
            f"  {t['name']:20}  O={'Y' if t['O'] else 'n'}  "
            f"P={'Y' if t['P'] else 'n'}  {t['cell']}"
        )
    c_sum = aggregate(c_results)
    print()
    print("  What changed after we added process")
    print(f"    Outcome Pass@K            {a_sum['outcome_pass_at_k']} → still {c_sum['outcome_pass_at_k']}")
    print(f"    Outcome Pass^K            {a_sum['outcome_pass_hat_k']} → {c_sum['outcome_pass_hat_k']}")
    print(f"    Clean Pass@K              n/a → {c_sum['clean_pass_at_k']}")
    print(f"    Clean Pass^K              n/a → {c_sum['clean_pass_hat_k']}")
    print(f"    DirtyPassRate             n/a → {_pct(c_sum['dirty_pass_rate'])} of outcome-correct runs")
    print(f"    DangerRate                n/a → {_pct(c_sum['danger_rate'])} of all runs")
    print()
    print("  Talk track: outcome-only said 3/4 'correct'. Joint says only 1/4 is")
    print("  a close you would sign. The other two correct endings were dirty.")

    payload = {
        "task": task.get("task_name"),
        "phase_a_outcome_only": {"trials": a_results, "summary": a_sum},
        "phase_c_joint": {"trials": c_results, "summary": c_sum},
        "variations": [
            {"name": t["name"], "kind": t.get("kind"), "what_we_changed": t.get("what_we_changed")}
            for t in DEMO_TRIALS
        ],
    }
    out = Path(out_dir)
    (out / "results").mkdir(parents=True, exist_ok=True)
    (out / "results" / "case_study.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out / "variations.md").write_text(_variations_md(task), encoding="utf-8")
    return payload


def _variations_md(task):
    lines = [
        f"# Variations on {task.get('task_name')}\n\n",
        "Starting point: published APEX gold (prompt + expert JE + 2 outcome criteria).\n\n",
        "We did not write a new gold answer. We added process invariants and three\n",
        "labeled ways an agent can finish the same task.\n\n",
    ]
    for t in DEMO_TRIALS:
        lines.append(f"## {t['name']}\n\n{t.get('what_we_changed')}\n\n")
    lines.append(
        "## Metrics we then execute\n\n"
        "Phase A: Mean Outcome, Outcome Pass@K, Outcome Pass^K.\n\n"
        "Phase C: the same, plus Process and Clean Pass@K / Pass^K, DirtyPassRate, DangerRate.\n"
    )
    return "".join(lines)


def _pct(x):
    if x is None:
        return "n/a"
    return f"{100 * x:.0f}%"
