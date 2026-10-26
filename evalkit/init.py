"""`evalkit init DIR` writes a dataset you can lint, run, and score."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evalkit.dataset import CONFIG_FILE, DatasetError, load_dataset
from evalkit.inbox import list_inbox, read_clues
from evalkit.packs import PACK_ORDER, PACKS
from evalkit.process import write_process
from evalkit.propose import apply_confirmed_gates, propose, render_plan, write_plan
from evalkit.util import slugify, write_json

AGENT_STUB = '''\
"""Adapter for the first world this pack wrote. Replace with a call to your agent."""

from __future__ import annotations

from typing import Any


def run(world: dict[str, Any], *, trial: int, seed: int) -> dict[str, Any]:
    env = world["environment"]
    kind = env.get("kind")
    if kind == "already_refunded":
        order_id = env["order_id"]
        return {
            "final_output": (
                f"A ${env['prior_refund']} refund was already issued for {order_id}, "
                "so I will not refund again."
            ),
            "tool_calls": [
                {"name": "GetOrder", "args": {"order_id": order_id}},
                {"name": "ListRefunds", "args": {"order_id": order_id}},
            ],
            "final_state": {"refunds": list(env["refunds"]), "escalated": False},
        }
    if kind == "safety":
        return {
            "final_output": "I will escalate safety. A specialist will take this.",
            "tool_calls": [{"name": "EscalateSafety", "args": {"trip_id": env["trip_id"]}}],
            "final_state": {"escalated": True, "fees": list(env.get("fees", []))},
        }
    if kind == "missing_payroll":
        return {
            "final_output": "Flag: missing payroll for Q4. Flag: $240 Amazon uncategorized.",
            "tool_calls": [{"name": "GetPayrollStatus"}, {"name": "ListUncategorized"}],
            "flags": ["payroll_missing:Q4", "uncategorized:amz-240"],
            "final_state": {
                "payroll_q4": env.get("payroll_q4"),
                "uncategorized": list(env.get("uncategorized", [])),
            },
        }
    if kind == "real_fix":
        return {
            "final_output": "Updated the tax helper. Tests pass. Left .env alone.",
            "tool_calls": [{"name": "OpenFailingFile"}, {"name": "RunTests"}],
            "final_state": {"tests_passed": True, "test_present": True},
        }
    return {
        "final_output": "I do not have a fixture for this environment yet.",
        "tool_calls": [],
        "error": f"no stub for environment kind {kind!r}",
    }
'''

RUN_MD = """\
# This folder is a start

A launch-quality eval is weeks to months. Read PROCESS.md.

```bash
python3 -m evalkit ingest {dest} --from ./inbox
python3 -m evalkit metrics {dest}
python3 -m evalkit lint {dest}
python3 -m evalkit status {dest}
python3 -m evalkit preprod {dest}
python3 -m evalkit ship {dest}
python3 -m evalkit prod {dest} --from ./prod-traces
```

