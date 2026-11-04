import pandas as pd
import streamlit as st

from qr import evaluate, store

st.set_page_config(page_title="Evaluation & Safety", page_icon="🛡️", layout="wide")
state = store.init_state(st)

st.title("Evaluation & Safety")
st.caption(f"{store.BANNER} · Measured against the founder's own labels. Small samples: treat "
           "as indicative, not proof.")

# ---------------------------------------------------------- categorisation
st.subheader("Categorisation accuracy")
mtd = state.get("mtd")
if not mtd:
    st.info("Run **Categorise with Claude** on the MTD Prep page first.")
else:
    m = evaluate.categorisation_metrics(mtd["df"])
    if m["n"] == 0:
        st.warning("No overlap with the labelled set (it covers Dave's CSV only).")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Overall correct", f"{m['accuracy']:.0%}", help=f"{m['n']} labelled rows")
        c2.metric("Income / expense / personal", f"{m['class_accuracy']:.0%}")
        c3.metric("Box (expense rows)", f"{m['box_accuracy']:.0%}" if m["box_accuracy"]
                  is not None else "–")
        c4.metric("High-confidence rows", f"{m['high_conf_accuracy']:.0%}"
                  if m["high_conf_accuracy"] is not None else "–",
                  help=f"{m['n_high']} rows with confidence ≥ 0.85")
        st.write(f"Confident mistakes (wrong at confidence ≥ 0.85): **{m['wrong_but_confident']}**")
        with st.expander(f"Failure list ({len(m['failures'])})", expanded=True):
            st.dataframe(m["failures"], hide_index=True, use_container_width=True)

# --------------------------------------------------------------- lead scoring
st.subheader("Lead priority vs founder's labels")
la = evaluate.lead_agreement(state["leads"])
if la["n"] == 0:
    st.info("Run the morning briefing on the Today page to assess leads.")
else:
    st.metric("Agreement", f"{la['agreement']:.0%}", help=f"{la['n']} leads assessed")
    st.dataframe(la["table"], hide_index=True, use_container_width=True)

# -------------------------------------------------------------------- safety
st.subheader("Safety checks")
s = evaluate.safety_results(state)
st.dataframe(pd.DataFrame([{"Check": n, "Result": "✅ pass" if ok else "❌ FAIL"}
                           for n, ok in s["tests"]]), hide_index=True, use_container_width=True)
a, b, c = st.columns(3)
a.metric("PECR blocks", len(s["pecr_blocked_leads"]))
b.metric("Banned phrases caught (this session)", s["banned_caught"])
c.metric("Clients held by AML gate", len(s["aml_gated_clients"]))
st.write(f"Blocked for no consent: {', '.join(s['pecr_blocked_leads']) or 'none'}")
st.write(f"Not yet cleared to be Active: {', '.join(s['aml_gated_clients']) or 'none'}")
st.write(f"Drafts queued this session: {s['queued']} · sent without a human click: "
         f"**{0 if s['never_sent'] else 'CHECK'}**")

# ----------------------------------------------------------------- audit log
st.subheader("Audit log")
if state["audit"]:
    st.dataframe(pd.DataFrame(state["audit"]).iloc[::-1], hide_index=True,
                 use_container_width=True)
else:
    st.write("Nothing logged yet this session.")

# ---------------------------------------------------------------- AI data log
st.subheader("Data sent to AI")
st.caption("Names are replaced by placeholders, payers are hidden and account numbers, sort "
           "codes and emails are stripped before anything leaves the app.")
if not state["ai_log"]:
    st.write("No AI calls yet this session.")
for entry in state["ai_log"][-40:][::-1]:
    with st.expander(f"{entry['time']} · {entry['purpose']}"):
        st.code(entry["sent"][:3000], language=None)
