import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qr import categorise as cz  # noqa: E402


def fake_complete_factory(drop_first_time=False):
    calls = {"n": 0}

    def complete(system, messages, tools, max_tokens, tool_choice=None):
        calls["n"] += 1
        prompt = messages[-1]["content"]
        out = []
        for line in prompt.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 4 or not parts[0].isdigit():
                continue
            rid, desc = int(parts[0]), parts[2].upper()
            base = dict(row_id=rid, business_pct=100, needs_query=False, client_question="")
            if "FASTER PAYMENT" in desc or "REFUND" in desc:
                row = dict(income_or_expense="income", sa103_box=None, category_name="Sales",
                           allowable="yes", confidence=0.97, reason="Customer payment")
            elif "GRAND HOTEL" in desc or "BISTRO" in desc or "TUPELO" in desc:
                row = dict(income_or_expense="expense", sa103_box=39, category_name="Entertainment",
                           allowable="no", confidence=0.9, reason="entertainment is disallowable")
            elif "AMZN" in desc:
                row = dict(income_or_expense="expense", sa103_box=17, category_name="Materials",
                           allowable="yes", confidence=0.7, reason="Generic merchant")
            elif "VANS DIRECT" in desc:
                row = dict(income_or_expense="expense", sa103_box=29, category_name="Vehicle",
                           allowable="no", confidence=0.9, reason="Vehicle is capital")
            else:
                row = dict(income_or_expense="expense", sa103_box=17, category_name="Materials",
                           allowable="yes", confidence=0.95, reason="Trade materials")
            out.append({**base, **row})
        if drop_first_time and calls["n"] == 1:
            out = out[1:]  # model forgets a row; the re-ask must recover it
        return {"content": [{"type": "tool_use", "id": "x", "name": "record_categorisations",
                             "input": {"categorisations": out}}], "stop_reason": "tool_use",
                "usage": {"input_tokens": 1, "output_tokens": 1}}

    return complete, calls


@pytest.fixture(scope="module")
def dave():
    return cz.load_transactions(cz.DAVE_CSV)


def test_load_and_redaction(dave):
    assert len(dave) > 290 and {"row_id", "Date", "Description", "Amount"} <= set(dave.columns)
    sent = " ".join(r["description"] for r in cz.redacted_rows(dave))
    assert "SMITH" not in sent and "PATEL" not in sent and "[PAYER]" in sent


def test_batches_of_50_and_guards(dave):
    complete, calls = fake_complete_factory()
    df = cz.categorise(dave, complete, [])
    assert calls["n"] == -(-len(dave) // cz.BATCH) and len(df) == len(dave)
    van = df[df.Description.str.contains("VANS DIRECT")].iloc[0]
    assert van.colour == "red" and "capital" in van.flag.lower()
    refunds = df[df.Description.str.startswith("REFUND SCREWFIX")]
    assert set(refunds.flag) == {"Possible duplicate"} and set(refunds.colour) == {"red"}
    assert set(df.colour) <= {"green", "amber", "red"}
    assert (df[df.Description.str.contains("AMZN")].colour == "amber").all()


def test_missing_row_is_reasked_then_red():
    df = cz.load_transactions(cz.DAVE_CSV).head(10)
    complete, calls = fake_complete_factory(drop_first_time=True)
    out = cz.categorise(df, complete, [])
    assert calls["n"] == 2 and len(out) == 10 and (out.confidence > 0).all()

    def never(system, messages, tools, max_tokens, tool_choice=None):
        return {"content": [{"type": "text", "text": "sorry"}], "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1}}

    out = cz.categorise(df, never, [])
    assert set(out.colour) == {"red"} and out.needs_query.all()


def test_colour_rule():
    assert cz.colour(0.85, False) == "green" and cz.colour(0.84, False) == "amber"
    assert cz.colour(0.60, False) == "amber" and cz.colour(0.59, False) == "red"
    assert cz.colour(0.99, True) == "red" and cz.colour(0.99, False, "dup") == "red"


def test_invalid_box_rejected():
    with pytest.raises(ValueError):
        cz.Cat(row_id=1, income_or_expense="expense", sa103_box=99, category_name="x",
               allowable="yes", business_pct=100, confidence=0.9, reason="x")


def test_summary_and_export():
    df = pd.DataFrame([
        {"row_id": 1, "Date": "d", "Description": "a", "Amount": 1000.0,
         "income_or_expense": "income", "sa103_box": None, "allowable": "yes",
         "business_pct": 100},
        {"row_id": 2, "Date": "d", "Description": "b", "Amount": -100.0,
         "income_or_expense": "expense", "sa103_box": 17, "allowable": "yes",
         "business_pct": 100},
        {"row_id": 3, "Date": "d", "Description": "phone", "Amount": -40.0,
         "income_or_expense": "expense", "sa103_box": 23, "allowable": "partial",
         "business_pct": 50},
        {"row_id": 4, "Date": "d", "Description": "lunch", "Amount": -60.0,
         "income_or_expense": "expense", "sa103_box": 39, "allowable": "no",
         "business_pct": 100},
        {"row_id": 5, "Date": "d", "Description": "atm", "Amount": -50.0,
         "income_or_expense": "not_business", "sa103_box": None, "allowable": "no",
         "business_pct": 0},
        {"row_id": 6, "Date": "d", "Description": "amazon", "Amount": -30.0,
         "income_or_expense": "expense", "sa103_box": 17, "allowable": "yes",
         "business_pct": 100},
    ])
    s = cz.summarise(df, {6: {"decision": "Ask client"}})
    assert s["turnover"] == 1000 and s["boxes"] == {17: 100.0, 23: 20.0}
    assert s["disallowed"] == 80.0 and s["not_business"] == 50.0 and len(s["excluded"]) == 1
    # human override moves a row to a different box
    s2 = cz.summarise(df, {2: {"decision": "Override", "box": 30}})
    assert s2["boxes"] == {17: 30.0, 23: 20.0, 30: 100.0}
    text = cz.export_csv(s, "A. Accountant", "Dave")
    assert "Reviewed and approved by A. Accountant – not submitted to HMRC" in text
    assert "SYNTHETIC" in text
