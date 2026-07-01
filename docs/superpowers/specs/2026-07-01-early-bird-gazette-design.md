# Early Bird Gazette — Design Spec

**Date:** 2026-07-01
**Status:** Draft for review
**Location:** `C:\AI\Early Bird Gazette\`

## 1. Overview

Early Bird Gazette is a local, single-user Windows desktop app (PyQt6) that ingests AI
"tricks & techniques" (Stable Diffusion image generation, LoRA training, Anima, local
LLMs) from online sources, uses a local LLM to extract them into structured records,
deduplicates them, and stores everything in one SQLite database. Sibling apps in the
`C:\AI\` suite (Lora_Trainer / kohya_ss, Anima Forge, Animus Image Tagger / Sorter,
Lora Interrogator) consume that database as a shared read source.

The system is **domain-agnostic by construction**: new sources are added by config +
a small connector class; new domains are added by a domain classifier plugin. Neither
requires rewriting the pipeline core.

### Design decisions locked in this session

- **Local LLM:** GPU + `llama.cpp` already available. Extraction calls a running
  **`llama-server` HTTP endpoint** with GBNF / JSON-schema constrained output.
- **Ingestion trigger:** **Manual only** (per-source and "ingest all" buttons). No
  background scheduler.
- **Curation model:** **Auto-publish with confidence flag.** Extracted techniques are
  written directly as `published`, tagged with the LLM's confidence score. No review
  queue; the UI provides confidence filtering plus edit/delete.
- **Integration:** **No MCP server.** Integration is a **shared WAL-mode SQLite file**
  plus a small importable **Python query client library** that sibling apps use for
  read access.
- **Connector mechanism:** **Decorator registry** (`@register_source("github")`) +
  YAML source registry. No pluggy / entry-points (YAGNI for a solo desktop suite).
- **Package structure:** **Two packages in one repo** — `gazette` (core library, no
  PyQt6 dependency) and `gazette_app` (PyQt6 front-end). Sibling apps import `gazette`
  only.

### Explicitly out of scope / deferred

- Background scheduling, review queue, MCP server (removed per decisions above).
- Reddit and YouTube connectors (designed behind the connector interface; built in a
  later stage after Reddit app pre-approval / when needed).
- Discord ingestion (excluded — ToS/legal risk; manual paste only if ever needed).
- A dedicated vector database (unwarranted below ~10M records).

## 2. Sub-project roadmap & build order

Each sub-project gets its own spec → plan → build cycle. This spec covers the whole
architecture so the pieces fit; P1–P8 are the concrete near-term build.

| #  | Sub-project | Delivers | Depends on |
|----|-------------|----------|------------|
| P1 | Core storage + schema | `gazette` skeleton, SQLite (WAL) schema, migrations, FTS5 + sqlite-vec setup, low-level DB access | — |
| P2 | Query client library | Reusable read API for sibling apps (`search`, `get_by_domain`, hybrid RRF search, filters) | P1 |
| P3 | Connector framework + GitHub | Decorator registry, `SourceConnector` interface, YAML registry, incremental state, GitHub connector | P1 |
| P4 | Extraction pipeline | Rule pre-filter → `llama-server` GBNF/JSON extraction → Pydantic validation | P1 |
| P5 | Dedup cascade | SHA-256 → MinHash/LSH → embedding cosine, cluster IDs, `dedup_key` | P1, P4 |
| P6 | Ingestion orchestration | Wires P3→P4→P5→P1 into one manual "ingest source" run with stats/logging | P3, P4, P5 |
| P7 | PyQt6 app | Browse/search/filter, source management, "ingest now", edit/delete, confidence filter | P2, P6 |
| P8 | More connectors | Civitai, HuggingFace (later Reddit/YouTube behind same interface) | P3, P4 |
| P9 | Domain layer scaling | Additional domain classifiers, tag-vocabulary normalization, embedding-based tag suggestion | P4 |

**Stage mapping to research doc:** P1–P8 (Civitai/HF) = Stage 1 MVP + real UI.
Reddit/YouTube = Stage 2. P9 = Stage 3.

## 3. Architecture / layers

Repo layout (two packages, one repo):

```
Early Bird Gazette/
  gazette/                  # core library — NO PyQt6 dependency
    storage.py             # connection mgmt (WAL pragmas), schema/migrations, load sqlite-vec + FTS5
    models.py              # Pydantic models: Technique, SourceItem, Parameter, Tag, RawRecord
    client.py              # read API used by sibling apps (hybrid RRF search, filters)
    config.py              # YAML config + secrets resolution
    secrets.py             # token resolver (env var, then keyfile) — no fallbacks/dummy
    sources/
      registry.py          # @register_source decorator + type->class map
      base.py              # SourceConnector interface (Singer-style get_records())
      github.py            # GitHub connector (P3)
      civitai.py           # (P8)
      huggingface.py       # (P8)
    extract/
      prefilter.py         # cheap keyword/rule pre-filter
      llm.py               # llama-server client, GBNF/json_schema request
      schema.py            # extraction JSON schema + Pydantic validation + retry
    dedup/
      cascade.py           # 3-tier: hash -> MinHash/LSH -> embedding cosine
    embed/
      backend.py           # swappable embedding backend (default sentence-transformers)
    pipeline.py            # orchestrates a manual ingest run
  gazette_app/             # PyQt6 front-end — depends on gazette
    main.py
    ...
  config.yaml
  sources.yaml
  data/gazette.db          # shared WAL SQLite (source of truth)
  docs/superpowers/specs/
  tests/
