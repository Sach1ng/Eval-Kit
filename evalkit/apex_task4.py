"""Worked example from the public APEX-Accounting sample (Mercor, CC BY 4.0).

Source: https://huggingface.co/datasets/mercor/apex-accounting
The company in that sample is fictional. This file is not employer data.
Outcome criteria are theirs. Process gates are added here.
"""

from pathlib import Path
import json

TASK_PATH = (
    Path(__file__).resolve().parent.parent
    / "apex-accounting"
    / "tasks"
    / "world_9_task_04.json"
)


def load_task():
    if TASK_PATH.exists():
        return json.loads(TASK_PATH.read_text())
    return _fallback_task()


def _fallback_task():
    return {
        "task_id": "task_baa139877a4d4fbfa601df50610262d5",
        "task_name": "World 9 Task 4",
        "prompt": (
            "Review the contingency case status and the journal entry register, "
            "together with relevant documents, and propose a journal entry where "
            "applicable for all relevant transactions. If entries have already been "
            "posted into the QBO journal entry register 2024 document, do not propose "
            "a journal entry.\n\nFor all of the above, focus on the settled case.\n\n"
            "Provide answers in the console, present amounts in $, and round numeric "
            "data to the nearest whole number, but do not round intermediate values."
        ),
        "gold_output": (
            "Proposed JE\nDate: 12/31/2024\nMemo: Whitfield post-settlement "
            "administrator holdback\n4200 Contingency Fee Revenue $29,700\n"
            "2050 Accrued Expenses $29,700"
        ),
        "rubric": [
            {
                "id": "ver_6ab475c82b184f7282b9ad3938aa518b",
                "criterion_type": "Reasoning (numerical)",
                "description": (
                    "Proposes the journal entry for Whitfield post-settlement holdback "
                    "as $29,700 Dr Contingency Fee Revenue (or Account 4200), Cr Accrued "
                    "Expenses (or Account 2050) (acceptable value is $29,700)"
                ),
            },
            {
                "id": "ver_eb52d163a3cc4863a9acd057d88d13ad",
                "criterion_type": "Reasoning (qualitative)",
                "description": "Identifies no more than one journal entry.",
            },
        ],
        "context_files": [
            "Whitfield_PostSettlement_Holdback_Memo.pdf",
            "qbo_journal_entry_register_2024.xlsx",
        ],
    }


def outcome_criteria(task):
    return [
        {
            "id": c["id"],
            "layer": "outcome",
            "description": c["description"],
            "source": "published APEX rubric (from prompt asks + expert solve)",
        }
        for c in task["rubric"]
    ]


def process_criteria():
    return [
        {
            "id": "proc_opened_holdback_memo",
            "layer": "process",
            "type": "required",
            "description": (
                "Opened Whitfield_PostSettlement_Holdback_Memo.pdf (or an equivalent "
                "authoritative holdback source) before proposing the $29,700 JE."
            ),
            "source": "evalkit process invariant, not in APEX",
        },
        {
            "id": "proc_no_extra_writes",
            "layer": "process",
            "type": "required",
            "description": (
                "Did not post journal entries other than the single proposed holdback JE."
            ),
            "source": "evalkit process invariant, not in APEX",
        },
        {
            "id": "proc_number_grounded",
            "layer": "process",
            "type": "required",
            "description": (
                "The $29,700 in the final answer can be traced to a file actually opened "
                "in this run. Guessing the gold number fails this gate."
            ),
            "source": "evalkit process invariant, not in APEX",
        },
    ]


# Three canned trials so `evalkit run` works with no API key.
# A later version calls a real model + tools and fills this same shape.

DEMO_TRIALS = [
    {
        "name": "gold_expert",
        "kind": "published_gold",
        "what_we_changed": "Nothing. Mercor's expert solve, with a plausible clean trace.",
        "final_output": None,  # filled from task gold
        "trace": {
            "files_opened": [
                "workpaper_contingency_case_status_2024.xlsx",
                "qbo_journal_entry_register_2024.xlsx",
                "Whitfield_PostSettlement_Holdback_Memo.pdf",
            ],
            "writes": [],
            "je_count_in_answer": 1,
        },
    },
    {
        "name": "dirty_guess",
        "kind": "variation",
        "what_we_changed": (
            "Same $29,700 JE as gold. Trace does not open the holdback memo. "
            "Outcome-only still passes. Process should fail."
        ),
        "final_output": (
            "Proposed JE\n4200 Contingency Fee Revenue $29,700\n"
            "2050 Accrued Expenses $29,700"
        ),
        "trace": {
            "files_opened": ["qbo_journal_entry_register_2024.xlsx"],
            "writes": [],
            "je_count_in_answer": 1,
        },
    },
    {
        "name": "wrong_amount",
        "kind": "variation",
        "what_we_changed": (
            "Opened the right memo, posted $30,000 instead of $29,700. "
            "Path is acceptable. Ending is wrong."
        ),
        "final_output": (
            "Proposed JE\n4200 Contingency Fee Revenue $30,000\n"
            "2050 Accrued Expenses $30,000"
        ),
        "trace": {
            "files_opened": [
                "Whitfield_PostSettlement_Holdback_Memo.pdf",
                "qbo_journal_entry_register_2024.xlsx",
            ],
            "writes": [],
            "je_count_in_answer": 1,
        },
    },
    {
        "name": "dirty_extra_post",
        "kind": "variation",
        "what_we_changed": (
            "Final console JE is the gold $29,700, but the agent already posted "
            "an extra JE. APEX outcome can pass. A controller would not."
        ),
        "final_output": (
            "Proposed JE\n4200 Contingency Fee Revenue $29,700\n"
            "2050 Accrued Expenses $29,700"
        ),
        "trace": {
            "files_opened": [
                "Whitfield_PostSettlement_Holdback_Memo.pdf",
            ],
            "writes": ["JE-WRONG-001 posted to 1000"],
            "je_count_in_answer": 1,
        },
    },
]
