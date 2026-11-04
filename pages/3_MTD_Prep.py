import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from qr import agent, cache, categorise as cz, categories, rules, store, ui  # noqa: E402
from qr.tools import Ctx  # noqa: E402

st.set_page_config(page_title="MTD Prep", page_icon="🧾", layout="wide")
state = store.init_state(st)

st.title("MTD Prep – quarterly bank transactions")
st.caption(f"{store.BANNER} · The AI suggests; you review. Nothing is submitted to HMRC.")

ICON = {"green": "🟢", "amber": "🟠", "red": "🔴"}
DECISIONS = ["Pending", "Accept", "Override", "Ask client"]
NO_BOX = "–"
BOX_OPTIONS = [NO_BOX] + [categories.box_label(b) for b in sorted(categories.SA103)]


def box_from_label(label: str) -> int | None:
    return None if label == NO_BOX else int(label.split(" · ")[0])


# ------------------------------------------------------------------ input
has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
client = next(c for c in state["clients"] if c["id"] == "C001")
st.markdown("**Source:** Dave Hartley's Q2 2026/27 bank CSV (synthetic) by default, or upload "
            "another CSV with Date, Description, Amount columns.")
upload = st.file_uploader("Bank CSV", type="csv")
offline, local = ui.pick_mode(st)
engine_ready = st.session_state["_engine_ready"]
source_name = upload.name if upload else "dave_q2_2026.csv"

if st.button("Categorise transactions", type="primary", disabled=not engine_ready):
    try:
        raw = cz.load_transactions(upload if upload else cz.DAVE_CSV)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not read that CSV: {exc}")
        st.stop()
    ctx = Ctx(state, offline=offline, local=local)
    ctx.complete = agent.make_complete(ctx)
    with st.spinner(f"Categorising {len(raw)} rows in batches of {cz.BATCH}…"):
        try:
            df = cz.categorise(raw, ctx.complete, state["ai_log"])
            state["mtd"] = {"source": source_name, "df": df, "decisions": {},
                            "engine": "Local rule-based engine (not Claude)" if local else agent.MODEL}
            store.log(state, "agent", "categorised", f"{source_name}: {len(df)} rows")
        except cache.CacheMiss as exc:
            st.error(f"Offline: {exc} Run once in Live mode to record the cache.")
        except Exception as exc:  # noqa: BLE001
            st.error("; ".join(ctx.banners) or f"Categorisation failed: {exc}")

mtd = state.get("mtd")
if not mtd and state.get("categorised", {}).get("C001"):  # produced by the morning briefing
    mtd = state["mtd"] = {"source": "dave_q2_2026.csv (from briefing)",
                          "df": pd.DataFrame(state["categorised"]["C001"]), "decisions": {}}
if not mtd:
    st.info("Press **Categorise transactions** to start.")
    st.stop()

st.caption(f"Categorised by: {mtd.get('engine', 'unknown engine')}")
df: pd.DataFrame = mtd["df"]
decisions: dict = mtd["decisions"]

# ------------------------------------------------------------ review table
if st.button("Accept all 🟢 green rows"):
    for r in df.itertuples():
        if r.colour == "green" and decisions.get(r.row_id, {}).get("decision") in (None, "Pending"):
            decisions[r.row_id] = {"decision": "Accept"}
    store.log(state, "human", "accept_all_green", mtd["source"])

view = pd.DataFrame({
    "": [ICON[c] for c in df.colour],
    "Date": df.Date, "Description": df.Description, "Amount": df.Amount,
    "AI box": [categories.box_label(None if pd.isna(b) else int(b)) for b in df.sa103_box],
    "Your box": [decisions.get(r.row_id, {}).get("label", categories.box_label(
        None if pd.isna(r.sa103_box) else int(r.sa103_box))) for r in df.itertuples()],
    "Allowable": df.allowable, "Conf.": df.confidence.round(2), "Reason": df.reason,
    "Flag": df.flag, "Question for client": df.client_question.where(df.needs_query, ""),
    "Decision": [decisions.get(r.row_id, {}).get("decision", "Pending") for r in df.itertuples()],
})
view.insert(0, "row_id", df.row_id)

