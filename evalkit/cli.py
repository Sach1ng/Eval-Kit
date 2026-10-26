"""Command line entry point: `evalkit <command>`.

Exit codes: 0 success, 1 a launch gate failed, 2 the dataset or arguments are invalid.
"""

from __future__ import annotations

import argparse
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
from evalkit.inbox import ingest, list_inbox
from evalkit.init import default_dest, interview, write_dataset
from evalkit.lint import format_findings, lint_dataset
from evalkit.packs import PACK_ORDER
from evalkit.process import render_process, write_process
from evalkit.prod import evaluate_prod, load_prod_traces, write_prod
from evalkit.propose import (
    METRICS_FILE,
    apply_confirmed_gates,
    corpus,
    load_plan,
    propose_for,
    render_plan,
    write_plan,
)
from evalkit.report import (
    build_report,
    compare_reports,
    render_summary,
    score_dataset,
    write_report,
)
from evalkit.runner import load_agent, run_agent
from evalkit.util import plural

COMMANDS = {
    "init",
    "ingest",
    "metrics",
    "lint",
    "status",
    "run",
    "score",
    "preprod",
    "ship",
    "prod",
    "demo",
}


def normalize_argv(argv: list[str]) -> list[str]:
    """`evalkit` with no command starts the interview (init)."""
    if not argv:
        return ["init"]
    if argv[0] in COMMANDS or argv[0] in {"-h", "--help", "--version"}:
        return argv
    return ["init", *argv]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(normalize_argv(argv))
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
        description=(
            "Build a golden set, confirm metrics, score pre-prod against gold, "
            "and watch unlabeled production traces."
        ),
    )
    parser.add_argument("--version", action="version", version=f"evalkit {__version__}")
    commands = parser.add_subparsers(title="commands", metavar="<command>")

    init = commands.add_parser(
        "init",
        help="write a golden dataset: worlds, pathways, and a stand-in agent",
        description="Write evalkit.json, one finished world, draft worlds for the other "
        "pathways, and a stand-in agent you replace with yours.",
    )
    init.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        help="folder to write (default: generated/<name>)",
    )
    init.add_argument("--pack", choices=PACK_ORDER, help="starter pack (asked if omitted)")
    init.add_argument("--yes", action="store_true", help="accept defaults, do not prompt")
    init.add_argument("--force", action="store_true", help="overwrite an existing evalkit.json")
    init.add_argument("--inbox", type=Path, help="folder of PRD/chat files (default: ./inbox)")
    init.set_defaults(handler=cmd_init)

    ingest_cmd = commands.add_parser(
        "ingest",
        help="turn transcripts, tickets, or traces into draft worlds",
        description="Each file becomes a draft world. Drafts are not gold until you add "
        "checks and a known-good reference run.",
    )
    ingest_cmd.add_argument("dataset", type=Path, help="dataset folder (contains evalkit.json)")
    ingest_cmd.add_argument(
        "--from",
        dest="source",
        type=Path,
        default=Path("inbox"),
        help="folder of transcripts or tickets (default: ./inbox)",
    )
    ingest_cmd.set_defaults(handler=cmd_ingest)

    metrics = commands.add_parser(
        "metrics",
        help="propose metrics from the job, harm, and PRD; confirm before ship",
        description="Print a metric plan. Company numbers (conversion, CSAT) stay "
        "experiments. Confirming writes launch gates. --yes leaves the plan a proposal.",
    )
    metrics.add_argument("dataset", type=Path, help="dataset folder (contains evalkit.json)")
    metrics.add_argument("--prd", type=Path, help="PRD or notes to read for stated numbers")
    metrics.add_argument("--inbox", type=Path, help="folder of PRD/chat files")
    metrics.add_argument(
        "--confirm",
        action="store_true",
        help="write the proposal as the pre-prod gates",
    )
    metrics.add_argument("--yes", action="store_true", help="do not prompt; leave unconfirmed")
    metrics.set_defaults(handler=cmd_metrics)

    lint = commands.add_parser(
        "lint",
        help="check a dataset against eval practice before trusting its scores",
        description="Check every world and the set as a whole. Exits 1 if there are errors.",
    )
    lint.add_argument("dataset", type=Path, help="dataset folder (contains evalkit.json)")
    lint.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    lint.set_defaults(handler=cmd_lint)

    status = commands.add_parser(
        "status",
        help="show how much of the eval is still on you",
        description="Ready vs draft worlds, and the remaining human work.",
    )
    status.add_argument("dataset", type=Path, help="dataset folder (contains evalkit.json)")
    status.set_defaults(handler=cmd_status)

    run = commands.add_parser(
        "run",
        help="run an agent adapter on every ready world, k trials each",
        description="Run each agent on every ready world and write traces/<agent>/*.json.",
    )
    run.add_argument("dataset", type=Path, help="dataset folder (contains evalkit.json)")
    run.add_argument(
        "--agent",
        action="append",
        metavar="NAME_OR_SPEC",
        help="a name from evalkit.json 'agents', or file.py:function or module:function "
        "(repeatable; default: every agent in evalkit.json)",
    )
    run.add_argument("--trials", type=int, help="trials per world (default: evalkit.json)")
    run.add_argument("--label", help="trace folder name for a single --agent spec")
    run.add_argument("--split", choices=SPLITS, help="run only this split")
    run.set_defaults(handler=cmd_run)

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

    preprod = commands.add_parser(
        "preprod",
        help="lint gold, run the adapter, score against the golden set",
        description="The pre-prod loop: lint, run, score. Ship bars apply only after "
        "you confirm metrics.",
    )
    preprod.add_argument("dataset", type=Path, help="dataset folder (contains evalkit.json)")
    preprod.add_argument(
        "--agent",
        action="append",
        metavar="NAME_OR_SPEC",
        help="agent to run (repeatable; default: every agent in evalkit.json)",
    )
    preprod.add_argument("--trials", type=int, help="trials per world (default: evalkit.json)")
    preprod.set_defaults(handler=cmd_preprod)

    ship = commands.add_parser(
        "ship",
        help="enforce confirmed launch gates; prefer the holdout split",
        description="Refuses to run until the metric plan is confirmed. Exits 1 if a "
        "gate fails. Scores holdout when that split exists.",
    )
    ship.add_argument("dataset", type=Path, help="dataset folder (contains evalkit.json)")
    ship.add_argument("--traces", type=Path, help="trace file or folder (default: DATASET/traces)")
    ship.add_argument("--k", type=int, help="k for pass@k and pass^k")
    ship.set_defaults(handler=cmd_ship)

    prod = commands.add_parser(
        "prod",
        help="watch live traces: gold regression plus unlabeled policy checks",
        description="Traces that name a ready world are scored against gold. The rest "
        "get crash / empty / PII checks. --ingest writes queued misses as draft worlds.",
    )
    prod.add_argument("dataset", type=Path, help="dataset folder (contains evalkit.json)")
    prod.add_argument(
        "--from",
        dest="source",
        type=Path,
        required=True,
        help="folder or file of production traces",
    )
    prod.add_argument(
        "--ingest",
        action="store_true",
        help="write unlabeled policy misses as draft worlds",
    )
    prod.set_defaults(handler=cmd_prod)

    demo = commands.add_parser(
        "demo",
        help="write a starter golden set, then lint, run, and score it (no API key)",
        description="Creates a dataset from a pack, lints it, runs the stand-in agent, "
        "and prints a scoreboard.",
    )
    demo.add_argument(
        "--pack",
        choices=PACK_ORDER,
        default="chatbot",
        help="which starter pack to write (default: chatbot)",
    )
    demo.add_argument(
        "--out",
        type=Path,
        default=Path("generated/demo"),
        help="folder to write (default: generated/demo)",
    )
    demo.set_defaults(handler=cmd_demo)
    return parser


