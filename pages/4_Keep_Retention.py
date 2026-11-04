import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from qr import agent, cache, rules, store, tools, ui  # noqa: E402
from qr.tools import Ctx  # noqa: E402

st.set_page_config(page_title="Keep – Retention", page_icon="🤝", layout="wide")
state = store.init_state(st)

st.title("Keep – Retention")
st.caption(f"{store.BANNER} · Health scores use a transparent formula; only the sentiment label "
           "comes from the AI.")

BAND_ICON = {"Healthy": "🟢", "Watch": "🟠", "At risk": "🔴"}
health = {c["id"]: store.client_health(state, c) for c in state["clients"]}

st.subheader("Client health")
rows = [{"Client": c["name"], "Score": health[c["id"]]["score"],
         "Band": f"{BAND_ICON[health[c['id']]['band']]} {health[c['id']]['band']}",
         "Why": "; ".join(f"{b['points']} {b['reason']}" for b in health[c["id"]]["breakdown"])
         or "No deductions"}
        for c in sorted(state["clients"], key=lambda c: health[c["id"]]["score"])]
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
st.caption("Start at 100. −25 records >14 days late · −5 per open query (max −20) · −20 negative "
           "message in the last 30 days · −10 no contact >45 days · −10 fee overrun >3 hours · "
           "−10 NPS ≤ 6. Healthy ≥ 75, Watch 50–74, At risk < 50.")

left, right = st.columns(2)
with left:
    st.subheader("At-risk and watch list")
    flagged = [c for c in state["clients"] if health[c["id"]]["band"] != "Healthy"]
    if not flagged:
        st.write("Nobody at risk.")
    for c in flagged:
        h = health[c["id"]]
        with st.container(border=True):
            st.markdown(f"**{c['name']}** – {BAND_ICON[h['band']]} {h['band']} ({h['score']})")
            for b in h["breakdown"]:
                st.write(f"{b['points']}: {b['reason']}")
            msgs = [m for m in state["messages"] if m["client_id"] == c["id"]]
            if msgs:
                last = max(msgs, key=lambda m: m["date"])
                st.caption(f"Latest message ({rules.fmt_date(last['date'])}): “{last['text']}”")
with right:
    st.subheader("Opportunities")
    found = [(c, rules.opportunities(c)) for c in state["clients"] if rules.opportunities(c)]
    for c, ops in found:
        with st.container(border=True):
            st.markdown(f"**{c['name']}**")
            for o in ops:
                st.write("• " + o)
            if c["turnover_last_12m"] >= 80_000:
                st.caption(f"Turnover £{c['turnover_last_12m']:,} vs £90,000 VAT registration "
                           "threshold.")

# ------------------------------------------------------------- retention draft
st.subheader("Draft a retention message")
has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
offline, local = ui.pick_mode(st)
engine_ready = st.session_state["_engine_ready"]
pick = st.selectbox("Client", [f"{c['id']} – {c['name']}" for c in state["clients"]],
                    index=next((i for i, c in enumerate(state["clients"])
                                if health[c["id"]]["band"] == "At risk"), 0))
cid = pick.split(" – ")[0]
if st.button("Draft retention message", disabled=not engine_ready):
    ctx = Ctx(state, offline=offline, local=local)
    ctx.complete = agent.make_complete(ctx)
    try:
        with st.spinner("Drafting…"):
            state["retention_draft"] = {"client_id": cid, **tools.draft_retention_message(ctx, cid)}
    except cache.CacheMiss as exc:
        st.error(f"Offline: {exc} Run once in Live mode to record the cache.")
    except Exception as exc:  # noqa: BLE001
        st.error("; ".join(ctx.banners) or f"Drafting failed: {exc}")

draft = state.get("retention_draft")
if draft and draft["client_id"] == cid and "body" in draft:
    ctx = Ctx(state, offline=True)
    subject = st.text_input("Subject", ctx.redactor.restore(draft["subject"]))
    body = st.text_area("Message", ctx.redactor.restore(draft["body"]), height=240)
    st.caption("No discounts without the partner's approval. Nothing is sent.")
    if st.button("Send to Approval Queue"):
        res = tools.queue_for_approval(ctx, cid, "email", subject, body,
                                       "Retention: client health flagged")
        if res["queued"]:
            st.success(f"Queued as {res['approval_id']}. Approve it on the Today page.")
        else:
            st.error(res["error"])
