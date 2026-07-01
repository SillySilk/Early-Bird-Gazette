# Early Bird Gazette

A local, single-user Windows desktop app (PyQt6) that ingests AI "tricks &
techniques" (Stable Diffusion, LoRA training, Anima, local LLMs) from online
sources, extracts them into structured records with a local LLM, deduplicates
them, and stores everything in one SQLite database that sibling apps can read.

## Status

**P1 — Core storage & schema: complete.** The `gazette` core library provides:

- WAL-mode SQLite connection management with `sqlite-vec` + FTS5 loaded
- An idempotent, atomic migration runner
- The full domain-agnostic schema (relational + FTS5 external-content +
  `sqlite-vec` embedding table)
- Pydantic v2 models and a low-level repository (CRUD) with atomic,
  composable writes

Later sub-projects (query client, source connectors, LLM extraction, dedup,
ingestion, PyQt6 UI) are designed in `docs/superpowers/`.

## Architecture & plans

- Design spec: `docs/superpowers/specs/2026-07-01-early-bird-gazette-design.md`
- Implementation plans: `docs/superpowers/plans/`

## Development

Requires Python 3.10. From the repo root:

```sh
py -3.10 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest -v
```

## Layout

- `gazette/` — core library (no PyQt6 dependency): storage, migrations, models, repo
- `gazette_app/` — PyQt6 front-end (future sub-project)
- `tests/` — pytest suite
