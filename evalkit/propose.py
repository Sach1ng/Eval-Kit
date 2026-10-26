"""Turn the job, harm, and PRD into a metric plan.

A plan is a proposal until a person confirms it. Company numbers in a PRD
(conversion, CSAT) stay experiments; they are not gold-set gates. Numbers that
were not in the answers or the PRD are not invented.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from evalkit.dataset import CONFIG_FILE, Dataset, load_dataset
from evalkit.util import write_json

METRICS_FILE = "metrics.json"

_EXPERIMENT = re.compile(r"\b(conversion|csat|nps|retention|revenue|gmv|churn)\b", re.I)
_PCT = r"(\d{1,3})\s*%"


def _pct_for(text: str, word: str) -> float | None:
    if not text.strip():
        return None
    patterns = (rf"{word}\D{{0,40}}{_PCT}", rf"{_PCT}\D{{0,40}}{word}")
    for pat in patterns:
        match = re.search(pat, text, re.I)
        if not match:
            continue
        digits = next((g for g in match.groups() if g and g.isdigit()), None)
        if digits is None:
            continue
        n = int(digits)
        if 0 <= n <= 100:
            return n / 100.0
    return None


def propose(
    *,
    job: str = "",
    harm: str = "",
    acts: bool = False,
    gold_unit: str = "environment",
    reliability: str = "both",
    trials: int = 8,
    gate: float | None = None,
    prd_text: str = "",
    company_goal: str = "",
) -> dict[str, Any]:
    verifiers = [
        {
            "id": "outcome",
            "kind": "code",
            "on": gold_unit,
            "why": f"Grade the {gold_unit} with yes/no checks, not a judge.",
        }
    ]
    if acts:
        verifiers.append(
            {
                "id": "path",
                "kind": "code",
                "on": "tool_calls",
                "why": "A right-looking result on a forbidden action is dirty, not a pass.",
            }
        )
    verifiers.append(
        {
            "id": "reference",
            "kind": "known_good_run",
            "on": "world.reference",
            "why": "If a known-good run fails the checks, the world is broken.",
        }
    )

    why = []
    if reliability in {"every_time", "both"}:
        why.append(f"Reliability is every-time (or both): report pass^{trials} (clean_pass_hat_k).")
    if reliability in {"at_least_once", "both"}:
        why.append(f"Report pass@{trials} (clean_pass_at_k).")
    if acts:
        why.append("The agent writes: track dirty_pass_rate. Dirty is not a pass.")

    offline: list[dict[str, Any]] = []
    if gate is not None:
        metric = "clean_pass_hat_k" if reliability != "at_least_once" else "clean_pass_at_k"
        offline.append({"metric": metric, "min": float(gate), "source": "interview"})
        why.append(f"Launch bar from the interview: {metric} >= {gate}.")

    precision = _pct_for(prd_text, r"(?:flag\s+)?precision")
    if precision is not None:
        offline.append({"metric": "precision", "min": precision, "source": "prd"})
        why.append(f"PRD stated precision; proposed precision >= {precision:.0%}.")
    completeness = _pct_for(prd_text, r"completeness")
    if completeness is not None:
        offline.append({"metric": "completeness", "min": completeness, "source": "prd"})
        why.append(f"PRD stated completeness; proposed completeness >= {completeness:.0%}.")

    experiments: list[dict[str, str]] = []
    goal = (company_goal or "").strip()
    if goal.lower() not in {"", "skip", "none"}:
        experiments.append(
            {
                "name": goal,
                "kind": "experiment",
                "why": "Company goal. Measure after ship in product analytics, not as a gold gate.",
            }
        )
    seen = {e["name"].lower() for e in experiments}
    for match in _EXPERIMENT.finditer(prd_text or ""):
        word = match.group(1).lower()
        if word in seen:
            continue
        seen.add(word)
        experiments.append(
            {
                "name": word,
                "kind": "experiment",
                "why": "Named in the PRD. Not a gold-set gate.",
            }
        )

    online = [
        {
            "metric": "crash_rate",
            "max": 0,
            "why": "Unlabeled live traces: the error field is set.",
        },
        {
            "metric": "pii_leak_rate",
            "max": 0,
            "why": "Unlabeled live traces: an email, card, or SSN in the reply.",
        },
        {
            "metric": "confirmed_misses",
            "why": "A person confirms a miss, then ingest it as a draft world.",
        },
    ]
    return {
        "confirmed": False,
        "verifiers": verifiers,
        "offline": offline,
        "online": online,
        "experiments": experiments,
        "why": why,
        "job": job,
        "harm": harm,
    }


def gates_from_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    gates = []
    for item in plan.get("offline") or []:
        gate: dict[str, Any] = {"metric": item["metric"]}
        if "min" in item:
            gate["min"] = item["min"]
        if "max" in item:
            gate["max"] = item["max"]
        gates.append(gate)
    return gates


def render_plan(plan: dict[str, Any]) -> str:
    state = "confirmed" if plan.get("confirmed") else "proposal — confirm before ship"
    lines = ["Metric plan  (" + state + ")", ""]
    lines.append("Verifiers (code checks against gold, not an LLM judge)")
    for item in plan.get("verifiers") or []:
        lines.append(f"  - {item['id']} on {item['on']}: {item['why']}")
    lines.append("")
    lines.append("Pre-prod gates (scored against the golden set)")
    offline = plan.get("offline") or []
    if offline:
        for item in offline:
            bound = "min" if "min" in item else "max"
            src = f"  [{item['source']}]" if item.get("source") else ""
            lines.append(f"  - {item['metric']} {bound} {item[bound]}{src}")
    else:
        lines.append("  - none yet. Set a launch bar, or confirm a number from the PRD.")
    lines.append("")
    lines.append("Post-prod (unlabeled live traces; no gold)")
    for item in plan.get("online") or []:
        bound = ""
        if "max" in item:
            bound = f"max {item['max']}. "
        elif "min" in item:
            bound = f"min {item['min']}. "
        lines.append(f"  - {item['metric']}: {bound}{item['why']}")
    experiments = plan.get("experiments") or []
    if experiments:
        lines.append("")
        lines.append("Company numbers (experiments, not this eval)")
        for item in experiments:
            lines.append(f"  - {item['name']}: {item['why']}")
    why = plan.get("why") or []
    if why:
        lines.append("")
        lines.append("Why")
        lines.extend(f"  - {line}" for line in why)
    return "\n".join(lines) + "\n"


def load_plan(root: Path) -> dict[str, Any] | None:
    path = Path(root) / METRICS_FILE
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def write_plan(root: Path, plan: dict[str, Any]) -> Path:
    path = Path(root) / METRICS_FILE
    write_json(path, plan)
    return path


def apply_confirmed_gates(root: Path, plan: dict[str, Any]) -> None:
    dataset = load_dataset(root)
    config = dict(dataset.config)
    config["gates"] = gates_from_plan(plan)
    write_json(dataset.root / CONFIG_FILE, config)


def corpus(dataset: Dataset, extra: list[Path] | None = None) -> str:
    bits = []
    product = dataset.root / "product.md"
    if product.is_file():
        bits.append(product.read_text(encoding="utf-8", errors="replace"))
    for path in extra or []:
        path = Path(path)
        if path.is_file():
            bits.append(path.read_text(encoding="utf-8", errors="replace"))
        elif path.is_dir():
            from evalkit.inbox import list_inbox, text_from_file

            for file in list_inbox(path):
                try:
                    bits.append(text_from_file(file))
                except OSError:
                    continue
    return "\n".join(bits)


def gate_from_config(config: dict[str, Any]) -> float | None:
    for item in config.get("gates") or []:
        if isinstance(item, dict) and "min" in item:
            return float(item["min"])
    return None


def propose_for(
    dataset: Dataset,
    *,
    prd_text: str = "",
    company_goal: str = "",
    gate: float | None = None,
) -> dict[str, Any]:
    cfg = dataset.config
    if gate is None:
        gate = gate_from_config(cfg)
    plan = propose(
        job=str(cfg.get("job") or ""),
        harm=str(cfg.get("harm") or ""),
        acts=bool(cfg.get("acts", False)),
        gold_unit=str(cfg.get("gold_unit") or "environment"),
        reliability=str(cfg.get("reliability") or "both"),
        trials=int(cfg.get("trials") or 8),
        gate=gate,
        prd_text=prd_text,
        company_goal=company_goal or str(cfg.get("company_goal") or ""),
    )
    if not plan["offline"] and dataset.gates:
        plan["offline"] = [{**g, "source": "evalkit.json"} for g in dataset.gates]
    return plan
