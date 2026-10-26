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
from evalkit.init import interview, write_dataset
from evalkit.lint import format_findings, lint_dataset
from evalkit.packs import PACK_ORDER
from evalkit.report import (
    build_report,
    compare_reports,
    render_summary,
    score_dataset,
    write_report,
)
from evalkit.runner import load_agent, run_agent
from evalkit.util import plural


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

    init = commands.add_parser(
        "init",
        help="write a golden dataset: worlds, pathways, and a stand-in agent",
        description="Write evalkit.json, one finished world, draft worlds for the other "
        "pathways, and a stand-in agent you replace with yours.",
    )
    init.add_argument("dataset", type=Path, help="folder to write (created if missing)")
    init.add_argument("--pack", choices=PACK_ORDER, help="starter pack (asked if omitted)")
    init.add_argument("--yes", action="store_true", help="accept defaults, do not prompt")
    init.add_argument("--force", action="store_true", help="overwrite an existing evalkit.json")
    init.set_defaults(handler=cmd_init)

    lint = commands.add_parser(
        "lint",
        help="check a dataset against eval practice before trusting its scores",
        description="Check every world and the set as a whole. Exits 1 if there are errors.",
    )
    lint.add_argument("dataset", type=Path, help="dataset folder (contains evalkit.json)")
    lint.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    lint.set_defaults(handler=cmd_lint)

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
    answers = interview(yes=args.yes, pack_id=args.pack)
    dest = write_dataset(args.dataset, answers["pack"], name=answers["name"], force=args.force)
    print_written(dest)
    print(f"Next: python3 -m evalkit lint {dest}")
    return 0


def print_written(dest: Path) -> None:
    dataset = load_dataset(dest)
    ready = dataset.ready_worlds()
    drafts = [w for w in dataset.worlds if w.get("status") == "draft"]
    print(f"Wrote golden set -> {dest.resolve()}")
    print(f"  {plural(len(ready), 'ready world')}: {', '.join(w['id'] for w in ready)}")
    if drafts:
        print(f"  {plural(len(drafts), 'draft')}: {', '.join(w['id'] for w in drafts)}")
    print("  Fill the drafts. Point agents.py at your agent. Then lint / run / score.")


if __name__ == "__main__":
    raise SystemExit(main())
