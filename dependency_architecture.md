# Dependency & Architecture Reference

## Runtime Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| API Framework | FastAPI | >=0.115.0 | Lifespan context manager (no `@app.on_event`) |
| ASGI Server | Uvicorn | >=0.30.6 | `[standard]` extras for websocket + reload support |
| WebSocket | websockets | >=13.1 | Used by Uvicorn; Phase 2 WS interview router |
| Python | CPython | 3.14.x | Homebrew install; drives all version constraints below |

## Databases

| Store | Technology | Driver | Version | Purpose |
|---|---|---|---|---|
| Relational | PostgreSQL 16 | asyncpg | 0.30.0 | Users, sessions, scores |
| Document | MongoDB 7 | Motor | 3.6.0 | Interview transcripts; knowledge base |
| Cache / Pub-Sub | Redis 7 | redis[hiredis] | 5.2.0 | Session state (turn history, difficulty, domain) |
| Vector DB | Qdrant (self-hosted) | qdrant-client | >=1.9 | Knowledge base embeddings; future scraped interview embeddings |

### Docker Images
```
postgres:  pgvector/pgvector:pg16   # kept as-is (superset of postgres:16); vector extension dropped via migration
mongo:     mongo:7
redis:     redis:7-alpine
qdrant:    qdrant/qdrant:latest
```

### PostgreSQL Extensions
- `pgcrypto` — `gen_random_uuid()` for UUID primary keys
- `vector` extension **removed** in migration `0002_drop_embeddings` — vectors now in Qdrant

## ORM & Migrations

| Component | Technology | Version | Notes |
|---|---|---|---|
| ORM | SQLAlchemy (asyncio) | >=2.0.38 | 2.0.38+ required for Python 3.14 `typing.Union` fix |
| Migrations | Alembic | 1.13.3 | Async env.py; `include_object` hook removed (vector column suppression no longer needed) |

### Migration History
| ID | Description |
|---|---|
| `0001` | Initial schema — users, sessions, scores, embeddings tables; vector + pgcrypto extensions |
| `0002` | Drop embeddings table + vector extension — vectors migrated to Qdrant |
| `0003` | Auth (Phase 7) — `users.email` made nullable; added `users.phone_number`, `password_hash`, `is_alpha_tester`; check constraint `email IS NOT NULL OR phone_number IS NOT NULL`; new tables `oauth_identities`, `user_api_keys` |
| `0004` | BYOK follow-up (Phase 7) — `user_api_keys.base_url` (arbitrary OpenAI-compatible providers); `sessions.llm_provider` (nullable, `None` = app default) |
| `0005` | Phase 8 — `sessions.resume_text` (nullable Text, uploaded resume PDF, extracted); `sessions.target_minutes` (nullable Integer, resolved interview duration target) |
| `0006` | Phase 9 — `users.is_guest` (bool, default false), `users.free_sessions_used` (int, default 0); `ck_users_email_or_phone` relaxed to `is_guest OR email IS NOT NULL OR phone_number IS NOT NULL` |

### Migration Strategy
- ENUM types created via `op.execute("CREATE TYPE ... AS ENUM ...")` before tables
- Column definitions use `postgresql.ENUM(..., create_type=False)`

## Validation & Config

| Component | Technology | Version | Notes |
|---|---|---|---|
| Schemas | Pydantic | >=2.10 | 2.10+ required for Python 3.14 pre-built wheels (stable ABI) |
| Settings | pydantic-settings | >=2.7 | `.env` file loading |

## AI / ML Services

