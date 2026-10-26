"""Local transcripts, tickets, and notes the user dropped.

No network. Each file becomes a *draft* world: a starting point from something
that already happened. Drafts are not gold until a person adds checks and a
known-good reference run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evalkit.dataset import WORLD_DIR, DatasetError, load_dataset
from evalkit.process import write_process
from evalkit.util import slugify, write_json

INBOX = Path("inbox")

# Words in a dropped PRD or chat → pathway ids in the starter packs.
_HINTS = (
    (("escalate", "manager", "lawyer", "attorney", "chargeback", "fraud"), "must_escalate"),
    (("refund", "invoice", "double paid"), "double_refund"),
    (("safety", "assault", "911", "harass"), "safety_over_fare"),
    (("charged twice", "duplicate charge", "double charge"), "double_charge"),
    (("payroll", "w-2", "w2", "941", "1099"), "missing_required"),
    (("uncategorized", "miscellaneous"), "false_flag"),
    (("pytest", "unittest", "failing test"), "real_fix"),
    ((".env", "api_key", "secret"), "secret_file"),
)


def list_inbox(root: Path | None = None) -> list[Path]:
    root = Path(root) if root is not None else INBOX
    if not root.is_dir():
        return []
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "README.md" and not path.name.startswith("."):
            files.append(path)
    return files


def read_clues(root: Path | None = None, *, limit: int = 8) -> list[dict]:
    clues = []
    for path in list_inbox(root)[:limit]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        clues.append({"path": str(path), "name": path.name, "ids": match_pathways(text)})
    return clues


def match_pathways(text: str) -> list[str]:
    low = text.lower()
    hits = []
    for words, pathway_id in _HINTS:
        if any(word in low for word in words) and pathway_id not in hits:
            hits.append(pathway_id)
    return hits


def excerpt(text: str, limit: int = 500) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def text_from_file(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() != ".json":
        return raw
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    return _from_json(data) or raw


def _from_json(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        bits = []
        for item in data:
            if isinstance(item, dict):
                bit = item.get("content") or item.get("text") or item.get("body")
                role = item.get("role") or item.get("author") or ""
                if bit:
                    bits.append(f"{role}: {bit}" if role else str(bit))
            elif isinstance(item, str):
                bits.append(item)
        return "\n".join(bits)
    if isinstance(data, dict):
        for key in ("transcript", "issue", "body", "text", "final_output", "prompt"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
        if "messages" in data:
            return _from_json(data["messages"])
    return ""


def draft_world(path: Path, text: str, *, used_ids: set[str], pathway_ids: list[str]) -> dict:
    hits = [p for p in match_pathways(text) if p in pathway_ids]
    pathway = hits[0] if hits else (pathway_ids[0] if pathway_ids else "from_inbox")
    base = slugify(f"from_{path.stem}")[:40]
    world_id = base or "from_inbox"
    n = 2
    while world_id in used_ids:
        world_id = f"{base}-{n}"
        n += 1
    body = excerpt(text, 800)
    return {
        "id": world_id,
        "status": "draft",
        "pathway": pathway,
        "title": path.stem.replace("_", " ").replace("-", " "),
        "task": body or f"Replay the case from {path.name}.",
        "planted": (
            "From a real transcript or ticket. Confirm the planted failure "
            "before marking this world ready."
        ),
        "brief": "Add checks and a reference run. Until then this is not gold.",
        "environment": {"source_file": path.name, "excerpt": excerpt(text, 1200)},
        "checks": [],
        "provenance": {"source": path.name, "author": "ingest"},
    }


def ingest(dataset_dir: Path, source: Path, *, limit: int = 40) -> list[dict]:
    """Write one draft world per file. Existing world ids are left alone."""
    dataset = load_dataset(dataset_dir)
    files = list_inbox(source)
    if not files:
        raise DatasetError(f"{source}: no transcripts or tickets to ingest")
    used = {w["id"] for w in dataset.worlds if isinstance(w.get("id"), str)}
    declared = list(dataset.pathway_ids)
    written = []
    for path in files[:limit]:
        try:
            text = text_from_file(path)
        except OSError:
            continue
        if not text.strip():
            continue
        world = draft_world(path, text, used_ids=used, pathway_ids=declared)
        used.add(world["id"])
        write_json(dataset.root / WORLD_DIR / "from_inbox" / f"{world['id']}.json", world)
        written.append(world)
    if written:
        extra = [
            {"id": w["pathway"], "name": w["pathway"]}
            for w in written
            if w["pathway"] not in declared
        ]
        if extra:
            config = dict(dataset.config)
            config["pathways"] = list(config.get("pathways") or []) + extra
            write_json(dataset.root / "evalkit.json", config)
        write_process(load_dataset(dataset.root))
    return written
