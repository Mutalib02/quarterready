"""Deterministic rules: MTD scope, deadlines, health score, PECR, AML, banned phrases.

Nothing in here calls an LLM. The LLM only supplies a sentiment label, which is
passed in as a plain bool.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta

DEFAULT_TODAY = date(2026, 11, 4)


def today() -> date:
    """The app's 'today' (configurable via QR_TODAY, default 4 Nov 2026)."""
    raw = os.environ.get("QR_TODAY")
    return date.fromisoformat(raw) if raw else DEFAULT_TODAY


def to_date(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def fmt_date(value: str | date | None) -> str:
    """UK dd/mm/yyyy."""
    d = to_date(value)
    return d.strftime("%d/%m/%Y") if d else "–"


# ---------------------------------------------------------------- MTD scope
def mtd_scope(turnover: float, property_income: float = 0) -> str:
    """Cohort from qualifying income (turnover + gross property income)."""
    qualifying = (turnover or 0) + (property_income or 0)
    if qualifying > 50_000:
        return "2026"
    if qualifying > 30_000:
        return "2027"
    if qualifying > 20_000:
        return "2028"
    return "not_in_scope"


COHORT_START = {
    "2026": date(2026, 4, 6),
    "2027": date(2027, 4, 6),
    "2028": date(2028, 4, 6),
}


# ---------------------------------------------------------------- deadlines
def quarter_calendar(tax_year_start: int) -> list[dict]:
    """Standard quarters for the tax year starting 6 Apr of `tax_year_start`."""
    y = tax_year_start
    return [
        {"label": "Q1", "start": date(y, 4, 6), "end": date(y, 7, 5), "due": date(y, 8, 7)},
        {"label": "Q2", "start": date(y, 7, 6), "end": date(y, 10, 5), "due": date(y, 11, 7)},
        {"label": "Q3", "start": date(y, 10, 6), "end": date(y + 1, 1, 5), "due": date(y + 1, 2, 7)},
        {"label": "Q4", "start": date(y + 1, 1, 6), "end": date(y + 1, 4, 5), "due": date(y + 1, 5, 7)},
    ]


def final_declaration_due(tax_year_start: int) -> date:
    """31 Jan after the end of the tax year."""
    return date(tax_year_start + 2, 1, 31)


def tax_year_start_for(d: date) -> int:
    return d.year if d >= date(d.year, 4, 6) else d.year - 1


def upcoming_deadlines(on: date | None = None, days_ahead: int = 120) -> list[dict]:
    """Quarterly deadlines falling between `on` and `on + days_ahead`, soonest first."""
    on = on or today()
    limit = on + timedelta(days=days_ahead)
    out = []
    ty = tax_year_start_for(on)
    for year in (ty - 1, ty, ty + 1):
        for q in quarter_calendar(year):
            if on <= q["due"] <= limit:
                out.append({**q, "tax_year": f"{year}/{str(year + 1)[2:]}",
                            "days_left": (q["due"] - on).days})
    return sorted(out, key=lambda q: q["due"])


def next_deadline(on: date | None = None) -> dict:
    return upcoming_deadlines(on, days_ahead=200)[0]


# ----------------------------------------------------------- health score
def records_days_late(quarter_status: dict, on: date | None = None) -> int:
    """Days past the records due date (0 if on time)."""
    on = on or today()
    due = to_date(quarter_status.get("records_due"))
    if due is None:
        return 0
    received = to_date(quarter_status.get("records_received"))
    return max(((received or on) - due).days, 0)


def health_score(client: dict, negative_sentiment: bool = False,
                 on: date | None = None) -> dict:
    """0-100 score with a transparent breakdown. Returns score, band, breakdown."""
    on = on or today()
    score = 100
    breakdown: list[dict] = []

    def deduct(points: int, reason: str) -> None:
        nonlocal score
        score -= points
        breakdown.append({"points": -points, "reason": reason})

    qs = client.get("quarter_status") or {}
    late = records_days_late(qs, on)
    if late > 14:
        deduct(25, f"Records {late} days late")
    queries = int(qs.get("queries_open") or 0)
    if queries:
        deduct(min(5 * queries, 20), f"{queries} open client queries")
    if negative_sentiment:
        deduct(20, "Negative message in the last 30 days")
    last = to_date(client.get("last_contact_date"))
    if last and (on - last).days > 45:
        deduct(10, f"No contact for {(on - last).days} days")
    if (client.get("fee_overrun_hours") or 0) > 3:
        deduct(10, f"Fee overrun of {client['fee_overrun_hours']} hours")
    nps = client.get("nps")
    if nps is not None and nps <= 6:
        deduct(10, f"NPS of {nps}")

    score = max(score, 0)
    return {"score": score, "band": health_band(score), "breakdown": breakdown}


def health_band(score: int) -> str:
    if score >= 75:
        return "Healthy"
    if score >= 50:
        return "Watch"
    return "At risk"


# ---------------------------------------------------------- opportunities
def opportunities(client: dict) -> list[str]:
    out = []
    if (client.get("turnover_last_12m") or 0) >= 80_000:
        out.append("Approaching VAT threshold £90k")
    if client.get("mtd_cohort") == "2027":
        out.append("MTD onboarding before Apr 2027")
    if client.get("property_income_rising"):
        out.append("Landlord service review")
    return out


# ------------------------------------------------------------ compliance
CONTACTED_US_FIRST = {"website_form", "referral", "phone", "social_enquiry", "event"}


def can_market(lead: dict) -> bool:
    """PECR gate: individuals may only be marketed to if they contacted us or consented."""
    return bool(lead.get("consent_to_contact")) or lead.get("source") in CONTACTED_US_FIRST


def consent_status(lead: dict) -> str:
    return "OK to contact" if can_market(lead) else "Do not contact – no consent"


def aml_gate(client: dict) -> bool:
    """A client may be Active only once a human has ticked ID and AML risk assessment."""
    ob = client.get("onboarding") or {}
    return bool(ob.get("id_verified") and ob.get("aml_risk_assessment"))


def onboarding_status(client: dict) -> str:
    ob = client.get("onboarding") or {}
    if aml_gate(client) and ob.get("engagement_letter") and ob.get("hmrc_agent_authorised"):
        return "Active"
    if aml_gate(client):
        return "Active (paperwork outstanding)"
    return "Onboarding – blocked by AML checks"


BANNED_PHRASES = [
    "guarantee", "guaranteed", "you will save", "refund guaranteed",
    "you will get a refund", "you'll get a refund", "no risk of enquiry",
]


def banned_phrases_found(text: str) -> list[str]:
    low = (text or "").lower()
    return [p for p in BANNED_PHRASES if re.search(r"\b" + re.escape(p), low)]


def draft_is_safe(text: str) -> bool:
    return not banned_phrases_found(text)
