import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qr import agent, cache, categorise as cz, evaluate, store  # noqa: E402
from qr.tools import Ctx  # noqa: E402


def boom(*a, **k):
    raise AssertionError("the recorded engine must never call the API")


@pytest.fixture(scope="module")
def replay():
    state = store.load_all()
    ctx = Ctx(state, recorded=True)
    out = agent.run_briefing(ctx, api_call=boom)
    return state, ctx, out


def test_recorded_set_exists_and_is_labelled():
    files = list(cache.RECORDED_DIR.glob("[0-9a-f]*.json"))
    assert len(files) >= 39
    assert all("Claude Code" in cache.get(f.stem, cache.RECORDED_DIR)["recorded_by"] for f in files)


def test_full_briefing_replays_with_no_api_calls(replay):
    state, ctx, out = replay
    assert ctx.usage["calls"] == 0 and ctx.usage["recorded"] >= 39
    assert out["engine"] == agent.RECORDED_LABEL
    assert len(out["steps"]) < 60 and out["summary"].startswith("1. **Call Priya Rentwell")
    assert len(state["outbox"]) == 9 and all(o["status"] == "pending" for o in state["outbox"])


def test_gates_and_names_hold_on_recorded_output(replay):
    state, _, _ = replay
    prio = {l["id"]: l["assessment"]["priority"] for l in state["leads"]}
    assert prio["L009"].startswith("Do not contact") and prio["L010"].startswith("Do not contact")
    queued = {o["recipient_id"] for o in state["outbox"]}
    assert not queued & {"L007", "L008", "L009", "L010", "L012"}
    assert all("[NAME_" not in o["body"] and "[FIRST_" not in o["body"] for o in state["outbox"])
    assert any(o["body"].startswith("Hi Kev,") for o in state["outbox"])
    from qr import rules
    assert all(rules.draft_is_safe(o["subject"] + o["body"]) for o in state["outbox"])


def test_recorded_evaluation_numbers(replay):
    import pandas as pd

    state, _, _ = replay
    df = pd.DataFrame(state["categorised"]["C001"])
    m = evaluate.categorisation_metrics(df)
    assert m["n"] == 90 and m["wrong_but_confident"] == 0 and m["high_conf_accuracy"] == 1.0
    assert abs(m["accuracy"] - 82 / 90) < 1e-9
    assert (df.colour == "red").sum() == 40
    van = df[df.Description.str.contains("VANS DIRECT")].iloc[0]
    assert van.sa103_box == 29 and van.colour == "red"
    la = evaluate.lead_agreement(state["leads"])
    assert la["n"] == 12 and la["agreement"] == 1.0


def test_unrecorded_request_is_a_clean_miss():
    state = store.load_all()
    state["leads"][0]["message"] = "Changed text, so the request hash changes."
    with pytest.raises(cache.CacheMiss):
        agent.run_briefing(Ctx(state, recorded=True), api_call=boom)
