"""Tool definitions + Python implementations for the agent.

Rules, pricing, scores and compliance gates are Python. The LLM is only used for judgement
and language, via ctx.ask_json (which funnels through agent.complete and the cache).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal

from pydantic import BaseModel, Field, ValidationError

from qr import rules, store
from qr.redact import Redactor

SERVICE_KEYS = ["mtd_sole_trader", "landlord_1_2", "bookkeeping", "vat_returns"]


# ------------------------------------------------------------------ context
@dataclass
class Ctx:
    """Everything a tool needs. `complete` is injected by agent.py."""
    state: dict
    complete: Callable | None = None
    offline: bool = False
    redactor: Redactor = field(default_factory=Redactor)
    banners: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=lambda: {"input": 0, "output": 0, "calls": 0, "cached": 0})

    def __post_init__(self) -> None:
        for p in (self.state.get("leads", []) + self.state.get("clients", [])):
            person = p.get("business_type", p.get("type")) != "limited_company"
            self.redactor.add_name(p["name"], person=person)
        self.state.setdefault("ai_log", [])
        self.state.setdefault("outbox", [])
        self.state.setdefault("sentiments", {})

    def ask_json(self, purpose: str, system: str, prompt: str, model: type[BaseModel]):
        """One cached LLM call returning a validated pydantic object; re-asks once."""
        prompt = self.redactor.redact(prompt)
        schema = json.dumps(model.model_json_schema().get("properties", {}))
        system = system + f"\nReply with ONLY a JSON object with these fields: {schema}"
        messages = [{"role": "user", "content": prompt}]
        for attempt in range(2):
            self.state["ai_log"].append({"purpose": purpose, "sent": prompt,
                                         "time": datetime.now().isoformat(timespec="seconds")})
            resp = self.complete(system, messages, None, 700)
            text = "".join(b["text"] for b in resp["content"] if b["type"] == "text")
            try:
                start, end = text.index("{"), text.rindex("}") + 1
                return model.model_validate(json.loads(text[start:end]))
            except (ValueError, ValidationError) as exc:
                messages = messages + [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": f"That was invalid ({exc}). Reply with ONLY "
                                                f"valid JSON matching the fields."}]
        raise ValueError(f"{purpose}: model did not return valid JSON")


# --------------------------------------------------------------- LLM schemas
class LeadAssessment(BaseModel):
    priority: Literal["High", "Medium", "Low"]
    fit_reason: str = Field(description="max 25 words")
    urgency_reason: str
    suggested_services: list[str] = Field(description=f"subset of {SERVICE_KEYS}")


class Draft(BaseModel):
    subject: str
    body: str


class QuoteWording(BaseModel):
    wording: str = Field(description="max 60 words: what the fixed monthly fee includes")


class Sentiment(BaseModel):
    label: Literal["positive", "neutral", "negative"]
    reason: str


# ------------------------------------------------------------------- helpers
def _lead(ctx: Ctx, lead_id: str) -> dict | None:
    return next((x for x in ctx.state["leads"] if x["id"] == lead_id), None)


def _client(ctx: Ctx, client_id: str) -> dict | None:
    return next((c for c in ctx.state["clients"] if c["id"] == client_id), None)


def _tone(ctx: Ctx) -> str:
    p = ctx.state["practice"]
    first = p["partner"].split()[0]
    return (f"Practice: {p['name']}, {p['town']}. Tone: {p['tone']}. Sign off as {first}. "
            f"Use UK spelling, £ and dd/mm/yyyy. Never promise tax outcomes, savings or refunds; "
            f"never use the words 'guarantee' or 'you will save'.")


def _qualifying(lead: dict) -> int:
    return (lead.get("est_turnover") or 0) + (lead.get("property_income") or 0)


# --------------------------------------------------------------------- tools
def list_new_leads(ctx: Ctx) -> dict:
    new = [x for x in ctx.state["leads"] if x["status"] == "New"]
    return {"leads": [{"lead_id": x["id"], "name": x["name"], "source": x["source"],
                       "received": x["received_date"]} for x in new]}


def assess_lead(ctx: Ctx, lead_id: str) -> dict:
    lead = _lead(ctx, lead_id)
    if not lead:
        return {"error": f"unknown lead {lead_id}"}
    cohort = rules.mtd_scope(lead.get("est_turnover") or 0, lead.get("property_income") or 0)
    if not rules.can_market(lead):  # PECR gate runs BEFORE any LLM call
        lead["assessment"] = {"priority": "Do not contact – no consent", "cohort": cohort}
        return {"lead_id": lead_id, "priority": "Do not contact – no consent",
                "reason": "Purchased-list lead with no consent (PECR). Do not draft or contact."}
    nd = rules.next_deadline()
    prompt = (
        f"Assess this enquiry for a small UK accounting practice.\n"
        f"Lead: {lead['name']}, {lead['business_type']}, {lead['trade']}, {lead['town']}. "
        f"Source: {lead['source']}.\n"
        f"Estimated qualifying income: {_qualifying(lead) or 'unknown'}. "
        f"MTD cohort by our rules: {cohort if _qualifying(lead) else 'unknown'}. "
        f"Next quarterly deadline: {nd['label']} on {rules.fmt_date(nd['due'])} "
        f"({nd['days_left']} days away).\nEnquiry: \"{lead['message']}\"\n"
        f"Rules: High = mandated now or near a deadline and ready to engage; Medium = 2027/2028 "
        f"wave or too little information (then say 'ask for turnover'); Low = poor fit "
        f"(limited company audit, large firm, or under £20k). fit_reason max 25 words.")
    a = ctx.ask_json("assess_lead", "You triage enquiries for a UK accountancy practice. "
                     "suggested_services must use only these keys: " + ", ".join(SERVICE_KEYS),
                     prompt, LeadAssessment)
    out = a.model_dump()
    out["suggested_services"] = [s for s in out["suggested_services"] if s in SERVICE_KEYS]
    out["cohort"] = cohort
    lead["assessment"] = out
    return {"lead_id": lead_id, **out}


def draft_lead_reply(ctx: Ctx, lead_id: str) -> dict:
    lead = _lead(ctx, lead_id)
    if not lead:
        return {"error": f"unknown lead {lead_id}"}
    if not rules.can_market(lead):
        return {"error": "BLOCKED: lead has no consent (PECR). Do not draft a reply."}
    a = lead.get("assessment", {})
    prompt = (f"Write a short personalised email reply to this enquiry and offer a free 15-minute "
              f"call. Lead: {lead['name']} ({lead['trade']}, {lead['town']}). Their message: "
              f"\"{lead['message']}\". Our assessment: {a.get('fit_reason', '')} "
              f"{a.get('urgency_reason', '')}")
    d = ctx.ask_json("draft_lead_reply", "You draft emails for an accountant to approve. "
                     + _tone(ctx), prompt, Draft)
    return {"lead_id": lead_id, "subject": d.subject, "body": d.body}


def build_quote(ctx: Ctx, lead_id: str, services: list[str]) -> dict:
    lead = _lead(ctx, lead_id)
    if not lead:
        return {"error": f"unknown lead {lead_id}"}
    prices = ctx.state["practice"]["price_list"]
    bad = [s for s in services if s not in prices]
    if bad or not services:
        return {"error": f"services must be from {list(prices)}; got {services}"}
    lines = [{"service": prices[s]["label"], "monthly": prices[s]["monthly"]} for s in services]
    total = sum(x["monthly"] for x in lines)  # pricing is Python, never the LLM
    prompt = (f"Write the 'what's included' wording for a fixed monthly fee of £{total} covering: "
              f"{', '.join(x['service'] for x in lines)}. Client: {lead['name']}. Max 60 words.")
    w = ctx.ask_json("build_quote", "You write fixed-fee quote wording. " + _tone(ctx), prompt,
                     QuoteWording)
    return {"lead_id": lead_id, "lines": lines, "monthly_total": total, "wording": w.wording}


def list_deadlines(ctx: Ctx, days_ahead: int = 14) -> dict:
    nd = rules.next_deadline()
    if nd["days_left"] > days_ahead:
        return {"deadline": None, "clients": []}
    out = []
    for c in ctx.state["clients"]:
        if c["mtd_cohort"] != "2026" or not rules.aml_gate(c):
            continue
        qs = c["quarter_status"]
        out.append({
            "client_id": c["id"], "name": c["name"], "quarter": nd["label"],
            "due": nd["due"].isoformat(), "days_left": nd["days_left"],
            "records_received": qs["records_received"],
            "records_days_late": rules.records_days_late(qs), "queries_open": qs["queries_open"],
            "summary_signed_off": qs["summary_signed_off"]})
    return {"deadline": {"quarter": nd["label"], "due": nd["due"].isoformat(),
                         "days_left": nd["days_left"]}, "clients": out}


def chase_records(ctx: Ctx, client_id: str) -> dict:
    c = _client(ctx, client_id)
    if not c:
        return {"error": f"unknown client {client_id}"}
    qs = c["quarter_status"]
    prompt = (f"Write a polite email asking {c['name']} ({c['trade']}) for their missing records "
              f"for {qs['period']}. Records are {rules.records_days_late(qs)} days overdue and "
              f"the update is due {rules.fmt_date(rules.next_deadline()['due'])}. Include a short "
              f"checklist: bank statements, sales invoices, receipts for expenses over £25, "
              f"mileage log. Be kind, not nagging.")
    d = ctx.ask_json("chase_records", "You draft client emails for an accountant to approve. "
                     + _tone(ctx), prompt, Draft)
    return {"client_id": client_id, "subject": d.subject, "body": d.body}


def prep_mtd_quarter(ctx: Ctx, client_id: str) -> dict:
    """Categorise the client's bank CSV into SA103 boxes (via categorise.py)."""
    from qr import categorise  # local import: categorise depends on agent, which imports tools

    c = _client(ctx, client_id)
    if not c:
        return {"error": f"unknown client {client_id}"}
    path = categorise.DATA / "transactions" / f"{c['name'].split()[0].lower()}_q2_2026.csv"
    if not path.exists():
        return {"error": f"no bank CSV on file for {client_id}"}
    df = categorise.run_for_client(ctx, client_id, path)
    ctx.state.setdefault("categorised", {})[client_id] = df.to_dict("records")
    summary = categorise.summarise(df, {})
    return {"client_id": client_id, "rows": len(df),
            "green": int((df.colour == "green").sum()), "amber": int((df.colour == "amber").sum()),
            "red": int((df.colour == "red").sum()), "turnover": summary["turnover"],
            "expenses_by_box": summary["boxes"],
            "client_questions": categorise.client_questions(df)[:5]}


