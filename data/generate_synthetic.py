"""Builds all synthetic demo data with a fixed seed.

SYNTHETIC – NOT REAL DATA. Every name, message and transaction here is invented.
Run:  py data/generate_synthetic.py
"""
from __future__ import annotations

import csv
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qr import rules  # noqa: E402

DATA = ROOT / "data"
SEED = 20261104
MARK = "SYNTHETIC – NOT REAL DATA"


def dump(name: str, obj) -> None:
    (DATA / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------ practice
def practice() -> dict:
    return {
        "synthetic": MARK,
        "name": "Qistas Accountants (demo)",
        "partner": "Mutalib",
        "town": "Newcastle upon Tyne",
        "tone": "warm, plain English, no jargon, sign off with first name",
        "price_list": {
            "mtd_sole_trader": {"label": "MTD quarterly + year-end, sole trader", "monthly": 45},
            "landlord_1_2": {"label": "Landlord, 1–2 properties", "monthly": 40},
            "bookkeeping": {"label": "Bookkeeping add-on", "monthly": 25},
            "vat_returns": {"label": "VAT returns", "monthly": 30},
        },
    }


# --------------------------------------------------------------------- leads
def leads() -> list[dict]:
    def lead(i, name, btype, trade, town, source, turnover, prop, message, consent, received):
        return {
            "synthetic": MARK, "id": f"L{i:03d}", "name": name, "business_type": btype,
            "trade": trade, "town": town, "source": source, "est_turnover": turnover,
            "property_income": prop, "message": message, "consent_to_contact": consent,
            "received_date": received, "status": "New",
        }

    return [
        lead(1, "Kev Plumbwell (fictional)", "sole_trader", "Plumber", "Gateshead", "website_form",
             68000, 0,
             "I missed the first MTD quarter and the 7 November deadline is days away. I turn over "
             "about £68k and I'm panicking. Can you take me on this week?", False, "2026-11-03"),
        lead(2, "Lisa Tilman (fictional)", "sole_trader", "Tiler", "Durham", "referral", 74000, 0,
             "Was told by a mate I need to be doing quarterly updates. I've done nothing since April "
             "and make about £74k. Help!", False, "2026-11-02"),
        lead(3, "Sam Hedgely (fictional)", "sole_trader", "Gardener", "Hexham", "website_form",
             38000, 0,
             "I'm a gardener turning over about £38k. Do I need to do anything before next April?",
             False, "2026-10-30"),
        lead(4, "Ayesha Cuttler (fictional)", "sole_trader", "Mobile hairdresser", "Sunderland",
             "event", 44000, 0,
             "Spoke to you at the small business expo. I earn around £44k and want to get ahead of "
             "the 2027 changes.", False, "2026-10-29"),
        lead(5, "Tom Joinerson (fictional)", "sole_trader", "Joiner", "Middlesbrough",
             "social_enquiry", 33000, 0,
             "Saw your post about MTD. I'm on roughly £33k a year, is that me from April 2027?",
             False, "2026-10-31"),
        lead(6, "Margaret Flatley (fictional)", "landlord", "Residential landlord", "Gateshead",
             "referral", 0, 52000,
             "I let three flats in Gateshead (about £52k a year in rent). My current accountant "
             "retired. Can you handle the quarterly updates?", False, "2026-11-01"),
        lead(7, "Brightside Holdings Ltd (fictional)", "limited_company", "Property holding co.",
             "Newcastle upon Tyne", "website_form", 900000, 0,
             "We need a full statutory audit for our limited company group. Please quote.",
             False, "2026-10-28"),
        lead(8, "Northern Logistics Group (fictional)", "limited_company", "Logistics",
             "Middlesbrough", "website_form", 12000000, 0,
             "Looking for payroll and audit for 400 staff across 6 sites.", False, "2026-10-27"),
        lead(9, "Ricky Fakeman (fictional)", "sole_trader", "Builder", "Middlesbrough",
             "purchased_list", 55000, 0, "(no enquiry – name on a purchased marketing list)",
             False, "2026-10-26"),
        lead(10, "Donna Testley (fictional)", "sole_trader", "Hairdresser", "Durham",
             "purchased_list", 41000, 0, "(no enquiry – name on a purchased marketing list)",
             False, "2026-10-26"),
        lead(11, "Pat Vaguely (fictional)", "sole_trader", "Unknown", "Sunderland", "referral",
             None, 0, "Hi, do you do tax?", False, "2026-11-03"),
        lead(12, "Chris Sidehustle (fictional)", "sole_trader", "Occasional web design", "Hexham",
             "phone", 14000, 0,
             "I do a bit of freelance work on the side, about £14k last year. Do I need an "
             "accountant?", False, "2026-10-31"),
    ]


def labelled_leads() -> list[dict]:
    truth = {1: "High", 2: "High", 3: "Medium", 4: "Medium", 5: "Medium", 6: "High", 7: "Low",
             8: "Low", 9: "Do-not-contact", 10: "Do-not-contact", 11: "Medium", 12: "Low"}
    return [{"lead_id": f"L{i:03d}", "true_priority": p} for i, p in truth.items()]


# ------------------------------------------------------------------- clients
def clients() -> list[dict]:
    def onboarding(letter=True, idv=True, aml=True, agent=True):
        return {"engagement_letter": letter, "id_verified": idv, "aml_risk_assessment": aml,
                "hmrc_agent_authorised": agent}

    def qstatus(received="2026-10-12", queries=0):
        return {"period": "Q2 2026/27 (6 Jul – 5 Oct)", "records_due": "2026-10-14",
                "records_received": received, "queries_open": queries, "summary_signed_off": False}

    def client(i, name, ctype, trade, town, turnover, prop, fee, services, ob, qs, last, overrun,
               nps, notes, rising=False):
        return {
            "synthetic": MARK, "id": f"C{i:03d}", "name": name, "type": ctype, "trade": trade,
            "town": town, "mtd_cohort": rules.mtd_scope(turnover, prop), "monthly_fee": fee,
            "services": services, "onboarding": ob, "quarter_status": qs,
            "last_contact_date": last, "fee_overrun_hours": overrun,
            "turnover_last_12m": turnover, "property_income": prop,
            "property_income_rising": rising, "nps": nps, "notes": notes,
        }

    st = ["mtd_sole_trader"]
    return [
        client(1, "Dave Hartley (fictional)", "sole_trader", "Electrician", "Sunderland", 62000, 0,
               45, st, onboarding(), qstatus("2026-10-12", 1), "2026-10-30", 0, 9,
               "Q2 records received; bank CSV on file."),
        client(2, "Priya Rentwell (fictional)", "landlord", "Residential landlord (Heaton)",
               "Newcastle upon Tyne", 0, 58000, 40, ["landlord_1_2"], onboarding(),
               qstatus(None, 4), "2026-10-20", 1, 7,
               "Records three weeks late; unhappy about repeated requests.", rising=True),
        client(3, "Mark Spannerman (fictional)", "sole_trader", "Mobile mechanic", "Gateshead",
               86000, 0, 45, st, onboarding(), qstatus("2026-10-10", 0), "2026-10-28", 0, 9,
               "Turnover rising quickly."),
        client(4, "Jo Onboardley (fictional)", "sole_trader", "Decorator", "Durham", 55000, 0, 45,
               st, onboarding(True, False, False, False), {**qstatus(None, 0), "records_due": None}, "2026-10-25", 0, None,
               "New client; ID not yet verified."),
        client(5, "Hannah Hedgerow (fictional)", "sole_trader", "Gardener", "Hexham", 36000, 0, 45,
               st, onboarding(), qstatus("2026-10-15", 0), "2026-10-22", 0, 8,
               "2027 cohort; needs MTD software set-up before April 2027."),
        client(6, "Ian Plasterton (fictional)", "sole_trader", "Plasterer", "Middlesbrough",
               71000, 0, 45, st, onboarding(), qstatus("2026-10-08", 0), "2026-11-01", 0, 10,
               "Easy client."),
        client(7, "Beth Cakewell (fictional)", "sole_trader", "Baker", "Durham", 55000, 0, 45, st,
               onboarding(), qstatus("2026-11-03", 2), "2026-10-20", 4, 7,
               "Slow with records; fee overrun this quarter."),
        client(8, "Omar Taxiton (fictional)", "sole_trader", "Private hire driver", "Sunderland",
               58000, 0, 45, st, onboarding(), qstatus("2026-10-13", 0), "2026-10-27", 0, 8,
               "Reliable."),
        client(9, "Fiona Letsby (fictional)", "landlord", "Landlord (2 properties)", "Gateshead",
               0, 41000, 40, ["landlord_1_2"], onboarding(), qstatus("2026-10-16", 1),
               "2026-10-18", 0, 7, "Rental income increasing.", rising=True),
        client(10, "Colin Roofe (fictional)", "sole_trader", "Roofer", "Hexham", 52000, 0, 45, st,
               onboarding(), qstatus("2026-10-14", 0), "2026-10-29", 0, 9, "Solid."),
    ]


def messages() -> list[dict]:
    def m(i, cid, d, text, sentiment):
        return {"synthetic": MARK, "id": f"M{i:03d}", "client_id": cid, "date": d, "direction":
                "inbound", "text": text, "sentiment_seed": sentiment}

    return [
        m(1, "C002", "2026-10-28", "Third time I've been asked for the same statement. Thinking "
          "of moving to someone cheaper.", "negative"),
        m(2, "C002", "2026-10-20", "I've already sent the March statement. Can you check your "
          "emails please?", "neutral"),
        m(3, "C001", "2026-10-30", "Thanks, all received. Quick question about the van - is it "
          "claimable?", "positive"),
        m(4, "C003", "2026-10-28", "Business is mad busy this year, hit £80k already!", "positive"),
        m(5, "C004", "2026-10-25", "Sending my passport scans tomorrow, sorry for the delay.",
          "neutral"),
        m(6, "C005", "2026-10-22", "Do I need to buy software yet or can it wait?", "neutral"),
        m(7, "C007", "2026-09-12", "Yeah fine, I'll dig the receipts out when I get a minute.",
          "neutral"),
        m(8, "C009", "2026-10-18", "One query about the new flat's mortgage interest.",
          "neutral"),
        m(9, "C006", "2026-11-01", "Brilliant service as ever.", "positive"),
    ]


# ------------------------------------------------------------- transactions
# (description template, (min, max) amount, count, (class, box, allowable), trap)
EXP = ("expense", None, "yes")


def tx_templates() -> list[tuple]:
    return [
        ("FASTER PAYMENT FROM {cust}", (180, 1800), 50, ("income", None, "yes"), ""),
        ("CARD PAYMENT TO SCREWFIX DIRECT {d}", (8, 140), 40, ("expense", 17, "yes"), ""),
        ("CARD PAYMENT TO TOOLSTATION {d}", (6, 95), 20, ("expense", 17, "yes"), ""),
        ("CARD PAYMENT TO CITY ELECTRICAL FACTORS {d}", (25, 320), 20, ("expense", 17, "yes"), ""),
        ("CARD PAYMENT TO TRAVIS PERKINS {d}", (15, 210), 20, ("expense", 17, "yes"), ""),
        ("BP {site} A19", (35, 78), 28, ("expense", 20, "partial"), "fuel"),
        ("SHELL {site} A1M", (30, 75), 27, ("expense", 20, "partial"), "fuel"),
        ("GREGGS", (2, 9), 30, ("not_business", None, "no"), "generic merchant"),
        ("CARD PAYMENT TO CPS PARKING {d}", (2, 12), 8, ("expense", 20, "yes"), ""),
        ("AMZNMKTPLACE*{ref}", (9, 85), 17, ("expense", 17, "yes"), "generic merchant"),
        ("AMZNMKTPLACE*{ref}", (14, 120), 8, ("not_business", None, "no"),
         "personal Amazon purchase"),
        ("FACEBK *ADS {ref}", (15, 60), 6, ("expense", 24, "yes"), ""),
        ("ATM WITHDRAWAL {site}", (20, 100), 6, ("not_business", None, "no"), "cash withdrawal"),
        ("TFR TO SAVINGS", (200, 600), 4, ("not_business", None, "no"), "own-account transfer"),
        ("HMRC SA", (1200, 1200), 1, ("not_business", None, "no"), "tax payment"),
        ("MONTHLY ACCOUNT FEE", (7, 7), 3, ("expense", 26, "yes"), ""),
        ("HISCOX INSURANCE DD", (38, 38), 3, ("expense", 21, "yes"), ""),
        ("QISTAS ACCOUNTANTS DD", (45, 45), 3, ("expense", 28, "yes"), ""),
        ("VODAFONE LTD DD", (42, 42), 3, ("expense", 23, "partial"), "mixed-use phone"),
    ]


SITES = ["SUNDERLAND", "WASHINGTON", "BIRTLEY", "DURHAM", "SEAHAM", "FELLING"]
CUSTOMERS = ["J SMITH PLUMBING", "NORTHSIDE LETTINGS", "A & B BUILDERS", "M PATEL", "SEAHAM HOMES",
             "WEAR VALLEY PROPS", "K ROBSON", "TYNESIDE SHOPFITTERS", "L DIXON", "DURHAM CARE LTD"]


def build_transactions(rng: random.Random) -> list[dict]:
    start, end = date(2026, 7, 6), date(2026, 10, 5)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    weekdays = [d for d in days if d.weekday() < 5]
    rows: list[dict] = []

    def add(d, desc, amt, truth, trap=""):
        rows.append({"date": d, "desc": desc, "amount": round(amt, 2), "truth": truth,
                     "trap": trap})

    monthly_days = {0: date(2026, 7, 13), 1: date(2026, 8, 13), 2: date(2026, 9, 14)}
    for tmpl, (lo, hi), count, truth, trap in tx_templates():
        recurring = lo == hi and count <= 3  # fixed monthly direct debits: one per month
        for k in range(count):
            d = monthly_days[k] if recurring else rng.choice(weekdays)
            ds = d.strftime("%d/%m")
            desc = tmpl.format(
                d=ds, site=rng.choice(SITES), cust=rng.choice(CUSTOMERS),
                ref="".join(rng.choices("0123456789ABCDEFGHJKLMNPQRSTUVWXYZ", k=5)))
            amt = round(rng.uniform(lo, hi), 2)
            if truth[0] == "income":
                add(d, desc, amt, truth, trap)
            else:
                add(d, desc, -amt, truth, trap)

    # Hand-placed traps
    add(date(2026, 8, 21), "CARD PAYMENT TO THE GRAND HOTEL RESTAURANT 21/08", -86.40,
        ("expense", 39, "no"), "client lunch")
    add(date(2026, 9, 11), "CARD PAYMENT TO TUPELO KITCHEN NEWCASTLE 11/09", -64.20,
        ("expense", 39, "no"), "client lunch")
    add(date(2026, 9, 25), "CARD PAYMENT TO BISTRO 21 DURHAM 25/09", -118.00,
        ("expense", 39, "no"), "client lunch")
    add(date(2026, 8, 14), "CARD PAYMENT TO SCREWFIX DIRECT 14/08", -212.30,
        ("expense", 17, "yes"), "")
    add(date(2026, 9, 3), "CARD PAYMENT TO VANS DIRECT NE LTD 03/09", -8500.00,
        ("expense", 29, "no"), "capital: £8,500 van")
    add(date(2026, 8, 18), "REFUND SCREWFIX DIRECT 18/08", 54.99, ("expense", 17, "yes"),
        "duplicate refund")
    add(date(2026, 8, 18), "REFUND SCREWFIX DIRECT 18/08", 54.99, ("expense", 17, "yes"),
        "duplicate refund")

    rows.sort(key=lambda r: (r["date"], r["desc"]))
    balance = 4200.00
    for i, r in enumerate(rows, start=1):
        balance = round(balance + r["amount"], 2)
        r["balance"] = balance
        r["row_id"] = i
    return rows


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        f.write(f"# {MARK}\n")
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    rng = random.Random(SEED)
    (DATA / "transactions").mkdir(parents=True, exist_ok=True)

    dump("practice.json", practice())
    dump("leads.json", leads())
    dump("clients.json", clients())
    dump("messages.json", messages())
    write_csv(DATA / "labelled_leads.csv", ["lead_id", "true_priority"],
              [[r["lead_id"], r["true_priority"]] for r in labelled_leads()])

    tx = build_transactions(rng)
    write_csv(DATA / "transactions" / "dave_q2_2026.csv",
              ["Date", "Description", "Amount", "Balance"],
              [[r["date"].strftime("%d/%m/%Y"), r["desc"], f"{r['amount']:.2f}",
                f"{r['balance']:.2f}"] for r in tx])

    # Labelled sample: every trap row plus random fill, ~90 rows
    traps = [r for r in tx if r["trap"] and r["trap"] not in ("fuel", "generic merchant")]
    others = [r for r in tx if r not in traps]
    sample = traps[:] + rng.sample(others, max(0, 90 - len(traps)))
    sample.sort(key=lambda r: r["row_id"])
    write_csv(DATA / "labelled_transactions.csv",
              ["row_id", "Date", "Description", "Amount", "true_class", "true_sa103_box",
               "true_allowable", "trap"],
              [[r["row_id"], r["date"].strftime("%d/%m/%Y"), r["desc"], f"{r['amount']:.2f}",
                r["truth"][0], r["truth"][1] if r["truth"][1] is not None else "",
                r["truth"][2], r["trap"]] for r in sample])

    print(f"leads={len(leads())} clients={len(clients())} transactions={len(tx)} "
          f"labelled={len(sample)}")


if __name__ == "__main__":
    main()
