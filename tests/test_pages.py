import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize("page", ["views/today.py", "pages/1_Win_Leads.py", "pages/2_Clients.py"])
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

    from qr import ui

    at = AppTest.from_file(str(ROOT / "views/today.py"), default_timeout=60).run()
    assert not at.exception
    assert at.radio[0].value == ui.RECORDED  # recorded wins even when a key is set
    at.radio[0].set_value(ui.LIVE).run()  # this test exercises the live path with a fake API
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


def _fake_categorise_env(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "tests"))
    from test_categorise import fake_complete_factory

    from qr import agent, cache

    complete, _ = fake_complete_factory()
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(agent, "make_complete", lambda ctx, **k: complete)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")


def test_mtd_prep_gate_and_export(tmp_path, monkeypatch):
    _fake_categorise_env(tmp_path, monkeypatch)
    at = AppTest.from_file(str(ROOT / "pages/3_MTD_Prep.py"), default_timeout=90).run()
    assert not at.exception
    next(b for b in at.button if b.label == "Categorise transactions").click().run()
    assert not at.exception
    df = at.session_state["mtd"]["df"]
    red = int((df.colour == "red").sum())
    assert red >= 3  # van, duplicate refunds, ...
    # red rows unresolved + no reviewer -> export locked
    assert any("Export is locked" in i.value for i in at.info)
    assert at.session_state["mtd"]["decisions"] == {}


@pytest.mark.parametrize("page", ["pages/4_Keep_Retention.py", "pages/5_Evaluation_Safety.py",
                                  "pages/3_MTD_Prep.py"])
def test_remaining_pages_render(page):
    at = AppTest.from_file(str(ROOT / page), default_timeout=60).run()
    assert not at.exception


def test_today_briefing_with_local_engine(tmp_path, monkeypatch):
    from qr import cache, ui

    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    at = AppTest.from_file(str(ROOT / "views/today.py"), default_timeout=90).run()
    at.radio[0].set_value(ui.LOCAL).run()  # recorded/ may exist, so pick Local explicitly
    assert not at.exception and any("not Claude" in i.value for i in at.info)
    next(b for b in at.button if "Run morning briefing" in b.label).click().run()
    assert not at.exception
    assert len(at.session_state["outbox"]) == 9
    assert any("Call Priya" in m.value for m in at.markdown)
    assert not list(tmp_path.glob("*.json"))


def test_recorded_engine_is_default_and_labelled(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    at = AppTest.from_file(str(ROOT / "views/today.py"), default_timeout=90).run()
    assert not at.exception
    assert at.radio[0].value == "Recorded by Claude (via Claude Code)"
    assert any("Claude output recorded via Claude Code today – live API mode needs a funded key"
               in s.value for s in at.success)
    next(b for b in at.button if "Run morning briefing" in b.label).click().run()
    assert not at.exception and len(at.session_state["outbox"]) == 9
    assert any("recorded via Claude Code" in c.value for c in at.caption)


def test_mtd_prep_and_evaluation_on_recorded_engine(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    at = AppTest.from_file(str(ROOT / "pages/3_MTD_Prep.py"), default_timeout=90).run()
    next(b for b in at.button if b.label == "Categorise transactions").click().run()
    assert not at.exception
    assert "recorded via Claude Code" in at.session_state["mtd"]["engine"]
    assert int((at.session_state["mtd"]["df"].colour == "red").sum()) == 40


def test_router_entrypoint_and_theme():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception
    cfg = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'primaryColor = "#0F766E"' in cfg and 'base = "light"' in cfg


def test_brand_bar_and_pills_render():
    from qr import ui

    html = ui.pill("At risk", "at risk") + ui.pill("Blocked – no consent", "blocked")
    assert "#DC2626" in html and "#64748B" in html and "🚫" in html
    at = AppTest.from_file(str(ROOT / "pages/2_Clients.py"), default_timeout=60).run()
    assert any("QuarterReady" in m.value and "SYNTHETIC – NOT REAL DATA" in m.value
               for m in at.markdown)


def test_headings_and_single_synthetic_notice(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    at = AppTest.from_file(str(ROOT / "views/today.py"), default_timeout=60).run()
    assert [t.value for t in at.title] == ["Today"]
    notice = "SYNTHETIC – NOT REAL DATA"
    assert sum(notice in m.value for m in at.markdown) == 1  # the brand-bar pill only
    assert not any(notice in c.value for c in at.caption)
    assert any(c.value.startswith("today is 04/11/2026 · nothing is ever sent or filed with HMRC")
               for c in at.caption)
