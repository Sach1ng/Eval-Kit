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

## Not in this repo

This kit does not decide what your product should test. It does not call a live model yet. It does not re-run the APEX leaderboard. Bring your own gold when you are ready. The demo runs on the published example above.
