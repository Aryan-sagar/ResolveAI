import csv, requests

API = "http://localhost:8000"

def run():
    rows = list(csv.DictReader(open("evals/golden_dataset.csv")))
    intent_hits = cite_hits = refusal_hits = 0
    for row in rows:
        r = requests.post(f"{API}/api/chat", json={"query": row["query"]}).json()
        if r["intent"] == row["expected_intent"]:
            intent_hits += 1
        if not row["expected_source"] or row["expected_source"] in [c["source"] for c in r["citations"]]:
            cite_hits += 1
        if row["expected_intent"] == "unsafe" and r["intent"] == "unsafe":
            refusal_hits += 1
    n = len(rows)
    print(f"n={n}  intent_accuracy={intent_hits/n:.0%}  citation_accuracy={cite_hits/n:.0%}")
    print(f"injection_refusals={refusal_hits}/{sum(1 for r in rows if r['expected_intent']=='unsafe')}")

if __name__ == "__main__":
    run()