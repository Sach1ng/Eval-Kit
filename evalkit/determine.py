"""Turn interview answers into an eval architecture. Inspectable rules, not a black box."""


def determine(answers):
    writes = answers.get("writes_or_side_effects") == "yes"
    path_wrong = answers.get("path_can_be_wrong") in ("yes", "not sure")
    final_ok = answers.get("final_verifiable") in ("yes", "partly")
    need = answers.get("need_every_time", "both")

    use_outcome = final_ok or answers.get("final_verifiable") == "no"
    use_process = writes or path_wrong
    if answers.get("path_can_be_wrong") == "no" and not writes:
        use_process = False

    if need == "every time":
        reliability = "pass_hat_k"
    elif need == "can it ever":
        reliability = "pass_at_k"
    else:
        reliability = "both"

    if use_outcome and use_process:
        architecture = "outcome_and_process"
        label = "Outcome + process (joint / clean vs dirty)"
    elif use_process and not use_outcome:
        architecture = "process_primary"
        label = "Process / behavior primary (no clean final-answer key)"
    else:
        architecture = "outcome_only"
        label = "Outcome only (APEX-style final checklist)"

    k = 8
    return {
        "architecture": architecture,
        "label": label,
        "use_outcome": use_outcome,
        "use_process": use_process,
        "reliability": reliability,
        "k": k,
        "metrics": _metrics(use_outcome, use_process, reliability, k),
        "rationale": _rationale(answers, use_outcome, use_process, writes),
    }


def _metrics(use_outcome, use_process, reliability, k):
    metrics = []
    if use_outcome:
        metrics.append("Mean Outcome Criteria")
        if reliability in ("pass_at_k", "both"):
            metrics.append(f"Outcome Pass@{k}")
        if reliability in ("pass_hat_k", "both"):
            metrics.append(f"Outcome Pass^{k}")
    if use_process:
        metrics.append("Mean Process Criteria")
        if reliability in ("pass_at_k", "both"):
            metrics.append(f"Process Pass@{k}")
        if reliability in ("pass_hat_k", "both"):
            metrics.append(f"Process Pass^{k}")
    if use_outcome and use_process:
        metrics.extend(
            [
                f"Clean Pass@{k}",
                f"Clean Pass^{k}",
                "DirtyPassRate = P(process fail | outcome pass)",
                "DangerRate = P(outcome pass AND process fail)",
            ]
        )
    return metrics


def _rationale(answers, use_outcome, use_process, writes):
    bits = []
    if use_outcome:
        bits.append("Final answer can be checked as a yes/no checklist.")
    if use_process:
        if writes:
            bits.append("Agent can change the books or the world, so path gates matter.")
        else:
            bits.append("A right ending can still be an unacceptable path.")
    if not use_process:
        bits.append("You said the path does not change the call. Outcome only is enough.")
    if answers.get("has_gold") == "no":
        bits.append("You still need gold before this is a real eval. Demo can use APEX.")
    return bits
