import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from qr import agent, cache, rules, store, ui  # noqa: E402
from qr.tools import Ctx  # noqa: E402

st.set_page_config(page_title="QuarterReady", page_icon="📅", layout="wide")
state = store.init_state(st)
state.setdefault("banners", [])

st.title("QuarterReady – Today")
st.caption(f"{store.BANNER} · {state['practice']['name']} · today is "
           f"{rules.fmt_date(rules.today())} · nothing is ever sent or filed with HMRC")

# ----------------------------------------------------------------- KPI strip
nd = rules.next_deadline()
pending = [o for o in state["outbox"] if o["status"] == "pending"]
new_leads = [x for x in state["leads"] if x["status"] == "New"]
at_risk = [c for c in state["clients"] if store.client_health(state, c)["band"] == "At risk"]
k1, k2, k3, k4 = st.columns(4)
k1.metric("New leads", len(new_leads))
k2.metric(f"{nd['label']} due {rules.fmt_date(nd['due'])}", f"{nd['days_left']} days")
k3.metric("At-risk clients", len(at_risk))
k4.metric("Awaiting approval", len(pending))

# ------------------------------------------------------------ briefing control
has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
offline, local = ui.pick_mode(st)
engine_ready = st.session_state["_engine_ready"]

for b in state["banners"]:
    st.warning(b)

if st.button("▶ Run morning briefing", type="primary", disabled=not engine_ready):
    # a fresh run starts from the original data so the demo is repeatable
    fresh = store.load_all()
    for k in ("leads", "clients", "messages", "outbox", "audit"):
        state[k] = fresh[k]
    state["ai_log"], state["sentiments"], state["banners"] = [], {}, []
    ctx = Ctx(state, offline=offline, local=local)
    with st.status("Agent is working…", expanded=True) as status:
        def show(step: dict) -> None:
            args = ", ".join(f"{k}={v!r}" for k, v in step["args"].items() if k != "body")
            if step["reason"] and step["reason"] != "(same batch)":
                st.markdown(f"_{step['reason']}_")
            st.markdown(f"🔧 **{step['tool']}**({args[:90]}) → {step['result']}")
        try:
            agent.run_briefing(ctx, on_step=show)
            status.update(label="Briefing complete", state="complete", expanded=False)
        except cache.CacheMiss as exc:
            state["banners"].append(f"Offline: {exc} Run once in Live mode to record the cache.")
            status.update(label="Stopped: nothing cached for this step", state="error")
        except Exception as exc:  # noqa: BLE001
            state["banners"].extend(ctx.banners or [f"Briefing failed: {exc}"])
            status.update(label="Briefing failed", state="error")
    st.rerun()

briefing = state.get("briefing")
if briefing:
    st.subheader("Prioritised to-do list")
    st.markdown(briefing["summary"])
    u = briefing["usage"]
    st.caption(f"Engine: {briefing.get('engine', '?')} · {len(briefing['steps'])} tool calls · "
               f"{u['calls']} live API calls, "
               f"{u['cached']} replayed from cache · {u['input']:,} tokens in / "
               f"{u['output']:,} out")
    with st.expander("Step trace"):
        for s in briefing["steps"]:
            st.markdown(f"**{s['turn']}.** `{s['tool']}` – {s['result']}")

# ----------------------------------------------------------- approval queue
st.subheader("Approval Queue")
st.caption("Every outbound message waits here. Approving only moves it to the simulated Sent log.")
if not pending:
    st.write("Nothing waiting.")

for item in pending:
    iid = item["id"]
    with st.container(border=True):
        st.markdown(f"**To {item['recipient_name']}** ({item['kind']}) · {item['channel']} · "
                    f"_{item['reason']}_")
        editing = st.session_state.get(f"edit_{iid}", False)
        if editing:
            subj = st.text_input("Subject", item["subject"], key=f"s_{iid}")
            body = st.text_area("Body", item["body"], height=200, key=f"b_{iid}")
            if st.button("Save edit", key=f"save_{iid}"):
                found = rules.banned_phrases_found(subj + " " + body)
                if found:
                    st.error(f"Not saved: contains banned phrases {found}.")
                else:
                    item["subject"], item["body"] = subj, body
                    store.log(state, "human", "edit_draft", iid)
                    st.session_state[f"edit_{iid}"] = False
                    st.rerun()
        else:
            st.markdown(f"**{item['subject']}**")
            st.text(item["body"])
        a, e, r, _ = st.columns([1, 1, 1, 5])
        if a.button("✅ Approve", key=f"ap_{iid}", disabled=editing):
            item["status"] = "approved"
            if item["kind"] == "lead":
                next(x for x in state["leads"] if x["id"] == item["recipient_id"])[
                    "status"] = "Replied"
            store.log(state, "human", "approve", iid)
            st.rerun()
        if e.button("✏️ Edit", key=f"ed_{iid}", disabled=editing):
            st.session_state[f"edit_{iid}"] = True
            st.rerun()
        if r.button("🚫 Reject", key=f"rj_{iid}", disabled=editing):
            item["status"] = "rejected"
            store.log(state, "human", "reject", iid)
            st.rerun()

sent = [o for o in state["outbox"] if o["status"] == "approved"]
with st.expander(f"Sent log (simulated) – {len(sent)}"):
    for o in sent:
        st.markdown(f"✅ **{o['recipient_name']}** – {o['subject']} _(simulated send, "
                    f"nothing left this app)_")
