"""LOCAL ENGINE – a rule-based stand-in for Claude. It is NOT an AI model.

Used when there is no API key or credit. It speaks the same interface as the Claude call, so
the agent loop, tools, compliance gates, Approval Queue and evaluation all run unchanged.
Output is template-based and keyword-driven: good enough to show the workflow, and the
Evaluation page measures how much weaker it is than the real model. Responses from here are
never written to cache/.
"""
from __future__ import annotations

import json
import re

ENGINE_NAME = "Local rule-based engine (not Claude)"
_U = {"input_tokens": 0, "output_tokens": 0}


def _text(t: str) -> dict:
    return {"type": "text", "text": t}


def _resp(blocks: list, stop: str = "end_turn") -> dict:
    return {"content": blocks, "stop_reason": stop, "usage": dict(_U)}


def local_api(model, system, messages, tools, max_tokens, tool_choice=None) -> dict:
    """Same signature as agent._anthropic_call."""
    if tool_choice and tool_choice.get("name") == "record_categorisations":
        return _categorise(messages[-1]["content"])
    if tools and len(tools) > 1:
        return _plan(messages)
    return _resp([_text(json.dumps(_structured(system, messages[-1]["content"])))])


# ------------------------------------------------------ structured sub-calls
def _first_tag(tag_text: str) -> str:
    """[NAME_3] -> [FIRST_3] so templates can greet people by first name."""
    m = re.search(r"\[NAME_(\d+)\]", tag_text)
    return f"[FIRST_{m.group(1)}]" if m else "there"


def _signoff(system: str) -> str:
    m = re.search(r"Sign off as (\w+)", system)
    return m.group(1) if m else "Your accountant"


def _structured(system: str, prompt: str) -> dict:
    if "Assess this enquiry" in prompt:
        return _assess(prompt)
    if "fixed monthly fee" in prompt:
        return _quote(prompt)
    if "Message:" in prompt and "sentiment" in system:
        return _sentiment(prompt)
    who = _first_tag(prompt)
    sign = _signoff(system)
    if "personalised email reply" in prompt:
        return _lead_reply(prompt, who, sign)
    if "missing records" in prompt:
        return _chase(prompt, who, sign)
    if "empathetic email" in prompt:
        return _retention(prompt, who, sign)
    return {"subject": "Following up", "body": f"Hi {who},\n\nThanks for getting in touch.\n\n{sign}"}


def _assess(p: str) -> dict:
    btype = (re.search(r"Lead: [^,]+, (\w+),", p) or [None, ""])[1]
    q = (re.search(r"qualifying income: (\d+|unknown)", p) or [None, "unknown"])[1]
    cohort = (re.search(r"cohort by our rules: (\w+)", p) or [None, "unknown"])[1]
    days = int((re.search(r"\((\d+) days away\)", p) or [None, "0"])[1])
    enquiry = (re.search(r'Enquiry: "(.*)"', p, re.S) or [None, ""])[1].lower()
    urgent = bool(re.search(r"missed|panick|deadline|nothing since|this week|days away", enquiry))
    if btype == "limited_company":
        return {"priority": "Low", "fit_reason": "Limited company needing audit or payroll – "
                "outside our MTD sole trader and landlord service.",
                "urgency_reason": "None", "suggested_services": []}
    if q == "unknown":
        return {"priority": "Medium", "fit_reason": "Too little information – ask for turnover "
                "before quoting.", "urgency_reason": "Unknown", "suggested_services": []}
    svc = ["landlord_1_2"] if btype == "landlord" else ["mtd_sole_trader"]
    if cohort == "2026":
        why = f"Over £50k so mandated now; Q2 update due in {days} days."
        return {"priority": "High", "fit_reason": why[:140],
                "urgency_reason": "Missed earlier quarter" if urgent else "Mandated now",
                "suggested_services": svc}
    if cohort in ("2027", "2028"):
        return {"priority": "Medium", "fit_reason": f"Joins MTD in April {cohort}; good to onboard "
                "early.", "urgency_reason": "No immediate deadline", "suggested_services": svc}
    return {"priority": "Low", "fit_reason": "Below the £20k MTD threshold for now.",
            "urgency_reason": "None", "suggested_services": []}


def _quote(p: str) -> dict:
    total = (re.search(r"fee of £(\d+)", p) or [None, "0"])[1]
    covering = (re.search(r"covering: (.*?)\. Client", p) or [None, "our service"])[1]
    return {"wording": f"A fixed £{total} a month covering {covering}: quarterly updates, "
                       "records chasing and your year-end return, with a named contact."}


NEG = ("cheaper", "thinking of moving", "third time", "frustrat", "unhappy", "disappoint",
       "cancel", "leave you", "fed up", "not happy", "ridiculous")
