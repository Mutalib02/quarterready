import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_categorise import fake_complete_factory  # noqa: E402

from qr import categorise as cz, evaluate, store  # noqa: E402


def test_categorisation_metrics_on_fake_model():
    complete, _ = fake_complete_factory()
    df = cz.categorise(cz.load_transactions(cz.DAVE_CSV), complete, [])
    m = evaluate.categorisation_metrics(df)
    assert m["n"] == 90 and 0 <= m["accuracy"] <= 1
    assert len(m["failures"]) == round(m["n"] * (1 - m["accuracy"]))
    assert m["wrong_but_confident"] >= 0


def test_perfect_model_scores_100():
    truth = evaluate.labelled_transactions()
    df = pd.DataFrame({
        "row_id": truth.row_id, "Description": truth.Description,
        "income_or_expense": truth.true_class, "sa103_box": truth.true_sa103_box,
        "allowable": truth.true_allowable, "confidence": 0.9, "reason": "", })
    m = evaluate.categorisation_metrics(df)
    assert m["accuracy"] == 1.0 and m["failures"].empty


def test_lead_agreement():
    state = store.load_all()
    assert evaluate.lead_agreement(state["leads"])["n"] == 0
    state["leads"][0]["assessment"] = {"priority": "High"}
    state["leads"][8]["assessment"] = {"priority": "Do not contact – no consent"}
    state["leads"][1]["assessment"] = {"priority": "Low"}
    la = evaluate.lead_agreement(state["leads"])
    assert la["n"] == 3 and abs(la["agreement"] - 2 / 3) < 1e-9


def test_safety_results_all_pass():
    s = evaluate.safety_results(store.load_all())
    assert all(ok for _, ok in s["tests"]) and len(s["pecr_blocked_leads"]) == 2
    assert s["never_sent"]
