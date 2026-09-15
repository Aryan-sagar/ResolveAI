# ResolveAI

> Production-grade AI support operations assistant built with FastAPI, RAG, tool calling, guardrails, human approval workflows, and LLM-based evaluation.

ResolveAI is an AI-powered customer support system designed to handle both **knowledge-based questions** and **operational support workflows**.

Instead of treating support as a simple chatbot, ResolveAI separates routing, retrieval, reasoning, tool execution, risk assessment, and evaluation into explicit stages.

---

## What It Does

ResolveAI can:

- Answer policy and FAQ questions using Retrieval-Augmented Generation (RAG)
- Retrieve and rerank relevant knowledge-base documents
- Understand multi-turn conversations and rewrite follow-up queries
- Check live order information through tools
- Create and manage support tickets
- Handle refund workflows with approval gates
- Block prompt-injection and unsafe requests
- Generate grounded answers with source citations
- Detect invalid/hallucinated citation references
- Track per-stage latency
- Evaluate different retrieval configurations using a golden dataset
- Use an LLM judge to measure faithfulness, relevance, and context precision

---

## Architecture

```text
                         ┌──────────────────────┐
                         │      Client/API       │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     Input Guardrail  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Conversation History│
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Query Rewriter     │
                         │  (follow-up queries) │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      Intent Router   │
                         └───────┬───────┬──────┘
                                 │       │
                    requires RAG │       │ requires API
                                 ▼       ▼
                    ┌──────────────┐   ┌──────────────┐
                    │ Hybrid RAG   │   │ Tool System  │
                    │              │   │              │
                    │ Vector       │   │ Orders       │
                    │ BM25         │   │ Tickets      │
                    │ RRF          │   │ CRM          │
                    │ Reranking    │   │ Refunds      │
                    └──────┬───────┘   └──────┬───────┘
                           │                  │
                           └────────┬─────────┘
                                    ▼
                         ┌──────────────────────┐
                         │     LLM Orchestrator │
                         │  Reason + Tool Loop  │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │ Risk / Approval Gate │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Grounded Response +  │
                         │ Citations + Metadata │
                         └──────────────────────┘
````

---

## Core Design

### 1. Input Guardrails

Unsafe or malicious requests are checked before they reach the LLM.

Examples include:

* Prompt injection
* Requests to reveal system instructions
* Requests for unauthorized customer data
* Requests involving sensitive information

The system fails closed for blocked requests.

---

### 2. Conversation-Aware Query Rewriting

Follow-up questions often lack enough context for retrieval.

For example:

```text
User: Where is my order ORD456?

Assistant: Your order has shipped.

User: Can I track it?
```

The retriever receives a standalone query such as:

```text
Where is my order ORD456?
```

while the LLM still receives the original conversation.

This separates **retrieval optimization** from **conversation semantics**.

---

### 3. Intent Routing

Every request is classified into an explicit support intent:

```text
policy_question
order_status
refund_request
complaint
ticket_request
callback_request
account_question
out_of_scope
unsafe
```

The router also determines:

```text
requires_rag
requires_api
risk_level
entities
```

Few-shot examples are used to improve routing accuracy for ambiguous support requests.

---

### 4. Hybrid Retrieval

ResolveAI supports configurable retrieval modes:

```text
Vector
Hybrid
```

Hybrid retrieval combines:

* Dense vector search using Qdrant
* BM25 lexical search
* Reciprocal Rank Fusion (RRF)

The retrieval pipeline is:

```text
Query
  │
  ├── Vector Search
  │
  └── BM25 Search
          │
          ▼
      RRF Fusion
          │
       Top-N
          │
          ▼
      Reranking
          │
          ▼
       Top-K