POS = ("thanks", "thank you", "brilliant", "great", "happy with", "fantastic", "excellent")


def _sentiment(p: str) -> dict:
    t = p.lower()
    if any(w in t for w in NEG):
        return {"label": "negative", "reason": "Complaint or intent to leave (keyword match)."}
    if any(w in t for w in POS):
        return {"label": "positive", "reason": "Positive wording (keyword match)."}
    return {"label": "neutral", "reason": "No strong sentiment words found."}


def _lead_reply(p: str, who: str, sign: str) -> dict:
    ask = "ask for turnover" in p.lower() or "too little" in p.lower()
    urgent = bool(re.search(r"mandated now|missed|days away|Q2 update", p))
    msg = (re.search(r'Their message: "(.*?)"\.', p, re.S) or [None, ""])[1]
    para = ("Could you tell me roughly what you turned over last year, and whether you let any "
            "property? That lets me recommend the right setup." if ask else
            "The next quarterly update is due on 07/11/2026, so the sooner we start the easier "
            "it is to catch up. I can get your records sorted and your updates filed once you "
            "approve them." if urgent else
            "You may join Making Tax Digital in a later year, so it's worth getting the right "
            "software and habits in place early.")
    return {"subject": "Making Tax Digital – how we can help" if not urgent
            else "Getting you ready for the 7 November deadline",
            "body": f"Hi {who},\n\nThanks for getting in touch"
                    + (f" – I read your note: “{msg[:120]}”." if msg else ".")
                    + f"\n\n{para}\n\nWould a free 15-minute call this week suit you?\n\n"
                      f"Kind regards,\n{sign}"}


def _chase(p: str, who: str, sign: str) -> dict:
    days = (re.search(r"(\d+) days overdue", p) or [None, "a few"])[1]
    return {"subject": "A quick nudge for your quarterly records",
            "body": f"Hi {who},\n\nI hope you're well. Your records for this quarter are about "
                    f"{days} days overdue and the update is due on 07/11/2026. Could you send:\n"
                    "• Bank statements for 6 July – 5 October\n• Sales invoices\n"
                    "• Receipts for expenses over £25\n• Your mileage log\n\n"
                    "If anything is hard to find, tell me and we'll work it out together.\n\n"
                    f"Thanks,\n{sign}"}


def _retention(p: str, who: str, sign: str) -> dict:
    latest = (re.search(r'latest message: "(.*?)"\. Issues', p, re.S) or [None, ""])[1]
    issues = (re.search(r"Account health flags: (.*?)\. Some flags", p, re.S) or [None, ""])[1]
    return {"subject": "I'd like to put this right",
            "body": f"Hi {who},\n\nThank you for being straight with me"
                    + (f" – “{latest[:100]}”" if latest else "")
                    + f". I'm sorry you've had to repeat yourself. Looking at your file: "
                      f"{issues or 'we have been slow to follow up'}. I'll make sure you're "
                      "asked for each thing only once, and I'll check your account personally.\n\n"
                      "Could we have a short call this week to talk it through?\n\n"
                      f"Kind regards,\n{sign}"}


# ------------------------------------------------------- categorisation rules
_RULES = [  # (regex, class, box, allowable, pct, confidence, reason, query?)
    (r"FASTER PAYMENT FROM|BACS CREDIT|PAYMENT FROM", "income", None, "yes", 100, 0.95,
     "Money in from a customer.", ""),
    (r"HMRC", "not_business", None, "no", 0, 0.95, "Tax payment is not a business expense.", ""),
    (r"TFR TO|TRANSFER|SAVINGS", "not_business", None, "no", 0, 0.9,
     "Transfer between own accounts.", ""),
    (r"ATM|CASH", "not_business", None, "no", 0, 0.4, "Cash withdrawal – purpose unknown.",
     "What was this cash used for?"),
    (r"AMZN|AMAZON|PAYPAL|EBAY", "expense", 17, "yes", 100, 0.45,
     "Generic merchant – could be business or personal.", "What was this purchase for?"),
    (r"RESTAURANT|HOTEL|BISTRO|KITCHEN|CAFE|PUB\b", "expense", 39, "no", 0, 0.7,
     "Meals out are entertainment and disallowable.", "Was this a client meal?"),
    (r"GREGGS|COSTA|PRET|MCDONALD|TESCO|SAINSBURY|ASDA|CO-OP", "not_business", None, "no", 0,
     0.65, "Food and drink is usually personal.", ""),
    (r"SCREWFIX|TOOLSTATION|ELECTRICAL|TRAVIS|WICKES|B&Q|SELCO|JEWSON", "expense", 17, "yes",
     100, 0.93, "Trade materials and tools.", ""),
    (r"\bBP\b|SHELL|ESSO|TEXACO|FUEL|PETROL", "expense", 20, "partial", 80, 0.78,
     "Fuel – part may be private mileage.", ""),
    (r"PARKING|TOLL|TRAIN|TAXI", "expense", 20, "yes", 100, 0.9, "Business travel costs.", ""),
    (r"VODAFONE|\bEE\b|\bO2\b|THREE|SKY MOBILE|BT ", "expense", 23, "partial", 70, 0.72,
     "Phone is likely mixed business and personal use.", ""),
    (r"INSURANCE|HISCOX|AVIVA", "expense", 21, "yes", 100, 0.9, "Business insurance.", ""),
    (r"ACCOUNT FEE|BANK CHARGE|INTEREST CHARGED", "expense", 26, "yes", 100, 0.9,
     "Bank charges.", ""),
    (r"ACCOUNTANT|ACCOUNTANTS", "expense", 28, "yes", 100, 0.9, "Accountancy fees.", ""),
    (r"FACEBK|FACEBOOK|GOOGLE ADS|ADVERT|CANVA", "expense", 24, "yes", 100, 0.88,
     "Advertising.", ""),
    (r"REFUND", "expense", 17, "yes", 100, 0.55, "Supplier refund reduces costs.",
     "Is this refund correct?"),
]


