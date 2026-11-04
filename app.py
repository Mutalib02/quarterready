import streamlit as st

from qr import rules, store

st.set_page_config(page_title="QuarterReady", page_icon="📅", layout="wide")
state = store.init_state(st)

st.title("QuarterReady – Today")
st.caption(f"{store.BANNER} · {state['practice']['name']} · today is {rules.fmt_date(rules.today())}")

nd = rules.next_deadline()
leads_new = [x for x in state["leads"] if x["status"] == "New"]
at_risk = [c for c in state["clients"] if store.client_health(state, c)["band"] == "At risk"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("New leads", len(leads_new))
c2.metric(f"{nd['label']} deadline ({rules.fmt_date(nd['due'])})", f"{nd['days_left']} days")
c3.metric("At-risk clients", len(at_risk))
c4.metric("Awaiting approval", len([o for o in state["outbox"] if o.get("status") == "pending"]))

st.info("The morning briefing agent and Approval Queue are coming next. "
        "Use the Win – Leads and Clients pages in the sidebar.")
