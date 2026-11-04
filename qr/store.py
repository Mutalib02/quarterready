"""Load/save JSON into st.session_state, plus a simple audit log. No database."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from qr import rules

DATA = Path(__file__).resolve().parents[1] / "data"
BANNER = "SYNTHETIC – NOT REAL DATA"


def _read(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def load_all() -> dict:
    return {
        "practice": _read("practice.json"),
        "leads": _read("leads.json"),
        "clients": _read("clients.json"),
        "messages": _read("messages.json"),
        "audit": [],
        "outbox": [],
        "ai_log": [],
        "sentiments": {},
        "banners": [],
    }


def init_state(st) -> dict:
    """Load data once per session; returns the session_state."""
    if "practice" not in st.session_state:
        st.session_state.update(load_all())
    return st.session_state


def log(state, actor: str, action: str, detail: str = "") -> None:
    state["audit"].append({"time": datetime.now().isoformat(timespec="seconds"),
                           "actor": actor, "action": action, "detail": detail})


def negative_recent(state, client_id: str, days: int = 30) -> bool:
    """Seed sentiment label in the last `days` days (the agent replaces this with an LLM label)."""
    llm = state.get("sentiments", {}).get(client_id)
    if llm is not None:
        return llm["label"] == "negative"
    now = rules.today()
    for m in state["messages"]:
        if m["client_id"] == client_id and m.get("sentiment_seed") == "negative":
            if (now - rules.to_date(m["date"])).days <= days:
                return True
    return False


def client_health(state, client: dict) -> dict:
    return rules.health_score(client, negative_recent(state, client["id"]))


def convert_lead(state, lead_id: str) -> dict | None:
    """Convert a lead to a client in onboarding. Blocked leads can't be converted."""
    lead = next(x for x in state["leads"] if x["id"] == lead_id)
    if not rules.can_market(lead):
        return None
    n = len(state["clients"]) + 1
    turnover = lead.get("est_turnover") or 0
    prop = lead.get("property_income") or 0
    client = {
        "synthetic": BANNER, "id": f"C{n:03d}", "name": lead["name"],
        "type": "landlord" if lead["business_type"] == "landlord" else "sole_trader",
        "trade": lead["trade"], "town": lead["town"], "mtd_cohort": rules.mtd_scope(turnover, prop),
        "monthly_fee": 40 if lead["business_type"] == "landlord" else 45, "services": [],
        "onboarding": {"engagement_letter": False, "id_verified": False,
                       "aml_risk_assessment": False, "hmrc_agent_authorised": False},
        "quarter_status": {"period": "Q2 2026/27 (6 Jul – 5 Oct)", "records_due": None,
                           "records_received": None, "queries_open": 0,
                           "summary_signed_off": False},
        "last_contact_date": rules.today().isoformat(), "fee_overrun_hours": 0,
        "turnover_last_12m": turnover, "property_income": prop, "property_income_rising": False,
        "nps": None, "notes": f"Converted from lead {lead_id}.",
    }
    state["clients"].append(client)
    lead["status"] = "Won"
    log(state, "human", "convert_lead", f"{lead_id} -> {client['id']}")
    return client