```

---

### 5. Configurable Reranking

The reranking layer supports:

```text
none
local
cohere
```

The `none` provider acts as the baseline control group.

The local implementation uses a cross-encoder and loads lazily so application startup remains fast.

This allows experiments such as:

```text
Hybrid
vs
Hybrid + Reranking
```

without changing the retrieval implementation.

---

### 6. Tool Calling

The LLM can invoke structured support tools for operations that cannot be answered reliably from static documentation.

Examples:

```text
get_order_status
create_ticket
get_customer
add_crm_note
issue_refund
request_callback
```

Tools are executed through a controlled tool layer rather than allowing the model to directly access backend systems.

---

### 7. Human Approval for High-Risk Actions

Sensitive actions do not execute blindly.

For example:

```text
Refund request
      │
      ▼
Verify order
      │
      ▼
Check policy
      │
      ▼
Determine risk
      │
      ▼
Approval required?
      │
     YES
      │
      ▼
Pending approval
```

The assistant never falsely claims that a pending refund has already been completed.

---

### 8. Citation Validation

Generated answers can reference retrieved chunks:

```text
According to the refund policy, damaged items must be
reported within 7 days [1].
```

ResolveAI validates the citation references against the retrieved context.

Invalid references are exposed separately:

```json
{
  "citations": [...],
  "invalid_citations": []
}
```

This makes citation hallucinations measurable instead of silently ignoring them.

---

## Evaluation

ResolveAI includes an evaluation harness with a **31-question golden dataset** covering:

* Policy questions
* Order status
* Refund requests
* Ticket creation
* Complaints
* Prompt injection
* Out-of-scope questions
* Multi-turn conversations
* Query rewriting

### Retrieval Metrics

```text
Hit@5
MRR
Context Precision
```

### Generation Metrics

```text
Faithfulness
Answer Relevance
Citation Accuracy
```

### Safety / Behavior Metrics

```text
Intent Accuracy
Refusal Accuracy
Invalid Citations
Query Rewrite Hits
```

### Performance Metrics

```text
Latency P50
Latency P95
```

---

## Evaluation Variants

The evaluation harness supports four configurations:

```bash
python -m evals.run_eval --variant vector
```

```bash
python -m evals.run_eval --variant hybrid
```

```bash
python -m evals.run_eval --variant hybrid_rr --rerank local
```

```bash
python -m evals.run_eval --variant full --rerank local
```

For fast iteration without LLM judges:

```bash
python -m evals.run_eval --variant full --rerank local --fast
```

Results are appended to:

```text
evals/results.md
```

This makes it possible to compare retrieval and generation configurations using the same dataset.

---

## Tech Stack

| Component              | Technology                                   |
| ---------------------- | -------------------------------------------- |
| API                    | FastAPI                                      |
| Language               | Python                                       |
| LLM Interface          | OpenAI-compatible Chat Completions           |
| LLM Providers          | Gemini / Groq / OpenAI / OpenRouter / Ollama |
| Embeddings             | Sentence Transformers                        |
| Vector Database        | Qdrant                                       |
| Lexical Search         | BM25                                         |
| Retrieval Fusion       | Reciprocal Rank Fusion                       |
| Reranking              | Cross-Encoder / Cohere                       |
| Database               | SQLite                                       |
| Cache / Infrastructure | Redis                                        |
| Validation             | Pydantic                                     |
| Evaluation             | Custom LLM-as-Judge                          |
| Testing                | Pytest                                       |
| Deployment             | Docker Compose                               |

---

## Project Structure

```text
resolve-ai/
│
├── app/
│   ├── core/
│   │   ├── embeddings.py
│   │   ├── guardrails.py
│   │   ├── llm.py
│   │   ├── router.py
│   │   └── vectorstore.py
│   │
│   ├── db/
│   │   ├── models.py
│   │   └── session.py
│   │
│   ├── schemas/
│   │   └── chat.py
│   │
│   ├── services/
│   │   ├── ingestion.py
│   │   ├── query_rewriter.py
│   │   ├── reranker.py
│   │   ├── retrieval.py
│   │   └── orchestrator.py
│   │
│   └── main.py
│
├── data/
│   ├── password_reset.md
│   ├── refund_policy.md
│   ├── returns_exchange.md
│   └── shipping_faq.md
│
├── evals/
│   ├── golden_dataset.csv
│   ├── metrics.py
│   └── run_eval.py
│
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Getting Started

