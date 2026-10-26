# Method

How Eval Kit maps to current eval practice, and the calls we made.

## Write gold from failures, not from a prompt

Husain and Shankar: start with error analysis on real traces, then write tests for those failures. Anthropic: 20–50 tasks from real misses is enough to start; a 0% pass@k is usually a broken task.

`evalkit init` writes pathways (failure types) and one finished world per pack, plus drafts for the rest. It does not invent a 300-row set. Grow the set by filling drafts and adding worlds from production misses.

## Grade the end state, then the path

τ-bench grades the database after the run. Anthropic: grade what the agent produced; do not require an exact tool sequence, which punishes valid paths.

Outcome checks read `final_output`, `final_state`, and `flags`. Path checks are invariants, not scripts: this tool was called, that tool was not. They do not require call order.

## Code checks before judges

Husain and Shankar: if a rule can decide, use code. LLM judges need Pass and Fail labels and calibration (TPR/TNR). Eval Kit ships eight code check types. There is no judge in v0.2.

## A known-good run on every world

Anthropic: every task needs a reference solution that passes the graders. If a known-good run fails, the world is broken.

`evalkit lint` scores the reference. That is how a world whose must-find was a whole sentence would get caught.

## Repeat the same world

Chen et al. 2021: pass@k, unbiased estimator over *n* trials. Yao et al. 2024: pass^k, probability that *k* independent trials all succeed. A single run is not a reliability claim.

`evalkit run` repeats each world `trials` times with a stable seed. `evalkit score` reports both estimators, plus the share of outcome-passes that were dirty.

## Balanced sets

Anthropic: test both “should act” and “should not.” One-sided evals create one-sided agents.

Lint warns when the clean-world share is outside 15–50%, once you have 10 ready worlds. It also wants a holdout split you do not tune on.

## Sources

- Hamel Husain and Shreya Shankar, [Your AI Product Needs Evals](https://hamel.dev/blog/posts/evals-faq/)
- Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)
- Chen et al., 2021, pass@k estimator
- Yao et al., 2024, [τ-bench](https://arxiv.org/abs/2406.12045), pass^k
