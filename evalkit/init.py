"""`evalkit init DIR` writes a dataset you can lint, run, and score."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evalkit.dataset import CONFIG_FILE, DatasetError
from evalkit.packs import PACK_ORDER, PACKS
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
# Next

```bash
python3 -m evalkit lint {dest}
python3 -m evalkit run {dest}
python3 -m evalkit score {dest}
```

`agents.py:run` is a stand-in that passes the first world. Point `evalkit.json`
`agents` at a function that calls your real agent. That function receives only
`world["task"]` and `world["environment"]`.
"""


def write_dataset(
    dest: Path, pack_id: str, *, name: str | None = None, force: bool = False
) -> Path:
    pack = PACKS.get(pack_id)
    if pack is None:
        raise DatasetError(f"unknown pack {pack_id!r}. Choose one of: {', '.join(PACK_ORDER)}")
    dest = dest.expanduser()
    if dest.exists() and (dest / CONFIG_FILE).is_file() and not force:
        raise DatasetError(f"{dest} already has {CONFIG_FILE}. Pass --force to overwrite.")
    dest.mkdir(parents=True, exist_ok=True)

    ready = dict(pack["ready"])
    ready["provenance"] = {"source": f"pack:{pack_id}", "author": "init", "reviewer": "fixture"}
    label = name or slugify(pack["label"])
    write_json(
        dest / CONFIG_FILE,
        {
            "name": label,
            "product": pack["label"],
            "job": pack["job"],
            "harm": pack["harm"],
            "acts": pack["acts"],
            "trials": 4,
            "reliability": "both",
            "pathways": pack["pathways"],
            "agents": {"stub": "agents.py:run"},
        },
    )
    write_json(dest / "worlds" / f"{ready['id']}.json", ready)
    for pathway in pack["pathways"]:
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
    return dest


def interview(
    queued: list[str] | None = None, *, yes: bool = False, pack_id: str | None = None
) -> dict[str, Any]:
    queued = list(queued or [])
    default_pack = pack_id or "chatbot"
    chosen = _ask(
        "Which kind of agent?",
        options=PACK_ORDER,
        default=default_pack,
        queued=queued,
        yes=yes,
    )
    pack = PACKS[chosen]
    name = _ask("Dataset name?", default=slugify(pack["label"]), queued=queued, yes=yes)
    return {"pack": chosen, "name": name}


def _ask(
    text: str,
    *,
    options: list[str] | None = None,
    default: str | None = None,
    queued: list[str],
    yes: bool,
) -> str:
    hint = f" [{' | '.join(options)}]" if options else ""
    suffix = f" [{default}]" if default else ""
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
    if options:
        lookup = {o.lower(): o for o in options}
        raw = lookup.get(raw.lower(), default or options[0])
    return raw
