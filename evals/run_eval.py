"""Usage (from repo root):
  python -m evals.run_eval --variant vector
  python -m evals.run_eval --variant hybrid
  python -m evals.run_eval --variant hybrid_rr --rerank local
  python -m evals.run_eval --variant full --rerank local
Add --fast to skip LLM judges for quick iteration; run full for report numbers.
"""
import argparse, csv, uuid
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.db.session import SessionLocal
from app.db.models import Conversation, Message
from app.services.retrieval import retriever
from app.services.reranker import make_reranker
from app.services.orchestrator import run_chat
from evals.metrics import judge_faithfulness, judge_relevance, judge_context_precision

HERE = Path(__file__).parent

def apply_variant(variant: str, rerank: str):
    settings.retrieval_mode = "vector" if variant == "vector" else "hybrid"
    settings.query_rewrite_enabled = variant == "full"
    provider = "none" if variant in ("vector", "hybrid") else rerank
    settings.rerank_provider = provider
    retriever.reranker = make_reranker(provider)

def ensure_ingested():
    retriever._build_index()
    if retriever._chunks:
        return
    from app.services.ingestion import ingest_directory
    print("knowledge base empty — ingesting data/ ...")
    ingest_directory("data", tenant_id="acme")
    retriever.invalidate()

def seed_conversation(setup_user: str, setup_assistant: str) -> str:
    conv_id = f"eval_{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    db.add(Conversation(id=conv_id, user_id="eval_user", tenant_id="acme"))
    db.add_all([Message(conversation_id=conv_id, role="user", content=setup_user),
                Message(conversation_id=conv_id, role="assistant", content=setup_assistant)])
    db.commit(); db.close()
    return conv_id

def cleanup():
    db = SessionLocal()
    db.query(Message).filter(Message.conversation_id.like("eval_%")).delete(synchronize_session=False)
    db.query(Conversation).filter(Conversation.id.like("eval_%")).delete(synchronize_session=False)
    db.commit(); db.close()

def mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None

def pctl(vals, p):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return 0
    return vals[round((len(vals) - 1) * p / 100)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True,
                    choices=["vector", "hybrid", "hybrid_rr", "full"])
    ap.add_argument("--rerank", choices=["none", "cohere", "local"],
                    default=settings.rerank_provider)
    ap.add_argument("--fast", action="store_true", help="skip LLM judges")
    args = ap.parse_args()

    apply_variant(args.variant, args.rerank)
    ensure_ingested()
    cleanup()

    rows = list(csv.DictReader(open(HERE / "golden_dataset.csv")))
    lat, intents, hits, mrrs, cites = [], [], [], [], []
    faith, rel, ctxp, rewrites, refuses, invalid_cites = [], [], [], [], [], []
    faith_n = 0

    for i, row in enumerate(rows, 1):
        conv = (seed_conversation(row["setup_user"], row["setup_assistant"])
                if row["setup_user"] else f"eval_{uuid.uuid4().hex[:10]}")
        resp = run_chat(row["query"], conversation_id=conv, tenant_id="acme", role="customer")

        exp_src = row["expected_source"].strip()
        srcs = [r["source"] for r in resp["retrieved"]]
        cited = [c["source"] for c in resp["citations"]]

        intent_ok = resp["intent"] == row["expected_intent"]
        cite_ok = not exp_src or exp_src in cited
        hit = exp_src in srcs if exp_src else None
        mrr = 1.0 / (srcs.index(exp_src) + 1) if hit else (0.0 if exp_src else None)
        rewrite_ok = (row["expected_rewrite_contains"].lower()
                      in (resp.get("rewritten_query") or "").lower()
                      if row["expected_rewrite_contains"] else None)
        refused = resp.get("guardrail") is not None or resp["intent"] == "unsafe"

        intents.append(intent_ok); cites.append(cite_ok)
        if hit is not None: hits.append(hit); mrrs.append(mrr)
        if rewrite_ok is not None: rewrites.append(rewrite_ok)
        if row["expected_intent"] == "unsafe": refuses.append(refused)
        if resp["invalid_citations"]: invalid_cites.append(len(resp["invalid_citations"]))
        lat.append(resp["latency_ms"])

        if not args.fast:
            f = judge_faithfulness(row["query"], resp["answer"], resp["retrieved"])
            if f["score"] is not None:
                faith.append(f["score"]); faith_n += 1
                if f["score"] < 1.0:
                    print(f"  [faith] {row['query'][:50]!r} unsupported: {f['unsupported']}")
            rel.append(judge_relevance(row["query"], resp["answer"]))
            ctxp.append(judge_context_precision(row["query"], resp["retrieved"]))

        problems = []
        if not intent_ok: problems.append(f"intent={resp['intent']} want={row['expected_intent']}")
        if not cite_ok: problems.append(f"cited={cited} want={exp_src}")
        if rewrite_ok is False:
            problems.append(f"rewrite={resp.get('rewritten_query')!r} missing {row['expected_rewrite_contains']!r}")
        if row["expected_intent"] == "unsafe" and not refused: problems.append("NOT refused")
        if problems:
            print(f"  FAIL [{i}] {row['query'][:60]!r} -> {'; '.join(problems)}")

    n = len(rows)
    print(f"\n=== variant={args.variant}  rerank={args.rerank}  n={n}  judges={'off' if args.fast else 'on'} ===")
    print(f"intent_acc        {sum(intents)}/{n}  {sum(intents)/n:.1%}")
    if hits: print(f"hit@5             {sum(hits)}/{len(hits)}  {sum(hits)/len(hits):.1%}   mrr={mean(mrrs):.2f}")
    print(f"citation_acc      {sum(cites)}/{n}  {sum(cites)/n:.1%}")
    if rewrites: print(f"rewrite_hits      {sum(rewrites)}/{len(rewrites)}")
    if refuses: print(f"refusals          {sum(refuses)}/{len(refuses)}")
    print(f"invalid_citations {sum(invalid_cites)}")
    if not args.fast:
        if faith: print(f"faithfulness      {mean(faith):.2f}  (n={faith_n} judged)")
        if ctxp:  print(f"context_precision {mean(ctxp):.2f}")
        if rel:   print(f"answer_relevance  {mean(rel):.1f}/5")
    print(f"latency p50/p95   {pctl(lat,50)/1000:.1f}s / {pctl(lat,95)/1000:.1f}s")

    # append to the README-able results table
    results = HERE / "results.md"
    if not results.exists():
        results.write_text("| run_at | variant | rerank | n | intent | hit@5 | mrr | ctx_prec | "
                           "faith | ans_rel | cite_acc | rewrite | refuse | p50_ms | p95_ms |\n"
                           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    def pc(xs): return f"{100*sum(xs)/len(xs):.0f}%" if xs else "-"
    with open(results, "a") as f:
        f.write(f"| {datetime.now():%Y-%m-%d %H:%M} | {args.variant} | {args.rerank} | {n} | "
                f"{pc(intents)} | {pc(hits)} | {mean(mrrs) or 0:.2f} | "
                f"{mean(ctxp) if not args.fast else '-'} | "
                f"{mean(faith) if not args.fast else '-'} | "
                f"{mean(rel) if not args.fast else '-'} | {pc(cites)} | "
                f"{pc(rewrites) if rewrites else '-'} | {pc(refuses) if refuses else '-'} | "
                f"{pctl(lat,50)} | {pctl(lat,95)} |\n")

if __name__ == "__main__":
    main()