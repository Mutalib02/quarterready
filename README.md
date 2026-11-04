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