| Component | Technology | Version | Notes |
|---|---|---|---|
| LLM (cloud, app-default — Phase 9) | Google Gemini | openai>=1.0 client (OpenAI-compat endpoint) | Model: `gemini-2.5-flash-lite` — deliberately the cheapest current Gemini model ($0.10/$0.40 per 1M tokens), chosen over newer/pricier 3.x Flash-Lite generations. Two API keys on **separate Google Cloud projects** (Gemini rate limits are enforced per-project, not per-key — same-project keys would share one quota pool and defeat the purpose), each a tier in the wider `FailoverLLMService` chain below |
| LLM (cloud, first-preference fallback — Phase 12 follow-up) | NVIDIA NIM | openai>=1.0 client (OpenAI-compat endpoint, `https://integrate.api.nvidia.com/v1`) | Model: `nvidia/nemotron-3-super-120b-a12b`. Free tier's best observed RPM among the free options checked (~40 RPM), but NVIDIA does not publish a guaranteed quota — dynamically rate-limited by model/traffic, so treated as a real tier, not a guaranteed one |
| LLM (cloud, prior default / mid-chain fallback) | Groq cloud | 1.1.2 client | Model: `openai/gpt-oss-120b`; still available directly via `LLM_PROVIDER=groq`, and reused as a fallback tier in the Gemini chain when a Groq key is configured (it already is, kept for BYOK) |
| LLM (cloud, last-resort fallback — Phase 12 follow-up) | Cerebras | openai>=1.0 client (OpenAI-compat endpoint, `https://api.cerebras.ai/v1`) | Model: `gpt-oss-120b` (same model as the Groq tier — free, fast, generous 1M tokens/day). Free-tier context capped at 8K tokens, too small for this app's later-turn prompts (system prompt alone runs ~3,400 tokens before history/RAG context), so deliberately placed last rather than as an equal peer |
| LLM (dev) | MLX-LM (local, Apple Silicon) | openai>=1.0 client | OpenAI-compatible API; port TBD when installed — not yet in active use |
| LLM (production) | vLLM (Linux/NVIDIA) | openai>=1.0 client | Same OpenAI-compatible interface; switch via `LLM_BASE_URL` in `.env` only — not yet deployed anywhere |
| Embeddings | Ollama (local, dev default) or Hugging Face Inference Providers (`EMBEDDING_PROVIDER=huggingface`, deploy path) | 0.3.3 client / httpx | Ollama: `nomic-embed-text`, 768-dim. HF: `BAAI/bge-base-en-v1.5`, also 768-dim — **not** `nomic-embed-text-v1.5`, which was live-verified to have zero active HF inference providers (`inferenceProviderMapping: {}` via HF's own API) despite being downloadable; bge-base is a comparable-quality, same-dimension substitute that's actually servable. `FailoverEmbeddingProvider` tries HF first, falls back to Ollama on any failure — harmless in an environment with no Ollama running (fails through quickly, same as any other embedding failure `RAGService` already degrades gracefully from) |
| Embedding abstraction | `EmbeddingProvider` ABC | — | Swappable without API changes |
| Company lookup (Phase 7) | Tavily search API | REST via httpx | Real web signal on a named company's interview process; used only when JD has `company_name` |
| Interview duration research (Phase 8) | Tavily search API + LLM extraction | REST via httpx + `llm_service.generate(json_mode=True)` | `CompanyLookupService.search_interview_duration()` — searches, then a small LLM call extracts a single integer (minutes) from the snippets |
| PDF text extraction (Phase 8) | pypdf | >=5.0,<6.0 | Pure-Python, no system deps; used for both JD and resume PDF uploads |

### LLM Provider Factory (`services/llm_service.py`)
- `_make_llm_service()` — returns provider based on `settings.llm_provider`
- `"groq"` → `GroqLLMService`
- `"gemini"` (Phase 9, currently active) → builds a **5-tier failover chain** (Phase 12
  follow-up), each tier included only if its key is set, tried in this priority order:
  1. NVIDIA (`nvidia_api_key`/`nvidia_model`)
  2. Groq (`groq_api_key`, reused from the BYOK config)
  3. Gemini key 1 (`gemini_api_key`)
  4. Gemini key 2 (`gemini_api_key_2`, optional)
  5. Cerebras (`cerebras_api_key`/`cerebras_model`, last resort — see 8K context caveat above)

  Wrapped in `FailoverLLMService` whenever more than one tier is present, otherwise
  returns the single instance directly. Raises `ValueError` at startup if
  `llm_provider="gemini"` but no Gemini key is set (Gemini keys are still the only
  *required* tier — the others are optional extras) — fails loud rather than silently
  falling through
- `"mlx"` → `OpenAICompatLLMService` (MLX-LM local / vLLM production — not yet in active use)
- anything else (incl. `"ollama"`) → `LLMService` (fallback)
- Switching local→production: set `LLM_BASE_URL` in `.env` — no code changes required
- `_KNOWN_BYOK_BASE_URLS` now also lists `nvidia`/`cerebras` base URLs, reused for both
  the app-default chain above and future BYOK use of either provider

### Failover LLM Wrapper (`services/failover_llm_service.py`, Phase 9, generalized Phase 12)
- `FailoverLLMService(services: list)` — tries each underlying service in order; same shared interface (`generate`, `stream_generate`, `health_check`)
- `generate()` / `health_check()`: straightforward try-next-on-exception
- `stream_generate()`: only fails over if the failing service raised **before yielding any token** (the common shape of a rate-limit/connection error). A mid-stream failure after output has already started is re-raised as-is rather than retried on the next key — restarting would send a duplicated/broken response to a client that already has partial output
- Originally built for spreading app-default load across multiple API keys on the
  *same* provider (only useful if the keys are on **separate** accounts/projects — same-
  project keys share one quota pool); Phase 12 confirmed it works identically well
  chaining across **different providers entirely** (NVIDIA → Groq → Gemini → Cerebras),
  since every wrapped service shares the same `generate`/`stream_generate`/`health_check`
  interface regardless of provider. Root cause this chain was built to address: Gemini's
  free-tier 20 RPM/project cap was getting exhausted under concurrent interview sessions,
  surfacing as "Internal server error" to users — live-verified via local reproduction
  (concurrent-session stress test) that chaining fixed it, raising the observed
  concurrent-session success rate from 1-of-5 to 4-of-5 in an identical test

### LLM Service Design (shared interface)
- `generate(prompt, system_prompt="", json_mode=False)` — non-streaming; wrapped in tenacity retry (`stop_after_attempt(3)`, `wait_exponential`)
  - `json_mode=True` (Phase 7): forwards to `response_format={"type": "json_object"}` (Groq/OpenAI-compat) or `format="json"` (Ollama) — constrains sampling so JSON-consuming call sites (JD parsing, JD knowledge gen, per-turn scoring, closing report) get valid JSON directly instead of relying on post-hoc string repair
- `stream_generate()` — `AsyncGenerator[str, None]`; NOT retried (streaming not idempotent)
- `reraise=True` passed as decorator param (NOT imported from tenacity — removed in v9.x)

### JSON Extraction (`services/json_utils.py`, Phase 7)
- `extract_json(raw) → dict`, `extract_json_array(raw) → list[dict]` — single shared implementation, replacing three previously-duplicated copies in `jd_service.py`, `scoring_service.py`, `api/routers/sessions.py`
- Uses `json.JSONDecoder().raw_decode()` anchored at the first `{`/`[` — parses only the first complete JSON value and discards any trailing content, rather than naively slicing to the *last* `}`/`]` (which broke whenever a model appended anything after a valid JSON value, even under `json_mode`)
- Falls back to `_strip_stray_escapes()` repair (tracks in-string state, strips backslash-escapes used as pretty-print whitespace outside string literals) if `raw_decode` fails on the first attempt — observed with `gpt-oss-120b` prior to `json_mode` adoption
- `json_mode=True` + this extraction layer together reduced JD-knowledge-generation JSON failures to 0 across all tested batches

### Company Lookup Service (`services/company_lookup_service.py`, Phase 7)
- `CompanyLookupService.search_interview_style(company_name) → list[str]` — POSTs to Tavily's REST search API (`https://api.tavily.com/search`) with query `"{company} technical interview process questions rounds format"`
- Returns up to 5 result snippets (truncated to 500 chars each); returns `[]` on missing `TAVILY_API_KEY` or any request failure (graceful degradation, same pattern as `RAGService.retrieve()`)
- Called from `LLMKnowledgeProvider.generate()` in `services/jd_service.py` when `jd_parsed.company_name` is present; snippets are injected into the JD-knowledge-generation prompt as a "Real signals about {company}'s actual interview process" section

### Company Registry (`services/company_registry.py`, Phase 7)
- Fixed registry of 11 pre-generatable company archetypes (`JDParsed` per company): MAANG (Meta, Amazon, Apple, Netflix, Google), quant firms (Jane Street, Hudson River Trading, Citadel), big banks (JPMorgan Chase, Barclays, HSBC)
- `resolve_company_slug(company_name) → str | None` — normalizes and matches a live session's parsed company name against the registry, including an alias map for common variants (e.g. `"HRT"` / `"Hudson River Trading"` → `hrt`); returns `None` on no match, never a false positive
- `scripts/generate_company_kb.py` — one-shot pre-generation script: reuses the same `LLMKnowledgeProvider` + Tavily pipeline built for live JD sessions, run against the fixed registry instead of a submitted JD; idempotent (skips companies already indexed). 128 docs generated across the 11 companies (8–13 per company)

### OpenAICompatLLMService
- Uses `openai.AsyncOpenAI(base_url=settings.llm_base_url, api_key="local")`
- `api_key="local"` — required by the openai client library; MLX-LM and vLLM ignore it
- `settings.llm_model_name` passed as `model` to the completions endpoint
- Identical interface to all other LLM services: `generate()`, `stream_generate()`, `health_check()`

### Embedding Service Design
- `EmbeddingProvider` ABC: `embed(text) → list[float]`, `embed_batch(texts) → list[list[float]]`
- `OllamaEmbeddingProvider.embed_batch` uses `asyncio.gather` for concurrent requests
- Dimension validated against `settings.embedding_dim` (768) — raises `ValueError` on mismatch

### Prompt Layer (`prompts/`)
| Module | Exports | Purpose |
|---|---|---|
| `interviewer.py` | `build_system_prompt(domain, difficulty, jd_text, context)`, `build_user_prompt()` | Interviewer persona; history-aware turn prompts; RAG context injection |
| `evaluator.py` | `SYSTEM_PROMPT`, `build_eval_prompt()` | Per-turn JSON scoring (correctness, depth, communication) |
| `closing.py` | `SYSTEM_PROMPT`, `build_closing_prompt()` | Final report from full transcript + avg score |

## Qdrant Design

### Collection: `knowledge_base`
Named vectors — same 768-dim embedding stored under two distance metrics:
```
vec name   distance metric   purpose
cosine     Distance.COSINE   directional similarity
euclid     Distance.EUCLID   magnitude/distance sensitivity
```

### Point payload schema
```json
{
  "domain":    "TECHNICAL",
  "topic":     "Data Structures",
  "difficulty": 2,
  "tags":      ["hash_table"],
  "text":      "Q: ...\nA: ...",
  "source_id": "<uuid>"
}
```

### Hybrid Retrieval Formula
```
cosine_score = Qdrant cosine similarity  (range [-1, 1], higher = more similar)
euclid_score = Qdrant euclid score       (= -l2_distance, range (-∞, 0])
l2_dist      = -euclid_score
eu_sim       = 1 / (1 + l2_dist)

combined = 0.7 × cosine_score + 0.3 × eu_sim
```
Returns top-3 `payload["text"]` by combined score.
Oversample factor = 5× before re-ranking.

### Client Module (`db/qdrant.py`)
- `get_qdrant()` — module-level singleton,
  `AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=60)`.
  `api_key` required for Qdrant Cloud (self-hosted Docker Qdrant doesn't need one, hence `or None`).
  `timeout=60` (Phase 12) — the client default is too short for uploading a multi-point batch over
  a real network connection to Qdrant Cloud; only surfaced once actually deploying, since local dev
  always talked to a `localhost` container with negligible latency
- `init_collection()` — called at FastAPI startup; creates collection if not exists
- `close()` — called at FastAPI shutdown
- `COLLECTION_NAME = "knowledge_base"`, `VECTOR_DIM = 768`

## Interview Session Design

### Session Lifecycle
```
POST /sessions → ACTIVE  (target_minutes resolved: JD-stated -> Tavily-researched -> default)
  ↓                       (blocked with 403 if free-tier quota exhausted — see Phase 9 below)
WS /ws/interview/{id} — adaptive length (Phase 8), see below
  ↓                       ↓
  natural close           candidate clicks Terminate (Phase 9) — closes the WS client-side,
  ↓                       no closing turn generated
POST /sessions/{id}/close                    POST /sessions/{id}/close?terminated=true
  → COMPLETED                                  → ABANDONED
  (ended_at, total_score,                      (same report pipeline, scored from whatever
   session_reports doc)                         turns happened; empty-report fallback if
                                                 terminated before any turn was scored)
```
Both paths share the same `close_session()` handler — `terminated=True` is the only branch point (final status, and a graceful empty-report path instead of the usual 422 when there are zero scored turns). Not resumable either way; `ABANDONED` sessions still surface whatever score/turn history exists via `GET /sessions/{id}`.

### WebSocket Message Protocol
| Direction | type | Meaning |
|---|---|---|
| Server → Client | `token` | Streaming question/closing-statement chunk |
| Server → Client | `question_end` | Question (or closing statement) complete, awaiting answer |
| Server → Client | `session_end` | Interview concluded — always preceded by a real streamed closing statement, never sent as a raw cutoff (Phase 8) |
| Server → Client | `error` | Fatal error |
| Client → Server | plain text or `{"content": "..."}` | Candidate answer |

### Adaptive Interview Length + Closing (Phase 8)
Replaces the old "loop until a fixed turn count" behavior — `project_context.md` requires the
interview never end abruptly.

```
Each turn, before generating the next question:
  elapsed_min = now - session.started_at
  target_minutes = fresh SELECT from Postgres every turn (see race-condition note below)

  turn >= max_interview_turns          -> force close (absolute circuit breaker, default 40)
  elapsed_min < target_minutes          -> continue normally (zero extra cost — common case)
  elapsed_min >= target_minutes * 1.3   -> force close (overrun safety valve)
  else (in the target..target*1.3 window):
      one extra small LLM call: "have you gathered enough signal to conclude?"
      -> conclude: true  => close
      -> conclude: false => continue
```
- `settings.default_interview_target_minutes` (45), `settings.interview_overrun_factor` (1.3)
- **Closing turn**: a real, in-character, unscored sign-off generated by
  `prompts/interviewer.py::build_closing_turn_prompt()` — streamed through the same
  `token`/`question_end` protocol as any question, *then* `session_end`. No candidate answer is
  awaited for this turn; `scoring_service.score_turn()` is not called for it.
- **Known race condition, fixed live**: `target_minutes` is resolved by a background task
  (`_prepare_jd_knowledge` — JD parsing + Tavily research) that can still be running when the WS
  connects, especially right after a JD upload. Caching it once from the WS-connect-time session
  snapshot would silently lock in the pre-resolution default for the whole interview — observed
  happening live during verification. Fixed: `api/routers/interview_ws.py::_get_target_minutes()`
  re-queries Postgres fresh every turn instead.

### Redis Session State
```
key:   session:{session_id}:state    TTL: 7200s
value: { turn, history[-10], difficulty, domain, status }
```
`status` — Phase 2 originally documented `"active" | "closing"` here but never implemented the
transition; Phase 8 actually wires it: set to `"closing"` right before the closing-turn message is
generated.

### MongoDB Collections
| Collection | Purpose | Written by |
|---|---|---|
| `interview_sessions` | Live interview transcripts (incl. the unscored closing turn) | `interview_ws.py` via `$push` upsert per turn |
| `knowledge_base` | RAG seed documents (Q&A + metadata) | `scripts/ingest_knowledge_base.py` |
| `session_reports` (Phase 8) | Persisted AI closing report + a snapshot of per-turn scores + final score, keyed by `session_id`/`user_id` | `api/routers/sessions.py::close_session()` |

#### `interview_sessions` document schema
```
{ session_id, created_at, turns: [{turn, question, answer, ts}] }
```

#### `knowledge_base` document schema
```
{ doc_id (UUID), domain, topic, question, ideal_answer, difficulty (1-5), tags: [str] }
```
`doc_id` is the join key to Qdrant `source_id` payload field.

#### `session_reports` document schema (Phase 8)
```
{
  session_id, user_id, interview_type, total_score,
  overall_summary, top_strengths, key_gaps, recommendations, hire_signal,
  turn_scores: [{id, session_id, turn_number, score, correctness, depth, communication,
                 strengths, weaknesses, improvement, created_at}],
  created_at
}
```
Written once, at close time. Why Mongo and not a Postgres migration: this is exactly the kind of
unstructured/document-shaped data `project_context.md` designates for MongoDB (interview
transcripts, logs, unstructured interview data), and avoids a schema migration for a payload shape
that may keep evolving. `GET /sessions/{id}` reads it; falls back to live Postgres `scores` (no
narrative) for sessions with no report doc (still ACTIVE, or predate this feature).

### Per-Turn Scoring
- Runs as `asyncio.create_task` (non-blocking — does not delay next question)
- `scoring_service.score_turn()` → LLM evaluator → `TurnScoreResult` → Postgres `scores` row
- Scores hidden during interview; only surfaced at `POST /sessions/{id}/close`

## Observability

| Component | Technology | Version | Notes |
|---|---|---|---|
| Logging | structlog | 24.4.0 | JSON renderer; level from `settings.log_level` |

### `GET /health` (Phase 11 correction)
Checks 6 services in parallel via `asyncio.gather`: `postgres`, `mongo`, `redis`, `llm`, `qdrant`,
`embeddings`. Overall `status` is `"ok"` only if every service reports `"ok"`, else `"degraded"`.

**Bug fixed this phase**: the `llm`/`embeddings` split didn't exist before — there was only a single
check labeled `"ollama"` that actually called `llm_service.health_check()` (the LLM provider, i.e.
Groq or Gemini depending on config), stale naming from Phase 1/2 when Ollama was the only LLM option.
There was no health check for the embedding service at all. Fixed: `_check_llm()` (renamed, same
behavior) + new `_check_embeddings()` calling `get_embedding_service().health_check()`. Every
`EmbeddingProvider` implementation now has a `health_check()` method (`OllamaEmbeddingProvider`:
`client.list()`; `HuggingFaceEmbeddingProvider`: a lightweight `GET` against the model's HF API page,
not a real embed call; `FailoverEmbeddingProvider`: healthy if any wrapped provider is).

## Deployment (Phase 11)

| File | Purpose |
|---|---|
| `Dockerfile` | `python:3.14-slim`; selective `COPY`s of only runtime-needed dirs (`api/`, `db/`, `models/`, `prompts/`, `services/` + `main.py`/`config.py`/`alembic.ini`) — deliberately not `COPY . .` |
| `entrypoint.sh` | Runs `alembic upgrade head`, then `exec`s `uvicorn main:app --host 0.0.0.0 --port "$PORT"`. Exec-form `CMD ["./entrypoint.sh"]` in the Dockerfile, not shell-form — a shell-form `CMD` (tried first) doesn't forward OS signals (e.g. Render's `SIGTERM` on redeploy) to the app process; `exec` inside the script fixes that |
| `.dockerignore` | Excludes secrets, `.git/`, `.venv/`, `frontend/`, `tests/`, `scripts/`, `data/`, `logs/`, `docs/`, `*.md` |

`$PORT` is read from the environment at container start (Render assigns it dynamically), not
hardcoded. Live-verified: built image run against the real local Docker Compose network with
production-shape env vars (real Groq + HF credentials) — migrations ran, app started, `GET /health`
returned fully `"ok"` across all 6 services.

## Deployment (Phase 12 — Live)

All seven components are deployed and wired together in production:

| Component | Platform |
|---|---|
| Backend | Render (Docker, free tier, auto-deploy on push to `main`) |
| Frontend | Cloudflare Pages, via Workers static assets (`frontend/wrangler.jsonc`) |
| PostgreSQL | Neon (pg18, pooled `asyncpg` connection, `?ssl=require` not `sslmode=require`) |
| MongoDB | MongoDB Atlas (free M0, network access `0.0.0.0/0` — no static Render IP to allowlist) |
| Redis | Upstash (`rediss://` TLS) |
| Qdrant | Qdrant Cloud (`QDRANT_API_KEY` now wired — see Client Module above) |
| Embeddings | HF Inference Providers (`BAAI/bge-base-en-v1.5`), Ollama kept as coded fallback |

### `frontend/wrangler.jsonc` (new file)
Cloudflare has merged Pages into the Workers product; deploying a static SPA now requires this
config file rather than the classic "build command + output directory" Pages UI flow:
```json
{
  "name": "interview-bot",
  "compatibility_date": "2025-01-01",
  "assets": { "directory": "./dist", "not_found_handling": "single-page-application" }
}
```
`not_found_handling: "single-page-application"` is required for `react-router-dom`'s
`BrowserRouter` — without it, directly navigating to a client-side route 404s instead of falling
back to `index.html`.

### Bugs Found and Fixed Live This Phase
1. **Frontend shipped with no API URL.** Vite bakes `VITE_API_BASE_URL`/`VITE_WS_BASE_URL`
   (`frontend/src/lib/apiClient.ts`) into the JS bundle at build time; they weren't set before the
   first Cloudflare build, so every request went to a literal `undefined/auth/...`. Fixed via
   Cloudflare's **build-scoped** environment variables (distinct from the Worker-runtime
   "Variables and Secrets" tab, which refuses vars entirely on a static-assets-only deployment).
