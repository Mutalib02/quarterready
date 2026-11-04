import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qr import agent, cache, categorise as cz, evaluate, store  # noqa: E402
from qr.local_model import local_api  # noqa: E402
from qr.tools import Ctx  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    return tmp_path


def test_local_briefing_end_to_end(isolated_cache):
    state = store.load_all()
    ctx = Ctx(state, local=True)
    out = agent.run_briefing(ctx)
    assert out["engine"].startswith("Local") and "not Claude" in out["summary"]
    assert len(out["steps"]) < 60 and ctx.usage["calls"] == 0 and ctx.usage["local"] > 0
    # PECR: both purchased-list leads blocked, nothing drafted or queued for them
    assert {l["id"] for l in state["leads"] if l["assessment"]["priority"].startswith("Do not")} \
        == {"L009", "L010"}
    queued = {o["recipient_id"] for o in state["outbox"]}
    assert not queued & {"L009", "L010", "L007", "L008", "L012"}  # blocked or Low priority
    assert {"L001", "L002", "C002"} <= queued
    # Priya at risk, Mark VAT opportunity, real names (no placeholders) in drafts
    assert "Call Priya Rentwell" in out["summary"] and "Mark Spannerman" in out["summary"]
    assert all("[NAME_" not in o["body"] and "[FIRST_" not in o["body"] for o in state["outbox"])
    assert any(o["body"].startswith("Hi Kev,") for o in state["outbox"])
    assert all(o["status"] == "pending" for o in state["outbox"])
    assert state["categorised"]["C001"]
    assert not list(isolated_cache.glob("*.json"))  # local engine never writes the cache


def test_local_categoriser_rules():
    df = cz.categorise(cz.load_transactions(cz.DAVE_CSV),
                       lambda s, m, t, mt, tc=None: local_api("x", s, m, t, mt, tc), [])
    van = df[df.Description.str.contains("VANS DIRECT")].iloc[0]
    assert van.colour == "red" and van.sa103_box == 29 and van.allowable == "no"
    lunch = df[df.Description.str.contains("GRAND HOTEL")].iloc[0]
    assert lunch.sa103_box == 39 and "disallowable" in lunch.reason
    # recurring direct debits are no longer flagged as duplicates
    assert not df[df.Description.str.contains("ACCOUNT FEE|QISTAS")].flag.any()
    m = evaluate.categorisation_metrics(df)
    assert m["n"] == 90 and m["wrong_but_confident"] == 0


def test_local_sentiment_and_assess():
    r = local_api("x", "classify the sentiment of a client", [{"role": "user", "content":
                  'Message: "Third time I\'ve been asked. Thinking of moving to someone cheaper."'}],
                  None, 100)
    assert '"negative"' in r["content"][0]["text"]
