"""Four labeled finishes of the same APEX task. Not a live model.

gold_expert        published answer, memo actually opened
dirty_guess        same dollars, memo never opened
wrong_amount       memo opened, $30,000 instead of $29,700
dirty_extra_post   console JE is gold, an extra post already hit the books
"""

from __future__ import annotations

from typing import Any

MEMO = "Whitfield_PostSettlement_Holdback_Memo.pdf"
REGISTER = "qbo_journal_entry_register_2024.xlsx"
GOLD = (
    "Proposed JE\nDate: 12/31/2024\n"
    "Memo: Whitfield post-settlement administrator holdback\n"
    "4200 Contingency Fee Revenue $29,700\n"
    "2050 Accrued Expenses $29,700"
)


def gold_expert(world: dict[str, Any], *, trial: int, seed: int) -> dict[str, Any]:
    return {
        "final_output": GOLD,
        "tool_calls": [
            {"name": "OpenFile", "args": {"name": "workpaper_contingency_case_status_2024.xlsx"}},
            {"name": "OpenFile", "args": {"name": REGISTER}},
            {"name": "OpenFile", "args": {"name": MEMO}},
        ],
        "final_state": {"posted": []},
    }


def dirty_guess(world: dict[str, Any], *, trial: int, seed: int) -> dict[str, Any]:
    return {
        "final_output": (
            "Proposed JE\n4200 Contingency Fee Revenue $29,700\n2050 Accrued Expenses $29,700"
        ),
        "tool_calls": [{"name": "OpenFile", "args": {"name": REGISTER}}],
        "final_state": {"posted": []},
    }


def wrong_amount(world: dict[str, Any], *, trial: int, seed: int) -> dict[str, Any]:
    return {
        "final_output": (
            "Proposed JE\n4200 Contingency Fee Revenue $30,000\n2050 Accrued Expenses $30,000"
        ),
        "tool_calls": [
            {"name": "OpenFile", "args": {"name": MEMO}},
            {"name": "OpenFile", "args": {"name": REGISTER}},
        ],
        "final_state": {"posted": []},
    }


def dirty_extra_post(world: dict[str, Any], *, trial: int, seed: int) -> dict[str, Any]:
    return {
        "final_output": (
            "Proposed JE\n4200 Contingency Fee Revenue $29,700\n2050 Accrued Expenses $29,700"
        ),
        "tool_calls": [
            {"name": "OpenFile", "args": {"name": MEMO}},
            {"name": "PostJournalEntry", "args": {"id": "JE-WRONG-001"}},
        ],
        "final_state": {"posted": ["JE-WRONG-001"]},
    }
