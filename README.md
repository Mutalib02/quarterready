# QuarterReady

AI practice agent for North East accountants: win, manage and keep clients through Making Tax Digital.

**All data in this repo is synthetic (`SYNTHETIC – NOT REAL DATA`).** The agent never sends messages and never files with HMRC.

## Run

```
pip install -r requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY
py data/generate_synthetic.py
py -m pytest
streamlit run app.py
```

Licence: MIT

## Engines

| Engine | Needs | Notes |
|---|---|---|
| Live | `ANTHROPIC_API_KEY` + API credit | Cache first, calls Claude on a miss; every response is saved to `cache/` |
| Offline | committed `cache/*.json` | Replays recorded Claude responses |
| Local | nothing | Rule-based stand-in (`qr/local_model.py`), **not Claude**. Same tools, compliance gates and approval queue; keyword rules and templates. Never writes `cache/`. |

`py record_briefing.py [--offline | --local]` runs the morning briefing from the command line.