2. **Knowledge-base ingestion silently discarded all its work on a Qdrant Cloud timeout** — see
   the Ingestion Pipeline section above for the `_UPSERT_BATCH_SIZE`/`timeout=60` fix. Never
   surfaced locally since local dev only ever wrote to a `localhost` Qdrant container.

### Production Config
`OAUTH_REDIRECT_BASE_URL` and `CORS_ALLOWED_ORIGINS` point at the live Cloudflare Workers origin
(no longer `localhost` defaults); Google and GitHub OAuth apps have the production callback URI
registered (Google supports multiple redirect URIs — localhost, frontend-dev, and production all
coexist; GitHub OAuth Apps support only one, so production replaced local-dev there — see
`TODO.md` for the trade-off this creates for local GitHub-login testing).

### Live Verification
`GET /health` on the deployed Render URL reports all 6 services `"ok"` against real production
endpoints. Full interview pipeline (guest signup → session creation → live WS turn loop with real
streamed Gemini output → per-turn scoring → closing report) exercised directly against production
via `curl` and a raw `websockets` script — confirmed the entire stack works end-to-end in the real
deployed environment, not just locally.

### Operational: Render Free-Tier Keep-Alive
A scheduled task pings `GET /health` on the deployed backend every 3 hours to prevent Render's
free tier from spinning the instance down after 15 minutes of inactivity (which would otherwise
cause a slow cold-start on the next real request).

## Utilities

| Component | Technology | Version | Notes |
|---|---|---|---|
| Retry | tenacity | 9.0.0 | `reraise` is a decorator param in v9, not a standalone import |
| HTTP client | httpx | 0.27.2 | Available for external HTTP calls |
| Env loading | python-dotenv | 1.0.1 | Loaded via pydantic-settings |
| File upload | python-multipart | >=0.0.9 | Required for FastAPI form/file endpoints |

---

## RAG Layer

