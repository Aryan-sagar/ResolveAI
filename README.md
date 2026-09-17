# ResolveAI

> A production-oriented AI support platform: RAG, tool calling, conversation memory, safety controls, evaluation, and observability — built to explore where these systems actually break.

Most "chat with your documents" demos stop at retrieval + generation. ResolveAI goes further: it retrieves knowledge, calls real tools, gates risky actions behind human approval, protects sensitive data, caches semantically, and traces every stage so a bad answer is debuggable instead of mysterious.

This README covers what I built, why, what works, and what doesn't — the trade-offs, not just the feature list.

---

## Why

A basic support chatbot is `User → LLM → Answer`. A useful one has to answer harder questions:

- What should be retrieved, and what happens when retrieval is wrong?
- What happens when the model wants to do something destructive?
- How do you preserve context without resending the whole conversation?
- How do you know *why* a response was produced?
- How do you evaluate changes without cache contamination?
- How do you keep sensitive data out of prompts, logs, and traces?

ResolveAI is built around answering those, not around demoing an LLM.

---

## Architecture

```text
User → PII handling → Query rewrite (+ memory) → Intent router
                                                        │
                                    ┌───────────────────┼───────────────────┐
                                    ▼                    ▼                   ▼
                                RAG path            Tool path          Simple response
                                    │                    │
                              Retrieve+Rerank      Preflight+Risk check
                                    │                    │
                                    └─────────┬──────────┘
                                               ▼
                                              LLM
                                     ┌─────────┴─────────┐
                                     ▼                    ▼
                                  Answer              Human approval → Execute
```

Everything above is wrapped in Langfuse tracing, with a no-op fallback so observability can never take the request path down.

---

## Core Capabilities

| Capability | What it does |
|---|---|
| **RAG** | Retrieves from Qdrant; separates public vs. internal docs by role so customers never see agent-only knowledge |
| **Conversation memory** | Rolling summary (entities, order/ticket IDs, actions taken) + recent messages, instead of unbounded context growth |
| **Query rewriting** | Resolves "that order" / "can I cancel it?" into a self-contained retrieval query using summary + recent turns |
| **Tool calling** | Typed tools with schemas, validation, preflight checks, and risk levels — not arbitrary code execution |
| **Human approval** | High-risk actions (e.g. order cancellation) are proposed, not executed; state is **re-validated at approval time**, not just at proposal time |
| **Ticket intelligence** | Best-effort LLM classification (`damaged_item`, `billing`, etc.) — failure here never blocks ticket creation |
| **PII minimization** | Card/email/phone data is masked before it reaches storage, the LLM, or Langfuse — the app decides what's safe, not the model |
| **Semantic cache** | Embedding-similarity cache scoped by tenant/role, invalidated on re-ingestion |
| **Evaluation harness** | Golden dataset + variant comparison (`--variant hybrid`, `--variant full --rerank local`); **cache is disabled during eval** so results aren't contaminated |
| **Observability** | Langfuse traces per request: route taken, retrieved docs, tool calls, latency per stage, token usage |
| **Model routing** | Configurable simple/full model split, falls back to the default model if simple isn't configured |
| **Streaming** | SSE endpoint (`/api/chat/stream`) emitting `stage` / `delta` / `tool` / `final` events over the same orchestration path as the non-streaming API |

---

## Tech Stack

FastAPI · Python · Google Gemini · Sentence Transformers · Qdrant · Redis · SQLite/PostgreSQL · Langfuse · Streamlit · Docker Compose · Pytest

---

## API

```
GET  /health
POST /api/chat
POST /api/chat/stream            (SSE)
POST /api/actions/{id}/approve
POST /api/actions/{id}/reject
POST /api/feedback               (linked to Langfuse trace)
POST /api/ingest?data_dir=data&tenant_id=acme
GET  /api/stats
```

---

## Running Locally

