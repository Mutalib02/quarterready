import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qr.redact import Redactor  # noqa: E402


def test_first_name_not_matched_inside_other_words():
    r = Redactor()
    r.add_name("Jo Onboardley (fictional)")
    r.add_name("Tom Joinerson (fictional)")
    out = r.redact("Jo asked; Tom Joinerson is a Joiner in Durham")
    assert "Joiner in" in out and "[FIRST_1] asked" in out and "[NAME_2]" in out


def test_turnover_not_treated_as_account_number():
    r = Redactor()
    assert "12000000" in r.redact("turnover 12000000")
    assert "[ACCOUNT_NO]" in r.redact("account number 12345678") and "[SORT_CODE]" in r.redact("20-45-17")
    assert "[EMAIL]" in r.redact("mail me at a.b@example.co.uk")


def test_restore_round_trip():
    r = Redactor()
    r.add_name("Kev Plumbwell (fictional)")
    assert r.restore(r.redact("Hi Kev Plumbwell, Kev here")) == "Hi Kev Plumbwell, Kev here"
