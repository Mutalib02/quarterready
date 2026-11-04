import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from fake_claude import fake_api  # noqa: E402

from qr import agent, cache, store  # noqa: E402
from qr.tools import Ctx  # noqa: E402


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)  # never touch the committed cache
    return tmp_path


def test_full_briefing_with_gates(tmp_cache):
    state = store.load_all()
    ctx = Ctx(state)
    seen = []
    out = agent.run_briefing(ctx, on_step=seen.append, api_call=fake_api)

    assert out["summary"].startswith("1. Reply to")
    assert len(seen) == len(out["steps"]) > 10
    # PECR: purchased-list leads are blocked in assess_lead and can't be drafted or queued
    assess = {s["args"]["lead_id"]: s["result"] for s in out["steps"] if s["tool"] == "assess_lead"}
    assert "Do not contact" in assess["L009"] and "Do not contact" in assess["L010"]
    blocked = [s for s in out["steps"] if s["tool"] in ("draft_lead_reply", "queue_for_approval")
               and s["args"].get("lead_id", s["args"].get("recipient_id")) == "L009"]
    assert blocked and all("Not queued" in s["result"] or "BLOCKED" in s["result"]
                           for s in blocked)
    # Banned-phrase draft refused; only two real drafts queued, all pending
    queue = state["outbox"]
    assert [o["recipient_id"] for o in queue] == ["L001", "C002"]
    assert all(o["status"] == "pending" for o in queue)
    assert any(a["action"] == "banned_phrase_blocked" for a in state["audit"])
    # Names are restored in drafts but were redacted in what was sent to the model
    assert "Kev" in queue[0]["body"]
    assert state["ai_log"] and not any("Plumbwell" in e["sent"] for e in state["ai_log"])
    assert ctx.usage["calls"] > 0 and ctx.usage["cached"] == 0


def test_replay_offline_uses_cache_only(tmp_cache):
    agent.run_briefing(Ctx(store.load_all()), api_call=fake_api)
    state = store.load_all()
    ctx = Ctx(state, offline=True)

    def boom(*a, **k):
        raise AssertionError("API must not be called in offline mode")

    out = agent.run_briefing(ctx, api_call=boom)
    assert out["summary"].startswith("1. Reply to")
    assert ctx.usage["calls"] == 0 and ctx.usage["cached"] > 0
    assert [o["recipient_id"] for o in state["outbox"]] == ["L001", "C002"]


def test_offline_cache_miss_raises(tmp_cache):
    with pytest.raises(cache.CacheMiss):
        agent.run_briefing(Ctx(store.load_all(), offline=True), api_call=fake_api)


def test_step_limit(tmp_cache):
    def loop_forever(model, system, messages, tools, max_tokens, tool_choice=None):
        return {"content": [{"type": "tool_use", "id": f"t{len(messages)}",
                             "name": "list_new_leads", "input": {}}],
                "stop_reason": "tool_use", "usage": {"input_tokens": 1, "output_tokens": 1}}

    out = agent.run_briefing(Ctx(store.load_all()), api_call=loop_forever)
    assert len(out["steps"]) == agent.MAX_STEPS - 1
    assert "step limit" in out["summary"].lower()