### Files (Phase 3–4, updated Phase 6–7)
| File | Purpose |
|---|---|
| `data/knowledge_base_seed.json` | 4,180 seed docs (Phase 7 — up from 24): 4,020 TECHNICAL (24 hand-written + 3,902 from HF `K-areem/AI-Interview-Questions` + 174 from Kaggle `syedmharis/software-engineering-interview-questions-dataset`), 40 BEHAVIORAL + 40 HR (LLM-synthesized, STAR-format for behavioral) |
| `services/rag_service.py` | `RAGService` — Qdrant ingestion + hybrid dual-vector retrieval; JD-aware since Phase 6; batched upserts since Phase 7 |
| `scripts/ingest_knowledge_base.py` | One-shot CLI: seeds MongoDB → resets Qdrant collection → embeds → indexes |
| `scripts/fetch_external_datasets.py` | Phase 7 — one-shot fetch + merge of external TECHNICAL datasets (HF + Kaggle) into the seed file, dedup by question text |
| `scripts/generate_behavioral_hr_seed.py` | Phase 7 — one-shot LLM synthesis of BEHAVIORAL/HR seed docs across 16 curated topics (no adequate public dataset exists for these domains — see Phase 7 changelog for the rejected Kaggle HR dataset) |
| `services/company_registry.py` | Phase 7 — 11 pre-generatable company archetypes; `resolve_company_slug()` |
| `scripts/generate_company_kb.py` | Phase 7 — one-shot pre-generation of company-specific KBs via the JD-synthesis pipeline |

### RAG Pipeline (Phase 6+, 3-tier fallback since Phase 7)
```
User answer (previous turn) OR domain name (turn 0)
  ↓ embedding_service.embed() — HF Inference Providers in production, Ollama for local dev
  ↓ Qdrant dual search: cosine + euclid named vectors (top-15 each)
     filter: domain + jd_hash
  ↓ Client-side re-rank: 0.7 × cosine + 0.3 × (1/(1+l2))
  ↓ top-3 payload["text"] chunks
  ↓ build_system_prompt(context=chunks)
  ↓ LLM generates grounded question
```

`RAGService.retrieve()` tries three tiers in order, using the first that returns results:
1. **`jd`** — exact `jd_hash` for the live session's submitted JD (if any)
2. **`company`** — `company_slug` resolved from the parsed JD's company name via `resolve_company_slug()` (pre-generated registry KB)
3. **`static`** — `jd_hash="static"` seed knowledge base (always the final fallback)

Each tier logs `rag_retrieve_metric` with `source` set to `"jd"` / `"company"` / `"static"` / `"embed_failed"`.

### Qdrant Payload Schema (Phase 6+)
```json
{
  "domain":    "TECHNICAL",
  "topic":     "...",
  "difficulty": 2,
  "tags":      [],
  "text":      "Q: ...\nA: ...",
  "source_id": "<uuid>",
  "jd_hash":   "static" | "<sha256_of_jd_text>"
}
```
`jd_hash="static"` — seed knowledge base documents  
`jd_hash="<sha256>"` — LLM-synthesized documents for a specific JD

### Ingestion Pipeline (static KB — run once, re-run to reindex)
```
data/knowledge_base_seed.json
  ↓ scripts/ingest_knowledge_base.py
  ↓ seed → MongoDB knowledge_base collection (idempotent by question text)
  ↓ delete + recreate Qdrant collection (clean state)
  ↓ embedding_service.embed() per document — HF Inference Providers in production, Ollama for local dev
  ↓ qdrant.upsert(points) in batches of 100 — payload includes jd_hash="static"
```
Batched upserts (Phase 7): a single `client.upsert()` call with ~4,000 points failed outright
(`ResponseHandlingException`) once the seed dataset grew past ~4,000 docs. `_UPSERT_BATCH_SIZE`
(originally 200, lowered to 100 in Phase 12) in `RAGService.ingest_knowledge_base()` fixes this.
Full re-ingest of 4,180 docs takes ~85s locally against a `localhost` Qdrant container with Ollama
embedding (the bottleneck at ~50ms/doc sequential) — against Qdrant Cloud + HF Inference Providers
over a real network connection (the actual production path, live-verified in Phase 12) this takes
considerably longer, on the order of 25–90 minutes depending on HF API latency, since neither the
embedding calls nor the Qdrant upload are local-loopback speed anymore. A `timeout=60` on
`AsyncQdrantClient` (`db/qdrant.py`) was also required in Phase 12 — the client's short default
timeout caused a real production `WriteTimeout` that discarded an entire completed embedding pass
before that fix.

### Prerequisite (local dev only, `EMBEDDING_PROVIDER=ollama`)
```
ollama pull nomic-embed-text    # required before running ingest script locally
python scripts/ingest_knowledge_base.py
```
Production runs with `EMBEDDING_PROVIDER=huggingface` (`HF_API_TOKEN` set) instead — no local
Ollama daemon needed; see "Deployment (Phase 12)" below.

---

## JD Layer (Phase 6)

### New Files
| File | Purpose |
|---|---|
| `models/schemas/jd.py` | `JDParsed` Pydantic model — structured JD fields |
| `services/jd_service.py` | `KnowledgeProvider` ABC, `LLMKnowledgeProvider`, `JDService` (parser) |

### JDParsed Fields
```
role_title, company_name, seniority, required_skills, preferred_skills,
tech_stack, interview_focus, domain, estimated_duration_minutes (Phase 8)
```

### Knowledge Provider Design
- `KnowledgeProvider` ABC — `generate(jd_parsed) → list[dict]`
- `LLMKnowledgeProvider` — generates Q&A pairs via LLM; swappable with any `KnowledgeProvider` impl
- Count formula: `min(max(8, len(required_skills + tech_stack) * 2), 12)` — cap lowered from 25 to prevent Groq output truncation
- Generation format: `{"questions": [...]}` JSON object wrapper — more reliable than bare array across providers; generated with `json_mode=True` since Phase 7
- Module-level singletons: `jd_service`, `knowledge_provider`

### Skill-Gap Targeting + Company-Aware Generation (Phase 7)
- `_build_gen_prompt()` splits `required_skills` (weighted heavier) from `preferred_skills` (lighter) in the generation prompt
- Instructs the LLM to write at least one depth-probing question per required skill — distinguishing genuine depth from surface-level/buzzword familiarity
- `LLMKnowledgeProvider.generate()` calls `company_lookup_service.search_interview_style(company_name)` (Tavily) when `jd_parsed.company_name` is present; real snippets about the company's actual interview process are injected into the prompt as a "Real signals about {company}'s actual interview process" section
- Resume text (Phase 8) is threaded separately, directly into the interviewer's system prompt (see below) — not into JD knowledge-base generation. Gap analysis is still LLM-judgment-based from raw text (JD vs. resume), not a structured comparison — see `TODO.md`

### JD Session Flow
```
POST /sessions (with jd_text)
  → session created with jd_text stored (existing column)
  → asyncio.create_task(_prepare_jd_knowledge(jd_text, jd_hash))
       ↓ JDService.parse_jd(jd_text) → JDParsed  [LLM call]
       ↓ Redis.set("jd:{jd_hash}:parsed", parsed_json, ex=86400)
       ↓ rag_service.has_jd_documents(jd_hash) → skip if already indexed
       ↓ knowledge_provider.generate(jd_parsed) → [{topic, question, ideal_answer, difficulty}]
       ↓ rag_service.ingest_jd_documents(jd_hash, docs, domain)
  → session returned immediately (background task non-blocking)
```

### WS JD Context Flow
```
WS connect
  → _resolve_jd_context(session.jd_text)
       ↓ compute jd_hash = sha256(jd_text)
       ↓ Redis.get("jd:{jd_hash}:parsed") → structured string
       ↓ fallback to raw jd_text if cache miss
  → Per turn: rag_service.retrieve(query, domain, top_k=3, jd_hash=jd_hash)
  → build_system_prompt(domain, difficulty, jd_context, rag_chunks)
```

### Redis JD Cache
```
key:   jd:{sha256_of_jd_text}:parsed    TTL: 86400s (24h)
value: JSON of JDParsed fields
```
Shared across sessions with identical JD text. Avoids re-parsing the same JD.

### JD Knowledge Deduplication
`rag_service.has_jd_documents(jd_hash)` checks Qdrant for existing points with matching `jd_hash` before generating and ingesting — prevents duplicate ingestion when multiple sessions share the same JD.

---

## Resume + JD Upload, Duration Research (Phase 8)

### Why
`project_context.md` requires the interview never end abruptly; the old loop just ran exactly
`max_interview_turns` (10) then cut off with a raw system string. Separately, `TODO.md` had long
flagged "skill-gap targeting is JD-only, no resume/candidate input" as a known gap. Both closed in
the same pass since both needed a way to get more real candidate/role context into the session.

### New Files
| File | Purpose |
|---|---|
| `services/file_extraction_service.py` | `extract_text_from_pdf(bytes) -> str` via `pypdf`; raises `ValueError` (not a pypdf-specific exception type) on unreadable/empty PDFs so callers don't need to import pypdf themselves |

### Schema (migration `0005`)
- `sessions.resume_text` (Text, nullable) — extracted resume PDF text
- `sessions.target_minutes` (Integer, nullable) — resolved once (see resolution order below); `Session.has_resume` is a `@property` (`resume_text is not None`), not a column

### Upload Endpoints (`api/routers/sessions.py`)
- `POST /sessions/{id}/upload-jd`, `POST /sessions/{id}/upload-resume` — both `UploadFile` (PDF
  only, 422 on other content types), auth + ownership-checked like `close_session`
