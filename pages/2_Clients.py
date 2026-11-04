import pandas as pd
import streamlit as st

from qr import rules, store

st.set_page_config(page_title="Clients", page_icon="👥", layout="wide")
state = store.init_state(st)

st.title("Clients")
st.caption(f"{store.BANNER} · MTD deadlines, records and onboarding")

nd = rules.next_deadline()
st.markdown(f"**Next deadline:** {nd['label']} update for {nd['tax_year']} due "
            f"**{rules.fmt_date(nd['due'])}** ({nd['days_left']} days).")

BAND_ICON = {"Healthy": "🟢 Healthy", "Watch": "🟠 Watch", "At risk": "🔴 At risk"}


def records_status(c: dict) -> str:
    qs = c["quarter_status"]
    if qs.get("records_received"):
        late = rules.records_days_late(qs)
        suffix = f" ({late}d late)" if late else ""
        return f"Received {rules.fmt_date(qs['records_received'])}{suffix}"
    if qs.get("records_due") is None:
        return "Not yet due"
    return f"⚠️ Missing – {rules.records_days_late(qs)}d late"


rows = []
for c in state["clients"]:
    h = store.client_health(state, c)
    rows.append({
        "ID": c["id"], "Name": c["name"], "Type": c["type"].replace("_", " "),
        "MTD cohort": c["mtd_cohort"].replace("_", " "), "Next deadline": rules.fmt_date(nd["due"]),
        "Records": records_status(c), "Status": rules.onboarding_status(c),
        "Health": f"{BAND_ICON[h['band']]} ({h['score']})",
        "Opportunities": "; ".join(rules.opportunities(c)),
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

st.subheader("Client detail")
choice = st.selectbox("Choose a client", [f"{c['id']} – {c['name']}" for c in state["clients"]])
client = next(c for c in state["clients"] if c["id"] == choice.split(" – ")[0])

left, right = st.columns(2)
with left:
    st.markdown(f"**{client['name']}** – {client['trade']}, {client['town']}")
    st.markdown(f"Fee £{client['monthly_fee']}/month · MTD cohort {client['mtd_cohort']}")
    qs = client["quarter_status"]
    st.markdown(f"**{qs['period']}** · open queries: {qs['queries_open']} · "
                f"records: {records_status(client)}")
    st.caption(client["notes"])
    h = store.client_health(state, client)
    st.markdown(f"**Health score {h['score']} – {h['band']}**")
    if h["breakdown"]:
        for b in h["breakdown"]:
            st.write(f"{b['points']}: {b['reason']}")
    else:
        st.write("No deductions.")

with right:
    st.markdown("**Onboarding checklist**")
    st.caption("The agent can remind, but only a human can tick the ID and AML boxes.")
    ob = client["onboarding"]
    labels = {"engagement_letter": "Engagement letter signed",
              "id_verified": "ID verified (human)",
              "aml_risk_assessment": "AML risk assessment done (human)",
              "hmrc_agent_authorised": "HMRC agent authorisation"}
    for key, label in labels.items():
        new = st.checkbox(label, value=ob[key], key=f"{client['id']}_{key}")
        if new != ob[key]:
            ob[key] = new
            store.log(state, "human", f"tick_{key}", f"{client['id']} -> {new}")
    if rules.aml_gate(client):
        st.success(rules.onboarding_status(client))
    else:
        st.warning("Cannot be Active until ID verified and AML risk assessment are both ticked.")

    st.markdown("**Messages**")
    msgs = [m for m in state["messages"] if m["client_id"] == client["id"]]
    for m in sorted(msgs, key=lambda m: m["date"], reverse=True):
        st.write(f"{rules.fmt_date(m['date'])} – “{m['text']}”")
    if not msgs:
        st.write("No messages.")
