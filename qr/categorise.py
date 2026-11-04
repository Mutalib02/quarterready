"""Transaction categorisation into SA103 boxes: batches of 50, tool use, pydantic, cached.

The LLM judges each row; Python adds deterministic guards (duplicates, large one-offs) and the
green/amber/red colour rule.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Callable, Literal

import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator

from qr import agent, categories
from qr.redact import Redactor

BATCH = 50
DATA = Path(__file__).resolve().parents[1] / "data"
DAVE_CSV = DATA / "transactions" / "dave_q2_2026.csv"
LARGE_ONE_OFF = 2500  # outgoings at/over this are queried as possible capital items

SYSTEM = f"""You categorise a UK sole trader's bank transactions into HMRC SA103 boxes for a \
qualified accountant to review. Use the record_categorisations tool for EVERY row you are given.

SA103 boxes:
{categories.prompt_table()}

Rules:
- income_or_expense: 'income' (money in from customers), 'expense', or 'not_business' (drawings, \
HMRC payments, transfers between own accounts, personal spending).
- For income set sa103_box to null. For not_business set sa103_box to null.
- Client entertainment is disallowable: allowable 'no', box 39.
- Big equipment or vehicles are likely capital: box 29, allowable 'no', needs_query true.
- Mixed-use items (e.g. phone) are allowable 'partial' with a business_pct.
- Give LOW confidence (<0.6) to generic merchants (Amazon, PayPal), cash withdrawals and transfers.
- Prefer needs_query=true (with a short, friendly client_question) to guessing.
- reason: max 20 words, plain English, explain the rule (e.g. 'entertainment is disallowable').
- confidence is 0 to 1. business_pct is 0 to 100 (100 if fully business, 0 if not_business).
Names and account numbers have been redacted; ignore the placeholders."""


class Cat(BaseModel):
    row_id: int
    income_or_expense: Literal["income", "expense", "not_business"]
    sa103_box: int | None = None
    category_name: str
    allowable: Literal["yes", "no", "partial"]
    business_pct: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    reason: str
    needs_query: bool = False
    client_question: str = ""

    @field_validator("sa103_box")
    @classmethod
    def valid_box(cls, v):
        if v is not None and v not in categories.VALID_BOXES:
            raise ValueError(f"sa103_box {v} is not a valid box")
        return v


class Batch(BaseModel):
    categorisations: list[Cat]


TOOL = {
    "name": "record_categorisations",
    "description": "Record the categorisation of every transaction row supplied.",
    "input_schema": {
        "type": "object",
        "properties": {"categorisations": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "row_id": {"type": "integer"},
                "income_or_expense": {"type": "string",
                                      "enum": ["income", "expense", "not_business"]},
                "sa103_box": {"type": ["integer", "null"]},
                "category_name": {"type": "string"},
                "allowable": {"type": "string", "enum": ["yes", "no", "partial"]},
                "business_pct": {"type": "integer"},
                "confidence": {"type": "number"},
                "reason": {"type": "string"},
                "needs_query": {"type": "boolean"},
                "client_question": {"type": "string"}},
            "required": ["row_id", "income_or_expense", "sa103_box", "category_name",
                         "allowable", "business_pct", "confidence", "reason", "needs_query",
                         "client_question"]}}},
        "required": ["categorisations"]},
}


# ------------------------------------------------------------------- loading
def load_transactions(source) -> pd.DataFrame:
    """Read a bank CSV (path or file-like): Date, Description, Amount, Balance."""
    df = pd.read_csv(source, comment="#")
    df.columns = [c.strip().title() for c in df.columns]
    missing = {"Date", "Description", "Amount"} - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing columns: {', '.join(sorted(missing))}")
    df = df[["Date", "Description", "Amount"] + (["Balance"] if "Balance" in df else [])].copy()
    df["Amount"] = pd.to_numeric(df["Amount"], errors="raise")
    df.insert(0, "row_id", range(1, len(df) + 1))
    return df


def _clean_description(desc: str, redactor: Redactor) -> str:
    """Hide payer names (people and small firms) and any account numbers/emails."""
    desc = re.sub(r"(?i)^FASTER PAYMENT FROM\s+.+$", "FASTER PAYMENT FROM [PAYER]", str(desc))
    desc = re.sub(r"\d{8}", "[ACCOUNT_NO]", desc)  # bare 8-digit numbers in bank text
    desc = re.sub(r"\b\d{8}\b", "[ACCOUNT_NO]", desc)  # bare 8-digit numbers in bank text
    return redactor.redact(desc)


def redacted_rows(df: pd.DataFrame, redactor: Redactor | None = None) -> list[dict]:
    """What is actually sent to the AI: no payer names, account numbers or emails."""
    redactor = redactor or Redactor()
    return [{"row_id": int(r.row_id), "date": str(r.Date),
             "description": _clean_description(r.Description, redactor),
             "amount": float(r.Amount)} for r in df.itertuples()]


# ---------------------------------------------------------------- calling AI
def _ask_batch(complete: Callable, rows: list[dict], log: list) -> list[Cat]:
    prompt = "Categorise these transactions:\n" + "\n".join(
        f"{r['row_id']} | {r['date']} | {r['description']} | £{r['amount']:.2f}" for r in rows)
    log.append({"purpose": f"categorise rows {rows[0]['row_id']}–{rows[-1]['row_id']}",
                "sent": prompt, "time": pd.Timestamp.now().strftime("%H:%M:%S")})
    messages = [{"role": "user", "content": prompt}]
    choice = {"type": "tool", "name": "record_categorisations"}
    wanted = {r["row_id"] for r in rows}
    got: dict[int, Cat] = {}
    for attempt in range(2):  # validate with pydantic; re-ask once on failure
        resp = complete(SYSTEM, messages, [TOOL], 8000, choice)
        block = next((b for b in resp["content"] if b["type"] == "tool_use"), None)
        error = "no tool call returned"
        if block:
            raw = block["input"].get("categorisations", [])
            ok, bad = [], []
            for item in raw:
                try:
                    ok.append(Cat.model_validate(item))
                except ValidationError as exc:
                    bad.append(str(exc).splitlines()[0])
            got.update({c.row_id: c for c in ok if c.row_id in wanted})
            if wanted <= set(got):
                break
            error = f"missing or invalid rows {sorted(wanted - set(got))}: {bad[:2]}"
        if attempt == 0:
            rows = [r for r in rows if r["row_id"] not in got]
            prompt = (f"Your answer was incomplete ({error}). Categorise ONLY these rows:\n"
                      + "\n".join(f"{r['row_id']} | {r['date']} | {r['description']} | "
                                  f"£{r['amount']:.2f}" for r in rows))
            messages = [{"role": "user", "content": prompt}]
    # anything still missing becomes a red 'query' row rather than a silent guess
    for rid in wanted - set(got):
        got[rid] = Cat(row_id=rid, income_or_expense="not_business", category_name="Unknown",
                       allowable="no", business_pct=0, confidence=0.0,
                       reason="No valid answer from the AI – needs your review.",
                       needs_query=True, client_question="Can you tell us what this was for?")
    return [got[i] for i in sorted(wanted)]


def categorise(df: pd.DataFrame, complete: Callable, ai_log: list | None = None) -> pd.DataFrame:
    """Categorise every row; returns df with AI columns + guards + colour."""
    ai_log = ai_log if ai_log is not None else []
    rows = redacted_rows(df)
    cats: dict[int, Cat] = {}
    for i in range(0, len(rows), BATCH):
        for c in _ask_batch(complete, rows[i:i + BATCH], ai_log):
            cats[c.row_id] = c
    out = df.copy()
    for col in ("income_or_expense", "sa103_box", "category_name", "allowable", "business_pct",
                "confidence", "reason", "needs_query", "client_question"):
        out[col] = [getattr(cats[int(r)], col) for r in out["row_id"]]
    return apply_guards(out)


def apply_guards(df: pd.DataFrame) -> pd.DataFrame:
    """Deterministic checks layered on top of the AI's answer."""
    df = df.copy()
    df["flag"] = ""
    dup = df.duplicated(subset=["Date", "Description", "Amount"], keep=False)
    for idx in df.index[dup]:
        df.at[idx, "flag"] = "Possible duplicate"
        df.at[idx, "needs_query"] = True
        if not df.at[idx, "client_question"]:
            df.at[idx, "client_question"] = "This looks like it appears twice – is that right?"
    big = (df["Amount"] <= -LARGE_ONE_OFF) & (df["income_or_expense"] == "expense")
    for idx in df.index[big]:
        df.at[idx, "flag"] = (df.at[idx, "flag"] + "; " if df.at[idx, "flag"] else "") \
            + "Large one-off: possible capital item"
        df.at[idx, "needs_query"] = True
        if not df.at[idx, "client_question"]:
            df.at[idx, "client_question"] = "Is this a one-off purchase of equipment or a vehicle?"
    df["colour"] = [colour(r.confidence, r.needs_query, r.flag) for r in df.itertuples()]
    return df