```powershell
git clone https://github.com/Aryan-sagar/ResolveAI.git
cd ResolveAI
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.env` from `.env.example` (never commit real keys):

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
QDRANT_URL=http://localhost:6333
DATABASE_URL=sqlite:///./supportops.db
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=your_key_here
LANGFUSE_SECRET_KEY=your_key_here
```

```powershell
docker compose up -d          # Qdrant, Redis, PostgreSQL, Langfuse
python -m uvicorn app.main:app --reload     # http://127.0.0.1:8000/docs
python data/make_kb.py
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/ingest?data_dir=data&tenant_id=acme" -Method POST
```

---

## What I Tested

Not just happy paths — failure boundaries:

- **Retrieval**: public vs. internal access control, citation correctness, role-based restrictions
- **Memory**: rolling summaries, query rewriting, cross-turn reference resolution
- **Tools**: order lookup, cancellation preflight, approval, rejection, **re-validation before execution**
- **Evaluation**: variant comparisons with cache explicitly bypassed
- **Observability**: trace creation, stage spans, tool spans, token usage metadata
- **Infra**: Docker Compose, Qdrant, Redis, PostgreSQL, local dev loop

---

## Where It Breaks (and what I'd do about it)

Being honest about gaps is the point of this section — a system isn't production-ready because it demos well.

**LLM provider quotas.** Gemini free tier hit `429 RESOURCE_EXHAUSTED` during dev. Not an app bug — needs retry/backoff, provider fallback, and real rate limiting, which the provider abstraction was built to support.

**Observability SDK drift.** An earlier version used `client.trace(...)` against a Langfuse SDK that had moved on. Lesson: third-party observability code is part of the production dependency surface and needs version pinning, not assumed compatibility.

**Local Langfuse vs. Langfuse Cloud.** The local Docker deployment and installed SDK didn't line up cleanly, so the project runs against Langfuse Cloud instead. A real deployment should pin and test the full `app → SDK → API → dashboard` chain explicitly.

**Streaming is the least mature path.** More moving parts than the normal request path — partial output, tool-call fragments across chunks, provider/client disconnects. Needs dedicated lifecycle handling and integration tests before I'd trust it in prod.

**Semantic cache is approximate.** Similar questions can still need different answers (different order/user/role/policy/date). Cache stays scoped and conservative; next step is stronger cache-key metadata and KB-version-based invalidation.

**RAG quality is bounded by retrieval quality.** Bad chunking → bad embeddings → wrong context → wrong answer, regardless of model quality. Next: hybrid BM25 + vector retrieval, better chunking, retrieval-specific eval metrics.

**Citations aren't fully grounded.** The model can produce a plausible-looking citation that doesn't match retrieved evidence. The fix is architectural, not prompting: pass explicit chunk IDs into the model and validate citations against them deterministically, rather than trusting model output.

**Known gaps, not hidden ones:** auth/RBAC, prod DB migrations, distributed task processing, provider failover, distributed caching, vector index versioning, load testing, adversarial prompt testing, CI/CD regression evals.

---

## Engineering Lessons

1. **The LLM is one component, not the architecture.** It's `LLM + retrieval + state + tools + permissions + validation + observability + evaluation`, not `prompt → LLM → answer`.
2. **Tool authorization belongs outside the model.** A model can *request* an action; deterministic application code decides if it's *allowed*.
3. **Evaluation infra matters as much as prompt quality.** A better prompt means nothing if cache or retrieval config contaminates the comparison.
4. **Observability is part of the product**, not an add-on — when an answer is wrong, I need to see the route, retrieval, tool calls, model, and token cost that produced it.
5. **Failure handling is a feature.** Provider quotas, retrieval misses, malformed output, and observability outages are normal operating conditions, not edge cases.

---

## Project Structure

```text
app/
├── api/          chat, ingest, tickets, orders, eval, stats
├── core/         llm, rag, router, tools, guardrails, observability
├── services/     ingestion, retrieval, reranker, memory, semantic_cache,
│                 query_rewriter, ticket_intel, orchestrator
├── db/           models, session
└── schemas/
data/             faqs, internal, policies, products, make_kb.py
evals/            golden_dataset.csv, scenarios.json, run_eval.py
frontend/         app.py (user), admin.py
docker-compose.yml · requirements.txt · .env.example
```

---

## Roadmap

**Near term:** finish Langfuse Cloud verification, token usage aggregation, feedback→scoring, streaming integration tests, admin dashboard, automated regression eval.

**Production hardening:** Postgres-first config, Redis-backed distributed cache, auth/RBAC, rate limiting, provider failover, background ingestion, stronger citation grounding, KB versioning, load testing, CI/CD eval gates.

---

## The Point

Anyone can get an LLM to answer "what's your refund policy?" The real questions are whether it retrieves the *right* policy, avoids leaking internal info, remembers five messages back, safely touches an order system, stops before a destructive action, and is debuggable when it's wrong.

I'd rather be able to say **"I built it, I know where it breaks, and I know what I'd change"** than claim it's finished.
