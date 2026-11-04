import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize("page", ["app.py", "pages/1_Win_Leads.py", "pages/2_Clients.py"])
def test_page_renders_without_exception(page):
    at = AppTest.from_file(str(ROOT / page), default_timeout=30).run()
    assert not at.exception


def test_blocked_lead_cannot_convert():
    at = AppTest.from_file(str(ROOT / "pages/1_Win_Leads.py"), default_timeout=30).run()
    at.selectbox[0].select("L009 – Ricky Fakeman (fictional)").run()
    assert at.button[0].disabled
    assert any("Do not contact" in e.value for e in at.error)


def test_today_briefing_and_approval_queue(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "tests"))
    from fake_claude import fake_api

    from qr import agent, cache

    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)  # keep the real cache untouched
    monkeypatch.setattr(agent, "_anthropic_call", fake_api)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception
    next(b for b in at.button if "Run morning briefing" in b.label).click().run()
    assert not at.exception
    assert any("Reply to" in m.value for m in at.markdown)
    approve = [b for b in at.button if b.label.endswith("Approve")]
    assert len(approve) == 2
    approve[0].click().run()
    assert not at.exception
    assert len([b for b in at.button if b.label.endswith("Approve")]) == 1
    assert at.session_state["outbox"][0]["status"] == "approved"
    assert at.session_state["leads"][0]["status"] == "Replied"
