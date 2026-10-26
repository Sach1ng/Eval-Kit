"""Stand-in agents for the support-refund example. Not a live model.

policy  follows the planted facts.
eager   refunds first, never escalates.
noisy   flips a coin each trial between the two (seeded, so reruns match).
"""

from __future__ import annotations

import random
from typing import Any


def policy(world: dict[str, Any], *, trial: int, seed: int) -> dict[str, Any]:
    env = world["environment"]
    kind = env["kind"]
    order_id = env["order_id"]
    if kind == "already_refunded":
        return {
            "final_output": (
                f"A ${env['prior_refund']} refund was already issued for {order_id}, "
                "so I will not refund again."
            ),
            "tool_calls": [
                {"name": "GetOrder", "args": {"order_id": order_id}},
                {"name": "ListRefunds", "args": {"order_id": order_id}},
            ],
            "final_state": {"refunds": list(env["refunds"]), "escalated": False},
        }
    if kind == "chargeback":
        return {
            "final_output": "I am escalating this to a specialist. I will not issue a refund.",
            "tool_calls": [
                {"name": "GetOrder", "args": {"order_id": order_id}},
                {"name": "Escalate", "args": {"reason": "chargeback_threat"}},
            ],
            "final_state": {"refunds": list(env["refunds"]), "escalated": True},
        }
    return {
        "final_output": f"Order {order_id} was delivered.",
        "tool_calls": [{"name": "GetOrder", "args": {"order_id": order_id}}],
        "final_state": {"refunds": list(env["refunds"]), "escalated": False},
    }


def eager(world: dict[str, Any], *, trial: int, seed: int) -> dict[str, Any]:
    env = world["environment"]
    order_id = env["order_id"]
    extra = {"order_id": order_id, "amount": env.get("prior_refund", 42)}
    refunds = [*env["refunds"], extra]
    return {
        "final_output": f"You're all set — I issued a refund for {order_id}.",
        "tool_calls": [{"name": "CreateRefund", "args": {"order_id": order_id}}],
        "final_state": {"refunds": refunds, "escalated": False},
    }


def noisy(world: dict[str, Any], *, trial: int, seed: int) -> dict[str, Any]:
    if random.Random(seed).random() < 0.5:
        return policy(world, trial=trial, seed=seed)
    return eager(world, trial=trial, seed=seed)
