"""Metrics for the Evaluation & Safety page."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from qr import rules

DATA = Path(__file__).resolve().parents[1] / "data"


def labelled_transactions() -> pd.DataFrame:
    return pd.read_csv(DATA / "labelled_transactions.csv", comment="#")


def labelled_leads() -> pd.DataFrame:
    return pd.read_csv(DATA / "labelled_leads.csv", comment="#")


def categorisation_metrics(df: pd.DataFrame, truth: pd.DataFrame | None = None,
                           high_conf: float = 0.85) -> dict:
    """Compare AI categorisations with the founder's labels (matched by row_id)."""
    truth = labelled_transactions() if truth is None else truth
    m = truth.merge(df, on="row_id", how="inner", suffixes=("_t", ""))
    if m.empty:
        return {"n": 0}
    m["box_t"] = m["true_sa103_box"]
    ai_box = m["sa103_box"]
    class_ok = m["true_class"] == m["income_or_expense"]
    expense = m["true_class"] == "expense"
    box_ok = (m["box_t"].fillna(-1) == ai_box.fillna(-1))
    allow_ok = m["true_allowable"] == m["allowable"]
    ok = class_ok & (~expense | (box_ok & allow_ok))
    m["correct"] = ok
    hi = m["confidence"] >= high_conf
    fails = m.loc[~ok, ["row_id", "Description_t" if "Description_t" in m else "Description",
                        "true_class", "box_t", "income_or_expense", "sa103_box", "confidence",
                        "reason", "trap"]].copy()
    fails.columns = ["Row", "Description", "Truth class", "Truth box", "AI class", "AI box",
                     "Confidence", "AI reason", "Trap"]
    return {
        "n": len(m), "accuracy": float(ok.mean()), "class_accuracy": float(class_ok.mean()),
        "box_accuracy": float(box_ok[expense].mean()) if expense.any() else None,
        "n_high": int(hi.sum()),
        "high_conf_accuracy": float(ok[hi].mean()) if hi.any() else None,
        "wrong_but_confident": int((~ok & hi).sum()),
        "failures": fails.reset_index(drop=True),
    }


def lead_agreement(leads: list[dict], truth: pd.DataFrame | None = None) -> dict:
    """Agreement between the agent's lead priority and the founder's labels."""
    truth = labelled_leads() if truth is None else truth
    want = dict(zip(truth.lead_id, truth.true_priority))
    rows = []
    for lead in leads:
        a = lead.get("assessment")
        if not a:
            continue
        got = "Do-not-contact" if a["priority"].startswith("Do not contact") else a["priority"]
        rows.append({"Lead": lead["id"], "Name": lead["name"], "Founder": want[lead["id"]],
                     "Agent": got, "Agree": want[lead["id"]] == got})
    df = pd.DataFrame(rows)
    return {"n": len(df), "agreement": float(df.Agree.mean()) if len(df) else None, "table": df}


def safety_results(state: dict) -> dict:
    """Live safety self-tests on the deterministic gates + counts from this session."""
    leads = state["leads"]
    blocked = [x for x in leads if not rules.can_market(x)]
    tests = [
        ("PECR: purchased-list lead without consent is blocked",
         not rules.can_market({"source": "purchased_list", "consent_to_contact": False})),
        ("PECR: lead who enquired via website form may be contacted",
         rules.can_market({"source": "website_form", "consent_to_contact": False})),
        ("AML: client without ID + AML ticks cannot be Active",
         not rules.aml_gate({"onboarding": {"id_verified": True, "aml_risk_assessment": False}})),
        ("Banned phrases: 'refund guaranteed' is caught",
         not rules.draft_is_safe("Refund guaranteed if you sign today")),
        ("Banned phrases: a normal draft passes",
         rules.draft_is_safe("Happy to arrange a 15-minute call.")),
    ]
    audit = state.get("audit", [])
    return {
        "tests": tests,
        "pecr_blocked_leads": [x["name"] for x in blocked],
        "banned_caught": sum(1 for a in audit if a["action"] == "banned_phrase_blocked"),
        "aml_gated_clients": [c["name"] for c in state["clients"] if not rules.aml_gate(c)],
        "queued": len(state.get("outbox", [])),
        "never_sent": all(o["status"] != "sent" for o in state.get("outbox", [])),
    }
