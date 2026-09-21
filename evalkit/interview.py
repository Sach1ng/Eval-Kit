"""Short interview. Answers pick the eval architecture."""

QUESTIONS = [
    {
        "id": "has_gold",
        "text": "Do you already have a golden dataset (tasks + an expert answer per task)?",
        "options": ["yes", "no", "use apex demo"],
        "help": "Gold is the expert's worked answer. It is not the grader.",
    },
    {
        "id": "final_verifiable",
        "text": "Can you tell success from the final answer alone (the number, JE, recommendation)?",
        "options": ["yes", "no", "partly"],
        "help": "If yes, you can score outcome criteria on the last message.",
    },
    {
        "id": "path_can_be_wrong",
        "text": "Could the agent get that final answer right in a way you would still reject (skipped a check, guessed, used the wrong file, posted extra entries)?",
        "options": ["yes", "no", "not sure"],
        "help": "If yes, you need process gates on the trace, not just the ending.",
    },
    {
        "id": "need_every_time",
        "text": "Do you need it right every time, or is once-in-eight-tries enough to learn if the model can do it?",
        "options": ["every time", "can it ever", "both"],
        "help": "Once = Pass@K (skill). Every time = Pass^K (reliability).",
    },
    {
        "id": "writes_or_side_effects",
        "text": "Does the agent take actions that change something (post a JE, send money, email a customer, file)?",
        "options": ["yes", "no"],
        "help": "Writes make process gates almost mandatory.",
    },
]


def ask(stdin_answers=None):
    """Ask questions. stdin_answers is an optional list for non-interactive demos."""
    answers = {}
    queued = list(stdin_answers or [])
    print("\nEvalkit will ask a few questions, then propose how to score your gold set.\n")
    for q in QUESTIONS:
        print(q["text"])
        print(f"  ({q['help']})")
        print("  options: " + " | ".join(q["options"]))
        if queued:
            raw = queued.pop(0).strip().lower()
            print(f"  → {raw}")
        else:
            raw = input("  → ").strip().lower()
        if raw not in q["options"]:
            raw = q["options"][0]
            print(f"  (using {raw})")
        answers[q["id"]] = raw
        print()
    return answers
