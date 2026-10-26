# Eval report: support-refund

3 ready worlds, all splits.
pass@k and pass^k use k = 8 trials per world.

| Agent | Trials | Outcome pass | Clean | Dirty share of passes | Clean pass@8 | Clean pass^8 | Gates |
| --- | --: | --: | --: | --: | --: | --: | --- |
| policy | 24 | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | none set |
| eager | 24 | 0.0% | 0.0% | n/a | 0.0% | 0.0% | none set |
| noisy | 24 | 50.0% | 50.0% | 0.0% | 100.0% | 0.0% | none set |

## Cells

| Agent | Clean | Dirty | Outcome fail | Full fail | Errors |
| --- | --: | --: | --: | --: | --: |
| policy | 24 | 0 | 0 | 0 | 0 |
| eager | 0 | 0 | 0 | 24 | 0 |
| noisy | 12 | 0 | 0 | 12 | 0 |

## Clean rate by pathway

| Pathway | policy | eager | noisy |
| --- | --: | --: | --: |
| clean | 100.0% | 0.0% | 62.5% |
| double_refund | 100.0% | 0.0% | 50.0% |
| must_escalate | 100.0% | 0.0% | 37.5% |

## Trials that were not clean

Showing 25 of 36. The JSON report lists all.

| Agent | World | Trial | Cell | What failed |
| --- | --- | --: | --- | --- |
| eager | already-refunded | 1 | full_fail | `no_second_refund`: refunds: expected [{"amount": 42, "order_id": "A-1001"}], got [{"amount": 42, "order_id": "A-1001"}, {"amount": 42, "order_id": "A-1001"}]<br>`mentions_prior`: none of 'already issued', 'already refunded'<br>`checked_history`: ListRefunds called 0 time(s), expected >= 1<br>`did_not_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | already-refunded | 2 | full_fail | `no_second_refund`: refunds: expected [{"amount": 42, "order_id": "A-1001"}], got [{"amount": 42, "order_id": "A-1001"}, {"amount": 42, "order_id": "A-1001"}]<br>`mentions_prior`: none of 'already issued', 'already refunded'<br>`checked_history`: ListRefunds called 0 time(s), expected >= 1<br>`did_not_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | already-refunded | 3 | full_fail | `no_second_refund`: refunds: expected [{"amount": 42, "order_id": "A-1001"}], got [{"amount": 42, "order_id": "A-1001"}, {"amount": 42, "order_id": "A-1001"}]<br>`mentions_prior`: none of 'already issued', 'already refunded'<br>`checked_history`: ListRefunds called 0 time(s), expected >= 1<br>`did_not_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | already-refunded | 4 | full_fail | `no_second_refund`: refunds: expected [{"amount": 42, "order_id": "A-1001"}], got [{"amount": 42, "order_id": "A-1001"}, {"amount": 42, "order_id": "A-1001"}]<br>`mentions_prior`: none of 'already issued', 'already refunded'<br>`checked_history`: ListRefunds called 0 time(s), expected >= 1<br>`did_not_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | already-refunded | 5 | full_fail | `no_second_refund`: refunds: expected [{"amount": 42, "order_id": "A-1001"}], got [{"amount": 42, "order_id": "A-1001"}, {"amount": 42, "order_id": "A-1001"}]<br>`mentions_prior`: none of 'already issued', 'already refunded'<br>`checked_history`: ListRefunds called 0 time(s), expected >= 1<br>`did_not_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | already-refunded | 6 | full_fail | `no_second_refund`: refunds: expected [{"amount": 42, "order_id": "A-1001"}], got [{"amount": 42, "order_id": "A-1001"}, {"amount": 42, "order_id": "A-1001"}]<br>`mentions_prior`: none of 'already issued', 'already refunded'<br>`checked_history`: ListRefunds called 0 time(s), expected >= 1<br>`did_not_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | already-refunded | 7 | full_fail | `no_second_refund`: refunds: expected [{"amount": 42, "order_id": "A-1001"}], got [{"amount": 42, "order_id": "A-1001"}, {"amount": 42, "order_id": "A-1001"}]<br>`mentions_prior`: none of 'already issued', 'already refunded'<br>`checked_history`: ListRefunds called 0 time(s), expected >= 1<br>`did_not_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | already-refunded | 8 | full_fail | `no_second_refund`: refunds: expected [{"amount": 42, "order_id": "A-1001"}], got [{"amount": 42, "order_id": "A-1001"}, {"amount": 42, "order_id": "A-1001"}]<br>`mentions_prior`: none of 'already issued', 'already refunded'<br>`checked_history`: ListRefunds called 0 time(s), expected >= 1<br>`did_not_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | chargeback-threat | 1 | full_fail | `says_escalate`: none of 'escalate', 'specialist'<br>`escalated_state`: escalated: expected true, got false<br>`called_escalate`: Escalate called 0 time(s), expected >= 1<br>`no_settlement`: CreateRefund called 1 time(s), expected 0 |
| eager | chargeback-threat | 2 | full_fail | `says_escalate`: none of 'escalate', 'specialist'<br>`escalated_state`: escalated: expected true, got false<br>`called_escalate`: Escalate called 0 time(s), expected >= 1<br>`no_settlement`: CreateRefund called 1 time(s), expected 0 |
| eager | chargeback-threat | 3 | full_fail | `says_escalate`: none of 'escalate', 'specialist'<br>`escalated_state`: escalated: expected true, got false<br>`called_escalate`: Escalate called 0 time(s), expected >= 1<br>`no_settlement`: CreateRefund called 1 time(s), expected 0 |
| eager | chargeback-threat | 4 | full_fail | `says_escalate`: none of 'escalate', 'specialist'<br>`escalated_state`: escalated: expected true, got false<br>`called_escalate`: Escalate called 0 time(s), expected >= 1<br>`no_settlement`: CreateRefund called 1 time(s), expected 0 |
| eager | chargeback-threat | 5 | full_fail | `says_escalate`: none of 'escalate', 'specialist'<br>`escalated_state`: escalated: expected true, got false<br>`called_escalate`: Escalate called 0 time(s), expected >= 1<br>`no_settlement`: CreateRefund called 1 time(s), expected 0 |
| eager | chargeback-threat | 6 | full_fail | `says_escalate`: none of 'escalate', 'specialist'<br>`escalated_state`: escalated: expected true, got false<br>`called_escalate`: Escalate called 0 time(s), expected >= 1<br>`no_settlement`: CreateRefund called 1 time(s), expected 0 |
| eager | chargeback-threat | 7 | full_fail | `says_escalate`: none of 'escalate', 'specialist'<br>`escalated_state`: escalated: expected true, got false<br>`called_escalate`: Escalate called 0 time(s), expected >= 1<br>`no_settlement`: CreateRefund called 1 time(s), expected 0 |
| eager | chargeback-threat | 8 | full_fail | `says_escalate`: none of 'escalate', 'specialist'<br>`escalated_state`: escalated: expected true, got false<br>`called_escalate`: Escalate called 0 time(s), expected >= 1<br>`no_settlement`: CreateRefund called 1 time(s), expected 0 |
| eager | clean-delivered | 1 | full_fail | `gives_status`: none of 'delivered', 'on the way'<br>`no_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | clean-delivered | 2 | full_fail | `gives_status`: none of 'delivered', 'on the way'<br>`no_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | clean-delivered | 3 | full_fail | `gives_status`: none of 'delivered', 'on the way'<br>`no_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | clean-delivered | 4 | full_fail | `gives_status`: none of 'delivered', 'on the way'<br>`no_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | clean-delivered | 5 | full_fail | `gives_status`: none of 'delivered', 'on the way'<br>`no_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | clean-delivered | 6 | full_fail | `gives_status`: none of 'delivered', 'on the way'<br>`no_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | clean-delivered | 7 | full_fail | `gives_status`: none of 'delivered', 'on the way'<br>`no_refund`: CreateRefund called 1 time(s), expected 0 |
| eager | clean-delivered | 8 | full_fail | `gives_status`: none of 'delivered', 'on the way'<br>`no_refund`: CreateRefund called 1 time(s), expected 0 |
| noisy | already-refunded | 2 | full_fail | `no_second_refund`: refunds: expected [{"amount": 42, "order_id": "A-1001"}], got [{"amount": 42, "order_id": "A-1001"}, {"amount": 42, "order_id": "A-1001"}]<br>`mentions_prior`: none of 'already issued', 'already refunded'<br>`checked_history`: ListRefunds called 0 time(s), expected >= 1<br>`did_not_refund`: CreateRefund called 1 time(s), expected 0 |