### 1. Clone

```bash
git clone https://github.com/<your-username>/resolve-ai.git
cd resolve-ai
```

### 2. Create a virtual environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

Create `.env` from `.env.example`.

Example:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
LLM_MODEL=gemini-3.6-flash

JUDGE_PROVIDER=groq
GROQ_API_KEY=your_key_here
JUDGE_MODEL=llama-3.3-70b-versatile

EMBEDDING_PROVIDER=local
RERANK_PROVIDER=local

QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379
DATABASE_URL=sqlite:///./supportops.db
```

Never commit `.env` or API keys.

### 5. Start infrastructure

```bash
docker compose up -d
```

Verify:

```bash
docker compose ps
```

### 6. Ingest the knowledge base

```bash
python -c "from app.services.ingestion import ingest_directory; print(ingest_directory('data', tenant_id='acme'))"
```

### 7. Start the API

```bash
uvicorn app.main:app --reload
```

Health check:

```text
GET http://127.0.0.1:8000/health
```

---

## Example

### Request

```http
POST /api/chat
Content-Type: application/json
```

```json
{
  "query": "What is your refund policy for damaged items?"
}
```

### Response

```json
{
  "conversation_id": "conv_xxxxx",
  "answer": "According to our refund policy...",
  "intent": "policy_question",
  "rewritten_query": "What is your refund policy for damaged items?",
  "citations": [
    {
      "source": "refund_policy.md",
      "score": 0.0328
    }
  ],
  "invalid_citations": [],
  "requires_approval": false,
  "latency_ms": 6386
}
```

---

## Engineering Decisions

### Why hybrid retrieval?

Dense retrieval handles semantic similarity while BM25 handles exact terms such as:

```text
ORD123
refund
password
7 days
```

Combining both gives a stronger baseline than relying on either method independently.

### Why rerank?

RRF determines which documents are strong candidates based on agreement between retrieval systems. It is not itself a fine-grained relevance model.

The reranker therefore operates on a smaller candidate pool:

```text
Retrieval → Top 20 → Cross Encoder → Top 5
```

This improves relevance while controlling inference cost.

### Why custom evaluation instead of RAGAS?

The evaluation system needs:

* per-claim faithfulness debugging
* fewer judge calls
* minimal dependency overhead
* direct integration with the project's response schema

The implementation follows RAGAS-style concepts while keeping the evaluation pipeline project-specific.

### Why human approval?

LLMs should not autonomously execute irreversible or financially sensitive actions without an explicit authorization boundary.

ResolveAI separates:

```text
Reasoning
   ↓
Proposal
   ↓
Approval
   ↓
Execution
```

---

## Current Limitations

This project intentionally uses lightweight local infrastructure for development.

Current limitations include:

* SQLite is used for the application database
* BM25 index is rebuilt from application data
* Tool implementations are local/mock support systems
* LLM latency depends on the selected provider
* Local reranking is CPU-bound
* Production authentication and authorization are simplified
* Evaluation scores depend on the selected judge model

These are deliberate trade-offs for a portfolio/development implementation and provide clear upgrade paths for production deployment.

---

## Roadmap

* [ ] PostgreSQL production database
* [ ] Redis-backed conversation/session state
* [ ] Streaming responses
* [ ] Production authentication and RBAC
* [ ] Async tool execution
* [ ] Distributed task processing
* [ ] Better observability with OpenTelemetry
* [ ] Prometheus/Grafana metrics
* [ ] Automated regression evaluation in CI
* [ ] Production vector-index versioning
* [ ] More comprehensive adversarial evaluation
* [ ] Kubernetes deployment

---

## License

MIT License
