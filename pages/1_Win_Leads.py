import pandas as pd
import streamlit as st

from qr import rules, store, ui

ui.chrome(st)
state = store.init_state(st)

st.title("Win Leads")
st.caption("Pipeline: New → Replied → Quoted → Won/Lost")

COHORT = {"2026": "Mandated now", "2027": "Apr 2027 wave", "2028": "Apr 2028 wave",
          "not_in_scope": "Not in scope"}


def cohort_for(lead: dict) -> str:
    if lead["business_type"] == "limited_company":
        return "Limited company (not MTD for ITSA)"
    if lead["est_turnover"] is None:
        return "Unknown – ask for turnover"
    return COHORT[rules.mtd_scope(lead["est_turnover"], lead.get("property_income") or 0)]


STATUSES = ["New", "Replied", "Quoted", "Won", "Lost"]
leads = state["leads"]

blocked = [x for x in leads if not rules.can_market(x)]
m1, m2, m3 = st.columns(3)
m1.metric("Leads", len(leads))
m2.metric("Blocked – no consent", len(blocked))
m3.metric("Won", len([x for x in leads if x["status"] == "Won"]))

rows = []
for x in leads:
    rows.append({
        "ID": x["id"], "Name": x["name"], "Source": x["source"].replace("_", " "),
        "Town": x["town"], "Turnover": (x["est_turnover"] or 0) + (x.get("property_income") or 0)
        or None,
        "MTD cohort": cohort_for(x),
        "Consent": "OK to contact" if rules.can_market(x) else "🚫 Do not contact – no consent",
        "Priority": "Not yet assessed", "Status": x["status"],
        "Received": rules.fmt_date(x["received_date"]),
    })
df = pd.DataFrame(rows)
st.dataframe(df, hide_index=True, use_container_width=True,
             column_config={"Turnover": st.column_config.NumberColumn(format="£%d")})

st.subheader("Lead detail")
choice = st.selectbox("Choose a lead", [f"{x['id']} – {x['name']}" for x in leads])
lead = next(x for x in leads if x["id"] == choice.split(" – ")[0])

left, right = st.columns([2, 1])
with left:
    st.markdown(f"**Enquiry** ({lead['source'].replace('_', ' ')}, {rules.fmt_date(lead['received_date'])})")
    st.write(lead["message"])
    st.markdown(f"**Trade:** {lead['trade']} · **Town:** {lead['town']}")
with right:
    st.markdown(f"**MTD cohort:** {cohort_for(lead)}")
    if rules.can_market(lead):
        st.markdown(ui.pill("OK to contact", "healthy"), unsafe_allow_html=True)
        st.success("OK to contact – they contacted us first or consented.")
    else:
        st.markdown(ui.pill("Blocked – no consent", "blocked"), unsafe_allow_html=True)
        st.error("🚫 Do not contact – no consent (PECR). The agent cannot draft marketing "
                 "to this lead.")
    can_convert = rules.can_market(lead) and lead["status"] != "Won" \
        and lead["business_type"] != "limited_company"
    if st.button("Convert to client", disabled=not can_convert, key=f"conv_{lead['id']}"):
        new = store.convert_lead(state, lead["id"])
        st.success(f"Created {new['id']} with an onboarding checklist. "
                   "ID and AML checks must be ticked by a human.")
