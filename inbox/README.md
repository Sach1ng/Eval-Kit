# Inbox

Drop anonymized transcripts, tickets, issues, or a PRD here. Then:

```bash
python3 -m evalkit              # interview; ingest if files are present
python3 -m evalkit ingest my-eval --from ./inbox
python3 -m evalkit metrics my-eval --prd ./inbox/prd.md
```

Each transcript or ticket becomes a **draft** world. Drafts are not gold. A PRD is clues for pathways and for metrics that were actually written down (precision, completeness). Company goals such as conversion stay experiments, not launch gates.

Strip names, emails, and account numbers first. The kit reads local files only.
