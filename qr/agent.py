"""Claude tool-use loop (max 12 steps) with a step trace and cached replay.

All Claude calls go through `complete`, which is cache-first: key = hash(model, prompt version,
full request). In offline mode a cache miss raises CacheMiss instead of calling the API.
"""
from __future__ import annotations

import json
import os
import time
from typing import Callable

from qr import cache, store
from qr.tools import TOOL_DEFS, Ctx, run_tool, summarise

MAX_STEPS = 12
MODEL = os.environ.get("QR_MODEL", "claude-sonnet-5-5")

SYSTEM_PROMPT = """You are the practice assistant for a small UK accounting practice in the \
North East. You prepare work; a qualified human approves everything. You never send anything \
and never file with HMRC.

Goal of the morning briefing, in this order:
1. Handle new leads: list them, assess each, and for every lead that is NOT 'Do not contact' \
and is High or Medium priority, draft a reply, build a quote (High priority only) and queue \
the drafts for approval. Do not draft anything for Low priority or blocked leads.
2. Protect this week's MTD deadlines: list_deadlines, and chase records for clients who are \
missing them.
3. Protect at-risk clients: check client_health for clients with open queries, late records or \
recent messages; for At risk clients draft a retention message and queue it.
4. Surface opportunities with find_opportunities.

Rules: Never contact a lead that the tools mark 'Do not contact'. Never promise tax outcomes. \
If unsure, say so and ask the human. Call several tools in parallel in one turn when they are \
independent, because you have at most 12 turns. Before each batch of tool calls write ONE short \
sentence saying why. Pass drafts to queue_for_approval exactly as the draft tools returned them.

Finish with a prioritised to-do list (max 8 items, each with a short reason, most urgent first) \
in plain English with UK dates and £, plus one line on anything you could not do. Be brief."""


# ------------------------------------------------------------- Claude access
def _to_plain(resp) -> dict:
    blocks = []
    for b in resp.content:
        if b.type == "text":
            blocks.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    return {"content": blocks, "stop_reason": resp.stop_reason,
            "usage": {"input_tokens": resp.usage.input_tokens,
                      "output_tokens": resp.usage.output_tokens}}


def make_complete(ctx: Ctx, model: str = MODEL, api_call: Callable | None = None) -> Callable:
    """Build the cached completion function. `api_call(model, system, messages, tools,
    max_tokens)` can be injected for tests."""

    def complete(system: str, messages: list, tools: list | None, max_tokens: int = 1500) -> dict:
        payload = {"system": system, "messages": messages, "tools": tools,
                   "max_tokens": max_tokens}
        key = cache.make_key(model, payload)
        hit = cache.get(key)
        if hit is not None:
            ctx.usage["cached"] += 1
            return hit
        if ctx.offline:
            raise cache.CacheMiss(f"No cached response for this step (key {key}).")
        call = api_call or _anthropic_call
        last: Exception | None = None
        for attempt in range(2):  # retry once
            try:
                resp = call(model, system, messages, tools, max_tokens)
                break
            except Exception as exc:  # noqa: BLE001 - API errors vary
                last = exc
                time.sleep(1)
        else:
            ctx.banners.append("Claude API error – switch to offline mode to replay the cache.")
            raise RuntimeError(f"Claude API failed twice: {type(last).__name__}") from last
        ctx.usage["calls"] += 1
        ctx.usage["input"] += resp["usage"]["input_tokens"]
        ctx.usage["output"] += resp["usage"]["output_tokens"]
        cache.put(key, resp)
        return resp

    return complete


def _anthropic_call(model, system, messages, tools, max_tokens) -> dict:
    import anthropic  # imported lazily so offline mode needs no key

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY; never logged
    kwargs = {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages}
    if tools:
        kwargs["tools"] = tools
    return _to_plain(client.messages.create(**kwargs))


# ---------------------------------------------------------------- the loop
def run_briefing(ctx: Ctx, on_step: Callable[[dict], None] | None = None,
                 api_call: Callable | None = None) -> dict:
    """Run the morning briefing. Calls on_step(step) for every tool call as it happens.
    Returns {"summary": str, "steps": [...], "usage": {...}}."""
    on_step = on_step or (lambda s: None)
    ctx.complete = make_complete(ctx, api_call=api_call)
    messages: list[dict] = [{"role": "user", "content":
                             "Run this morning's briefing for the practice."}]
    steps: list[dict] = []
    summary = ""

    for turn in range(1, MAX_STEPS + 1):
        last_turn = turn == MAX_STEPS
        ctx.state["ai_log"].append({"purpose": f"agent turn {turn}",
                                    "sent": _last_text(messages),
                                    "time": time.strftime("%H:%M:%S")})
        resp = ctx.complete(SYSTEM_PROMPT, messages, TOOL_DEFS, 1500)
        messages.append({"role": "assistant", "content": resp["content"]})
        reason = " ".join(b["text"] for b in resp["content"] if b["type"] == "text").strip()
        calls = [b for b in resp["content"] if b["type"] == "tool_use"]
        if not calls or last_turn:
            summary = reason
            break

        results = []
        for i, call in enumerate(calls):
            result = run_tool(ctx, call["name"], call["input"])
            step = {"turn": turn, "tool": call["name"], "args": call["input"],
                    "reason": ctx.redactor.restore(reason) if i == 0 else "(same batch)",
                    "result": ctx.redactor.restore(summarise(call["name"], result))}
            steps.append(step)
            on_step(step)
            # tool results are redacted before they go back to the model
            results.append({"type": "tool_result", "tool_use_id": call["id"],
                            "content": ctx.redactor.redact(json.dumps(result, ensure_ascii=False))})
        if turn + 1 == MAX_STEPS:  # next turn is the last: force the write-up
            results.append({"type": "text", "text": "Step limit reached. Make no more tool "
                            "calls; write the final to-do list now."})
        messages.append({"role": "user", "content": results})

    summary = summary or "Stopped at the step limit without a to-do list."

    summary = ctx.redactor.restore(summary)
    store.log(ctx.state, "agent", "morning_briefing",
              f"{len(steps)} tool calls, {ctx.usage['calls']} API calls, "
              f"{ctx.usage['cached']} cached")
    out = {"summary": summary, "steps": steps, "usage": dict(ctx.usage)}
    ctx.state["briefing"] = out
    return out


def _last_text(messages: list) -> str:
    last = messages[-1]["content"]
    if isinstance(last, str):
        return last
    return "\n".join(r["content"] for r in last if isinstance(r, dict) and "content" in r)