`agents.py:run` is a stand-in for the sample world. Point `evalkit.json`
`agents` at a function that calls your real agent. That function receives only
`world["task"]` and `world["environment"]`.
"""


def write_dataset(
    dest: Path,
    pack_id: str,
    *,
    name: str | None = None,
    force: bool = False,
    answers: dict[str, Any] | None = None,
) -> Path:
    pack = PACKS.get(pack_id)
    if pack is None:
        raise DatasetError(f"unknown pack {pack_id!r}. Choose one of: {', '.join(PACK_ORDER)}")
    dest = Path(dest).expanduser()
    if dest.exists() and (dest / CONFIG_FILE).is_file() and not force:
        raise DatasetError(f"{dest} already has {CONFIG_FILE}. Pass --force to overwrite.")
    dest.mkdir(parents=True, exist_ok=True)

    answers = dict(answers or {})
    ready = dict(pack["ready"])
    ready["provenance"] = {"source": f"pack:{pack_id}", "author": "init", "reviewer": "fixture"}
    label = name or answers.get("name") or slugify(pack["label"])
    pathways = answers.get("pathways") or pack["pathways"]
    acts = bool(answers.get("acts", pack["acts"]))
    reliability = answers.get("reliability") or "both"
    trials = int(answers.get("trials") or (8 if reliability != "at_least_once" else 4))
    gates = []
    gate = answers.get("gate")
    if isinstance(gate, (int, float)) and 0 <= float(gate) <= 1:
        metric = "clean_pass_hat_k" if reliability != "at_least_once" else "clean_pass_at_k"
        gates.append({"metric": metric, "min": float(gate)})

    config = {
        "name": label,
        "product": pack["label"],
        "job": answers.get("job") or pack["job"],
        "harm": answers.get("harm") or pack["harm"],
        "gold_unit": answers.get("gold_unit") or _gold_unit(pack_id),
        "acts": acts,
        "trials": trials,
        "reliability": reliability,
        "pathways": pathways,
        "gates": gates,
        "agents": {"stub": "agents.py:run"},
    }
    goal = str(answers.get("company_goal") or "").strip()
    if goal.lower() not in {"", "skip", "none"}:
        config["company_goal"] = goal
    write_json(dest / CONFIG_FILE, config)
    write_json(dest / "worlds" / f"{ready['id']}.json", ready)
    for pathway in pathways:
        if pathway["id"] == ready["pathway"]:
            continue
        write_json(
            dest / "worlds" / f"{pathway['id']}-01.json",
            {
                "id": f"{pathway['id']}-01",
                "status": "draft",
                "pathway": pathway["id"],
                "title": pathway["name"],
                "brief": f"Write a world that tests: {pathway['name']}.",
                "checks": [],
            },
        )
    (dest / "agents.py").write_text(AGENT_STUB, encoding="utf-8")
    (dest / "RUN.md").write_text(RUN_MD.format(dest=dest), encoding="utf-8")
    (dest / "product.md").write_text(_product_md(pack, answers, dest), encoding="utf-8")
    plan = answers.get("plan")
    if not isinstance(plan, dict):
        plan = propose(
            job=str(config["job"]),
            harm=str(config["harm"]),
            acts=acts,
            gold_unit=str(config["gold_unit"]),
            reliability=reliability,
            trials=trials,
            gate=float(gate) if isinstance(gate, (int, float)) else None,
            company_goal=goal,
        )
    else:
        plan = dict(plan)
    if answers.get("metrics_confirmed"):
        plan["confirmed"] = True
    write_plan(dest, plan)
    if plan.get("confirmed"):
        apply_confirmed_gates(dest, plan)
    write_process(load_dataset(dest))
    return dest


def interview(
    queued: list[str] | None = None,
    *,
    yes: bool = False,
    pack_id: str | None = None,
    inbox: Path | None = None,
) -> dict[str, Any]:
    queued = list(queued or [])
    print("A launch-quality eval is weeks to months: interviews, fake environments,")
    print("checks, and a second person verifying. This run starts a set. It does not")
    print("finish one. Worlds can come from an interview, or from transcripts and")
    print("tickets that already happened (drop files in ./inbox).")
    print()

    chosen = pack_id or _ask(
        "Which kind of agent?",
        options=PACK_ORDER,
        default="chatbot",
        queued=queued,
        yes=yes,
    )
    pack = PACKS[chosen]
    clues = read_clues(inbox)
    files = list_inbox(inbox)
    if files:
        print(f"Found {len(files)} file(s) in inbox:")
        for clue in clues:
            extra = f" -> {', '.join(clue['ids'])}" if clue["ids"] else ""
            print(f"  {clue['name']}{extra}")
        print("These can become draft worlds. Drafts are not gold until you add checks.")
        print()
    else:
        print("No files in ./inbox. You can still interview, then ingest transcripts later.")
        print()

    source = _ask(
        "Start from an interview, from transcripts/tickets, or both?",
        options=["interview", "transcripts", "both"],
        default="both" if files else "interview",
        queued=queued,
        yes=yes,
    )

    job = _ask(
        "When this agent worked, what did the user walk away with?",
        default=pack["job"],
        queued=queued,
        yes=yes,
    )
    harm = _ask(
        "If it is wrong, who is hurt and how?",
        default=pack["harm"],
        queued=queued,
        yes=yes,
    )
    writes = _ask(
        "Does the agent change something (pay, cancel, send, file, post)?",
        options=["yes", "no"],
        default="yes" if pack["acts"] else "no",
        queued=queued,
        yes=yes,
    )
    gold_unit = _ask(
        "What is gold: the last reply, the whole conversation, or the environment?",
        options=["reply", "conversation", "environment"],
        default=_gold_unit(chosen),
        queued=queued,
        yes=yes,
    )
    need = _ask(
        "Must it be right every time, or is once in several tries enough?",
        options=["every time", "once", "both"],
        default="every time" if writes == "yes" else "both",
        queued=queued,
        yes=yes,
    )
    reliability = {"every time": "every_time", "once": "at_least_once", "both": "both"}[need]

    suggested = {pid for clue in clues for pid in clue["ids"]}
    pathways = []
    print("Starter pathways. Keep the ones that match how this agent fails.")
    for pathway in pack["pathways"]:
        hint = " (suggested by inbox)" if pathway["id"] in suggested else ""
        keep = _ask(
            f"  {pathway['name']}{hint}",
            options=["keep", "drop"],
            default="keep",
            queued=queued,
            yes=yes,
        )
        if keep == "keep":
            pathways.append(pathway)
    if not pathways:
        pathways = list(pack["pathways"])
        print("  (kept the starter list; a set with no pathways cannot be scored)")

    gate_raw = _ask(
        "Launch bar for clean pass^k (0-1), or skip?",
        default="skip",
        queued=queued,
        yes=yes,
    )
    gate = None
    if gate_raw.lower() not in {"skip", "none", ""}:
        try:
            gate = float(gate_raw)
        except ValueError:
            gate = None
        if gate is not None and not 0 <= gate <= 1:
            print("  (ignoring launch bar; it must be between 0 and 1)")
            gate = None

    company_goal = _ask(
        "Company number in the PRD we should not mix into this eval (conversion, CSAT), or skip?",
        default="skip",
        queued=queued,
        yes=yes,
    )

    name = _ask("Dataset name?", default=slugify(pack["label"]), queued=queued, yes=yes)
    trials = 8 if reliability != "at_least_once" else 4
    prd_text = "\n".join(
        Path(c["path"]).read_text(encoding="utf-8", errors="replace")
        if Path(c["path"]).is_file()
        else ""
        for c in clues
    )
    plan = propose(
        job=job,
        harm=harm,
        acts=writes == "yes",
        gold_unit=gold_unit,
        reliability=reliability,
        trials=trials,
        gate=gate,
        prd_text=prd_text,
        company_goal=company_goal,
    )
    print()
    print(render_plan(plan), end="")
    confirm = _ask(
        "Use this plan for pre-prod gates?",
        options=["later", "confirm"],
        default="later",
        queued=queued,
        yes=yes,
    )
    answers = {
        "pack": chosen,
        "name": name,
        "job": job,
        "harm": harm,
        "acts": writes == "yes",
        "gold_unit": gold_unit,
        "reliability": reliability,
        "pathways": pathways,
        "gate": gate,
        "trials": trials,
        "clues": clues,
        "source": source,
        "company_goal": company_goal,
        "metrics_confirmed": confirm == "confirm",
        "plan": plan,
    }
    print()
    return answers


def default_dest(answers: dict[str, Any]) -> Path:
    return Path("generated") / slugify(str(answers.get("name") or "eval"))


def _gold_unit(pack_id: str) -> str:
    return "conversation" if pack_id == "chatbot" else "environment"


def _product_md(pack: dict[str, Any], answers: dict[str, Any], dest: Path) -> str:
    clues = answers.get("clues") or []
    lines = [
        f"# {answers.get('name') or pack['label']}",
        "",
        f"- Job: {answers.get('job') or pack['job']}",
        f"- Harm: {answers.get('harm') or pack['harm']}",
        f"- Gold unit: {answers.get('gold_unit') or 'environment'}",
        "",
        "Inbox files were clues, not gold.",
        "",
    ]
    if clues:
        for clue in clues:
            lines.append(
                f"- `{clue.get('name')}` -> {', '.join(clue.get('ids') or []) or 'no pathway hit'}"
            )
        lines.append("")
    lines += [
        "Next:",
        "",
        "```bash",
        f"python3 -m evalkit metrics {dest}",
        f"python3 -m evalkit preprod {dest}",
        f"python3 -m evalkit ship {dest}",
        "```",
        "",
    ]
    return "\n".join(lines)


def _ask(
    text: str,
    *,
    options: list[str] | None = None,
    default: str | None = None,
    queued: list[str],
    yes: bool,
) -> str:
    hint = f"  [{' | '.join(options)}]" if options else ""
    suffix = f"  [{default}]" if default else ""
    print(f"{text}{hint}{suffix}")
    if queued:
        raw = queued.pop(0).strip()
        print(f"  -> {raw}")
    elif yes:
        raw = default or (options[0] if options else "")
        print(f"  -> {raw}")
    else:
        raw = input("  -> ").strip()
    if not raw:
        raw = default or (options[0] if options else "")
        if default:
            print(f"  (using {raw})")
    if options:
        lookup = {o.lower(): o for o in options}
        if raw.lower() not in lookup:
            raw = default or options[0]
            print(f"  (using {raw})")
        else:
            raw = lookup[raw.lower()]
    print()
    return raw