def cmd_lint(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    findings = lint_dataset(dataset)
    print(format_findings(dataset, findings))
    failing = ("error", "warning") if args.strict else ("error",)
    return 1 if any(f.severity in failing for f in findings) else 0


def cmd_run(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    dataset.require_valid()
    requested = args.agent or list(dataset.agents)
    if not requested:
        raise DatasetError(
            "no agent to run: pass --agent file.py:function, or list agents in evalkit.json"
        )
    if args.label and len(requested) != 1:
        raise DatasetError("--label works with exactly one --agent")
    trials = args.trials if args.trials is not None else dataset.trials
    for item in requested:
        if item in dataset.agents:
            label, spec = item, dataset.agents[item]
        else:
            label, spec = args.label or item.rpartition(":")[2], item
        run = run_agent(
            dataset, load_agent(spec, dataset.root), label=label, trials=trials, split=args.split
        )
        worlds = plural(len(run.traces) // trials, "world")
        errored = f", {run.errors} errored" if run.errors else ""
        where = dataset.relative(run.out_dir)
        print(f"{label}: {plural(len(run.traces), 'trial')} over {worlds}{errored} -> {where}")
    print(f"Next: evalkit score {dataset.root}")
    return 0


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


def cmd_demo(args: argparse.Namespace) -> int:
    dest = write_dataset(args.out, args.pack, force=True)
    print_written(dest)
    print()
    lint_rc = cmd_lint(argparse.Namespace(dataset=dest, strict=False))
    if lint_rc != 0:
        return lint_rc
    print()
    run_rc = cmd_run(
        argparse.Namespace(dataset=dest, agent=None, trials=None, label=None, split=None)
    )
    if run_rc != 0:
        return run_rc
    print()
    return cmd_score(
        argparse.Namespace(
            dataset=dest,
            traces=None,
            split=None,
            k=None,
            out=None,
            baseline=None,
            no_gate=True,
        )
    )


def cmd_init(args: argparse.Namespace) -> int:
    answers = interview(yes=args.yes, pack_id=args.pack, inbox=args.inbox)
    dest = args.dataset or default_dest(answers)
    write_dataset(
        dest,
        answers["pack"],
        name=answers["name"],
        force=args.force,
        answers=answers,
    )
    inbox = args.inbox or Path("inbox")
    if answers.get("source") in {"transcripts", "both"} and list_inbox(inbox):
        drafts = ingest(dest, inbox)
        print(f"Ingested {plural(len(drafts), 'transcript')} as draft worlds.")
    print_written(dest)
    print(f"Next: python3 -m evalkit status {dest}")
    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    extra: list[Path] = []
    if args.prd:
        extra.append(args.prd)
    inbox = args.inbox if args.inbox is not None else Path("inbox")
    if inbox.is_dir():
        extra.append(inbox)
    plan = propose_for(dataset, prd_text=corpus(dataset, extra))
    existing = load_plan(dataset.root)
    if existing and existing.get("confirmed") and not args.confirm:
        print(render_plan(existing), end="")
        print(f"Already confirmed -> {dataset.root / METRICS_FILE}")
        return 0
    print(render_plan(plan), end="")
    confirmed = bool(args.confirm)
    if not confirmed and not args.yes:
        from evalkit.init import _ask

        choice = _ask(
            "Use this plan for pre-prod gates?",
            options=["later", "confirm"],
            default="later",
            queued=[],
            yes=False,
        )
        confirmed = choice == "confirm"
    plan["confirmed"] = confirmed
    write_plan(dataset.root, plan)
    if confirmed:
        apply_confirmed_gates(dataset.root, plan)
        print(f"Confirmed. Gates written to {dataset.root / 'evalkit.json'}.")
    else:
        print(f"Proposal only. Confirm with: evalkit metrics {dataset.root} --confirm")
    write_process(load_dataset(dataset.root))
    return 0


def cmd_preprod(args: argparse.Namespace) -> int:
    print("Pre-prod: lint the gold, run the adapter, score against the gold.")
    print()
    lint_rc = cmd_lint(argparse.Namespace(dataset=args.dataset, strict=False))
    if lint_rc != 0:
        return lint_rc
    print()
    run_rc = cmd_run(
        argparse.Namespace(
            dataset=args.dataset,
            agent=args.agent,
            trials=args.trials,
            label=None,
            split=None,
        )
    )
    if run_rc != 0:
        return run_rc
    print()
    plan = load_plan(args.dataset)
    no_gate = not (plan and plan.get("confirmed"))
    if no_gate:
        print("Metrics not confirmed; scoring without a ship bar.")
        print()
    return cmd_score(
        argparse.Namespace(
            dataset=args.dataset,
            traces=None,
            split=None,
            k=None,
            out=None,
            baseline=None,
            no_gate=no_gate,
        )
    )


def cmd_ship(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    plan = load_plan(dataset.root)
    if plan is None or not plan.get("confirmed"):
        raise DatasetError(
            f"Confirm the metric plan before ship: evalkit metrics {dataset.root} --confirm"
        )
    if not dataset.gates:
        raise DatasetError("No launch gates. Set a bar, then evalkit metrics DIR --confirm.")
    split = None
    if any(w.get("split") == "holdout" for w in dataset.ready_worlds()):
        split = "holdout"
        print("Scoring the holdout split.")
    else:
        print("No holdout yet; scoring every ready world. Do not treat this as a ship number.")
    print()
    return cmd_score(
        argparse.Namespace(
            dataset=args.dataset,
            traces=args.traces,
            split=split,
            k=args.k,
            out=None,
            baseline=None,
            no_gate=False,
        )
    )


def cmd_prod(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    traces = load_prod_traces(args.source)
    payload = evaluate_prod(dataset, traces, ingest_misses=args.ingest)
    paths = write_prod(dataset, payload)
    report = payload["report"]
    print(f"Production watch: {plural(report['traces'], 'trace')}")
    print(f"  scored against gold: {report['labeled']}")
    print(f"  unlabeled: {report['unlabeled']}")
    print(f"  queued: {report['queue']}")
    if report["drafts_written"]:
        print(f"  drafts: {', '.join(report['drafts_written'])}")
    shown = [p for p in paths if p.name in {"report.md", "report.json"}]
    print(f"Wrote {', '.join(str(p) for p in shown)}")
    gold = report.get("gold") or {}
    gold_failed = bool(gold) and not gold.get("passed", True)
    return 1 if report["queue"] or gold_failed else 0


def cmd_ingest(args: argparse.Namespace) -> int:
    drafts = ingest(args.dataset, args.source)
    print(
        f"Wrote {plural(len(drafts), 'draft world')} from {args.source}. "
        "Not gold until each has checks and a reference run."
    )
    for world in drafts:
        print(f"  {world['id']}  pathway={world['pathway']}")
    print(f"Next: python3 -m evalkit status {args.dataset}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    write_process(dataset)
    print(render_process(dataset))
    return 0


def print_written(dest: Path) -> None:
    dataset = load_dataset(dest)
    ready = dataset.ready_worlds()
    drafts = [w for w in dataset.worlds if w.get("status") == "draft"]
    print(f"Wrote starter set -> {dest.resolve()}  (not a finished eval)")
    print(f"  {plural(len(ready), 'ready world')}: {', '.join(w['id'] for w in ready)}")
    if drafts:
        print(f"  {plural(len(drafts), 'draft')}: {', '.join(w['id'] for w in drafts)}")
    print("  See PROCESS.md. Confirm metrics, then preprod / ship / prod.")


if __name__ == "__main__":
    raise SystemExit(main())
