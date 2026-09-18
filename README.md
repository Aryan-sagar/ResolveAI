# ResolveAI

**AI customer-support copilot built around RAG, tool calling, safety controls, semantic caching, conversation memory, and observable failure modes.**

ResolveAI is a support system designed to answer customer questions from internal knowledge, retrieve live order information, and propose high-risk actions such as refunds and cancellations without executing them automatically.

The goal was not to build a chatbot that produces convincing answers.

The goal was to build a system where I can answer:

* **What did the model use to answer this?**
* **Which tool did it call and why?**
* **What happens when retrieval is wrong?**
* **What happens when the model tries something unsafe?**
* **Can repeated queries avoid another LLM call?**
* **Can I trace a bad response back to a request?**
* **Can the system be tested without an API key?**
* **What breaks first under load?**

---

## Architecture

```text
                         ┌─────────────────────┐
                         │   Streamlit UI      │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │     FastAPI API     │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │    Orchestrator     │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
       ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
       │  Guardrails │       │   Router    │       │   Memory    │
       │ PII / Input │       │ Intent/Risk │       │ Summary +   │
       │   Safety    │       │             │       │ Recent Turns│
       └─────────────┘       └──────┬──────┘       └─────────────┘
                                    │
                         ┌──────────▼──────────┐
                         │  Semantic Cache     │
                         └──────────┬──────────┘
                                    │ miss
                         ┌──────────▼──────────┐
                         │ Query Rewriter      │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │ Retrieval / Qdrant  │
                         │ Vector + Hybrid     │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │      LLM Layer      │
                         │ Provider abstraction│
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │     Tool Layer      │
                         │ Orders / Refunds /  │
                         │ Tickets / Actions   │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │ Approval Boundary   │
                         │ High-risk actions   │
                         └─────────────────────┘

              Cross-cutting: Langfuse traces • usage • feedback • metrics
```

---

## What it does

### Grounded support answers

Questions are answered against indexed support documents rather than relying entirely on model knowledge.

The response pipeline supports:

* document ingestion
* chunking and embeddings
* Qdrant retrieval
* vector and hybrid retrieval
* optional reranking
* citation validation
* query rewriting for conversational follow-ups

Responses expose the retrieved context and citations so grounding can be inspected rather than assumed.

### Intent and risk routing

Requests are classified before tool execution.

Example:

```text
"What is your refund policy?"
        ↓
policy_question
        ↓
RAG
        ↓
grounded answer
```

Whereas:

```text
"Cancel order ORD789"
        ↓
cancel_request
        ↓
order lookup
        ↓
eligibility check
        ↓
proposed cancellation
        ↓
approval required
```

The important boundary is that **a model suggesting an action is not the same thing as the system executing it**.

---

## Safety

The system treats safety as an architectural boundary rather than a prompt instruction.

### PII minimization

Sensitive information is detected and masked before it reaches model providers.

Storage and observability paths use their own masking boundary so traces and persisted conversations do not unnecessarily contain sensitive customer data.

### High-risk actions

Refunds and cancellations can require approval.

The model cannot simply respond:

```text
"Your refund has been completed."
```

when the underlying operation has not actually happened.

Instead:

```text
LLM
 ↓
tool proposal
 ↓
risk classification
 ↓
approval boundary
 ↓
execution
```

This separates **generation from authorization**.

### Prompt injection

Input guardrails detect unsafe requests before they enter the normal generation pipeline.

---

## Conversation memory

ResolveAI maintains conversation state using:

* persistent messages
* recent-turn context
* rolling summaries for older conversation history

The model therefore does not need the entire conversation indefinitely.

```text
Conversation
│
├── Older turns ──────► Summary
│
└── Recent turns ─────► Direct context
                         │
                         ▼
                       LLM
```

The important trade-off is context size versus information retention.

A production implementation would need explicit policies around:

* summary correctness
* summary drift
* token budgets
* retention
* tenant isolation
* deletion requirements

---

