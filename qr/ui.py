"""Shared Streamlit bits: the engine/mode picker used on every AI page."""
from __future__ import annotations

import os
from dataclasses import dataclass

from qr import cache

LIVE = "Live (cache first, Claude on a miss)"
RECORDED = "Recorded by Claude (via Claude Code)"
OFFLINE = "Offline (replay cache)"
LOCAL = "Local engine (no API – rule-based, not Claude)"
RECORDED_NOTE = ("Claude output recorded via Claude Code today – live API mode needs a funded "
                 "key")


@dataclass
class Mode:
    offline: bool
    local: bool
    recorded: bool
    ready: bool

    @property
    def kwargs(self) -> dict:
        return {"offline": self.offline, "local": self.local, "recorded": self.recorded}


def pick_mode(st, key: str = "mode") -> Mode:
    """Defaults: Live with a key, else Recorded if present, else Offline if a cache exists,
    else the local engine (always the last fallback)."""
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_recorded = any(cache.RECORDED_DIR.glob("*.json"))
    has_cache = any(cache.CACHE_DIR.glob("*.json"))
    options = [LIVE, RECORDED, OFFLINE, LOCAL]
    default = (RECORDED if has_recorded else LIVE if has_key else OFFLINE if has_cache
               else LOCAL)
    mode = st.radio("Engine", options, index=options.index(default), horizontal=True, key=key)
    if mode == LIVE and not has_key:
        st.warning("No ANTHROPIC_API_KEY found. Add one to .env, or use another engine.")
    if mode == RECORDED:
        st.success("✅ " + RECORDED_NOTE + ". Replayed from `recorded/`; works on the standard "
                   "demo data only.")
        if not has_recorded:
            st.warning("Nothing recorded yet.")
    if mode == LOCAL:
        st.info("🔧 Local engine: keyword rules and templates, **not Claude**. Same tools, "
                "gates and approval queue; weaker judgement. Nothing is cached.")
    ready = (mode != LIVE or has_key) and (mode != RECORDED or has_recorded)
    return Mode(offline=mode == OFFLINE, local=mode == LOCAL, recorded=mode == RECORDED,
                ready=ready)


# ------------------------------------------------------------------- styling
NAVY, TEAL = "#0B2545", "#14B8A6"
PILLS = {"healthy": "#16A34A", "watch": "#D97706", "at risk": "#DC2626", "blocked": "#64748B"}
ROW_COLOURS = {"green": "#DCFCE7", "amber": "#FEF3C7", "red": "#FEE2E2"}

CSS = f"""
<style>
/* sidebar */
[data-testid="stSidebar"] {{ background: {NAVY}; }}
[data-testid="stSidebar"] * {{ color: #FFFFFF !important; }}
[data-testid="stSidebarNav"] a, [data-testid="stSidebarNavLink"] {{
  border-radius: 8px; margin: 2px 6px; }}
[data-testid="stSidebarNav"] a[aria-current="page"], [data-testid="stSidebarNavLink"][aria-current="page"],
[data-testid="stSidebarNav"] a[data-active="true"] {{ background: {TEAL} !important; font-weight: 700; }}
[data-testid="stSidebarNav"] a:hover, [data-testid="stSidebarNavLink"]:hover {{
  background: rgba(20,184,166,0.35); }}
/* brand bar */
.qr-brand {{ display:flex; align-items:center; gap:14px; flex-wrap:wrap;
  padding: 4px 0 14px 0; margin-bottom: 8px; border-bottom: 1px solid #DDE5EE; }}
.qr-brand .name {{ font-size: 1.6rem; font-weight: 800; color: {NAVY}; letter-spacing: -0.5px; }}
.qr-brand .tag {{ color: #0F766E; font-weight: 600; }}
.qr-brand .notice {{ margin-left:auto; background:#E2E8F0; color:#475569; font-size:0.72rem;
  padding: 3px 10px; border-radius: 999px; font-weight: 600; letter-spacing: .3px; }}
/* KPI cards */
[data-testid="stMetric"] {{ background:#FFFFFF; border-radius:12px; padding:14px 18px;
  border-top: 4px solid {TEAL}; box-shadow: 0 2px 8px rgba(15,23,42,0.08); }}
/* status pills */
.qr-pill {{ display:inline-block; color:#fff; border-radius:999px; padding:2px 12px;
  font-size:0.8rem; font-weight:700; white-space:nowrap; }}
/* approval queue cards */
[class*="st-key-draft_"] {{ background:#FFFFFF; border-left: 5px solid {TEAL} !important;
  border-radius: 10px; box-shadow: 0 2px 8px rgba(15,23,42,0.07); padding: 6px 10px; }}
[class*="st-key-ap_"] button {{ background:{TEAL}; color:#fff; border:1px solid {TEAL}; border-radius:8px; }}
[class*="st-key-ap_"] button:hover {{ background:#0F766E; color:#fff; border-color:#0F766E; }}
[class*="st-key-rj_"] button {{ background:#fff; color:#DC2626; border:1.5px solid #DC2626; border-radius:8px; }}
[class*="st-key-rj_"] button:hover {{ background:#FEE2E2; color:#B91C1C; border-color:#B91C1C; }}
/* primary buttons */
button[kind="primary"] {{ background:{TEAL}; color:#fff; border:none; border-radius:10px;
  font-weight:700; padding: 0.5rem 1.2rem; }}
button[kind="primary"]:hover {{ background:#0F766E; color:#fff; }}
</style>
"""


def pill(text: str, kind: str) -> str:
    """Coloured status pill as HTML: kind is healthy / watch / at risk / blocked."""
    colour = PILLS[kind.lower()]
    icon = "🚫 " if kind.lower() == "blocked" else ""
    return f'<span class="qr-pill" style="background:{colour}">{icon}{text}</span>'


def band_pill(band: str) -> str:
    return pill(band, band)


def chrome(st) -> None:
    """Inject the shared CSS and brand bar. Call at the top of every page."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="qr-brand"><span class="name">QuarterReady</span>'
        '<span class="tag">AI practice agent for North East accountants</span>'
        '<span class="notice">SYNTHETIC – NOT REAL DATA</span></div>', unsafe_allow_html=True)

