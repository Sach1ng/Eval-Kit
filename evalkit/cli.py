"""Command line entry point: `evalkit <command>`.

Exit codes: 0 success, 1 a launch gate failed, 2 the dataset or arguments are invalid.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evalkit import __version__
from evalkit.dataset import (
    RESULTS_DIR,
    SPLITS,
    TRACE_DIR,
    DatasetError,
    load_dataset,
    load_traces,
    read_json,
)
from evalkit.report import (
    build_report,
    compare_reports,
    render_summary,
    score_dataset,
    write_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 0
    try:
        return args.handler(args)
    except DatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evalkit",
        description="Build, lint, and score golden datasets for AI agents.",
    )
    parser.add_argument("--version", action="version", version=f"evalkit {__version__}")
    commands = parser.add_subparsers(title="commands", metavar="<command>")

    score = commands.add_parser(
        "score",
        help="grade traces against worlds, check launch gates, write a report",
        description="Grade every trace against its world and write results/report.md and .json.",
    )
    score.add_argument("dataset", type=Path, help="dataset folder (contains evalkit.json)")
    score.add_argument("--traces", type=Path, help="trace file or folder (default: DATASET/traces)")
    score.add_argument("--split", choices=SPLITS, help="score only this split")
    score.add_argument("--k", type=int, help="k for pass@k and pass^k (default: fewest trials)")
    score.add_argument("--out", type=Path, help="report folder (default: DATASET/results)")
    score.add_argument("--baseline", type=Path, help="earlier report.json to compare against")
    score.add_argument("--no-gate", action="store_true", help="exit 0 even if a launch gate fails")
    score.set_defaults(handler=cmd_score)

    demo = commands.add_parser("demo", help="run the APEX Task 4 case study (v0.1 flow)")
    demo.add_argument("--out", default="generated/apex-task4-eval")
    demo.set_defaults(handler=lambda args: _v01_flow(args.out, scripted=True))

    init = commands.add_parser("init", help="answer five questions and write an eval pack (v0.1)")
    init.add_argument("--out", default="generated/apex-task4-eval")
    init.set_defaults(handler=lambda args: _v01_flow(args.out, scripted=False))
    return parser


def cmd_score(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    dataset.require_valid()
    traces = load_traces(args.traces or dataset.root / TRACE_DIR)
    results, skipped = score_dataset(dataset, traces, args.split)
    try:
        report = build_report(dataset, results, k=args.k, split=args.split, skipped=skipped)
    except ValueError as exc:
        raise DatasetError(str(exc)) from exc
    if args.baseline:
        report["comparison"] = compare_reports(read_json(args.baseline), report)
    paths = write_report(report, args.out or dataset.root / RESULTS_DIR)
    print(render_summary(report))
    print(f"\nWrote {', '.join(str(p) for p in paths)}")
    if report["passed"] or args.no_gate:
        return 0
    print("A launch gate failed.", file=sys.stderr)
    return 1


DEMO_ANSWERS = ["use apex demo", "yes", "yes", "both", "yes"]


def _v01_flow(out: str, scripted: bool) -> int:
    from evalkit.apex_task4 import DEMO_TRIALS, load_task, outcome_criteria, process_criteria
    from evalkit.case_study import run_case_study
    from evalkit.determine import determine
    from evalkit.emit import emit_pack
    from evalkit.interview import ask
    from evalkit.score import aggregate, trial_score

    answers = ask(DEMO_ANSWERS if scripted else None)
    plan = determine(answers)
    print(f"PROPOSED EVAL: {plan['label']} (K={plan['k']})")
    for line in plan["rationale"]:
        print(f"  - {line}")
    task = load_task()
    o_crit = outcome_criteria(task) if plan["use_outcome"] else []
    p_crit = process_criteria() if plan["use_process"] else []
    pack = emit_pack(out, task, plan, o_crit, p_crit)
    print(f"Wrote eval pack -> {Path(pack).resolve()}")

    if scripted or answers.get("has_gold") == "use apex demo":
        payload = run_case_study(pack)
        (Path(pack) / "results" / "demo.json").write_text(
            json.dumps({"plan": plan, **payload["phase_c_joint"]}, indent=2), encoding="utf-8"
        )
        return 0

    results = []
    for trial in DEMO_TRIALS:
        final = trial["final_output"] or task["gold_output"]
        scored = trial_score(
            final, trial["trace"], o_crit, p_crit, plan["use_outcome"], plan["use_process"]
        )
        scored["name"] = trial["name"]
        results.append(scored)
        print(f"  {trial['name']:20}  {scored['cell']}")
    (Path(pack) / "results").mkdir(exist_ok=True)
    (Path(pack) / "results" / "demo.json").write_text(
        json.dumps({"plan": plan, "trials": results, "summary": aggregate(results)}, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
