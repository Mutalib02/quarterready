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
    default = (LIVE if has_key else RECORDED if has_recorded else OFFLINE if has_cache
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
