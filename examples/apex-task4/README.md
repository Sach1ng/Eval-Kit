# Example: APEX-Accounting World 9 Task 4

Public sample from [Mercor APEX-Accounting](https://huggingface.co/datasets/mercor/apex-accounting) (CC BY 4.0). The company is fictional.

The published rubric scores the final journal entry. This folder adds path checks the source dataset does not: the holdback memo was opened, and nothing extra was posted.

Four labeled finishes of the same world, one trial each:

| Agent | Outcome | Path | Cell |
|-------|---------|------|------|
| `gold_expert` | pass | pass | clean |
| `dirty_guess` | pass | fail | dirty |
| `wrong_amount` | fail | pass | outcome_fail |
| `dirty_extra_post` | pass | fail | dirty |

Outcome-only would pass 3 of 4. Joint grading leaves 1 of 4 clean.

```bash
python3 -m evalkit lint examples/apex-task4
python3 -m evalkit run examples/apex-task4
python3 -m evalkit score examples/apex-task4
```
