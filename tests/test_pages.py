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
