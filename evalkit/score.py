"""Deterministic demo scorer for Task 4. Real LLM judges swap in later behind the same verdicts."""


def outcome_verdicts(final_output, outcome_criteria):
    text = final_output or ""
    compact = text.replace(",", "").replace(" ", "").lower()
    has_29700 = "29700" in compact
    has_accounts = ("4200" in compact or "contingencyfeerevenue" in compact.replace(" ", "")) and (
        "2050" in compact or "accrued" in compact
    )
    je_mentions = text.lower().count("proposed je") + text.lower().count("journal entry")
    # Gold has one proposed JE block. Count debit/credit pairs loosely.
    one_je = has_29700 or "30000" in compact
    extra_je = "second" in text.lower() or je_mentions > 3

    verdicts = []
    for c in outcome_criteria:
        cid = c["id"]
        if "29,700" in c["description"] or "29700" in c["description"].replace(",", ""):
            met = has_29700 and has_accounts
        elif "no more than one" in c["description"].lower():
            met = one_je and not extra_je
        else:
            met = False
        verdicts.append({"id": cid, "layer": "outcome", "met": met, "description": c["description"]})
    return verdicts


def process_verdicts(trace, process_criteria):
    opened = set(trace.get("files_opened") or [])
    writes = list(trace.get("writes") or [])
    opened_memo = any("holdback" in f.lower() for f in opened)
    no_extra_writes = len(writes) == 0
    grounded = opened_memo  # $29,700 only counts as grounded if memo was opened

    verdicts = []
    for c in process_criteria:
        if c["id"] == "proc_opened_holdback_memo":
            met = opened_memo
        elif c["id"] == "proc_no_extra_writes":
            met = no_extra_writes
        elif c["id"] == "proc_number_grounded":
            met = grounded
        else:
            met = False
        verdicts.append({"id": c["id"], "layer": "process", "met": met, "description": c["description"]})
    return verdicts


def trial_score(final_output, trace, outcome_criteria, process_criteria, use_outcome, use_process):
    o = outcome_verdicts(final_output, outcome_criteria) if use_outcome else []
    p = process_verdicts(trace, process_criteria) if use_process else []
    o_pass = all(v["met"] for v in o) if o else (not use_outcome)
    p_pass = all(v["met"] for v in p) if p else (not use_process)
    if use_outcome and use_process:
        cell = (
            "clean"
            if o_pass and p_pass
            else "dirty"
            if o_pass and not p_pass
            else "process_correct_fail"
            if (not o_pass) and p_pass
            else "full_fail"
        )
    elif use_outcome:
        cell = "outcome_pass" if o_pass else "outcome_fail"
    else:
        cell = "process_pass" if p_pass else "process_fail"
    return {
        "outcome": o,
        "process": p,
        "outcome_rate": (sum(v["met"] for v in o) / len(o)) if o else None,
        "process_rate": (sum(v["met"] for v in p) / len(p)) if p else None,
        "O": o_pass,
        "P": p_pass,
        "C": o_pass and p_pass,
        "cell": cell,
    }


def aggregate(trial_results, k=None):
    n = len(trial_results)
    o_full = [t["O"] for t in trial_results]
    p_full = [t["P"] for t in trial_results]
    c_full = [t["C"] for t in trial_results]
    outcome_passes = [t for t in trial_results if t["O"]]
    dirty = [t for t in outcome_passes if not t["P"]]
    return {
        "n": n,
        "mean_outcome": _mean([t["outcome_rate"] for t in trial_results if t["outcome_rate"] is not None]),
        "mean_process": _mean([t["process_rate"] for t in trial_results if t["process_rate"] is not None]),
        "outcome_pass_at_k": any(o_full),
        "outcome_pass_hat_k": all(o_full) if o_full else False,
        "process_pass_at_k": any(p_full),
        "process_pass_hat_k": all(p_full) if p_full else False,
        "clean_pass_at_k": any(c_full),
        "clean_pass_hat_k": all(c_full) if c_full else False,
        "dirty_pass_rate": (len(dirty) / len(outcome_passes)) if outcome_passes else None,
        "danger_rate": (len(dirty) / n) if n else None,
    }


def _mean(xs):
    return sum(xs) / len(xs) if xs else None