def client_health(ctx: Ctx, client_id: str) -> dict:
    c = _client(ctx, client_id)
    if not c:
        return {"error": f"unknown client {client_id}"}
    now = rules.today()
    recent = [m for m in ctx.state["messages"] if m["client_id"] == client_id
              and (now - rules.to_date(m["date"])).days <= 30]
    negative = False
    sentiment = "no recent messages"
    if recent:
        latest = max(recent, key=lambda m: m["date"])
        s = ctx.ask_json("client_health_sentiment", "You classify the sentiment of a client "
                         "message to their accountant. Beware sarcasm.",
                         f"Message: \"{latest['text']}\"", Sentiment)
        sentiment = s.label
        negative = s.label == "negative"
        ctx.state["sentiments"][client_id] = {"label": s.label, "reason": s.reason}
    h = rules.health_score(c, negative)  # score maths is Python
    return {"client_id": client_id, "score": h["score"], "band": h["band"],
            "sentiment": sentiment, "breakdown": h["breakdown"]}


def find_opportunities(ctx: Ctx) -> dict:
    out = [{"client_id": c["id"], "name": c["name"], "opportunities": rules.opportunities(c),
            "turnover": c["turnover_last_12m"]}
           for c in ctx.state["clients"] if rules.opportunities(c)]
    return {"opportunities": out}