```

**Write ownership:** only the Gazette app / pipeline writes to the DB (single writer,
`BEGIN IMMEDIATE`, `busy_timeout`). Sibling apps open **read-only** connections
(`mode=ro`) or import `gazette.client`. WAL mode allows unlimited concurrent readers +
one writer.

## 4. Data model (SQLite)

Pragmas on every connection:
`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000; PRAGMA foreign_keys=ON;`

Core tables:

- `techniques` (id, title, summary, body, domain_id FK, dedup_key, cluster_id,
  confidence REAL, is_actionable INT, status TEXT default 'published',
  domain_meta JSON, created_at, updated_at, first_seen_at)
- `sources` (id, type, name, url, config_ref)
- `source_items` (id, source_id FK, external_id, url, author, raw_text,
  content_hash, fetched_at)
- `technique_sources` (technique_id FK, source_item_id FK, score, upvotes) — M:N;
  a technique can be attested by multiple source items (corroboration count)
- `tags` (id, name, tag_type), `technique_tags` (technique_id FK, tag_id FK)
- `domains` (id, name, parent_id) — the domain tree (SD, LoRA training, Local LLMs…)
- `parameters` (id, technique_id FK, key, value, unit) — structured settings
- `ingest_state` (source_id, key, value) — ETags / last-seen cursors per source
- `schema_migrations` (version, applied_at)

Search virtual tables:

- `techniques_fts` — FTS5 over (title, summary, body), external-content mirror of
  `techniques` keyed by rowid, kept in sync by triggers.
- `technique_vec` — sqlite-vec `vec0` table storing the embedding, keyed by
  rowid = `techniques.id`. Dimension configurable (default 384).

Domain-specific fields live in `domain_meta` JSON, never as per-domain columns.

**Auto-publish:** `status` defaults to `'published'`; `confidence` carries the LLM
score for filtering. `status` retained for future edit/delete/archive/hide.

## 5. Ingestion & connectors (P3, P8)

- `sources.yaml` declares source *instances* as data:
  `{type, name, domain, params, enabled}`. Adding a new instance = pure config.
- `@register_source("github")` maps `type` → connector class.
- `SourceConnector` base: `get_records() -> Iterator[RawRecord]` (Singer-style).
  `RawRecord` = normalized dict (`external_id`, `url`, `author`, `raw_text`,
  `metadata`, `score`/`upvotes`, `fetched_at`).
- **Incremental state:** connectors read/write `ingest_state`. GitHub uses
  ETag/Last-Modified conditional requests — a `304` doesn't count against the rate
  limit; ideal for polling releases/README/PRs cheaply.

Connectors:

- **GitHub (P3):** authenticated REST via `httpx` (5,000 req/hr auth). Polls
  releases, PRs, issues, discussions for configured repos (e.g. `kohya-ss/sd-scripts`).
  Conditional requests. Highest-value, lowest-risk source for training-technique deltas.
- **Civitai (P8):** REST `/models`, `/images` (generation params), articles, comments.
  API token optional for reads. Note: REST text-search unreliable since ~2025 → MVP
  relies on listing/browse endpoints; Meilisearch/community-MCP path is a later option.
- **HuggingFace (P8):** `huggingface_hub` (v1.2+) client for model cards, community
  discussions, papers.
- **Reddit / YouTube (deferred):** designed behind the same interface; Reddit via PRAW
  on the official OAuth free tier *after* app pre-approval; YouTube via
  `youtube-transcript-api` from the local residential IP, LLM-distilled.

## 6. Extraction pipeline (P4)

Two-stage:

1. **Pre-filter** (`extract/prefilter.py`): cheap keyword/rule + length heuristics to
   discard obvious non-techniques and cut LLM volume. Config-driven keyword lists.
2. **LLM extraction** (`extract/llm.py`): for each candidate, call the running
   `llama-server` (`/v1/chat/completions` with `response_format` json_schema, or
   `/completion` with a GBNF grammar generated from the schema). The grammar constrains
   **syntax only** — the field descriptions are also stated in the prompt.

Extraction output schema (`extract/schema.py`, Pydantic v2):
`title, technique_summary, steps[], domain, tools[],
parameters[{key,value,unit}], preconditions, confidence(0..1),
is_actionable(bool), tags[]`.

Pydantic validation + **retry loop** (N retries on validation failure) handles logical
(not just syntactic) errors from small models. Records with `is_actionable=false` are
dropped. Model + endpoint configurable in `config.yaml`.

## 7. Dedup cascade (P5)

Three tiers, cheapest first:

1. **Exact/normalized SHA-256** — lowercase, strip punctuation/markdown/URLs → `dedup_key`.
   Verbatim reposts dropped for free. If key exists, attach a new `technique_sources`
   attestation (corroboration) instead of creating a duplicate technique.
2. **Lexical near-dup** — MinHash + LSH via `datasketch` (1.10.0; `num_perm=128`,
   threshold ~0.8), confirm LSH candidates with exact Jaccard.
3. **Semantic near-dup** — embedding cosine (via `SemHash` 0.3.1 or manual sqlite-vec
   KNN). Threshold ~0.85 for "duplicate." Assigns `cluster_id`.

**Cluster policy:** one canonical technique per cluster (keep the higher-confidence /
more-complete record); additional matches recorded as attestations and increment a
corroboration count. Thresholds are calibration starting points, set in config.

## 8. Storage, embeddings & search (P1, P2)

- **Hybrid search:** FTS5 BM25 + sqlite-vec KNN combined with **Reciprocal Rank
  Fusion** (RRF, k=60). FTS5 wins precision (exact terms / parameter names like
  `--fused_backward_pass`); vectors win recall (fuzzy concepts).
- **Client filters:** domain, tags, min_confidence, tools, date.
- **Embeddings (`embed/backend.py`, swappable):** **default `sentence-transformers`
  `all-MiniLM-L6-v2` (384-dim)** — reliable, decoupled from the extraction model server.
  Config option: **EmbeddingGemma (308M)** via a `llama-server` embeddings endpoint, or
  Model2Vec static embeddings for max CPU speed. Dimension is config-driven so the
  `technique_vec` table matches the chosen backend.

## 9. Integration (P2)

- **Shared WAL SQLite** at `C:\AI\Early Bird Gazette\data\gazette.db` is the source of
  truth for reads.
- **`gazette.client.TrickDB(db_path)`** read API (read-only connection): `search()`,
  `get(id)`, `get_by_domain()`, `get_by_tool()`, `list_tags()`. WAL permits concurrent
  readers alongside the app's single writer.
- Writes go only through the Gazette app/pipeline.
- Ship a short usage snippet so sibling apps (Lora_Trainer, Anima Forge, taggers) can
  import and query in a few lines.

## 10. PyQt6 app (P7)

- **Browse/Search tab:** hybrid search bar; filter panel (domain tree, tags,
  min-confidence slider, tools); results list; detail pane (title, summary, steps,
  parameters table, source links, confidence badge, tags). Edit/delete actions.
- **Sources tab:** list of `sources.yaml` instances; enable/disable; "Ingest now" per
  source + "Ingest all"; last-run stats; progress/log view; add/edit source instance
  (type dropdown, params form, domain).
- **Management:** inline edit, delete, cluster/duplicate view for merging.
- **Settings:** llama-server endpoint + model, embedding backend, DB path, token
  location.
- **Threading:** ingestion runs on a QThread worker so the UI stays responsive; all
  writes funnel through the single-writer pipeline.

## 11. Config & secrets

- `config.yaml`: db path, llama-server url + model, embedding backend + model, dedup
  thresholds, pre-filter keywords.
- `sources.yaml`: source instances.
- **Secrets** (`secrets.py`): resolve tokens from environment variables first, then a
  keyfile in the existing `C:\AI\api keys, tokens, pass` folder. Config references key
  *names*, never inlines secrets. **No fallbacks / dummy values** — a missing required
  token is a hard error (per project rule: no fallbacks, dummy data, or placeholders).

## 12. Testing strategy

- **Unit tests per layer:** storage (temp db), connectors (mocked HTTP with recorded
  fixtures), extraction (mocked `llama-server` responses; assert schema validation +
  retry), dedup (known duplicate / near-dup / semantic fixtures), client search
  (seeded db, assert RRF ordering).
- **Integration test:** end-to-end ingest run over fixture data → DB assertions.
- **TDD** per the superpowers workflow while building each sub-project.

## 13. Key risks & open items

- **sqlite-vec extension loading on Windows:** stock CPython `sqlite3` frequently ships
  with `enable_load_extension` disabled. **First build task (P1) is a spike** to confirm
  we can load the `sqlite-vec` extension; fallback is `apsw` or a sqlite build with
  load-extension enabled.
- **API terms/pricing drift:** GitHub (auth limits tightened May 2025), HuggingFace
  (bucketed limits), Civitai (REST search unreliable), Reddit (per-app pre-approval,
  $12k/mo commercial tier) — all abstracted behind the connector interface so changes
  stay localized.
- **Small-model extraction errors:** grammar guarantees syntax, not correctness →
  Pydantic validation + confidence flag + edit/delete are the mitigations.
- **Dedup thresholds** are per-model/domain starting points → calibrate empirically,
  keep in config.
- **Anima is preview/non-commercial** and changing fast → reinforces continuous
  ingestion from GitHub/Civitai.

## 14. Version anchors

pluggy 1.6.0 (not used — decorator registry chosen), datasketch 1.10.0, semhash 0.3.1,
huggingface_hub 1.2.0+, sqlite-vec (single-file extension), EmbeddingGemma (308M,
Sept 2025), sentence-transformers `all-MiniLM-L6-v2` (384-dim), PyQt6, Pydantic v2,
Python 3.10.
