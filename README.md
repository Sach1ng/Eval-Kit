# Eval Kit

A launch-quality eval is **weeks to months**. This kit is the place to put that work, and it helps you **create the golden set**, **propose metrics you confirm**, **score pre-prod against that gold**, and **watch unlabeled production traces**.

Worlds come from two sources:

1. **Interview** — job, harm, pathways, launch bar (`evalkit init`)
2. **Ingest** — past transcripts, tickets, and issues (`evalkit ingest`)

A **world** is one test case: the task, the environment, what is planted, and yes/no checks. Checks cover the **outcome** (did the environment end right?) and the **path** (did the agent get there without a forbidden action?). A right-looking answer on the wrong path is **dirty**, not a pass.

Drafts are not gold. A world is gold when it has checks, a known-good reference run, and a reviewer who did not plant it.

No API key. The kit does not start your agent. There is no LLM judge: verifiers are code checks against gold, plus crash / empty / PII checks on unlabeled live traces.

**Created by [@Sach1ng](https://github.com/Sach1ng) and [@hardiktiwari](https://github.com/hardiktiwari)**

---

## Prove it

Python 3.9+. No install step from a clone.

```bash
git clone https://github.com/Sach1ng/Eval-Kit.git
cd Eval-Kit
python3 -m evalkit
```

Run that from the clone folder. It starts the interview (multiple choice + free text). Drop anonymized chats or tickets in `inbox/` first if you have them. Scripts should pass `--yes` so they do not wait on a prompt.

Skip typing for a canned starter:

```bash
python3 -m evalkit demo
```

---

## The loop

| Stage | Who | Command |
|-------|-----|---------|
| Frame the job | You, experts, customers, PRD | `evalkit init` |
| Collect real misses | Transcripts, tickets, issues you already have | `evalkit ingest` |
| Plant and write checks | You | edit `worlds/*.json` |
| Prove the world is solvable | You | reference run; `evalkit lint` |
| Propose metrics | Job, harm, PRD — then you confirm | `evalkit metrics` |
| Pre-prod against gold | Your adapter + code checks | `evalkit preprod` |
| Ship bar | Confirmed gates, prefer holdout | `evalkit ship` |
| Post-prod | Unlabeled live traces | `evalkit prod` |
| Grow gold | Confirmed live misses | `evalkit ingest` / `prod --ingest` |

`evalkit status DIR` prints what is still on you. Init writes `PROCESS.md` so the remaining months of work are in the folder, not implied.

Company numbers in a PRD (conversion, CSAT) stay **experiments**. They are not gold-set gates. `--yes` accepts interview defaults for scripts. It does not mean the eval is finished, and it does not confirm metrics.

Packs: `chatbot`, `marketplace`, `backoffice`, `coding`.

```bash
python3 -m evalkit init my-eval --pack chatbot
python3 -m evalkit ingest my-eval --from ./inbox
python3 -m evalkit metrics my-eval --prd ./inbox/prd.md --confirm
python3 -m evalkit preprod my-eval
python3 -m evalkit ship my-eval
python3 -m evalkit prod my-eval --from ./prod-traces
```

`ship` needs a confirmed launch bar (set one in the interview, or a number the gold set can actually score). Precision gates only apply when worlds have flag checks.

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

`evalkit metrics` proposes from the job, the harm, and numbers actually written in a PRD. You confirm before they become launch gates.

Each trial lands in one cell: **clean**, **dirty**, **outcome_fail**, **full_fail**.

Over *k* repeats of the same world:

- **pass@k** — it succeeded at least once (Chen et al., 2021)
- **pass^k** — it succeeded every time (Yao et al., τ-bench, 2024)

`evalkit preprod` lints, runs your adapter, and scores against gold. `evalkit ship` refuses until the plan is confirmed, then enforces the gates (holdout when that split exists). `evalkit prod` scores live traces that still name a world, and queues unlabeled ones that crash, come back empty, or look like personal data. `--ingest` turns those misses into drafts.

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

The kit does not call a live model, run your interviews for you, or stand in for a domain expert. LLM-as-judge is not shipped: use code checks, then add a judge only after you have Pass and Fail labels and have calibrated it.

Method notes: [docs/method.md](docs/method.md).
