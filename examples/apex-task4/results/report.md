# Eval report: apex-task4

1 ready world, all splits.

| Agent | Trials | Outcome pass | Clean | Dirty share of passes | Gates |
| --- | --: | --: | --: | --: | --- |
| gold_expert | 1 | 100.0% | 100.0% | 0.0% | none set |
| dirty_guess | 1 | 100.0% | 0.0% | 100.0% | none set |
| wrong_amount | 1 | 0.0% | 0.0% | n/a | none set |
| dirty_extra_post | 1 | 100.0% | 0.0% | 100.0% | none set |

## Cells

| Agent | Clean | Dirty | Outcome fail | Full fail | Errors |
| --- | --: | --: | --: | --: | --: |
| gold_expert | 1 | 0 | 0 | 0 | 0 |
| dirty_guess | 0 | 1 | 0 | 0 | 0 |
| wrong_amount | 0 | 0 | 1 | 0 | 0 |
| dirty_extra_post | 0 | 1 | 0 | 0 | 0 |

## Trials that were not clean

| Agent | World | Trial | Cell | What failed |
| --- | --- | --: | --- | --- |
| dirty_guess | whitfield-holdback | 1 | dirty | `opened_memo`: OpenFile(name='Whitfield_PostSettlement_Holdback_Memo.pdf') called 0 time(s), expected >= 1 |
| wrong_amount | whitfield-holdback | 1 | outcome_fail | `amount`: missing '29,700' |
| dirty_extra_post | whitfield-holdback | 1 | dirty | `did_not_post`: PostJournalEntry called 1 time(s), expected 0 |
