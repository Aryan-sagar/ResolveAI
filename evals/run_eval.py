"""Usage:
  python -m evals.run_eval --variant vector   (baseline)
  python -m evals.run_eval --variant hybrid
  python -m evals.run_eval --variant hybrid_rr --rerank local
  python -m evals.run_eval --variant full --rerank local   (scenarios expect this one)
"""
import argparse, csv, json, uuid
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.core import tools
from app.db.session import SessionLocal
from app.db.models import Conversation, Message
from app.services.retrieval import retriever
from app.services.reranker import make_reranker
from app.services.orchestrator import run_chat
from evals.metrics import judge_faithfulness, judge_relevance, judge_context_precision

HERE = Path(__file__).parent

def apply_variant(variant, rerank):
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

def seed_conversation(messages):
    conv_id = f"eval_{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    db.add(Conversation(id=conv_id, user_id="eval_user", tenant_id="acme"))
    db.add_all([Message(conversation_id=conv_id, role=m["role"], content=m["content"])
                for m in messages])
    db.commit(); db.close()
    return conv_id

def cleanup():
    db = SessionLocal()
    db.query(Message).filter(Message.conversation_id.like("eval_%")).delete(synchronize_session=False)
    db.query(Conversation).filter(Conversation.id.like("eval_%")).delete(synchronize_session=False)
    db.commit(); db.close()

def load_cases():
    cases = []
    for row in csv.DictReader(open(HERE / "golden_dataset.csv")):
        cases.append({
            "name": row["query"][:48],
            "query": row["query"],
            "history": ([{"role": "user", "content": row["setup_user"]},
                         {"role": "assistant", "content": row["setup_assistant"]}]
                        if row["setup_user"] else []),
            "expect": {"intent": row["expected_intent"],
                       "source": row["expected_source"].strip() or None,
                       "rewrite_contains": row["expected_rewrite_contains"] or None,
                       "tools_any": [t for t in row["expected_tools"].split(";") if t]},
            "judge": True,
        })
    for sc in json.load(open(HERE / "scenarios.json")):
        sc.setdefault("history", [])
        cases.append(sc)
    return cases

def run_case(case, fast):
    tools.reset_mock_state()  # determinism: one case must not see another's mutations
    conv = seed_conversation(case["history"]) if case["history"] else f"eval_{uuid.uuid4().hex[:10]}"
    resp = run_chat(case["query"], conversation_id=conv, tenant_id="acme", role="customer")
    exp = case.get("expect", {})
    calls = resp["tool_calls"]
    problems, tool_case, tool_ok, arg_case, arg_ok = [], False, True, False, True

    if exp.get("intent") and resp["intent"] != exp["intent"]:
        problems.append(f"intent={resp['intent']} want={exp['intent']}")
    if exp.get("source"):
        cited = [c["source"] for c in resp["citations"]]
        if exp["source"] not in cited:
            problems.append(f"cited={cited} want={exp['source']}")
    if exp.get("rewrite_contains"):
        if exp["rewrite_contains"].lower() not in (resp.get("rewritten_query") or "").lower():
            problems.append(f"rewrite={resp.get('rewritten_query')!r}")

    if exp.get("tools_any"):
        tool_case = True
        for tool in exp["tools_any"]:
            if not any(c["name"] == tool for c in calls):
                problems.append(f"missing tool {tool}"); tool_ok = False
    for tool, want_status in (exp.get("tools") or {}).items():
        tool_case = True
        matching = [c for c in calls if c["name"] == tool]
        if not matching:
            problems.append(f"missing tool {tool}"); tool_ok = False
        elif not any(c["status"] == want_status for c in matching):
            problems.append(f"{tool}: status={[c['status'] for c in matching]} want={want_status}")
            tool_ok = False
    for tool, want_args in (exp.get("args") or {}).items():
        arg_case = True
        if not any(all(c.get("arguments", {}).get(k) == v for k, v in want_args.items())
                   for c in calls if c["name"] == tool):
            problems.append(f"{tool}: args missing {want_args}"); arg_ok = False

    if exp.get("no_approval") and resp["requires_approval"]:
        problems.append("unexpected approval request")

    if "approve" in case and resp.get("proposed_action"):
        aid = resp["proposed_action"]["action_id"]
        (tools.approve_action if case["approve"] else tools.reject_action)(aid)
    for oid, want in (exp.get("order_state") or {}).items():
        got = tools.ORDERS.get(oid, {}).get("status")
        if got != want:
            problems.append(f"order {oid}: {got} want {want}")

    judges = {}
    if case.get("judge", True) and not fast:
        f = judge_faithfulness(case["query"], resp["answer"], resp["retrieved"])
        if f["score"] is not None:
            judges["faith"] = f["score"]
            if f["score"] < 1.0:
                print(f"    [faith] unsupported: {f['unsupported']}")
        judges["rel"] = judge_relevance(case["query"], resp["answer"])
        judges["ctxp"] = judge_context_precision(case["query"], resp["retrieved"])

    return {"problems": problems, "latency": resp["latency_ms"], "judges": judges,
            "tool_case": tool_case, "tool_ok": tool_ok, "arg_case": arg_case, "arg_ok": arg_ok}

def mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None

def pctl(vals, p):
    vals = sorted(v for v in vals if v is not None)
    return vals[round((len(vals) - 1) * p / 100)] if vals else 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=["vector", "hybrid", "hybrid_rr", "full"])
    ap.add_argument("--rerank", choices=["none", "cohere", "local"], default=settings.rerank_provider)
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()

    apply_variant(args.variant, args.rerank)
    ensure_ingested()
    cleanup()

    caps = {"rewrite": settings.query_rewrite_enabled}
    cases = load_cases()
    lat, intents, cites = [], [], []
    faith, rel, ctxp = [], [], []
    tool_n = tool_ok_n = arg_n = arg_ok_n = 0
    fails = 0

    for i, case in enumerate(cases, 1):
        req = case.get("requires")
        if req and not caps.get(req):
            print(f"  SKIP [{case['name']}] — requires {req}, disabled in variant {args.variant}")
            continue
        r = run_case(case, args.fast)
        lat.append(r["latency"])
        if not r["problems"]:
            intents.append(True); cites.append(True)
        else:
            fails += 1
            intents.append(False); cites.append(False)
            print(f"  FAIL [{i}] {case['name']!r} -> {'; '.join(r['problems'])}")
        if r["tool_case"]:
            tool_n += 1; tool_ok_n += r["tool_ok"]
        if r["arg_case"]:
            arg_n += 1; arg_ok_n += r["arg_ok"]
        if "faith" in r["judges"]: faith.append(r["judges"]["faith"])
        if r["judges"].get("rel") is not None: rel.append(r["judges"]["rel"])
        if r["judges"].get("ctxp") is not None: ctxp.append(r["judges"]["ctxp"])

    n = len(cases)
    print(f"\n=== variant={args.variant} rerank={args.rerank} n={n} judges={'off' if args.fast else 'on'} ===")
    print(f"case_pass_rate    {n - fails}/{n}")
    if tool_n: print(f"tool_selection    {tool_ok_n}/{tool_n}")
    if arg_n:  print(f"tool_args         {arg_ok_n}/{arg_n}")
    if not args.fast:
        if faith: print(f"faithfulness      {mean(faith):.2f}")
        if ctxp:  print(f"context_precision {mean(ctxp):.2f}")
        if rel:   print(f"answer_relevance  {mean(rel):.1f}/5")
    print(f"latency p50/p95   {pctl(lat,50)/1000:.1f}s / {pctl(lat,95)/1000:.1f}s")

    results = HERE / "results.md"
    if not results.exists():
        results.write_text("| run_at | variant | rerank | n | pass | tool_sel | tool_args | p50_ms | p95_ms |\n"
                           "|---|---|---|---|---|---|---|---|---|\n")
    with open(results, "a") as f:
        f.write(f"| {datetime.now():%Y-%m-%d %H:%M} | {args.variant} | {args.rerank} | {n} | "
                f"{n - fails}/{n} | {tool_ok_n}/{tool_n} | {arg_ok_n}/{arg_n} | "
                f"{pctl(lat,50)} | {pctl(lat,95)} |\n")

if __name__ == "__main__":
    main()