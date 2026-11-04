import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qr import rules  # noqa: E402

D = date(2026, 11, 4)


def test_mtd_scope_boundaries():
    assert rules.mtd_scope(50_001) == "2026"
    assert rules.mtd_scope(50_000) == "2027"
    assert rules.mtd_scope(30_001) == "2027"
    assert rules.mtd_scope(30_000) == "2028"
    assert rules.mtd_scope(20_001) == "2028"
    assert rules.mtd_scope(20_000) == "not_in_scope"


def test_mtd_scope_includes_property_income():
    assert rules.mtd_scope(30_000, 25_000) == "2026"


def test_deadlines():
    nd = rules.next_deadline(D)
    assert nd["label"] == "Q2" and nd["due"] == date(2026, 11, 7)
    assert nd["days_left"] == 3
    after = rules.next_deadline(date(2026, 11, 8))
    assert after["label"] == "Q3" and after["due"] == date(2027, 2, 7)
    assert rules.final_declaration_due(2026) == date(2028, 1, 31)


def test_quarter_dates():
    q = {q["label"]: q for q in rules.quarter_calendar(2026)}
    assert q["Q1"]["due"] == date(2026, 8, 7)
    assert q["Q4"]["end"] == date(2027, 4, 5) and q["Q4"]["due"] == date(2027, 5, 7)


def test_health_score_priya_is_35():
    priya = {
        "quarter_status": {"records_due": "2026-10-14", "records_received": None, "queries_open": 4},
        "last_contact_date": "2026-10-20", "fee_overrun_hours": 1, "nps": 7,
    }
    h = rules.health_score(priya, negative_sentiment=True, on=D)
    assert h["score"] == 35 and h["band"] == "At risk"
    assert len(h["breakdown"]) == 3


def test_health_score_healthy_and_caps():
    ok = {"quarter_status": {"records_due": "2026-10-14", "records_received": "2026-10-12",
                             "queries_open": 0},
          "last_contact_date": "2026-10-30", "fee_overrun_hours": 0, "nps": 9}
    assert rules.health_score(ok, on=D) == {"score": 100, "band": "Healthy", "breakdown": []}
    many = {"quarter_status": {"queries_open": 9}}
    assert rules.health_score(many, on=D)["score"] == 80  # query deduction capped at 20


def test_health_bands():
    assert rules.health_band(75) == "Healthy"
    assert rules.health_band(74) == "Watch"
    assert rules.health_band(50) == "Watch"
    assert rules.health_band(49) == "At risk"


def test_health_all_deductions():
    c = {"quarter_status": {"records_due": "2026-10-01", "queries_open": 4},
         "last_contact_date": "2026-08-01", "fee_overrun_hours": 4, "nps": 6}
    assert rules.health_score(c, True, on=D)["score"] == 100 - 25 - 20 - 20 - 10 - 10 - 10


def test_records_exactly_14_days_late_not_penalised():
    qs = {"records_due": "2026-10-21", "records_received": None}
    assert rules.records_days_late(qs, D) == 14
    assert rules.health_score({"quarter_status": qs}, on=D)["score"] == 100


def test_opportunities():
    assert "Approaching VAT threshold £90k" in rules.opportunities({"turnover_last_12m": 86_000})
    assert rules.opportunities({"turnover_last_12m": 62_000}) == []
    assert "MTD onboarding before Apr 2027" in rules.opportunities({"mtd_cohort": "2027"})


def test_pecr_gate():
    assert not rules.can_market({"source": "purchased_list", "consent_to_contact": False})
    assert rules.can_market({"source": "purchased_list", "consent_to_contact": True})
    for s in ("website_form", "referral", "phone", "social_enquiry", "event"):
        assert rules.can_market({"source": s, "consent_to_contact": False})
    assert rules.consent_status({"source": "purchased_list"}) == "Do not contact – no consent"


def test_aml_gate():
    ob = lambda i, a: {"onboarding": {"id_verified": i, "aml_risk_assessment": a}}  # noqa: E731
    assert rules.aml_gate(ob(True, True))
    assert not rules.aml_gate(ob(True, False))
    assert not rules.aml_gate(ob(False, True))
    assert not rules.aml_gate({})
    assert rules.onboarding_status(ob(False, False)).startswith("Onboarding")


def test_banned_phrases():
    assert rules.banned_phrases_found("We guarantee a refund") == ["guarantee"]
    assert "you will save" in rules.banned_phrases_found("You will save £500")
    assert rules.draft_is_safe("Happy to arrange a 15-minute call.")
    assert not rules.draft_is_safe("Refund guaranteed!")


def test_uk_date_format():
    assert rules.fmt_date("2026-11-07") == "07/11/2026"
    assert rules.fmt_date(None) == "–"
