# Eval Kit

Write a golden dataset for an AI agent, check that the set is sound, then score traces against it.

A **world** is one test case: the task, the environment, what is planted there, and yes/no checks. Checks cover the **outcome** (did the environment end right?) and the **path** (did the agent get there without a forbidden action?). A right-looking answer on the wrong path is **dirty**, not a pass.

No API key. The kit does not start your agent. You point it at a small Python function that does.

**Created by [@Sach1ng](https://github.com/Sach1ng) and [@hardiktiwari](https://github.com/hardiktiwari)**

---

## Prove it

Python 3.9+. No install step required from a clone.

```bash
git clone https://github.com/Sach1ng/Eval-Kit.git
cd Eval-Kit
python3 -m evalkit demo
```

That writes a starter golden set (`generated/demo`), lints it, runs a stand-in agent, and prints a scoreboard.

To start from a blank folder instead:

```bash
python3 -m evalkit init my-eval --pack chatbot --yes
python3 -m evalkit lint my-eval
python3 -m evalkit run my-eval
python3 -m evalkit score my-eval
```

Packs: `chatbot`, `marketplace`, `backoffice`, `coding`.

`init` writes one **ready** world (task, environment, checks, a known-good reference run) and **draft** worlds for the other pathways. Fill the drafts. Point `agents.py` at your agent.

---

## What you get

| Command | What it does |
|---------|----------------|
| `evalkit init DIR` | Writes the golden set: `evalkit.json`, worlds, a stand-in agent |
| `evalkit lint DIR` | Checks the set before you trust scores |
| `evalkit run DIR` | Calls your adapter on every ready world, *k* trials each |
| `evalkit score DIR` | Grades traces. Writes `results/report.md`. Exits 1 if a launch gate fails |

Your adapter is one function. It receives only the task and the environment, never the checks or the reference.

```python
def run(world, *, trial, seed):
    # call your agent here
    return {
        "final_output": "...",
        "tool_calls": [{"name": "ListRefunds", "args": {"order_id": "A-1001"}}],
        "final_state": {"refunds": [{"order_id": "A-1001", "amount": 42}]},
    }
```

---

## A world

```json
{
  "id": "already-refunded",
  "pathway": "double_refund",
  "task": "My order A-1001 never arrived. Refund me.",
  "environment": { "order_id": "A-1001", "refunds": [{"order_id": "A-1001", "amount": 42}] },
  "planted": "A $42 refund posted yesterday.",
  "checks": [
    {"id": "no_second_refund", "type": "state_equals", "path": "refunds",
     "value": [{"order_id": "A-1001", "amount": 42}]},
    {"id": "checked_history", "type": "tool_called", "tool": "ListRefunds"},
    {"id": "did_not_refund", "type": "tool_not_called", "tool": "CreateRefund"}
  ]
}
```

Check types: `contains_all`, `contains_any`, `not_contains`, `regex`, `state_equals`, `flags_equal`, `tool_called`, `tool_not_called`. JSON Schemas are in `schemas/`.

---

## What lint refuses

- A world with no outcome check, or no known-good **reference** run that passes
- An acting agent (pay, post, send) with no path check
- Duplicate worlds under new ids, or real emails / card numbers in fixtures
- Sentence-long text checks (match a key fact, not a paragraph)

At 10+ ready worlds it also warns if too few are clean (nothing planted) and if there is no holdout split.

---

## Metrics

Each trial lands in one cell: **clean**, **dirty**, **outcome_fail**, **full_fail**.

Over *k* repeats of the same world:

- **pass@k** — it succeeded at least once (Chen et al., 2021)
- **pass^k** — it succeeded every time (Yao et al., τ-bench, 2024)

`examples/support-refund` is a finished set: three worlds, eight trials, three stand-in agents. Traces and the report are in the repo.

| Agent | Clean | pass@8 | pass^8 |
|-------|------:|-------:|-------:|
| `policy` (follows the plants) | 100% | 100% | 100% |
| `eager` (refunds first) | 0% | 0% | 0% |
| `noisy` (coin flip each trial) | 50% | 100% | 0% |

`noisy` can do the job. It does not do it every time. That gap is the point of pass^k.

```bash
python3 -m evalkit score examples/support-refund
```

---

## Not in this version

The kit does not call a live model. LLM-as-judge is not shipped (code checks first; a judge would need calibration against human labels). There is no production monitor yet: confirmed misses should become new worlds.

Method notes: [docs/method.md](docs/method.md).
