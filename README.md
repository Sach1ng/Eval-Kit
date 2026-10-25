# Eval Kit

You already have a golden dataset. Eval Kit turns it into a score you can explain.

Gold is the expert's worked answer. It is not the grader. The grader is a yes/no checklist. If a right ending can still be the wrong way to get there, the kit adds process checks and reports clean vs dirty.

The worked example is the public [APEX-Accounting](https://huggingface.co/datasets/mercor/apex-accounting) sample from Mercor (CC BY 4.0). That company is fictional. This repo does not include anyone's real books.

**Created by [@Sach1ng](https://github.com/Sach1ng) and [@hardiktiwari](https://github.com/hardiktiwari)**

---

## Quick start

1. **Clone the repo**
   ```bash
   git clone https://github.com/Sach1ng/Eval-Kit.git
   cd Eval-Kit
   ```

2. **Run the demo** (no API key, Python 3.9+)
   ```bash
   python3 -m evalkit --demo
   ```

3. **Or answer the questions yourself**
   ```bash
   python3 -m evalkit
   ```

---

## What it asks

1. Do you have gold, or should we use the public APEX example?
2. Can you tell success from the final answer alone?
3. Could that answer still be unacceptable because of how the agent got there?
4. Do you need it right every time, or is once enough to know the model can do it?
5. Does the agent change something (post, pay, send, file)?

Those answers pick the metrics. The rules are in `evalkit/determine.py`.

---

## What you get

| Path | Purpose |
|------|---------|
| `evalkit/` | Interview, metric picker, Task 4 example, scorer |
| `generated/apex-task4-eval/` | Written when you run: rubrics, one judge file per check, metrics |
| `generated/apex-task4-eval/variations.md` | The demo talk track |

---

## The demo

We do not write a new task. We take one published APEX task (prompt, expert answer, two outcome checks) and add:

1. Process checks that dataset does not score.
2. Three labeled ways an agent can finish the same task.

Then we score twice:

- Outcome only. Three of four finishes look successful.
- Outcome plus process. One of four is clean. Two of the "correct" endings are dirty.

| Finish | Outcome | Process | Call |
|--------|---------|---------|------|
| Expert answer, files actually opened | pass | pass | Clean |
| Same dollars, memo never opened | pass | fail | Dirty |
| Right files, wrong dollar amount | fail | pass | Process-correct fail |
| Right console entry, extra post underneath | pass | fail | Dirty |

Those four rows are designed finishes, not eight draws from a model. The interview still writes K = 8 into the metric names. That 8 is how many live runs you would collect later. `Pass@K` on this table means "did any of these four fully pass," which is the shape of the metric, not an estimate of Pass@8.

---

## On your project

Run the questions for the agent you ship.

```bash
python3 -m evalkit
```

Read the block that starts `PROPOSED EVAL`. That is the architecture. Then do this before anyone calls a model:

1. Freeze one task: the prompt, and one expert answer. The expert answer is for you. The judge does not see it.
2. Write outcome checks a stranger can mark from the final answer alone.
3. Add process checks only if a right ending can still be a bad path, or if the agent changes something (post, pay, send, file).
4. Name a clean finish, a dirty finish, and a process-correct fail. If you cannot name a dirty finish, drop the process checks.
5. Put one judge on each check. Outcome judges see the prompt, that check, and the final answer. Process judges also see the trace (files, tools, writes), not hidden chain-of-thought.
6. Score a full pass, not a vibe. Clean means every selected check passed on the same run. Dirty means the outcome passed and the process did not.
7. Launch on clean behavior. Outcome Pass@K flatters an agent that guesses the right ending.

`generated/apex-task4-eval/` is the shape of the pack you hand over: `config.json`, one file in `judges/` per check, the rubrics, and `metrics/definitions.md`. The demo fills that shape for World 9 Task 4. For your task, keep the shape and replace the checks.

This CLI does not load an arbitrary golden file, call a model, or recompute a public leaderboard. The APEX scorer is a deterministic stand-in so the 3-of-4 versus 1-of-4 result can be checked with no API key.

---

## What the words mean

| Word | Meaning |
|------|---------|
| Gold | Expert's full answer. Humans use it. The judge does not. |
| Criterion | One yes/no box. |
| Outcome | Did the final answer hit every box? |
| Process | Did the visible trace follow the must / must-not rules? |
| Clean | Outcome and process both pass. |
| Dirty | Outcome passes, process does not. |
| Pass@K | It happened at least once in K runs. |
| Pass^K | It happened on every one of K runs. |

---

## What you still decide

The kit does not pick the task. You do. It does not call a live model, and it does not re-run the APEX leaderboard. Gold for a new product stays with you; the demo stays on the published example above.