edited = st.data_editor(
    view, hide_index=True, use_container_width=True, height=520, key="mtd_editor",
    disabled=[c for c in view.columns if c not in ("Your box", "Decision")],
    column_config={
        "row_id": None,
        "Amount": st.column_config.NumberColumn(format="£%.2f"),
        "Your box": st.column_config.SelectboxColumn(options=BOX_OPTIONS, required=True),
        "Decision": st.column_config.SelectboxColumn(options=DECISIONS, required=True),
        "Reason": st.column_config.TextColumn(width="large"),
    })

# fold the edits back into decisions (and log each change)
for r in edited.to_dict("records"):
    rid = int(r["row_id"])
    orig = view.loc[view.row_id == rid].iloc[0]
    new_decision, new_label = r["Decision"], r["Your box"]
    if new_label != orig["AI box"] and new_decision == "Pending":
        new_decision = "Override"
    prev = decisions.get(rid, {})
    entry = {"decision": new_decision, "label": new_label}
    if new_label != orig["AI box"]:
        entry["box"] = box_from_label(new_label)
        if entry["box"] in (29, 39):
            entry["allowable"] = "no"
    if (prev.get("decision", "Pending"), prev.get("label", orig["AI box"])) != \
            (new_decision, new_label):
        store.log(state, "human", f"mtd_{new_decision.lower().replace(' ', '_')}",
                  f"row {rid}: {orig['Description']} -> {new_label}")
    if new_decision != "Pending" or new_label != orig["AI box"]:
        decisions[rid] = entry
    else:
        decisions.pop(rid, None)

# ------------------------------------------------------------ status + gate
def effective(rid: int) -> str:
    return decisions.get(rid, {}).get("decision", "Pending")


red_open = [r for r in df.itertuples() if r.colour == "red" and effective(r.row_id) == "Pending"]
m1, m2, m3, m4 = st.columns(4)
m1.metric("🟢 Green", int((df.colour == "green").sum()))
m2.metric("🟠 Amber", int((df.colour == "amber").sum()))
m3.metric("🔴 Red", int((df.colour == "red").sum()))
m4.metric("Red rows still to resolve", len(red_open))

st.caption("🟢 confidence ≥ 0.85 · 🟠 0.60–0.85 · 🔴 below 0.60, flagged, or the AI wants a query. "
           "Resolve each red row: Accept, Override (change the box) or Ask client.")

with st.expander("Draft questions for the client"):
    for q in cz.client_questions(df):
        st.write("• " + q)

st.subheader("Sign-off and export")
summary = cz.summarise(df, decisions)
rows = [{"Box": "Income", "Description": "Turnover", "£": summary["turnover"]}]
rows += [{"Box": b, "Description": categories.SA103[b].split(" (")[0], "£": v}
         for b, v in summary["boxes"].items()]
rows += [{"Box": "n/a", "Description": "Not claimed (disallowable / capital)",
          "£": summary["disallowed"]},
         {"Box": "n/a", "Description": "Not business (drawings, transfers, tax)",
          "£": summary["not_business"]}]
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
             column_config={"£": st.column_config.NumberColumn(format="£%.2f")})
if summary["excluded"]:
    st.warning(f"{len(summary['excluded'])} rows are held back until the client answers.")

reviewer = st.text_input("Reviewed and approved by", value="")
confirm = st.checkbox("I have reviewed this summary. It is not submitted to HMRC.")
blockers = []
if red_open:
    blockers.append(f"{len(red_open)} red rows are unresolved")
if not reviewer.strip():
    blockers.append("enter the reviewer's name")
if not confirm:
    blockers.append("tick the review confirmation")
if blockers:
    st.info("Export is locked: " + "; ".join(blockers) + ".")
st.download_button(
    "Export summary (CSV)", disabled=bool(blockers), mime="text/csv",
    data=cz.export_csv(summary, reviewer.strip() or "[name]", client["name"].replace(
        " (fictional)", "")),
    file_name="dave_q2_2026_summary.csv",
    on_click=lambda: store.log(state, "human", "export_summary", f"approved by {reviewer}"))