def draft_retention_message(ctx: Ctx, client_id: str) -> dict:
    c = _client(ctx, client_id)
    if not c:
        return {"error": f"unknown client {client_id}"}
    recent = [m for m in ctx.state["messages"] if m["client_id"] == client_id]
    latest = max(recent, key=lambda m: m["date"])["text"] if recent else "(none)"
    h = rules.health_score(c, ctx.state["sentiments"].get(client_id, {}).get("label") == "negative")
    why = "; ".join(b["reason"] for b in h["breakdown"]) or "no issues"
    prompt = (f"Write an empathetic email to {c['name']} who may be thinking of leaving. Their "
              f"latest message: \"{latest}\". Issues on our side: {why}. Acknowledge the problem "
              f"specifically, apologise once, say what we will do, and offer a call. Do NOT offer "
              f"any discount.")
    d = ctx.ask_json("draft_retention_message", "You draft client retention emails for an "
                     "accountant to approve. " + _tone(ctx), prompt, Draft)
    return {"client_id": client_id, "subject": d.subject, "body": d.body}


def queue_for_approval(ctx: Ctx, recipient_id: str, channel: str, subject: str, body: str,
                       reason: str) -> dict:
    """Adds to the Approval Queue. NEVER sends. Compliance checks run here, in Python."""
    lead, client = _lead(ctx, recipient_id), _client(ctx, recipient_id)
    person = lead or client
    if not person:
        return {"queued": False, "error": f"unknown recipient {recipient_id}"}
    if lead and not rules.can_market(lead):
        return {"queued": False, "error": "BLOCKED: no consent (PECR)"}
    subject, body = ctx.redactor.restore(subject), ctx.redactor.restore(body)
    found = rules.banned_phrases_found(subject + " " + body)
    if found:
        store.log(ctx.state, "agent", "banned_phrase_blocked", f"{recipient_id}: {found}")
        return {"queued": False, "error": f"Draft contains banned phrases {found}. Redraft "
                                          f"without promising tax outcomes."}
    for o in ctx.state["outbox"]:
        if o["recipient_id"] == recipient_id and o["subject"] == subject \
                and o["status"] == "pending":
            return {"queued": False, "error": "already queued"}
    item = {"id": f"A{len(ctx.state['outbox']) + 1:03d}", "recipient_id": recipient_id,
            "recipient_name": person["name"], "kind": "lead" if lead else "client",
            "channel": channel, "subject": subject, "body": body,
            "reason": ctx.redactor.restore(reason), "status": "pending",
            "created": datetime.now().isoformat(timespec="seconds")}
    ctx.state["outbox"].append(item)
    store.log(ctx.state, "agent", "queued_for_approval", f"{item['id']} -> {recipient_id}")
    return {"queued": True, "approval_id": item["id"]}


