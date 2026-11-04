# QuarterReady

**The AI practice agent that helps North East accountants win, manage and keep clients through Making Tax Digital – with the accountant approving every action.**

Track 2: Small Business, Big Tools · Built with Claude Code at Claude Builder Club, Northumbria · 4 Nov 2026

---

## Live demo

**LIVE_DEMO_URL**

Demo uses Claude output recorded via Claude Code (no API credit today); Live mode works with a funded key.

All data is synthetic (`SYNTHETIC – NOT REAL DATA`). Nothing is ever sent, and nothing is ever filed with HMRC.

---

## The problem

Making Tax Digital for Income Tax started in April 2026, and 864,000+ sole traders and landlords are now in scope, with about 1.08 million more joining in April 2027. The second quarterly update is due on **7 November 2026**. MTD turned one annual job into four, and small North East practices (1–10 people) have no time left to chase clients for records, so they can't win new clients or keep the ones they have.

## What it does

| Stage | What the agent does | What the human does |
|---|---|---|
| **WIN** | Reads new enquiries, checks MTD scope, scores fit and urgency, drafts a personalised reply and a fixed-fee quote | Approves or edits the reply and quote |
| **MANAGE** | Tracks every client's MTD deadlines, chases missing records, categorises bank transactions into HMRC SA103 boxes with a confidence score and a reason, drafts client questions | Does the ID and AML checks; reviews and signs off the quarterly summary |
| **KEEP** | Gives each client a health score, flags at-risk clients, spots opportunities (VAT threshold, April 2027 wave), drafts retention messages | Approves messages and makes the call |

**Every message waits in an Approval Queue.** Approve, edit or reject; approving only moves a draft to a simulated Sent log.

The demo moment: click **Run morning briefing**. The agent works through leads, deadlines and client health, shows each step it took and why, and ends with a prioritised to-do list and a queue of drafts.

## How it works

The agent is a Claude tool-use loop (`qr/agent.py`): up to 12 turns, several tool calls per turn, a live step trace, and every response cached so the demo can replay offline.

| Tool | What it does |
|---|---|
| `list_new_leads` | Leads with status New |
| `assess_lead` | MTD cohort, priority, fit and urgency (blocked leads never reach the model) |
| `draft_lead_reply` | Personalised reply with a 15-minute call offer (refused if no consent) |
| `build_quote` | Fixed monthly fee from the price list, plus wording |
| `list_deadlines` | Clients with updates due and their records status |
| `chase_records` | Polite records reminder with a checklist |
| `prep_mtd_quarter` | Categorises a client's bank CSV into SA103 boxes (batches of 50) |
| `client_health` | Transparent health score, band and breakdown |
| `find_opportunities` | VAT threshold, 2027 cohort, landlord review |
| `draft_retention_message` | Empathetic message for an at-risk client; no discounts |
| `queue_for_approval` | Adds to the Approval Queue after safety checks; **never sends** |

**Deterministic Python (`qr/rules.py`), never the model:** MTD scope (£50k / £30k / £20k thresholds), quarterly deadlines, the health score and its bands, the PECR consent gate, the AML gate, the banned-phrases check, and all pricing.

**Claude does the judgement and language:** reading enquiries, explaining fit, message sentiment, drafting replies, quotes and retention messages, categorising transactions with a reason for each, and writing the briefing.

## Evaluation

Measured on the **Evaluation & Safety** page against labelled data, using Claude output recorded via Claude Code.

- **91% (82 of 90)** labelled transactions correct. SA103 box accuracy on expense rows was 100%, and the 41 high-confidence rows (≥ 0.85) were all correct, with **zero confident mistakes**.
- **All 8 misses are personal Amazon purchases** treated as business. The description gives nothing to tell them apart, so every Amazon row was **flagged red with a question for the client**.
- **12 of 12** lead priorities agree with the labels.
- **Caveats.** The labels were produced by the team's own data generator, not an independent annotator, so this is not a blind test. The simple rule-based Local engine also scores 91% on this set, so the set can't separate the two. The business Amazon rows count as correct only because the guess happened to be right. Treat the numbers as indicative, not proof.

**Five bugs found and fixed while producing the recorded output:**

1. A first name such as "Jo" was redacted inside other words ("Joiner").
2. A £12m turnover was redacted as if it were a bank account number.
3. A supplier refund was added to costs instead of reducing them.
4. The retention prompt listed the client's late records as "issues on our side", inviting an apology that blamed her.
5. SA103 box numbers printed as `17.0` instead of `17`.

## Safety and compliance

- **Approval Queue.** The agent never sends anything and never files with HMRC. Every outbound draft waits for a human click.
- **PECR consent gate.** Sole traders and landlords are individuals, so marketing is only drafted for leads who contacted us first or consented. Others are marked "Do not contact – no consent". This check is Python and runs before any model call.
- **AML gate.** A client can't become Active until a human ticks "ID verified" and "AML risk assessment done". The agent can remind; it can't tick.
- **No tax promises.** A banned-phrases check ("guarantee", "you will save", "refund guaranteed") runs on every draft, including after a human edit.
- **Sign-off gate.** The quarterly summary export stays locked until every red row has a decision and a named reviewer confirms. It is stamped "Reviewed and approved by [name] – not submitted to HMRC".
- **Confident mistakes.** Every categorisation has a confidence score and a reason, and the model is told to prefer a client question to a guess.
- **Sensitive data.** Names, payer names, account numbers, sort codes and emails are redacted before any model call, and the **Data sent to AI** viewer shows exactly what was sent.
- **Audit log.** Human and agent actions are logged.
- **Synthetic data only.** No real personal data is used anywhere.

## Business model

- **£99 per practice per month** (up to 30 active MTD clients); early-customer price £49 for the first 6 months.
- **About £35 per month cost to serve**: AI £15, support £15, hosting £3, payments £2. That is roughly a 65% contribution margin.
- **Break-even at 87 practices** (two founders paid at the National Living Wage); 50 practices with one founder paid.
- **At 100 practices: £9,900 per month revenue** (about £118,800 ARR).
- **£30k funding**: £5k founder money plus a £25k Start Up Loan at 7.5% fixed.

## Engines

| Engine | Needs | Notes |
|---|---|---|
| Live | `ANTHROPIC_API_KEY` + API credit | Cache first, calls Claude on a miss; every response is saved to `cache/` |
| Recorded | committed `recorded/*.json` | Claude output recorded via Claude Code today (no funded key). Replays one full briefing on the standard demo data; see `recorded/README.md` for how honest that is |
| Offline | committed `cache/*.json` | Replays recorded Claude responses |
| Local | nothing | Rule-based stand-in (`qr/local_model.py`), **not Claude**. Same tools, compliance gates and approval queue; keyword rules and templates. Never writes `cache/`. |

`py record_briefing.py [--recorded | --offline | --local]` runs the morning briefing from the command line.

## Run it

```
pip install -r requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY
py data/generate_synthetic.py
py -m pytest
streamlit run app.py
```

## Team

- **Mutalib** – founder, domain lead (36 months' finance experience in banking, working towards ACCA, founder of Qistas Accountants Ltd). Built solo in one afternoon with Claude Code.

## Licence

MIT – see [LICENSE](LICENSE).