def colour(confidence: float, needs_query: bool, flag: str = "") -> str:
    """green >= 0.85; amber 0.60-0.85; red < 0.60, flagged, or a query."""
    if needs_query or flag or confidence < 0.60:
        return "red"
    return "green" if confidence >= 0.85 else "amber"


# ------------------------------------------------------------------- summary
def summarise(df: pd.DataFrame, decisions: dict[int, dict]) -> dict:
    """Totals by SA103 box after human decisions. decisions[row_id] = {decision, box,
    allowable}. Rows sent 'ask client' are excluded and listed."""
    income, boxes, disallowed, not_business, excluded = 0.0, {}, 0.0, 0.0, []
    for r in df.itertuples():
        d = decisions.get(int(r.row_id), {})
        if d.get("decision") == "Ask client":
            excluded.append(r)
            continue
        kind = r.income_or_expense
        box = d.get("box", r.sa103_box)
        box = None if box is None or pd.isna(box) else int(box)
        allowable = d.get("allowable", r.allowable)
        amt = abs(float(r.Amount))
        if kind == "expense":
            amt = -float(r.Amount)  # a positive 'expense' row is a refund and reduces the cost
        if kind == "income":
            income += float(r.Amount)
        elif kind == "not_business" or (box is None and allowable == "no"):
            not_business += amt
        elif allowable == "no" or box in (29, 39):
            disallowed += amt
        else:
            share = amt * (r.business_pct / 100 if allowable == "partial" else 1)
            boxes[box if box is not None else 30] = boxes.get(box if box is not None else 30,
                                                              0) + share
            disallowed += amt - share
    return {"turnover": round(income, 2),
            "boxes": {b: round(v, 2) for b, v in sorted(boxes.items())},
            "disallowed": round(disallowed, 2), "not_business": round(not_business, 2),
            "excluded": [(int(r.row_id), r.Description, r.Amount) for r in excluded]}