# ----------------------------------------------------------- registry/schemas
def _schema(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or list(props)}


_S = {"type": "string"}
TOOL_SPECS = [
    ("list_new_leads", "List leads with status New.", _schema({}), list_new_leads),
    ("assess_lead", "Assess one lead: MTD cohort, priority, fit and urgency. Leads without "
     "consent come back as 'Do not contact – no consent'.",
     _schema({"lead_id": _S}), assess_lead),
    ("draft_lead_reply", "Draft a personalised reply to a lead (refused if no consent). "
     "Returns subject and body; then call queue_for_approval.",
     _schema({"lead_id": _S}), draft_lead_reply),
    ("build_quote", "Build a fixed monthly quote for a lead from the price list.",
     _schema({"lead_id": _S, "services": {"type": "array", "items": {"type": "string",
                                                                   "enum": SERVICE_KEYS}}}),
     build_quote),
    ("list_deadlines", "Clients with MTD quarterly updates due within days_ahead days, with "
     "records status.", _schema({"days_ahead": {"type": "integer"}}), list_deadlines),
    ("chase_records", "Draft a polite records reminder for a client. Then call "
     "queue_for_approval.", _schema({"client_id": _S}), chase_records),
    ("prep_mtd_quarter", "Categorise a client's quarterly bank CSV into HMRC SA103 boxes with "
     "confidence scores. Returns totals, counts of green/amber/red rows and draft client "
     "questions. The accountant reviews and signs off on the MTD Prep page.",
     _schema({"client_id": _S}), prep_mtd_quarter),
    ("client_health", "Health score, band and breakdown for a client.",
     _schema({"client_id": _S}), client_health),
    ("find_opportunities", "Clients with opportunities (VAT threshold, 2027 MTD cohort, "
     "landlord review).", _schema({}), find_opportunities),
    ("draft_retention_message", "Draft an empathetic retention message for an at-risk client. "
     "Then call queue_for_approval.", _schema({"client_id": _S}), draft_retention_message),
    ("queue_for_approval", "Put a draft in the Approval Queue. Nothing is ever sent; a human "
     "approves. Pass the subject and body exactly as drafted.",
     _schema({"recipient_id": _S, "channel": {"type": "string", "enum": ["email"]},
              "subject": _S, "body": _S, "reason": _S}), queue_for_approval),
]

IMPLS: dict[str, Callable] = {n: f for n, _, _, f in TOOL_SPECS}
TOOL_DEFS = [{"name": n, "description": d, "input_schema": s} for n, d, s, _ in TOOL_SPECS]


def run_tool(ctx: Ctx, name: str, args: dict) -> dict:
    fn = IMPLS.get(name)
    if fn is None:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(ctx, **args)
    except TypeError as exc:
        return {"error": f"bad arguments: {exc}"}


def summarise(name: str, result: dict) -> str:
    """One short line for the step trace."""
    if "error" in result:
        return f"⚠️ {result['error']}"[:160]
    if name == "list_new_leads":
        return f"{len(result['leads'])} new leads"
    if name == "assess_lead":
        return f"{result.get('priority')} – {result.get('fit_reason') or result.get('reason', '')}"[:160]
    if name in ("draft_lead_reply", "chase_records", "draft_retention_message"):
        return f"Drafted: “{result['subject']}”"
    if name == "build_quote":
        return f"£{result['monthly_total']}/month fixed fee"
    if name == "list_deadlines":
        d = result["deadline"]
        return (f"{d['quarter']} due in {d['days_left']} days; {len(result['clients'])} clients"
                if d else "No deadlines in range")
    if name == "prep_mtd_quarter":
        return (f"{result['rows']} rows: {result['green']} green, {result['amber']} amber, "
                f"{result['red']} red")
    if name == "client_health":
        return f"{result['score']} ({result['band']}), sentiment {result['sentiment']}"
    if name == "find_opportunities":
        return f"{len(result['opportunities'])} clients with opportunities"
    if name == "queue_for_approval":
        return f"Queued {result['approval_id']} for approval" if result.get("queued") \
            else f"Not queued: {result.get('error')}"
    return json.dumps(result)[:120]
