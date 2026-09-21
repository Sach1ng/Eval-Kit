"""Run: python -m evalkit [--demo] [--out DIR]"""

import argparse
import json
from pathlib import Path

from evalkit.apex_task4 import (
    DEMO_TRIALS,
    load_task,
    outcome_criteria,
    process_criteria,
)
from evalkit.determine import determine
from evalkit.emit import emit_pack
from evalkit.interview import ask
from evalkit.case_study import run_case_study
from evalkit.score import aggregate, trial_score


DEMO_ANSWERS = [
    "use apex demo",
    "yes",
    "yes",
    "both",
    "yes",
]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Interview → propose eval → emit judges → run a demo scoreboard."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Skip typing. Use the APEX Task 4 answers (outcome + process + reliability).",
    )
    parser.add_argument(
        "--out",
        default="generated/apex-task4-eval",
        help="Where to write the eval pack",
    )
    args = parser.parse_args(argv)

    print("=" * 64)
    print("EVALKIT")
    print("You bring gold. We turn it into a checklist and a score you can defend.")
    print("=" * 64)
    print()
    print("Gold = the expert's worked answer. It is not what we grade against.")
    print("Criteria = the yes/no boxes. The judge sees the prompt, one box,")
    print("and the model's final answer (plus the trace, if process matters).")
    print()

    answers = ask(DEMO_ANSWERS if args.demo else None)
    plan = determine(answers)

    print("-" * 64)
    print("PROPOSED EVAL")
    print(f"  {plan['label']}")
    print(f"  Reliability: {plan['reliability']} (K={plan['k']})")
    for r in plan["rationale"]:
        print(f"  • {r}")
    print("  Metrics:")
    for m in plan["metrics"]:
        print(f"    - {m}")
    print("-" * 64)

    task = load_task()
    o_crit = outcome_criteria(task) if plan["use_outcome"] else []
    p_crit = process_criteria() if plan["use_process"] else []

    print()
    print(f"Worked example: {task['task_name']} (APEX-Accounting public sample)")
    print("Outcome criteria (already published by Mercor):")
    for c in o_crit:
        print(f"  [O] {c['description'][:110]}")
    if p_crit:
        print("Process gates (we add these; APEX does not score them):")
        for c in p_crit:
            print(f"  [P] {c['description'][:110]}")

    out = emit_pack(args.out, task, plan, o_crit, p_crit)
    print()
    print(f"Wrote eval pack → {Path(out).resolve()}")

    if args.demo or answers.get("has_gold") == "use apex demo":
        payload = run_case_study(out)
        (Path(out) / "results" / "demo.json").write_text(
            json.dumps({"plan": plan, **payload["phase_c_joint"]}, indent=2),
            encoding="utf-8",
        )
        print()
        print("Read generated/apex-task4-eval/variations.md for the talk track.")
        return 0

    print()
    print("Running canned trials (no API key). Same scorer shape a live model run would use.")
    results = []
    for trial in DEMO_TRIALS:
        final = trial["final_output"] or task["gold_output"]
        scored = trial_score(
            final,
            trial["trace"],
            o_crit,
            p_crit,
            plan["use_outcome"],
            plan["use_process"],
        )
        scored["name"] = trial["name"]
        results.append(scored)
        print(
            f"  {trial['name']:20}  O={'Y' if scored['O'] else 'n'}  "
            f"P={'Y' if scored['P'] else 'n'}  {scored['cell']}"
        )

    summary = aggregate(results, plan["k"])
    (Path(out) / "results" ).mkdir(exist_ok=True)
    (Path(out) / "results" / "demo.json").write_text(
        json.dumps({"plan": plan, "trials": results, "summary": summary}, indent=2),
        encoding="utf-8",
    )

    print()
    print("SCOREBOARD")
    print(f"  Mean outcome criteria     { _pct(summary['mean_outcome']) }")
    print(f"  Mean process criteria     { _pct(summary['mean_process']) }")
    print(f"  Outcome Pass@K / Pass^K   {summary['outcome_pass_at_k']} / {summary['outcome_pass_hat_k']}")
    print(f"  Process Pass@K / Pass^K   {summary['process_pass_at_k']} / {summary['process_pass_hat_k']}")
    print(f"  Clean Pass@K / Pass^K     {summary['clean_pass_at_k']} / {summary['clean_pass_hat_k']}")
    print(f"  DirtyPassRate             { _pct(summary['dirty_pass_rate']) }  of outcome-correct runs")
    print(f"  DangerRate                { _pct(summary['danger_rate']) }  of all runs")
    print()
    print("Read the pack, then rerun with --demo anytime.")
    return 0


def _pct(x):
    if x is None:
        return "n/a"
    return f"{100 * x:.0f}%"


if __name__ == "__main__":
    raise SystemExit(main())