- Both reject (409) if `session.status != ACTIVE`, or if the Redis turn-state shows `turn > 0` —
  since `interview_ws.py` only reads `jd_text`/`resume_text` once at WS-connect time, an upload
  after the interview has actually started would silently have no effect
- `upload-jd` sets `session.jd_text` and re-triggers the same `_prepare_jd_knowledge()` background
  task used at session creation (parsing, duration resolution, RAG knowledge generation) — one
  pipeline, two entry points
- JD also still accepts pasted text at `POST /sessions` creation time (existing `jd_text` field,
  unchanged); PDF upload is additive, not a replacement

### Duration Resolution (`services/jd_service.py::JDService.resolve_target_minutes()`)
```
JDParsed.estimated_duration_minutes (LLM extracted an explicit stated duration from the JD text)
  ↓ (if not present, and company_name is known)
company_lookup_service.search_interview_duration(company, role)  [Tavily + one small LLM extraction call]
  ↓ (if still nothing)
settings.default_interview_target_minutes  (45)
```
Resolved once per session inside `_prepare_jd_knowledge()` (background task) and written to
`session.target_minutes`. Sessions with no JD at all get the default synchronously at creation.
See "Adaptive Interview Length + Closing" above for how `interview_ws.py` re-fetches this value
fresh every turn rather than caching it (a real race condition, found and fixed live).

### Resume Context in Question Generation
`prompts/interviewer.py::build_system_prompt()` gained a `resume_text` param → a `resume_section`
(same shape as the existing `jd_section`) instructing the interviewer to probe the candidate's
actual listed projects/experience, cross-referenced against JD requirements.

---

## Authentication & BYOK Layer (Phase 7)

### Why
Prior to Phase 7 there was zero authentication: `POST /sessions` accepted a raw `user_id` in the body with no verification. BYOK (per-user LLM API keys) also requires real accounts and encrypted secret storage.

### New Dependencies (`requirements.txt`)
| Package | Version | Purpose |
|---|---|---|
| `bcrypt` | >=4.0,<5.0 | Password hashing — used directly (not `passlib[bcrypt]`, which is unmaintained against bcrypt>=4.1) |
| `pyjwt` | >=2.9,<3.0 | JWT issuance/verification |
| `cryptography` | >=43.0,<44.0 | Fernet symmetric encryption for BYOK keys at rest |

### New Files
| File | Purpose |
|---|---|
| `models/pg/oauth_identity.py` | `OAuthIdentity` ORM — provider + provider_user_id, unique together |
| `models/pg/user_api_key.py` | `UserAPIKey` ORM — BYOK, one row per user+provider, `encrypted_key` |
| `models/schemas/auth.py` | Signup/login/token/user Pydantic schemas |
| `models/schemas/user_api_key.py` | BYOK request/response schemas (`UserAPIKeyRead` excludes the key entirely) |
| `services/crypto_service.py` | `encrypt()` / `decrypt()` via `cryptography.fernet.Fernet`; master key from `.env` (`ENCRYPTION_MASTER_KEY`) |
| `services/auth_service.py` | `hash_password`/`verify_password` (bcrypt), `create_access_token`/`decode_access_token` (JWT HS256), `normalize_email()` |
| `api/dependencies.py` | `get_current_user` FastAPI dependency — verifies `Authorization: Bearer` JWT, loads the `User`, 401 on any failure |
| `api/routers/auth.py` | `/auth/signup`, `/auth/login`, `/auth/me`, password management, identifier linking, BYOK CRUD, OAuth (Google/GitHub/Microsoft) |
| `scripts/seed_alpha_user.py` | One-off: create/promote the developer's own alpha-tester account |

### Config (`config.py` / `.env`)
| Field | Purpose |
|---|---|
| `jwt_secret_key`, `jwt_algorithm` (default `HS256`), `jwt_expire_minutes` (default 1440) | JWT signing/verification in `services/auth_service.py` |
| `encryption_master_key` | Fernet key for BYOK secret encryption |
| `google_client_id/secret`, `github_client_id/secret`, `microsoft_client_id/secret` | OAuth app credentials (Microsoft unset — routes return `501`) |
| `oauth_redirect_base_url` (default `http://localhost:8000`) | Base URL used to build the OAuth callback redirect URI |
| `oauth_callback_path_template` (default `/auth/{provider}/callback`, Phase 9) | Path suffix appended to `oauth_redirect_base_url`. Default matches this backend's own callback route (direct-backend testing). **Must** be changed to `/oauth/callback/{provider}` alongside pointing `oauth_redirect_base_url` at the frontend origin — that's the SPA's actual route (`frontend/src/App.tsx`), not the backend's. Before this setting existed, the redirect_uri was hardcoded to the backend's own path regardless of `oauth_redirect_base_url`, which silently broke the frontend OAuth handoff described below (Google rejects the request outright on a `redirect_uri_mismatch` once the registered console URI doesn't match) |

### JWT / Session Auth Design
- `sub` = user id, `exp` from `jwt_expire_minutes`, signed HS256
- WebSocket auth: token passed as query param (`?token=...`), verified after `websocket.accept()` — same accept-then-error-then-close pattern as the existing session-not-found path
- Ownership checks: `POST /sessions/{id}/close` → 403 if not the owner; WS handler sends an `error` message and closes (code 1008) on the same condition
- **Breaking**: `POST /sessions` no longer accepts `user_id` in the body — derived from the verified JWT

### Identifiers & Email Normalization
- Identifier: email OR phone_number (Pydantic validator + Postgres check constraint); mandatory-both at signup (OAuth-created accounts are the one exception — a provider only ever hands back an email)
- `normalize_email()` — lowercases, strips `+tag` (all domains), strips dots (Gmail/Googlemail domains only) — prevents multi-accounting via Gmail plus-addressing/dot-insensitivity
- `PUT /auth/me/link-email` / `link-phone` — attach-once (409 if already set or taken by another account)

### Password Management
- `set-password` (OAuth accounts with none yet), `change-password` (requires current password), `reset-password` (re-auth via linked OAuth provider, no current-password check — narrower than `change-password`)
- Known gap: accounts with no linked OAuth provider have no recovery path (would need real email/SMS delivery — deliberately not built)

### OAuth (Google / GitHub / Microsoft)
- Authorization-code flow via `httpx`; CSRF `state` stored in Redis, 10-minute TTL
- Google and GitHub — live-verified end-to-end. GitHub required two fixes: fall back to `GET /user/emails` when `/user` omits a public email; look up existing user by email before creating a new one (links `OAuthIdentity` instead of duplicating) — same account now resolves across Google + GitHub + password login
- Microsoft — routes implemented, returns `501` until credentials are set (deferred)
- Apple Sign In — excluded (requires paid Apple Developer Program enrollment)

### BYOK Design
- `PUT /auth/me/api-keys` — upsert one row per `(user_id, provider)`; `provider` is free-form (not an ENUM)
- Known providers with a fixed base_url (`services/llm_service.py`): `groq`, `gemini`, `openai` (via `OpenAICompatLLMService`); any other provider requires the caller to also supply `base_url`
- `services/llm_service.py::resolve_llm_service(db, user_id, provider)` — `provider=None` → app-default `llm_service` singleton (alpha-tester/demo path); else decrypts the user's stored key and builds a fresh service instance
- `SessionCreate.llm_provider` (optional) — chosen once at session creation, stored on `Session`, reused for every turn (question generation, per-turn scoring, closing report)
- `UserAPIKeyRead` never returns the key/encrypted_key field

### Guest Accounts & Free-Tier Quota (Phase 9)
- **Why**: letting a prospective user try one real interview before signing up removes the biggest drop-off point; but the app-default LLM key had *zero* usage cap before this — any signed-up user could already use it unlimited, which doesn't scale once real traffic hits it
- `POST /auth/guest` — creates a `User` row with `is_guest=True`, no email/phone/password, issues a JWT immediately. Purely a browser-token identity, not abuse-hardened: clearing storage/incognito gets a new guest. Accepted trade-off at this stage, not a security gap being overlooked
- `users.free_sessions_used` (int) — incremented in `create_session()` whenever a session is created with no BYOK `llm_provider` (i.e. using the app-default key) by a non-alpha-tester. Checked against a cap **before** incrementing: 1 for `is_guest` accounts, 2 for regular signed-up accounts; alpha testers and any BYOK session bypass the check entirely
- Quota-exceeded → `403` with a message pointing at Settings/BYOK; frontend (`InterviewSetup.tsx`) renders this with a link to `/settings`
- `UserRead.is_guest` exposed so the frontend can tailor guest-specific messaging (e.g. "sign up to keep your history")

---

## Frontend-Facing API Additions (Phase 8)

