# Inbox

Drop anonymized transcripts, tickets, or traces here. Then:

```bash
python3 -m evalkit              # interview; ingest if files are present
python3 -m evalkit ingest my-eval --from ./inbox
```

Each file becomes a **draft** world. Drafts are not gold. Strip names, emails, and account numbers first. The kit reads local files only.