## Semantic cache

Repeated or semantically equivalent requests can bypass the expensive retrieval/LLM path.

```text
Query
  │
  ▼
Embedding
  │
  ▼
Semantic cache
  │
  ├── hit ──► cached response
  │
  └── miss ─► normal pipeline
```

The cache is tenant- and role-aware and uses a similarity threshold rather than exact string matching.

The threshold is intentionally configurable because cache correctness is a product decision as much as a technical one:

**false hit → wrong answer**

is considerably worse than:

**false miss → unnecessary computation**

---

## LLM provider abstraction

The LLM layer is provider-independent.

Supported infrastructure includes:

* real provider clients
* model overrides
* streaming
* usage accounting
* retry handling
* deterministic mock provider

The mock provider exists for an important reason:

> CI should test the application, not whether a developer happens to have an API key.

The mock provider makes routing, tool orchestration, streaming, and API smoke tests deterministic and keyless.

It is deliberately **not** treated as a replacement for real-model evaluation.

---

## Observability

ResolveAI integrates tracing around the request lifecycle.

A request can be followed through:

```text
Request
  ↓
Guardrail
  ↓
Rewrite
  ↓
Retrieval
  ↓
LLM
  ↓
Tool calls
  ↓
Persistence
```

Tracked information includes:

* latency
* model
* intent
* cache hit
* tool calls
* usage
* feedback
* trace identifiers

User feedback can also be associated with the corresponding trace.

This makes debugging a response a trace inspection problem rather than guesswork.

---

## Evaluation

The evaluation harness tests multiple retrieval configurations:

```text
vector
hybrid
hybrid + reranking
full pipeline
```

Metrics include:

* intent accuracy
* retrieval/source correctness
* tool selection
* tool arguments
* faithfulness
* context precision
* answer relevance
* latency

The golden dataset includes policy questions, order scenarios, conversational follow-ups, product error codes, warranty, cancellation, shipping, COD, gift cards, and loyalty scenarios.

### Current evaluation result

The deterministic mock provider is intentionally limited.

The current matrix demonstrates that the infrastructure works, but some semantic cases remain failures because the mock provider does not model the full behavior of a production LLM.

That distinction matters:

**I did not tune the mock provider to manufacture a better evaluation score.**

For production-quality evaluation, the next step is running the same harness against the target LLM providers and tracking quality/cost/latency together.

---

## Load testing

Locust was used to exercise the API locally.

Latest run:

| Metric   | Result |
| -------- | -----: |
| Requests |     65 |
| Failures |     0% |
| P50      |  36 ms |
| P90      |  55 ms |
| P95      |  63 ms |
| P99      | 340 ms |
| Max      | 340 ms |

These numbers are **local infrastructure measurements using the deterministic mock LLM**.

They should not be interpreted as production LLM latency.

The important result is that the API path survives concurrent load without request failures in this test environment.

---

## Failure analysis

This is where the project becomes more than "RAG + LLM + FastAPI."

The current system has known failure boundaries.

### Retrieval failure

If the retriever returns the wrong document, the model can produce a fluent but incorrectly grounded answer.

**Current mitigation:**

* retrieval evaluation
* citation validation
* hybrid retrieval
* optional reranking

**Production improvement:**

Add retrieval confidence thresholds and a deliberate abstention path:

```text
low retrieval confidence
        ↓
do not generate confidently
        ↓
ask clarification / escalate
```

### Tool-selection failure

A model can select the wrong tool even when the retrieved context is correct.

**Current mitigation:**

* explicit tool schemas
* intent/risk routing
* evaluation of tool selection

**Production improvement:**

Constrain available tools by route instead of exposing every tool to every request.

### Tool-argument failure

Correct tool + incorrect arguments is still a failed transaction.

For production, arguments should be validated independently of the LLM using strict schemas and domain rules.

### Semantic-cache failure

A high similarity score does not guarantee semantic equivalence.

**Production improvement:**

Introduce:

