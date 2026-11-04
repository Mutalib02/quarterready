"""Save/replay Claude responses so the demo works offline.

Key = sha256 of (model, prompt version, canonical input). Cached files are committed: they
contain only synthetic data.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"
RECORDED_DIR = Path(__file__).resolve().parents[1] / "recorded"
PROMPT_VERSION = "v1"


class CacheMiss(Exception):
    """Offline mode and nothing cached for this request."""


def make_key(model: str, payload: dict, version: str = PROMPT_VERSION) -> str:
    blob = json.dumps({"m": model, "v": version, "p": payload}, sort_keys=True,
                      ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def get(key: str, directory: Path | None = None) -> dict | None:
    path = (directory or CACHE_DIR) / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def put(key: str, response: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(
        json.dumps(response, indent=1, ensure_ascii=False), encoding="utf-8")
