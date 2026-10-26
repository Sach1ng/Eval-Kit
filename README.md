# Eval Kit

A launch-quality golden set is **weeks to months**: you interview the people who see the failures, rebuild the environment, write checks, and have someone else verify. This kit does not skip that. It is a place to put the work, and it helps you **create the first worlds** from two sources:

1. **Interview** — job, harm, pathways, launch bar
2. **Ingest** — transcripts, tickets, and traces that already happened become draft worlds

A **world** is one test case: the task, the environment, what is planted, and yes/no checks. Checks cover the **outcome** (did the environment end right?) and the **path** (did the agent get there without a forbidden action?). A right-looking answer on the wrong path is **dirty**, not a pass.

Drafts are not gold. A world is gold when it has checks, a known-good reference run, and a reviewer who did not plant it.

No API key. The kit does not start your agent.

**Created by [@Sach1ng](https://github.com/Sach1ng) and [@hardiktiwari](https://github.com/hardiktiwari)**

---

## Prove it

Python 3.9+. No install step from a clone.

```bash
git clone https://github.com/Sach1ng/Eval-Kit.git
cd Eval-Kit
python3 -m evalkit
```

That starts the interview (multiple choice + free text). Drop anonymized chats or tickets in `inbox/` first if you have them.

Skip typing for a canned starter:

```bash
python3 -m evalkit demo
```

---

## The loop this kit covers

| Stage | Who | Command |
|-------|-----|---------|
| Frame the job | You, experts, customers | `evalkit init` (interview) |
| Collect real misses | Tickets, chats, traces you already have | `evalkit ingest` |
| Plant and write checks | You | edit `worlds/*.json` |
| Prove the world is solvable | You | reference run; `evalkit lint` |
| Second pair of eyes | Someone who did not plant it | `provenance.reviewer` |
| Run the agent | Your adapter | `evalkit run` / `score` |
| Grow | New production misses | `evalkit ingest` again |

`evalkit status DIR` prints what is still on you. Init writes `PROCESS.md` so the remaining months of work are in the folder, not implied.

Packs for the interview: `chatbot`, `marketplace`, `backoffice`, `coding`.

```bash
python3 -m evalkit init my-eval --pack chatbot
python3 -m evalkit ingest my-eval --from ./inbox
python3 -m evalkit status my-eval
python3 -m evalkit lint my-eval
python3 -m evalkit run my-eval
python3 -m evalkit score my-eval
```

`--yes` on init accepts defaults (for scripts). It does not mean the eval is finished.

Your adapter is one function. It receives only the task and the environment, never the checks.

```python
def run(world, *, trial, seed):
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

Ingest writes the same shape with `"status": "draft"` and empty `checks`. Lint will not score drafts. Promote one only after you plant the failure, add checks, and attach a reference run that passes.

Check types: `contains_all`, `contains_any`, `not_contains`, `regex`, `state_equals`, `flags_equal`, `tool_called`, `tool_not_called`. JSON Schemas are in `schemas/`.

---

## What lint refuses

- A ready world with no outcome check, or no known-good **reference** run that passes
- An acting agent (pay, post, send) with no path check
- Duplicate worlds under new ids, or real emails / card numbers in fixtures
- Sentence-long text checks (match a key fact, not a paragraph)

At 10+ ready worlds it also warns if too few are clean (nothing planted) and if there is no holdout split. Anthropic's starting range is 20–50 worlds from real failures, not a generated grid.

---

## Metrics

Each trial lands in one cell: **clean**, **dirty**, **outcome_fail**, **full_fail**.

Over *k* repeats of the same world:

- **pass@k** — it succeeded at least once (Chen et al., 2021)
- **pass^k** — it succeeded every time (Yao et al., τ-bench, 2024)

`examples/support-refund` is a small finished set, not a substitute for your interviews.

| Agent | Clean | pass@8 | pass^8 |
|-------|------:|-------:|-------:|
| `policy` (follows the plants) | 100% | 100% | 100% |
| `eager` (refunds first) | 0% | 0% | 0% |
| `noisy` (coin flip each trial) | 50% | 100% | 0% |

```bash
python3 -m evalkit score examples/support-refund
```

---

## Not in this version

The kit does not call a live model, run your interviews for you, or stand in for a domain expert. LLM-as-judge is not shipped. There is no production monitor: confirmed misses should be ingested as new drafts.

Method notes: [docs/method.md](docs/method.md).