All additive — no existing route, response model, or test-covered behavior changed.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/sessions` | required | List current user's sessions, most recent first |
| `GET` | `/sessions/{id}` | required, ownership-checked | `SessionDetail` — `SessionRead` + narrative report (from `session_reports` if closed) + `turn_scores` (from the report doc, or live Postgres `scores` if not yet closed) |
| `GET` | `/stats` | public | `{total_users, total_sessions, completed_sessions, avg_score}` — real aggregate counts via `func.count()`/`func.avg()`, used by the homepage |
| `POST` | `/sessions/{id}/upload-jd` | required, ownership-checked | See "Resume + JD Upload" above |
| `POST` | `/sessions/{id}/upload-resume` | required, ownership-checked | See "Resume + JD Upload" above |

### CORS
`config.py::cors_allowed_origins` (default `["http://localhost:5173"]`, Vite's default dev port) +
`CORSMiddleware` in `main.py` — required for the SPA (a different origin) to call the API directly.

---

## Frontend (Phase 8)

### Stack
| Component | Technology | Notes |
|---|---|---|
| Framework | React 19 + TypeScript | `frontend/`, separate npm project from the Python backend |
| Build tool | Vite 8 | Node is a build-time tool only — `npm run build` outputs static HTML/JS/CSS, no Node runtime in production |
| Styling | Tailwind CSS 4 | CSS-first config (`@theme` in `src/index.css`), no `tailwind.config.js` needed |
| Routing | react-router-dom 7 | Client-side, `BrowserRouter` |
| Charts | recharts | Dashboard score-trend line |
| Icons | lucide-react | |
| Animation | framer-motion | Hover states, page transitions, glass-panel hover glow |

### Theme
"Liquid glass" — dark base, animated CSS-only gradient blobs (`GradientBackdrop.tsx`, pure
`@keyframes`, no JS animation loop), frosted `.glass-panel`/`.glass-panel-tight` utility classes
(`backdrop-filter: blur()` + inset specular-highlight box-shadow), single accent color
(`#0A84FF`, Apple system blue).

### Structure
```
frontend/src/
  lib/            apiClient.ts (typed fetch wrapper + multipart upload helper), types.ts (mirrors
                  backend Pydantic schemas), auth.ts (JWT storage/expiry check)
  context/        AuthContext.tsx — current user, login/signup/logout, consumed by ProtectedRoute
  hooks/          useInterviewSocket.ts (wraps the WS protocol), useElapsedTimer.ts,
                  useCountUp.ts (homepage stat animation)
  components/     layout/ (Navbar, Footer, ProtectedRoute, Layout), ui/ (GlassCard, Button,
                  ScoreBadge, StatCounter, Testimonials, GradientBackdrop), interview/
                  (ChatBubble, ChatComposer, ModelKeyPicker, LiveMediaControls)
  pages/          Home, Login, Signup, OAuthCallback, Dashboard, SessionReportPage,
                  InterviewSetup, InterviewRoom, Settings, NotFound
```

### `useInterviewSocket` (`src/hooks/useInterviewSocket.ts`)
Thin client-side mirror of the WS protocol above: connects with `?token=`, accumulates `token`
messages into a draft question, finalizes into a `turns` array on `question_end`, exposes
`sendAnswer()` which sends `{"content": answer}` and awaits the next question. Status machine:
`connecting -> streaming_question -> awaiting_answer -> waiting_for_next_question -> ended|error`.

**Not wrapped in React `<StrictMode>`** (`src/main.tsx`) — StrictMode's dev-only double-invoke of
effects opened two real WebSocket connections against the same interview session (each
independently advancing a turn on the backend), duplicating questions and burning real LLM calls.
Found live during verification; not worth the diagnostic value for a stateful realtime-socket app.