def _categorise(prompt: str) -> dict:
    out = []
    for line in prompt.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 4 or not parts[0].isdigit():
            continue
        rid, desc = int(parts[0]), parts[2].upper()
        amount = float(parts[3].replace("£", "").replace(",", ""))
        row = dict(income_or_expense="expense", sa103_box=30, category_name="Other business",
                   allowable="yes", business_pct=100, confidence=0.35,
                   reason="No rule matched – needs your review.", needs_query=True,
                   client_question="What was this payment for?")
        for pat, cls, box, allow, pct, conf, reason, q in _RULES:
            if re.search(pat, desc):
                row.update(income_or_expense=cls, sa103_box=box, allowable=allow,
                           business_pct=pct, confidence=conf, reason=reason,
                           needs_query=bool(q), client_question=q)
                break
        if row["income_or_expense"] == "expense" and amount <= -2500:
            row.update(sa103_box=29, allowable="no", confidence=0.5, needs_query=True,
                       reason="Large purchase is likely capital, not an expense.",
                       client_question="Is this a vehicle or equipment purchase?")
        row["category_name"] = ("Income" if row["income_or_expense"] == "income" else
                                "Not business" if row["income_or_expense"] == "not_business"
                                else f"Box {row['sa103_box']}")
        out.append({"row_id": rid, **row})
    return _resp([{"type": "tool_use", "id": "local", "name": "record_categorisations",
                   "input": {"categorisations": out}}], "tool_use")


# ------------------------------------------------------------- agent planner
def _history(messages: list) -> dict:
    """tool name -> list of (args, parsed result) from the conversation so far."""
    names, out = {}, {}
    for m in messages:
        if not isinstance(m["content"], list):
            continue
        for b in m["content"]:
            if b.get("type") == "tool_use":
                names[b["id"]] = (b["name"], b["input"])
            elif b.get("type") == "tool_result" and b["tool_use_id"] in names:
                n, a = names[b["tool_use_id"]]
                out.setdefault(n, []).append((a, json.loads(b["content"])))
    return out


def _call(turn: int, i: int, name: str, **args) -> dict:
    return {"type": "tool_use", "id": f"local_{turn}_{i}", "name": name, "input": args}