def export_csv(summary: dict, reviewer: str, client_name: str) -> str:
    buf = io.StringIO()
    buf.write(f"# {client_name} – Q2 2026/27 quarterly summary by SA103 box\n")
    buf.write(f"# Reviewed and approved by {reviewer} – not submitted to HMRC\n")
    buf.write("# SYNTHETIC – NOT REAL DATA\n")
    buf.write("Section,Box,Description,Amount (GBP)\n")
    buf.write(f"Income,,Turnover,{summary['turnover']:.2f}\n")
    for b, v in summary["boxes"].items():
        buf.write(f"Expense,{b},\"{categories.SA103[b].split(' (')[0]}\",{v:.2f}\n")
    buf.write(f"Not claimed,,Disallowable / capital,{summary['disallowed']:.2f}\n")
    buf.write(f"Not business,,Drawings / transfers / tax,{summary['not_business']:.2f}\n")
    for rid, desc, amt in summary["excluded"]:
        buf.write(f"Held for client answer,,\"{desc}\",{float(amt):.2f}\n")
    return buf.getvalue()


def client_questions(df: pd.DataFrame) -> list[str]:
    return [f"{r.Date} {r.Description} (£{abs(r.Amount):.2f}): {r.client_question}"
            for r in df.itertuples() if r.needs_query and r.client_question]


def run_for_client(ctx, client_id: str, csv_path: Path = DAVE_CSV) -> pd.DataFrame:
    """Used by the agent tool: categorise a client's CSV through the cached completion."""
    df = load_transactions(csv_path)
    complete = ctx.complete or agent.make_complete(ctx)
    return categorise(df, complete, ctx.state["ai_log"])
