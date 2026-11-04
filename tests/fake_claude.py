"""Scripted stand-in for the Claude API, used ONLY in tests (never writes to the real cache).

It plays a plausible agent so the loop, tools, gates and queue can be tested without a key.
"""
import json
import re


def _usage():
    return {"input_tokens": 100, "output_tokens": 50}


def _text(t):
    return {"type": "text", "text": t}


def _use(turn, i, name, **args):
    return {"type": "tool_use", "id": f"toolu_{turn}_{i}", "name": name, "input": args}


def _tool_results(messages):
    """Map tool name -> list of (args, parsed result) in order."""
    names, out = {}, {}
    for m in messages:
        if isinstance(m["content"], list):
            for b in m["content"]:
                if b.get("type") == "tool_use":
                    names[b["id"]] = (b["name"], b["input"])
                if b.get("type") == "tool_result":
                    n, a = names[b["tool_use_id"]]
                    out.setdefault(n, []).append((a, json.loads(b["content"])))
    return out


def fake_api(model, system, messages, tools, max_tokens):
    if not tools:  # inner structured-output calls
        prompt = messages[-1]["content"]
        if "Assess this enquiry" in prompt:
            high = re.search(r"missed|panick|nothing since April", prompt) is not None
            body = {"priority": "High" if high else "Low",
                    "fit_reason": "Over £50k and mandated now" if high else "Small side income",
                    "urgency_reason": "Q2 due in 3 days" if high else "None",
                    "suggested_services": ["mtd_sole_trader"] if high else []}
        elif "Write a short personalised email" in prompt:
            body = {"subject": "Getting you ready for 7 November",
                    "body": "Hi [FIRST_1], happy to help. Can we have a 15-minute call? Demo"}
        elif "fixed monthly fee" in prompt:
            body = {"wording": "Quarterly MTD updates and year-end return."}
        elif "missing records" in prompt:
            body = {"subject": "Quick records check", "body": "Hi, could you send your statements?"}
        elif "Message:" in prompt:
            body = {"label": "negative" if "someone cheaper" in prompt else "neutral",
                    "reason": "test"}
        else:
            body = {"subject": "We want to put this right",
                    "body": "Hi, sorry about the repeated requests. Can we have a call?"}
        return {"content": [_text(json.dumps(body))], "stop_reason": "end_turn",
                "usage": _usage()}

    turn = sum(1 for m in messages if m["role"] == "assistant") + 1
    res = _tool_results(messages)
    if turn == 1:
        c = [_text("Checking leads, deadlines and opportunities."),
             _use(1, 0, "list_new_leads"), _use(1, 1, "list_deadlines", days_ahead=14),
             _use(1, 2, "find_opportunities"), _use(1, 3, "client_health", client_id="C002")]
    elif turn == 2:
        c = [_text("Assessing every new lead.")] + [
            _use(2, i, "assess_lead", lead_id=f"L{i + 1:03d}") for i in range(12)]
    elif turn == 3:
        c = [_text("Drafting for the urgent leads and at-risk client."),
             _use(3, 0, "draft_lead_reply", lead_id="L001"),
             _use(3, 1, "build_quote", lead_id="L001", services=["mtd_sole_trader"]),
             _use(3, 2, "draft_retention_message", client_id="C002"),
             _use(3, 3, "chase_records", client_id="C002"),
             _use(3, 4, "draft_lead_reply", lead_id="L009")]
    elif turn == 4:
        reply = res["draft_lead_reply"][0][1]
        ret = res["draft_retention_message"][0][1]
        c = [_text("Queueing drafts for approval."),
             _use(4, 0, "queue_for_approval", recipient_id="L001", channel="email",
                  subject=reply["subject"], body=reply["body"], reason="urgent lead"),
             _use(4, 1, "queue_for_approval", recipient_id="C002", channel="email",
                  subject=ret["subject"], body=ret["body"], reason="at risk"),
             _use(4, 2, "queue_for_approval", recipient_id="L009", channel="email",
                  subject="Hello", body="Hi", reason="trying to market to a blocked lead"),
             _use(4, 3, "queue_for_approval", recipient_id="L002", channel="email",
                  subject="Hi", body="Refund guaranteed if you sign today", reason="bad draft")]
    else:
        return {"content": [_text("1. Reply to Kev (urgent, Q2 due 07/11/2026).\n"
                                  "2. Call Priya (at risk).")],
                "stop_reason": "end_turn", "usage": _usage()}
    return {"content": c, "stop_reason": "tool_use", "usage": _usage()}