def _plan(messages: list) -> dict:
    h = _history(messages)
    turn = sum(1 for m in messages if m["role"] == "assistant") + 1
    if "list_new_leads" not in h:
        return _resp([_text("Checking new leads, this week's deadlines and opportunities."),
                      _call(turn, 0, "list_new_leads"),
                      _call(turn, 1, "list_deadlines", days_ahead=14),
                      _call(turn, 2, "find_opportunities")], "tool_use")

    leads = h["list_new_leads"][0][1]["leads"]
    deadlines = h["list_deadlines"][0][1]
    clients = deadlines.get("clients", [])
    ops = h["find_opportunities"][0][1]["opportunities"]

    if "assess_lead" not in h:
        calls = [_call(turn, i, "assess_lead", lead_id=x["lead_id"]) for i, x in enumerate(leads)]
        n = len(calls)
        for c in clients:
            if c.get("has_bank_csv") and c["records_received"]:
                calls.append(_call(turn, n, "prep_mtd_quarter", client_id=c["client_id"]))
                n += 1
        ids = list(dict.fromkeys([c["client_id"] for c in clients] +
                                 [o["client_id"] for o in ops]))
        for cid in ids:
            calls.append(_call(turn, n, "client_health", client_id=cid))
            n += 1
        return _resp([_text("Assessing every lead, preparing MTD categorisation and checking "
                            "client health."), *calls], "tool_use")

    assessed = {a["lead_id"]: r for a, r in h["assess_lead"]}
    health = {a["client_id"]: r for a, r in h.get("client_health", [])}
    drafts_started = any(k in h for k in ("draft_lead_reply", "chase_records",
                                          "draft_retention_message"))
    if not drafts_started:
        calls, n = [], 0
        for lid, r in assessed.items():
            if r.get("priority") in ("High", "Medium"):
                calls.append(_call(turn, n, "draft_lead_reply", lead_id=lid))
                n += 1
            if r.get("priority") == "High":
                svc = [s for s in r.get("suggested_services", [])] or ["mtd_sole_trader"]
                calls.append(_call(turn, n, "build_quote", lead_id=lid, services=svc))
                n += 1
        for c in clients:
            if not c["records_received"] and c["records_days_late"] > 0:
                calls.append(_call(turn, n, "chase_records", client_id=c["client_id"]))
                n += 1
        for cid, r in health.items():
            if r.get("band") == "At risk":
                calls.append(_call(turn, n, "draft_retention_message", client_id=cid))
                n += 1
        return _resp([_text("Drafting replies, quotes, record chasers and retention messages."),
                      *calls], "tool_use")

    if "queue_for_approval" not in h:
        quotes = {a["lead_id"]: r for a, r in h.get("build_quote", []) if "error" not in r}
        calls, n = [], 0
        for a, r in h.get("draft_lead_reply", []):
            if "error" in r:
                continue
            body = r["body"]
            q = quotes.get(a["lead_id"])
            if q:
                head, sep, tail = body.rpartition("\n\nKind regards,")
                note = f"\n\nFixed fee: £{q['monthly_total']} a month. {q['wording']}"
                body = head + note + sep + tail if sep else body + note
            calls.append(_call(turn, n, "queue_for_approval", recipient_id=a["lead_id"],
                               channel="email", subject=r["subject"], body=body,
                               reason=f"{assessed[a['lead_id']]['priority']} priority lead: "
                                      f"{assessed[a['lead_id']].get('fit_reason', '')}"))
            n += 1
        for key, why in (("chase_records", "Records overdue before the 07/11/2026 deadline"),
                         ("draft_retention_message", "Client health is At risk")):
            for a, r in h.get(key, []):
                if "error" not in r:
                    calls.append(_call(turn, n, "queue_for_approval", recipient_id=a["client_id"],
                                       channel="email", subject=r["subject"], body=r["body"],
                                       reason=why))
                    n += 1
        return _resp([_text("Queueing every draft for your approval – nothing is sent."),
                      *calls], "tool_use")

    return _resp([_text(_summary(h, leads, assessed, clients, health, ops))])


def _summary(h, leads, assessed, clients, health, ops) -> str:
    names = {x["lead_id"]: x["name"] for x in leads}
    cnames = {c["client_id"]: c["name"] for c in clients}
    items = []
    for lid, r in assessed.items():
        if r.get("priority") == "High":
            items.append(f"Approve the reply and quote for {names[lid]} (lead {lid}) – "
                         f"{r.get('fit_reason', '')}")
    for cid, r in health.items():
        if r.get("band") == "At risk":
            why = "; ".join(b["reason"] for b in r["breakdown"])
            items.append(f"Call {cnames.get(cid, cid)} today – health {r['score']} (At risk): "
                         f"{why}.")
    for a, r in h.get("prep_mtd_quarter", []):
        if "error" not in r:
            items.append(f"Review {cnames.get(a['client_id'], a['client_id'])}'s Q2 "
                         f"categorisation on MTD Prep – {r['red']} red rows need a decision "
                         f"before the 07/11/2026 deadline.")
    for o in ops:
        if any("VAT" in x for x in o["opportunities"]):
            items.append(f"Raise VAT registration with {o['name']} – turnover "
                         f"£{o['turnover']:,} vs £90,000 threshold.")
    med = [lid for lid, r in assessed.items() if r.get("priority") == "Medium"]
    if med:
        items.append(f"Review {len(med)} Medium-priority leads' replies (April 2027 wave or "
                     f"needs turnover).")
    blocked = [lid for lid, r in assessed.items() if str(r.get("priority", "")).startswith("Do not")]
    items = items[:8]
    text = "\n".join(f"{i}. {t}" for i, t in enumerate(items, 1))
    text += (f"\n\nNot contacted: {len(blocked)} lead(s) blocked – no consent (PECR)."
             if blocked else "")
    return text + "\n\n_Prepared by the local rule-based engine, not Claude._"
