import streamlit as st
import requests

st.set_page_config(page_title="SupportOps Admin", layout="wide")
st.title("SupportOps Admin")
r = requests.get("http://localhost:8000/api/stats").json()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Queries", r["queries"])
c2.metric("Avg latency", f"{r['latency_ms']['avg']/1000:.1f}s")
c3.metric("p95 latency", f"{r['latency_ms']['p95']/1000:.1f}s")
c4.metric("Cache hit rate", f"{r['cache']['hit_rate'] or 0:.0%}")
c5.metric("Feedback", f"👍 {r['feedback']['up']} / 👎 {r['feedback']['down']}")

left, right = st.columns(2)
with left:
    st.subheader("Latency (recent 100)")
    st.line_chart(r["latency_history"])
with right:
    st.subheader("Token usage by model")
    st.dataframe([{"model": m, **u} for m, u in r["token_usage"].items()] or [{"model": "no data yet"}],
                 hide_index=True)

st.subheader("Tool outcomes")
rows = [{"tool": t, **statuses} for t, statuses in r["tools"].items()]
st.dataframe(rows or [{"tool": "no calls yet"}], hide_index=True)

st.subheader("Recent tool calls (audit trail)")
st.dataframe(r["recent_tool_calls"] or [{"tool": "none"}], hide_index=True)
st.caption("Full per-request traces (retrieved chunks, prompts, spans) live in the Langfuse UI.")