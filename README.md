# AI Interview Simulator

An adaptive, RAG-grounded interview simulation platform. Candidates practice technical, behavioral,
and HR interviews against an AI interviewer that asks context-aware follow-ups, adapts to job
descriptions and résumés, and produces a scored closing report — not a static Q&A quiz.

Full technical detail lives in [`docs/HLD.md`](docs/HLD.md) (architecture) and
[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) (how to use the product). This file is just the map.

## What it does

- Runs a live, streaming interview over WebSocket — the interviewer asks a question, the candidate
  answers, the next question adapts to that answer.
- Grounds questions in a retrieval-augmented knowledge base (technical Q&A, behavioral/HR content,
  job-description-specific material, and pre-generated company-style question banks) rather than
  relying purely on the LLM's own training.
- Scores every turn silently, then produces a full closing report (strengths, gaps, actionable
  recommendations, hire signal) once the interview ends.
- Resolves a realistic interview length per session (stated in the job description, researched via
  web search for the named company/role, or a sensible default) instead of a fixed turn count, and
  closes with a real in-character sign-off rather than cutting off abruptly.
- Supports signing in with email/phone+password or Google/GitHub OAuth, a no-signup guest trial, and
  bring-your-own-key (BYOK) so a user can supply their own LLM provider key instead of the app's
  shared default.

## Stack at a glance

| Layer | Technology |
|---|---|
| Backend | FastAPI (async), Python 3.14 |
| Frontend | React + TypeScript + Vite + Tailwind (static build, no Node runtime in production) |
| Relational data | PostgreSQL (users, sessions, scores, auth) via SQLAlchemy async + Alembic |
| Document data | MongoDB (transcripts, knowledge base, closing reports) |
| Vector search | Qdrant (RAG retrieval over the knowledge base) |
| Cache / session state | Redis |
| LLM | Google Gemini (app default) or Groq — pluggable per session, users can bring their own key |
| Embeddings | Hugging Face Inference Providers (`BAAI/bge-base-en-v1.5`) in production; Ollama (`nomic-embed-text`) for local dev, kept as a coded fallback |

See [`docs/HLD.md`](docs/HLD.md) for how these pieces actually fit together, and
`dependency_architecture.md` for the full engineering-level reference (module dependency graph,
migration history, every service's design decisions).

## Local development

```bash
# Backend
docker compose up -d              # Postgres, MongoDB, Redis, Qdrant
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env              # fill in secrets — see .env.example for what each one is
alembic upgrade head
python scripts/ingest_knowledge_base.py   # one-time: seeds + embeds the knowledge base
uvicorn main:app --reload

# Frontend
cd frontend
npm install
cp .env.example .env
npm run dev
```

Run the test suite with `pytest tests/` (or `pytest tests/unit/ tests/integration/test_interview_ws.py`
for the subset that doesn't need Docker).

## Project status

Deployed. Backend on Render, frontend on Cloudflare Pages, PostgreSQL on Neon, MongoDB on
MongoDB Atlas, Redis on Upstash, Qdrant on Qdrant Cloud, embeddings via Hugging Face Inference
Providers — see `logs/changelog12.md` for the full deployment writeup and two real bugs found
running the stack against real cloud infra for the first time. See the project's internal TODO
for remaining follow-ups (Google OAuth consent screen publishing, Microsoft OAuth, live
video/audio).
