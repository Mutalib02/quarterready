"""Shared Streamlit bits: the engine/mode picker used on every AI page."""
from __future__ import annotations

import os

from qr import cache

LIVE = "Live (cache first, Claude on a miss)"
OFFLINE = "Offline (replay cache)"
LOCAL = "Local engine (no API – rule-based, not Claude)"


def pick_mode(st, key: str = "mode") -> tuple[bool, bool]:
    """Returns (offline, local). Defaults: Live with a key, else Offline if a cache exists,
    else the local engine."""
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_cache = any(cache.CACHE_DIR.glob("*.json"))
    default = LIVE if has_key else (OFFLINE if has_cache else LOCAL)
    options = [LIVE, OFFLINE, LOCAL]
    mode = st.radio("Engine", options, index=options.index(default), horizontal=True, key=key)
    if mode == LIVE and not has_key:
        st.warning("No ANTHROPIC_API_KEY found. Add one to .env, or use another engine.")
    if mode == LOCAL:
        st.info("🔧 Local engine: keyword rules and templates, **not Claude**. Same tools, "
                "gates and approval queue; weaker judgement. Nothing is cached.")
    ready = mode != LIVE or has_key
    st.session_state["_engine_ready"] = ready
    return mode == OFFLINE, mode == LOCAL