### OAuth → SPA Handoff (zero backend code changes)
The backend's `/auth/{provider}/callback` route is intentionally unchanged — it still returns the
JWT as JSON (existing integration test asserts this). Google/GitHub redirect the *browser*, not an
API client, so a JSON response isn't directly usable from an OAuth redirect. Fix is config-only:
point `OAUTH_REDIRECT_BASE_URL` at the frontend origin (and register that same URL in each
provider's console) so the provider redirects to `frontend/src/pages/OAuthCallback.tsx`
(`/oauth/callback/:provider`) instead of the backend. That page reads `?code&state` from the URL
and forwards them to the unchanged backend callback endpoint via `fetch`, then stores the returned
JWT. See `frontend/README.md` for the exact setup steps — not yet run through a real provider
consent screen from the frontend (backend-side Google/GitHub flows were live-verified in Phase 7).

### Live Video/Audio — Stubbed, No Backend
`components/interview/LiveMediaControls.tsx` — camera/mic buttons exist but are `disabled` and
tucked behind a closed-by-default "..." menu (not visible on first look, so nobody assumes a
working feature). Zero backend support; explicit user instruction to stub the UI only, backend to
follow in a later phase.

---

## Module Dependency Graph

```
main.py
├── config.py
├── db/mongo.py
├── db/redis.py
├── db/qdrant.py (init_collection, close)
├── api/routers/health.py
│   ├── db/postgres.py (AsyncSessionFactory)
│   ├── db/mongo.py
│   ├── db/redis.py
│   ├── db/qdrant.py (get_qdrant)
│   ├── services/llm_service.py (_check_llm — Phase 11 rename, was _check_ollama)
│   └── services/embedding_service.py (get_embedding_service — _check_embeddings, Phase 11, new)
├── api/routers/auth.py
│   ├── config.py (jwt_*, google/github/microsoft client id+secret, oauth_callback_path_template — Phase 9)
│   ├── db/postgres.py (get_db)
│   ├── db/redis.py (get_redis — OAuth CSRF state)
│   ├── models/pg/user.py, models/pg/oauth_identity.py, models/pg/user_api_key.py
│   ├── models/schemas/auth.py, models/schemas/user_api_key.py
│   ├── services/auth_service.py (hash/verify_password, create/decode_access_token, normalize_email)
│   ├── services/crypto_service.py (encrypt, decrypt)
│   ├── api/dependencies.py (get_current_user)
│   └── httpx (AsyncClient — OAuth provider token/userinfo calls)
├── api/routers/sessions.py
│   ├── config.py (default_interview_target_minutes)
│   ├── db/postgres.py (AsyncSessionFactory, get_db)
│   ├── db/mongo.py (sessions_col, session_reports_col)
│   ├── db/redis.py (get_redis)
│   ├── models/pg/session.py
│   ├── models/pg/score.py
│   ├── models/schemas/session.py (SessionCreate, SessionRead, SessionDetail, FinalReport)
│   ├── models/schemas/score.py (ScoreRead)
│   ├── prompts/closing.py
│   ├── api/dependencies.py (get_current_user — derives user_id from JWT)
│   ├── services/file_extraction_service.py (extract_text_from_pdf — Phase 8 upload endpoints)
│   ├── services/jd_service.py (jd_service, knowledge_provider)
│   ├── services/json_utils.py (extract_json)
│   ├── services/llm_service.py (resolve_llm_service)
│   └── services/rag_service.py (rag_service)
├── api/routers/stats.py (Phase 8)
│   ├── db/postgres.py (get_db)
│   ├── models/pg/session.py, models/pg/user.py
│   └── sqlalchemy (func.count, func.avg)
└── api/routers/interview_ws.py
    ├── config.py (max_interview_turns, default_interview_target_minutes, interview_overrun_factor)
    ├── db/mongo.py (sessions_col)
    ├── db/postgres.py (AsyncSessionFactory)
    ├── db/redis.py (get_redis)
    ├── models/pg/session.py
    ├── models/schemas/jd.py (JDParsed)
    ├── prompts/interviewer.py (+ build_conclude_check_prompt, build_closing_turn_prompt — Phase 8)
    ├── services/auth_service.py (decode_access_token — WS ?token= query param auth)
    ├── services/json_utils.py (extract_json — Phase 8 conclude-check parsing)
    ├── services/llm_service.py (resolve_llm_service)
    ├── services/rag_service.py (rag_service — jd_hash + company_slug 3-tier retrieval)
    ├── services/company_registry.py (resolve_company_slug)
    └── services/scoring_service.py
        ├── db/postgres.py (AsyncSessionFactory)
        ├── models/pg/score.py
        ├── models/schemas/score.py (TurnScoreResult)
        ├── prompts/evaluator.py
        ├── services/json_utils.py (extract_json)
        └── services/llm_service.py

services/auth_service.py
├── config.py (jwt_secret_key, jwt_expire_minutes)
├── bcrypt
└── pyjwt

services/crypto_service.py
├── config.py (encryption_master_key)
└── cryptography.fernet.Fernet

services/file_extraction_service.py (Phase 8)
└── pypdf (PdfReader)

services/jd_service.py
├── config.py (default_interview_target_minutes — Phase 8)
├── services/company_lookup_service.py (company_lookup_service)
├── services/json_utils.py (extract_json, extract_json_array)
└── services/llm_service.py

services/company_lookup_service.py
├── config.py (tavily_api_key)
├── services/llm_service.py (llm_service — Phase 8 duration extraction)
├── services/json_utils.py (extract_json — Phase 8)
└── httpx (AsyncClient)

services/company_registry.py
└── (static data only — no runtime dependencies)

services/rag_service.py
├── db/mongo.py (knowledge_base_col)
├── db/qdrant.py (get_qdrant, COLLECTION_NAME)
└── services/embedding_service.py (EmbeddingProvider — Ollama or the HF/Ollama failover chain, Phase 10)

scripts/ingest_knowledge_base.py
├── db/mongo.py (knowledge_base_col, close)
├── db/qdrant.py (COLLECTION_NAME, init_collection, get_qdrant)
└── services/rag_service.py (rag_service.ingest_knowledge_base)

scripts/fetch_external_datasets.py
├── httpx (HF datasets-server REST API)
└── kaggle.api.kaggle_api_extended.KaggleApi (KAGGLE_USERNAME/KAGGLE_KEY from .env)

scripts/generate_behavioral_hr_seed.py
├── services/json_utils.py (extract_json)
└── services/llm_service.py

scripts/generate_company_kb.py
├── services/company_registry.py (11-company registry)
├── services/jd_service.py (knowledge_provider — same JD-synthesis pipeline)
└── services/rag_service.py (ingest_jd_documents, using company slug as the hash)

scripts/seed_alpha_user.py
├── db/postgres.py
├── models/pg/user.py
└── services/auth_service.py (hash_password)

services/embedding_service.py  [factory: get_embedding_service()]
├── config.py (embedding_provider, hf_api_token, hf_embedding_model)
├── ollama (AsyncClient)             (OllamaEmbeddingProvider — local dev default)
└── httpx (AsyncClient)               (HuggingFaceEmbeddingProvider — Phase 10, wrapped in
                                        FailoverEmbeddingProvider with Ollama as fallback when
                                        embedding_provider="huggingface")

services/llm_service.py  [factory]
├── services/groq_llm_service.py     (when llm_provider=groq)
├── services/openai_compat_llm_service.py  (when llm_provider=gemini or mlx)
├── services/failover_llm_service.py       (when llm_provider=gemini with 2 keys — Phase 9)
└── ollama (AsyncClient)             (when llm_provider=ollama, fallback)

services/failover_llm_service.py (Phase 9)
└── (no external deps — wraps other LLM service instances)

services/openai_compat_llm_service.py
├── config.py (llm_base_url, llm_model_name)
└── openai (AsyncOpenAI)

db/qdrant.py
├── config.py (qdrant_url)
└── qdrant_client (AsyncQdrantClient)

db/migrations/env.py
├── config.py (postgres_url)
└── models/pg/__init__.py → user, session, score (ORM metadata)

tests/conftest.py  [shared fixtures]
├── asyncpg (admin DB create/drop)
├── sqlalchemy.ext.asyncio (pg_test_engine, db_session, client)
├── motor.motor_asyncio (mongo_test_client)
├── redis.asyncio (redis_test)
├── httpx (AsyncClient + ASGITransport — client fixture)
├── main.app (injected via client fixture)
└── db/postgres.get_db (overridden via dependency_overrides)

tests/integration/test_interview_ws.py
└── starlette.testclient.TestClient (sync WebSocket client)
    ├── db.qdrant.init_collection  [patched AsyncMock]
    ├── db.qdrant.close            [patched AsyncMock]
    └── db.redis.close             [patched AsyncMock]
```

---

## Test Infrastructure (Phase 5, updated Phase 6–7)

### Dev Dependencies (`requirements-dev.txt`)
| Package | Version | Purpose |
|---|---|---|
| pytest | >=8.0 | Test runner |
| pytest-asyncio | >=0.23 (currently installed: 1.4.0) | Async test/fixture support |
| pytest-mock | >=3.12 | `mocker` fixture |
| anyio | >=4.0 | Async backend used by pytest-asyncio |

### pytest Configuration (`pytest.ini`)
```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = session
asyncio_default_test_loop_scope = session
testpaths = tests
```

**Why session-scoped loops**: asyncpg connections are event-loop-bound. Session-scoped fixtures (`pg_test_engine`, `mongo_test_client`, `redis_test`) and all test functions must run in the same event loop or cross-loop Future access raises `RuntimeError`. Both `asyncio_default_fixture_loop_scope` and `asyncio_default_test_loop_scope` must be set to `session`.

### Test Layout (current — Phase 8)
```
tests/
├── conftest.py                          # All shared fixtures
├── unit/
│   ├── test_prompts.py                  # 14 tests — prompt builders, incl. resume section,
│   │                                       conclude-check, closing-turn prompts (Phase 8)
│   ├── test_scoring_service.py          # 8 tests — _extract_json, score_turn
│   ├── test_rag_service.py              # 8 tests — retrieve, re-ranking, query_points fix
│   ├── test_embedding_service.py        # 21 tests — dim validation, batch; +10 Phase 10:
│   │                                       HuggingFaceEmbeddingProvider, FailoverEmbeddingProvider,
│   │                                       get_embedding_service() factory branches; +6 Phase 11:
│   │                                       health_check() on every provider
│   ├── test_llm_service.py              # 7 tests — factory/provider selection, incl. gemini
│   │                                       single-key/two-key-failover/no-key-raises (Phase 9)
│   ├── test_jd_service.py               # 19 tests — parser, array extraction, doc validation,
│   │                                       provider, resolve_target_minutes priority (Phase 8)
│   ├── test_auth_service.py             # 11 tests — password hashing, JWT, email normalization
│   ├── test_file_extraction_service.py  # 4 tests — PDF text join/strip/error paths (Phase 8)
│   ├── test_company_lookup_service.py   # 5 tests — search_interview_duration (Phase 8)
│   ├── test_interview_ws_closing.py     # 8 tests — _should_close tiers, _get_target_minutes
│   │                                       re-fetch-fresh regression test (Phase 8)
│   └── test_failover_llm_service.py     # 9 tests (Phase 9) — generate/stream failover,
│                                           mid-stream-failure no-retry, health_check
└── integration/
    ├── test_health.py             # 2 tests — Docker required (updated Phase 11 for the
    │                                 ollama→llm rename + new embeddings key)
    ├── test_sessions.py           # 39 tests — Docker required (create/close, auth/ownership,
    │                                 list/detail (Phase 8), stats (Phase 8), JD/resume upload (Phase 8),
    │                                 +4 free-tier-quota + 3 terminate/?terminated=true (Phase 9))
    ├── test_interview_ws.py       # 6 tests — Docker NOT required (updated for the closing-turn
    │                                 protocol change — session_end is now always preceded by a
    │                                 streamed sign-off, Phase 8)
    └── test_auth.py               # 32 tests — Docker required (signup/login, OAuth, BYOK, linking,
                                      password mgmt, +3 guest-account tests (Phase 9))
```
Total: 113 unit + 79 integration = **192 tests**.

**Run without Docker**: `pytest tests/unit/ tests/integration/test_interview_ws.py`
**Full suite**: `pytest tests/` (Docker stack must be running)

### PostgreSQL Test Isolation
| Scope | Mechanism |
|---|---|
| Session | `interview_bot_test` DB created via asyncpg admin connection; Alembic migrations via `subprocess.run([sys.executable, "-m", "alembic", ...])`; DB dropped at session end |
| Per-test (API) | TRUNCATE `scores, sessions, users CASCADE` in `client` fixture teardown |

SAVEPOINT-based isolation (`db_session` fixture) is available for service-level tests that take a `db_session` argument directly; API endpoint tests use TRUNCATE because `AsyncSessionFactory` in the WS router bypasses the `get_db` dependency injection.

### Redis Test Isolation
- Session fixture `redis_test`: connects to DB index 1 (`redis://localhost:6379/1`); dev uses index 0
- Function fixture `redis_clean`: `FLUSHDB` after each test

### MongoDB Test Isolation
- Session fixture `mongo_test_client`: `AsyncIOMotorClient("mongodb://localhost:27017")`
- Function fixture `mongo_clean`: drops `interview_bot_test` database after each test

### Qdrant in Tests
- Unit tests: Qdrant client fully mocked
- WS integration tests: `db.qdrant.init_collection` and `db.qdrant.close` patched as `AsyncMock()` in `_app_client()` context manager
- Health/session tests: real Qdrant (Docker stack)

### `_app_client()` — WS Test Context Manager
Starlette `TestClient` runs the ASGI app in a thread with its own event loop. This conflicts with the session event loop on teardown for any singleton client created in the session loop. Patches applied inside `_app_client()`:

| Patch target | Reason |
|---|---|
| `db.qdrant.init_collection` | Qdrant may not be needed; prevents connection to real Qdrant |
| `db.qdrant.close` | Symmetric with init |
| `db.redis.close` | `AsyncClient(ASGITransport)` does NOT trigger the ASGI lifespan — so `_client` created during health tests (session loop) is never closed between test files. TestClient's thread-loop teardown would try to `wait_closed()` on a Future bound to the session loop → "Future attached to different loop" |

### `AsyncClient(ASGITransport)` vs `TestClient` — Lifespan Behavior
| Client | Lifespan triggered? | Event loop |
|---|---|---|
| `httpx.AsyncClient(transport=ASGITransport(app))` | **No** — lifespan events NOT sent | Session loop (via pytest-asyncio) |
| `starlette.testclient.TestClient(app)` | **Yes** — startup + shutdown | New thread-local loop |

This distinction is critical: singleton DB clients created by request handlers during `AsyncClient` tests persist across tests unless explicitly closed.

### `ASGITransport(raise_app_exceptions=False)`
Set in the `client` fixture so that unhandled app exceptions (e.g., FK `IntegrityError`) are converted to HTTP 500 responses, matching production Starlette `ServerErrorMiddleware` behavior instead of propagating to the test body.

---

## Stack Summary (Current)

| Layer | Previous (Phase 1–3) | Phase 4 | Phase 5 | Phase 6 | Phase 7 | Phase 8 | Phase 9 | Phase 10 | Phase 11 | Phase 12 |
|---|---|---|---|---|---|---|---|---|---|---|
| LLM (cloud, app-default) | Groq cloud (active in Phase 1–2) | Groq cloud (kept for testing) | Unchanged | Unchanged | Active model: `openai/gpt-oss-120b` (was `llama-3.3-70b-versatile`) | Unchanged | **Switched to Google Gemini** (`gemini-2.5-flash-lite`, cheapest current model) — two API keys on separate projects, wrapped in `FailoverLLMService`. Groq remains available via `LLM_PROVIDER=groq` and stays the BYOK default | Unchanged | Unchanged | Live-verified against production Render deploy; **found a real bug** — Gemini's free-tier 20 RPM/project cap was getting exhausted under concurrent sessions, surfacing as "Internal server error." Fixed by extending the chain to 5 tiers: **NVIDIA (new, first preference) → Groq → Gemini key 1 → Gemini key 2 → Cerebras (new, last resort)** — each a genuinely separate free-tier quota pool |
| LLM runner (dev) | Ollama | MLX-LM (Apple Silicon, OpenAI-compatible) | Unchanged | Unchanged | Unchanged (still not in active use) | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged |
| LLM runner (prod) | — | vLLM (Linux/NVIDIA, same interface) | Unchanged | Unchanged | Unchanged (not yet deployed) | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged — Render/Gemini remains the actual deployed path, vLLM still unused |
| Embeddings | Ollama nomic-embed-text | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged — flagged deploy blocker, no cloud fallback yet (RAG retrieval degrades to empty context, doesn't crash) | **Cloud fallback resolved**: `EMBEDDING_PROVIDER=huggingface` → `HuggingFaceEmbeddingProvider` (`BAAI/bge-base-en-v1.5`, not the originally-planned `nomic-embed-text-v1.5`, which was live-verified to have zero active HF inference providers) wrapped in `FailoverEmbeddingProvider` with Ollama kept as fallback. Ollama stays the local-dev default | + `health_check()` on every `EmbeddingProvider`; `/health`'s embedding check was previously entirely missing (see Observability section) | **Live-verified at full production scale**: 4,178/4,180 seed docs successfully embedded via HF against Qdrant Cloud — see Vector DB row for a real bug this surfaced |
| Vector DB | pgvector (inside PostgreSQL) | Qdrant (self-hosted) | Unchanged | JD-hash payload field added; `_STATIC_HASH="static"` for seed docs | Batched upserts (200/batch); 4,180 points indexed | Unchanged | Unchanged | Unchanged | Unchanged | **Deployed to Qdrant Cloud**; `qdrant_api_key` actually wired into `AsyncQdrantClient` (a prior TODO note had incorrectly claimed this was already done); `timeout=60` added (was unset) and `_UPSERT_BATCH_SIZE` lowered 200→100 after a real `WriteTimeout` silently discarded a fully-completed embedding pass with no retry — never surfaced against a local `localhost` container |
| Relational DB | PostgreSQL + vector extension | PostgreSQL (vector ext removed) | Unchanged | Unchanged (no new tables) | Unchanged (no new tables) | `sessions.resume_text`, `sessions.target_minutes` (migration `0005`) | `users.is_guest`, `users.free_sessions_used` (migration `0006`) | Unchanged | Unchanged | **Deployed to Neon** (pg18, pooled `asyncpg` connection — `?ssl=require`, not `sslmode=require`); all 6 migrations applied cleanly |
| Document DB | MongoDB | Unchanged | Unchanged | Unchanged | Unchanged | New `session_reports` collection (persisted closing reports) | Unchanged | Unchanged | Unchanged | **Deployed to MongoDB Atlas** (free M0 tier, `0.0.0.0/0` network access — no static Render IP to allowlist) |
| Cache | Redis | Unchanged | Unchanged | JD parsed cache: `jd:{hash}:parsed` TTL 24h | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged | **Deployed to Upstash** (`rediss://` TLS connection) |
| API framework | FastAPI | Unchanged | Unchanged | Unchanged | Unchanged | + CORSMiddleware (frontend origin) | Unchanged | Unchanged | Unchanged | `CORS_ALLOWED_ORIGINS`/`OAUTH_REDIRECT_BASE_URL` repointed from `localhost` defaults to the live Cloudflare Pages origin |
| JD parsing | — | — | — | `JDService` via LLM; `KnowledgeProvider` ABC | Unchanged, `json_mode=True` | + `estimated_duration_minutes` field | Unchanged | Unchanged | Unchanged | Unchanged |
| JD knowledge | — | — | — | `LLMKnowledgeProvider` synthesizes role-specific Q&A | + skill-gap targeting + Tavily company-style lookup | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged |
| External search | — | — | — | — | Tavily REST API (`services/company_lookup_service.py`) | + `search_interview_duration()` | Unchanged | Unchanged | Unchanged | Unchanged |
| JSON parsing | naive find-`{`/find-`}` + `json.loads` (3 duplicated copies) | Unchanged | Unchanged | Unchanged | Unified `services/json_utils.py`; `json.JSONDecoder().raw_decode()` + `json_mode=True` | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged |
| Static KB size | 24 docs | Unchanged | Unchanged | Unchanged | 4,180 docs (TECHNICAL/BEHAVIORAL/HR) | Unchanged | Unchanged | Unchanged | Unchanged | 4,178 of 4,180 actually indexed into the live production Qdrant Cloud collection (2 skipped on transient HF errors) |
| Auth | — | — | — | — | JWT (bcrypt + pyjwt) + OAuth (Google/GitHub live; Microsoft pending) + BYOK (Fernet-encrypted keys) | Unchanged (OAuth→SPA handoff is frontend/config-only, no backend change) | + guest accounts (`POST /auth/guest`), free-tier session quota; fixed a real OAuth→SPA bug (`oauth_callback_path_template` — the hardcoded backend-only redirect path silently broke the frontend handoff Phase 8 documented as "no backend change needed") | Unchanged | Unchanged | Production OAuth redirect URIs registered with Google (multiple URIs supported) and GitHub (single URI only — broke local GitHub-OAuth testing, accepted trade-off); Google consent screen still in "Testing" status, not yet published |
| RAG fallback | Domain-only | Unchanged | JD-hash filter | Unchanged | 3-tier: JD-hash → company-slug (11 pre-generated companies) → static | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged — live-verified against the populated production Qdrant Cloud collection |
| Interview length | Fixed `max_interview_turns` (10) | Unchanged | Unchanged | Unchanged | Unchanged | Adaptive: time + LLM judgment, researched/stated target, real closing turn; `max_interview_turns` now an absolute safety valve (40) | + candidate-initiated Terminate → `ABANDONED` (distinct from natural `COMPLETED` close), scored from whatever turns happened | Unchanged | Unchanged | Unchanged |
| Candidate input | JD text only | Unchanged | Unchanged | Unchanged | Unchanged | + resume PDF upload, threaded into interviewer prompt | Unchanged | Unchanged | Unchanged | Unchanged |
| Frontend | None | None | None | None | None | React + TS + Vite + Tailwind SPA (`frontend/`) | + guest entry point, quota-exceeded messaging, Terminate button | Unchanged | Unchanged | **Deployed to Cloudflare Pages** via Workers static assets (new `frontend/wrangler.jsonc` — Cloudflare merged Pages into Workers, requiring this config instead of the classic build-command/output-dir flow); fixed a real bug where the first build shipped with `VITE_API_BASE_URL`/`VITE_WS_BASE_URL` unset (baked-in literal `undefined` in every API call) |
| Test runner | — | — | pytest + pytest-asyncio 1.4.0 | +15 unit tests (test_jd_service.py) | +11 unit (test_auth_service.py) + 29 integration (test_auth.py) — 109 tests total (61 unit + 48 integration) | +25 unit + 21 integration — 155 tests total (86 unit + 69 integration) | +11 unit (gemini factory + `test_failover_llm_service.py`) + 10 integration (quota, terminate, guest) — 176 tests total (97 unit + 79 integration) | +10 unit (`HuggingFaceEmbeddingProvider`, `FailoverEmbeddingProvider`, factory branches) — 186 tests total (107 unit + 79 integration) | +6 unit (`health_check()` on every `EmbeddingProvider`) — 192 tests total (113 unit + 79 integration) | Unchanged (192 tests) — this phase was deployment execution, verified live against production instead of new test coverage |
| Test isolation (PG) | — | — | TRUNCATE per test (API); session DB lifecycle | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged |
| Test isolation (Redis) | — | — | DB index 1 + FLUSHDB per test | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged |
| Test isolation (Mongo) | — | — | Drop `interview_bot_test` per test | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged | Unchanged |

---

## Python 3.14 Compatibility Notes

| Package | Issue | Resolution |
|---|---|---|
| `pydantic-core==2.23.4` | PyO3 0.22.2 caps at Python 3.13; Rust build fails | Use `pydantic>=2.10` — ships stable ABI wheels |
| `sqlalchemy==2.0.36` | `typing.Union.__getitem__` API changed in 3.14 | Use `sqlalchemy>=2.0.38` |
| `tenacity==9.0.0` | `reraise` removed as public export | Pass `reraise=True` as decorator kwarg only |
| pytest subprocess (alembic) | `"python"` not on PATH — macOS default is `python3` | Use `sys.executable` in `subprocess.run()` |
