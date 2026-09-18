import json
import streamlit as st
import requests

API = "http://localhost:8000"
st.title("SupportOps AI Copilot")
st.caption("Orders, policies, refunds, cancellations — grounded answers with citations and safe actions.")

for k, v in [("conversation_id", None), ("messages", []), ("pending", None), ("fb_done", set())]:
    if k not in st.session_state:
        st.session_state[k] = v

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

def sse_events(payload):
    with requests.post(f"{API}/api/chat/stream", json=payload, stream=True) as r:
        event = None
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                yield event, json.loads(line.split(":", 1)[1])

if prompt := st.chat_input("e.g. My order ORD123 arrived damaged. I want a refund."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        info = st.empty()
        text = st.empty()
        answer, final = "", None
        for ev, data in sse_events({"query": prompt,
                                    "conversation_id": st.session_state.conversation_id}):
            if ev == "stage":
                info.caption(f"⚙️ {data}...")
            elif ev == "delta":
                answer += data["text"]
                text.markdown(answer + "▌")
            elif ev == "tool":
                st.caption(f"🔧 {data['name']} → {data['status']}")
            elif ev == "final":
                final = data
        text.markdown(answer)
        info.empty()
        if final:
            st.session_state.conversation_id = final["conversation_id"]
            if final["cache_hit"]:
                st.caption(f"⚡ served from semantic cache (similarity {final.get('cache_score')})")
            if final["citations"]:
                st.caption("Sources: " + ", ".join(c["source"] for c in final["citations"]))
            if final.get("retrieved"):
                with st.expander("Why this answer — retrieved chunks"):
                    for c in final["retrieved"]:
                        st.markdown(f"**{c['source']}** (score {c.get('score')})")
                        st.markdown(c["content"][:400] + "…")
            if final.get("ticket_enrichment"):
                st.caption(f"🎫 Ticket enriched: {final['ticket_enrichment']}")
            if final["requires_approval"] and final["proposed_action"]:
                st.session_state.pending = final["proposed_action"]
            st.session_state.messages.append({"role": "assistant", "content": answer})
            key = f"fb_{len(st.session_state.messages)}"
            c1, c2 = st.columns(2)
            if c1.button("👍", key=f"{key}_up") and key not in st.session_state.fb_done:
                requests.post(f"{API}/api/feedback", json={"conversation_id": final["conversation_id"], "rating": 1})
                st.session_state.fb_done.add(key); st.toast("Thanks!")
            if c2.button("👎", key=f"{key}_down") and key not in st.session_state.fb_done:
                requests.post(f"{API}/api/feedback", json={"conversation_id": final["conversation_id"], "rating": -1})
                st.session_state.fb_done.add(key); st.toast("Noted — this helps us find bad retrievals.")

if st.session_state.pending:
    pa = st.session_state.pending
    st.warning(f"⚠️ Proposed action requiring approval: **{pa['name']}**\n\n"
               f"```json\n{json.dumps(pa['arguments'], indent=2)}\n```")
    c1, c2 = st.columns(2)
    if c1.button("✅ Approve"):
        res = requests.post(f"{API}/api/actions/{pa['action_id']}/approve").json()
        st.session_state.messages.append({"role": "assistant",
            "content": f"Action approved and executed:\n```json\n{json.dumps(res, indent=2)}\n```"})
        st.session_state.pending = None
        st.rerun()
    if c2.button("❌ Reject"):
        requests.post(f"{API}/api/actions/{pa['action_id']}/reject")
        st.session_state.messages.append({"role": "assistant", "content": "Action rejected. No changes were made."})
        st.session_state.pending = None
        st.rerun()