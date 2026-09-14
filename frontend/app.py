import json
import streamlit as st
import requests

API = "http://localhost:8000"
st.title("SupportOps AI Copilot")
st.caption("Ask about orders, policies, refunds — or ask it to take an action.")

for k, default in [("conversation_id", None), ("messages", []), ("pending", None)]:
    if k not in st.session_state:
        st.session_state[k] = default

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("e.g. My order ORD123 arrived damaged. I want a refund."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"), st.spinner("Working..."):
        r = requests.post(f"{API}/api/chat", json={
            "query": prompt, "conversation_id": st.session_state.conversation_id}).json()
        st.session_state.conversation_id = r["conversation_id"]
        st.markdown(r["answer"])
        if r["citations"]:
            st.caption("Sources: " + ", ".join(c["source"] for c in r["citations"]))
        if r["tool_calls"]:
            st.caption("Actions: " + " · ".join(f"{t['name']} → {t['status']}" for t in r["tool_calls"]))
        if r["requires_approval"] and r["proposed_action"]:
            st.session_state.pending = r["proposed_action"]
        st.session_state.messages.append({"role": "assistant", "content": r["answer"]})

if st.session_state.pending:
    pa = st.session_state.pending
    st.warning(f"⚠️ Proposed action requiring approval: **{pa['name']}**\n\n```json\n{json.dumps(pa['arguments'], indent=2)}\n```")
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