* negative/near-miss test sets
* intent-aware cache keys
* TTLs
* invalidation policies
* confidence thresholds
* cache correctness monitoring

### Model failure

The LLM can still hallucinate, misclassify intent, or misunderstand a customer.

The architecture therefore avoids making the model the final authority for:

* authorization
* transaction state
* sensitive-data handling
* high-risk actions

---

## API

Core endpoints include:

```text
GET  /health
POST /api/chat
POST /api/chat/stream
POST /api/feedback
POST /api/ingest
GET  /api/stats
```

Interactive API documentation is available through FastAPI when the application is running.

---

## Local development

### 1. Clone

```bash
git clone https://github.com/Aryan-sagar/ResolveAI.git
cd ResolveAI
```

### 2. Create environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Start infrastructure

```powershell
docker compose up -d
```

Qdrant is exposed locally on:

```text
http://localhost:6333
```

### 5. Configure environment

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Set the provider and required configuration for the environment.

For keyless development and CI:

```text
LLM_PROVIDER=mock
```

### 6. Run the API

```powershell
uvicorn app.main:app --reload
```

### 7. Run the Streamlit UI

```powershell
streamlit run frontend/app.py
```

---

## Testing

Run smoke tests:

```powershell
pytest tests/ -q
```

Run lint checks:

```powershell
ruff check app evals
```

Run the evaluation harness:

```powershell
python -m evals.run_eval --variant vector
python -m evals.run_eval --variant hybrid
python -m evals.run_eval --variant hybrid_rr --rerank local
python -m evals.run_eval --variant full --rerank local
```

Run load tests:

```powershell
locust -f locustfile.py
```

---

## Project structure

```text
ResolveAI/
│
├── app/
│   ├── api/
│   │   ├── chat.py
│   │   ├── ingest.py
│   │   ├── actions.py
│   │   └── stats.py
│   │
│   ├── core/
│   │   ├── llm.py
│   │   ├── mock_llm.py
│   │   ├── rag.py
│   │   ├── router.py
│   │   ├── tools.py
│   │   ├── guardrails.py
│   │   └── observability.py
│   │
│   ├── services/
│   │   ├── ingestion.py
│   │   ├── retrieval.py
│   │   ├── reranker.py
│   │   ├── semantic_cache.py
│   │   ├── memory.py
│   │   ├── query_rewriter.py
│   │   ├── ticket_intel.py
│   │   └── orchestrator.py
│   │
│   ├── db/
│   └── schemas/
│
├── evals/
│   ├── golden_dataset.csv
│   ├── run_eval.py
│   ├── metrics.py
│   └── results.md
│
├── tests/
│   └── test_smoke.py
│
├── frontend/
│   ├── app.py
│   └── admin.py
│
├── locustfile.py
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

---

## CI

GitHub Actions runs the core validation pipeline with:

* Python environment setup
* CPU PyTorch installation
* dependency installation
* Ruff
* smoke tests
* deterministic mock LLM
* Qdrant service

This keeps CI independent of paid model APIs.

---

## Engineering takeaways

The central lesson from building ResolveAI was that an LLM application is mostly an **orchestration and failure-management problem**.

A working demo proves:

```text
request → LLM → response
```

A system I would be comfortable extending needs stronger boundaries:

```text
request
  ↓
validate
  ↓
classify
  ↓
retrieve
  ↓
verify confidence
  ↓
generate
  ↓
validate tool/action
  ↓
authorize
  ↓
execute
  ↓
observe
  ↓
evaluate
```

That is the architectural pattern I would carry into a production system.

I built ResolveAI to work.

More importantly, I built it to make the failure modes visible enough to reason about what should change next.

---

## Status

**Current state:** functional prototype / engineering portfolio project.

The system demonstrates the complete support-copilot loop, but production deployment would still require stronger authentication and authorization, distributed state, production database configuration, secret management, rate limiting, deeper evaluation against real models, and more rigorous reliability testing.

