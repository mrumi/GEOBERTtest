# GeoBERT 

GeoBERT is a production-grade Retrieval-Augmented Generation system for discovering and exploring GEO (Gene Expression Omnibus) datasets through natural language queries. It combines hybrid dense + sparse vector retrieval, cross-encoder reranking, biomedical ontology resolution, and an LLM answer generator into a full-stack web application with multi-user authentication and session memory.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Prerequisites](#prerequisites)
3. [Environment Setup](#environment-setup)
4. [Qdrant Setup with Docker](#qdrant-setup-with-docker)
5. [Backend Setup](#backend-setup)
6. [Database Setup with Alembic](#database-setup-with-alembic)
7. [Data Ingestion](#data-ingestion)
8. [Running the Backend](#running-the-backend)
9. [Frontend Setup](#frontend-setup)
10. [Running the Full Stack](#running-the-full-stack)
11. [Important Operational Notes](#important-operational-notes)
12. [GEO JSON Datasets Maker Pipeline](#geo-json-datasets-maker-pipeline)

---

## Project Structure

```
GEOBERT/
├── api/
│   ├── dependencies.py         # FastAPI dependency injection (auth, clients, settings)
│   ├── schemas.py              # Pydantic request/response models (API contract)
│   └── routes/
│       ├── auth.py             # POST /auth/register, POST /auth/login, GET /auth/me
│       ├── datasets.py         # GET /datasets/{gse_id} — direct Qdrant lookup, no ranking
│       ├── query.py            # POST /query — main RAG endpoint
│       └── sessions.py         # GET/POST/DELETE /sessions, GET /sessions/{id}
├── alembic/
│   ├── env.py                  # Reads DATABASE_URL from .env automatically
│   └── versions/
│       ├── 603f15ad2dd3_initial_schema.py
│       └── f01d3e76d98d_add_result_snapshot_to_messages.py
├── cache/                      # SQLite organism cache — auto-created at startup
├    ├── ontology_cache.db                      
├── core/
│   ├── clients.py              # All ML models + clients loaded once at startup
│   ├── config.py               # Pydantic-settings — reads from .env
│   ├── database.py             # SQLAlchemy async engine + session factory
│   └── security.py             # JWT + bcrypt password hashing
├── data/
│   ├── studies/                # GEO study JSON files — add yours here
│   └── samples/                # GEO sample JSON files — add yours here
├── frontend/                   # Next.js 16 + React 19 + TypeScript + Tailwind
│   └── src/
│       ├── app/
│       │   ├── layout.tsx      # Root layout with ThemeProvider (dark/light/system)
│       │   ├── page.tsx        # Main dashboard — auth guard + full state management
│       │   ├── login/          # Login page (email + password)
│       │   └── register/       # Register page (full_name, username, email, password, role)
│       ├── components/
│       │   ├── dashboard/
│       │   │   ├── chat-box.tsx
│       │   │   ├── dataset-detail-dialog.tsx
│       │   │   ├── result-card.tsx
│       │   │   ├── results-panel.tsx
│       │   │   ├── sample-card.tsx
│       │   │   ├── session-history-panel.tsx
│       │   │   ├── stat-bar.tsx
│       │   │   └── stats-quality-panel.tsx
│       │   ├── theme-provider.tsx
│       │   └── theme-toggle.tsx
│       └── lib/
│           ├── api.ts          # All API calls — reads NEXT_PUBLIC_API_BASE_URL
│           ├── auth-store.ts   # JWT in localStorage (getToken/setToken/clearToken)
│           └── types.ts        # TypeScript types mirroring schemas.py
├── indexing/
│   ├── chunker.py              # Token-based parent-child chunker (PubMedBERT tokenizer)
│   ├── document_parser.py      # parse_study_json() + parse_sample_json()
│   ├── qdrant_manager.py       # ensure_collection() + payload indexes
│   ├── registry_manager.py     # Incremental indexing registry
│   └── vector_uploader.py      # Batch dense + sparse embed + Qdrant upsert
├── models/
│   ├── message.py              # Message ORM — stores full result snapshot (JSONB)
│   ├── session.py              # ChatSession ORM — multi-turn conversation thread
│   └── user.py                 # User ORM — full_name, username, email, role
├── rag/
│   ├── answer_generator.py     # XML-tagged evidence-grounded LLM prompt
│   ├── hybrid_search.py        # Dense + sparse retrieval, MatchText filter, boosts
│   ├── organism_resolver.py    # NCBI Taxonomy resolution + SQLite cache + retry
│   ├── query_understanding.py  # Single merged LLM call — intent + filters + concepts
│   ├── rag_node.py             # Full pipeline orchestrator
│   ├── result_aggregator.py    # Dashboard stats computation
│   ├── sparse_vector.py        # SPLADE sparse vector generation
│   └── state.py                # GeoState TypedDict
├── registry/                   # Indexing registry — auto-created during ingestion
├── scripts/
│   └── run_indexing.py         # CLI ingestion script
├── .env.example                # Environment template
├── alembic.ini                 # Alembic config (sqlalchemy.url auto-overridden)
├── main.py                     # FastAPI app + lifespan startup hook
└── requirements.txt            # Python dependencies
```

---

## Prerequisites

- **Python 3.11+** — [python.org](https://www.python.org/downloads/)
- **Node.js 20+** — required by Next.js 16 — [nodejs.org](https://nodejs.org/)
- **Docker Desktop** — required for Qdrant — [docker.com](https://www.docker.com/products/docker-desktop/)
- **PostgreSQL 15+** — local install or managed cloud database
- **Groq API key** — [console.groq.com](https://console.groq.com/)
- **HuggingFace token** — optional but recommended — [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)

---

## Environment Setup

**Step 1 — Clone the repository:**
```bash
git clone repo
```

**Step 2 — Copy the environment template:**
```bash
cp .env.example .env
```

**Step 3 — Fill in `.env`:**
```env
# ── Required ──────────────────────────────────────────────────

# Groq LLM API key — get from console.groq.com
GROQ_API_KEY=your_groq_api_key_here

# PostgreSQL async connection string
# Local: postgresql+asyncpg://postgres:yourpassword@localhost:5432/geobert
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_DATABASE_PASSWORD@localhost:5432/geobert

# JWT secret 
JWT_SECRET_KEY=your_64_character_random_hex_string_here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

# ── Optional ───────────────────────────────────────────────────

# HuggingFace token — avoids rate limiting during model downloads
HF_TOKEN=hf_your_token_here

# Qdrant — default is local Docker, no API key needed for local
QDRANT_API_KEY= your key here [ only for cloud setup]

```

**Step 4 — Create and activate a Python virtual environment:**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

```

**Step 5 — Install Python dependencies:**
```bash
pip install -r requirements.txt
```

> **Note on first-run model downloads:** PubMedBERT (~400MB), SPLADE (~500MB), and the cross-encoder (~80MB) are downloaded from HuggingFace on first startup. Set `HF_TOKEN` in `.env` to avoid rate limiting.

---

## Qdrant Setup with Docker

> **Qdrant must be running before ingesting data or starting the backend.**
> **After every system reboot, run `docker start qdrant` before starting the backend.**

**Step 1 — Create a named Docker volume:**
```bash
docker volume create qdrant_storage
```

**Step 2 — Run the Qdrant container:**
```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

**Step 3 — Verify Qdrant is running:**
```bash
curl http://localhost:6333
# Returns: {"title":"qdrant","version":"..."}
```

Qdrant dashboard: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

**Stop Qdrant:**
```bash
docker stop qdrant
```

**Start Qdrant after reboot:**
```bash
docker start qdrant
```

> The named volume `qdrant_storage` keeps all indexed vectors safe across container restarts. Never run `docker volume rm qdrant_storage` unless you intend to delete all indexed data.

---

## Backend Setup

All commands run from `GEOBERT/` with the virtual environment activated.

---

## Database Setup with Docker

GeoBERT uses PostgreSQL for users, sessions, and message history with full result snapshots.

**Step 1 — Create a named Docker volume:**
```bash
docker volume create postgres_storage
```

**Step 2 — Run the Qdrant container:**
```bash
docker run -d \
  --name postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=YOUR_DATABASE_PASSWORD \
  -e POSTGRES_DB= geobert \
  -p 5432:5432 \
  -v postgres_storage:/var/lib/postgresql/data \
  postgres:17
```

## Database Align with Alembic

> `alembic/env.py` reads `DATABASE_URL` directly from your `.env` file. You do not need to edit `alembic.ini`.

**Step 1 — Run all migrations:**
```bash
alembic upgrade head
```

This runs two migrations in order:
- `603f15ad2dd3` — creates `users`, `sessions`, `messages` tables
- `f01d3e76d98d` — adds `studies`, `samples`, `dashboard_stats` JSONB columns to `messages`

**Step 2 — Verify:**
```bash
alembic current
# Should show: f01d3e76d98d (head)
```

**Useful Alembic commands:**
```bash
alembic history          # show all migrations
alembic downgrade -1     # roll back one migration

# For contributors adding new models/columns:
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

> Always use `--autogenerate` for new migrations. The first migration was hand-authored before a live database was available — all future migrations must use `--autogenerate`.

> When pulling new code with new migrations, always run `alembic upgrade head` before restarting the backend.

---

## Data Ingestion

> Qdrant must be running before ingestion.

**Step 1 — Place your GEO JSON files:**
```
data/studies/GSE296973.study.json
data/studies/GSE298119.study.json
...

data/samples/GSE296973.samples.json
data/samples/GSE298119.samples.json
...
```

**Step 2 — Run the indexing script from `GEOBERT/`:**
```bash
python scripts/run_indexing.py
```

> Run from `GEOBERT/`, not from inside `scripts/`. The script handles the path automatically.

**What the script does:**
- Creates Qdrant collections with dense (PubMedBERT, 768-dim cosine) + sparse (SPLADE) vectors
- Creates payload indexes for all metadata fields with correct types:
  - Identity fields (gse_id, gsm_id, parent_id, field, level) → KEYWORD (exact match)
  - Content fields (organism, tissue, disease, library_strategy, etc.) → TEXT with word tokenizer + lowercase (case-insensitive matching)
  - Series fields (is_superseries, is_subseries, parent_series_id, subseries_ids) → KEYWORD
- Parses study JSONs into parent-child token-based chunks (256 tokens, 50 overlap)
  - Each study produces 6–12 chunks from: title, study_summary, overall_design, protocol_* fields, data_processing, and optionally series_relationships
- Parses sample JSONs as one chunk per GSM — samples are fully self-contained, no study-level inheritance
- Embeds all chunks with PubMedBERT (dense) and SPLADE (sparse) in batches of 32
- Uses deterministic UUID5 point IDs — same content always gets the same ID, re-uploads overwrite instead of duplicating
- Tracks indexed files in `registry/indexed_studies.json` and `registry/indexed_samples.json`
- Skips already-indexed files — safe to re-run when adding new data

**Expected output:**
```
=== Checking Qdrant Collections ===
Creating collection: geo_study_collection
Creating collection: geo_sample_collection

=== Phase 1 — Indexing Studies ===
Study files found: 21
  [index]  GSE296973 → 8 chunks uploaded
  [index]  GSE298119 → 5 chunks uploaded
  ...

=== Phase 2 — Indexing Samples ===
  [file]   GSE296973.samples.json → 20 samples uploaded
  ...

=== Final Registry Status ===
Indexed studies : 21
Indexed samples : 772
```

**To add new data later:**
Place new JSON files in `data/studies/` or `data/samples/` and re-run the script. Already-indexed files are skipped.

**To re-index everything from scratch:**
```bash
# Delete collections
curl -X DELETE http://localhost:6333/collections/geo_study_collection
curl -X DELETE http://localhost:6333/collections/geo_sample_collection

# Delete registry
rm registry/indexed_studies.json
rm registry/indexed_samples.json

# Re-ingest
python scripts/run_indexing.py
```

---

## Running the Backend

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

**What happens at startup:**
1. `settings.ensure_directories()` — creates `cache/` and `registry/` directories if missing
2. `AppClients.load(settings)` — loads PubMedBERT, SPLADE, cross-encoder (~30–60s on first run)
3. `OrganismResolver` — creates SQLite organism cache at `cache/ontology_cache.db` if not present
4. `prewarm_common_organisms()` — makes ~30 NCBI Taxonomy API calls on first run to pre-cache common organisms (human, mouse, rat, zebrafish, etc.). Subsequent startups serve all from cache instantly

> **First startup takes 1–3 minutes longer than subsequent starts** due to model loading and organism pre-warming. Wait for the ready log message before sending queries.

---

## Frontend Setup

From `GEOBERT/frontend/`:

**Step 1 — Install dependencies:**
```bash
npm install
```

**Step 2 — Create `frontend/.env.local`:**
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001
```
---

## Running the Full Stack

Three terminals simultaneously:

**Terminal 1 — Qdrant or Use Docker application:**
```bash
docker start qdrant
```

**Terminal 2 — Backend (from `GEOBERT/`, venv activated):**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

**Terminal 3 — Frontend (from `GEOBERT/frontend/`):**
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

**First-time setup:**
1. Click **Register** — fill in Full Name, Username, Email, Password, Role (Researcher / Clinician / Student / Admin)
2. You are logged in automatically after registration
3. Type a biomedical query (e.g. "Find human retina RNA-seq datasets comparing control vs disease")
4. Study cards appear in the Results panel with relevance scores
5. Click **Details** on any card to see full study text, all samples, and series relationships
6. The LLM answer appears in the chat section below

**Dashboard features:**
- **Stat bar** — Datasets / Samples / Platforms / Tissues counts for the current query
- **Results panel** — study cards (organism, tissue, library strategy, score) and sample cards
- **SuperSeries/SubSeries badges** — shown conditionally only when a study has series relationships
- **Stats & Quality** — platform distribution, Query Match %, Metadata Match %, top fields matched
- **Chat** — conversation history with the LLM answer and suggested follow-up queries
- **"Query X of Y" navigation** — switch between past query results in the same session without re-running them (result snapshots are stored in PostgreSQL per turn)
- **Session history** — past sessions with auto-generated titles (first 42 chars of first query), download and delete options available.
- **Dark / Light / System theme** — toggle in header, defaults to system preference
- **Logout** — button in top-right header

---

## Important Operational Notes

**Qdrant must always be running.** After every system reboot:
```bash
docker start qdrant   # before starting the backend
```

**CORS allows `localhost:3000` and `localhost:5173`.** Port 5173 is a Vite leftover in `main.py` — the active frontend runs on port 3000. In production, update `allow_origins` in `main.py` to your frontend domain only.

**Default retrieval config(core/config) is tuned for large collections (1000+ studies):**

| Setting | Value | Description |
|---|---|---|
| `GROQ_QUERY_MODEL` | `openai/gpt-oss-120b` | LLM used for query understanding / query processing |
| `GROQ_ANSWER_MODEL` | `openai/gpt-oss-120b` | LLM used for generating the final answer |
| `DENSE_EMBED_MODEL` | `neuml/pubmedbert-base-embeddings` | Model used to generate dense embeddings |
| `SPARSE_EMBED_MODEL` | `prithivida/Splade_PP_en_v1` | Model used to generate sparse embeddings |
| `CROSS_ENCODER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder used for reranking retrieved chunks |
| `QDRANT_URL` | `http://localhost:6333` | Local Qdrant vector database endpoint |
| `TOP_K_STUDY_RETRIEVAL` | `250` | Study chunks retrieved before reranking |
| `TOP_K_SAMPLE_RETRIEVAL` | `50` | Sample chunks retrieved independently |
| `TOP_K_AFTER_RERANK` | `30` | Study chunks kept after cross-encoder reranking |
| `TOP_K_SAMPLE_AFTER_RERANK` | `10` | Sample chunks kept after cross-encoder reranking |
| `SIM_THRESHOLD` | `0.20` | Minimum dense similarity to pass the threshold gate |
| `ALPHA_DENSE` | `0.65` | Dense vector weight in hybrid fusion |
| `ALPHA_SPARSE` | `0.40` | Sparse vector weight in hybrid fusion |
| `FIELD_FOCUS_BOOST` | `0.15` | Boost applied to chunks matching `semantic_focus_fields` |
| `FIELD_MATCH_BOOST` | `0.10` | Boost applied to chunks matching filter field values |


**Organism cache.** `cache/ontology_cache.db` is permanent — delete only to force fresh NCBI lookups.

**Registry files.** Do not delete `registry/indexed_studies.json` or `registry/indexed_samples.json` unless you intend to re-index everything.

**Model loading.** PubMedBERT, SPLADE, and the cross-encoder are loaded once at startup and shared across all requests. Do not kill and restart the backend frequently — each restart triggers a 30–60 second model reload.

---

# GEO JSON Datasets Maker Pipeline

A pipeline that discovers GEO Series (GSE) studies published in a date range,
fetches their study + sample metadata, and normalizes each one into two clean JSON files
ready for downstream use (e.g. embedding/LLM ingestion).

## What it does (3 stages)

1. **Discover** — Queries NCBI E-utilities for every GSE accession published in a given
   date range and registers each ID in a local SQLite **registry** with status `discovered`.
2. **Ingest** — Downloads a bounded batch of not-yet-fetched GSEs. Each GSE's SOFT file is
   downloaded directly over HTTPS (with size verification against the server's
   `Content-Length` and automatic retries), then parsed locally by GEOparse — no reliance
   on GEOparse's own FTP fetch. Study + full sample metadata is saved into SQLite. Registry status becomes `fetched`
   (or `failed`, with the error saved, if a GSE couldn't be downloaded).
   SuperSeries are detected automatically — any SubSeries they reference are registered
   for a future run.
3. **Normalize** — Every registry row that's `fetched` (or previously `normalize_failed`)
   is read straight out of SQLite and converted into two clean JSON documents.

The **SQLite database is the single source of truth** — it doubles as a fetch/normalize
**registry**, so re-running the pipeline never re-downloads or re-processes a GSE that's
already done. You can safely stop and restart it at any point.

## How to run

Optional (recommended) — create a `.env` file next to the script for higher NCBI rate limits:
```
NCBI_API_KEY=your_key_here
NCBI_EMAIL=your_email@example.com
```

Run the notebook cell. Example input parameters:
```python
config = PipelineConfig(
    start_date="2026/01/01",   # or use year=2026, month=6, or years_back=5
    end_date="2026/05/31",
    fetch_limit=50,            # how many *new* GSEs to fetch this run
)
run_pipeline(config)
```

Every run does: discover (unless `skip_discovery=True`) → fetch up to `fetch_limit` new
GSEs → normalize everything that's fetched but not yet normalized. Just re-run to continue where it left off.

## Files it creates

All output lives under `geo_work/` (configurable via `PipelineConfig.base_dir`):

| Path | What it is | When it's created |
|---|---|---|
| `geo_work/geo_data.db` | SQLite database — **the registry + all raw fetched data** | On first run |
| `geo_work/geo_cache/{gse_id}_family.soft.gz` | Downloaded raw SOFT file per GSE (cache) | During ingest |
| `geo_work/studies/{gse_id}.study.json` | Final normalized **study-level** JSON | During normalize |
| `geo_work/samples/{gse_id}.sample.json` | Final normalized **sample-level** JSON | During normalize |

No other intermediate files are written — only the final `.study.json` / `.sample.json`
per GSE, plus the SOFT cache and the database.

## How tracking/resumability works

Everything is tracked in one SQLite table, `gse_registry`, keyed by `gse_id`:

| Status | Meaning |
|---|---|
| `discovered` | Found by NCBI search, not yet fetched |
| `fetched` | Metadata downloaded and stored in `gse_data`, ready to normalize |
| `normalized` | Final study/sample JSON written — fully done |
| `failed` | Ingest (download/parse) failed — `error` column has the reason; retried automatically next run |
| `normalize_failed` | Normalization failed after a successful fetch; retried automatically next run |


## Configuration knobs (all optional, on `PipelineConfig`)

| Param | Default | Purpose |
|---|---|---|
| `fetch_limit` | 50 | Max new GSEs to ingest in one run |
| `years_back` | 5 | Rolling discovery window if no explicit date is given |
| `start_date` / `end_date` | — | Explicit date range, format `YYYY/MM/DD` |
| `year` / `month` | — | Discover one calendar month or year |
| `max_concurrent_fetches` | 4 | Parallel GSE downloads |
| `geo_fetch_timeout_seconds` | 90 | Per-download HTTPS timeout |
| `skip_discovery` | False | Skip NCBI search; just keep working through the existing registry |
