"""Strip personal identifiers before text goes to the AI. Names become placeholders and are
restored in the reply, so the model never sees real names (here: synthetic ones)."""
from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\b\d{2}-\d{2}-\d{2}\b"), "[SORT_CODE]"),
    (re.compile(r"\b\d{8}\b"), "[ACCOUNT_NO]"),
    (re.compile(r"(?<!\w)(?:\+44\s?|0)\d{3,4}[\s-]?\d{3}[\s-]?\d{3,4}\b"), "[PHONE]"),
]


class Redactor:
    """Reversible redaction for one prompt: names -> [NAME_n], patterns -> tags."""

    def __init__(self, names: list[str] | None = None) -> None:
        self.mapping: dict[str, str] = {}
        self._n = 0
        for n in names or []:
            self.add_name(n)

    @staticmethod
    def clean_name(name: str) -> str:
        return re.sub(r"\s*\(fictional\)", "", name).strip()

    def add_name(self, name: str, person: bool = True) -> None:
        """Register a name. First names are only redacted for people, not companies."""
        full = self.clean_name(name)
        if not full or full in self.mapping:
            return
        self._n += 1
        self.mapping[full] = f"[NAME_{self._n}]"
        if person:
            self.mapping.setdefault(full.split()[0], f"[FIRST_{self._n}]")

    def redact(self, text: str) -> str:
        text = re.sub(r"\s*\(fictional\)", "", text or "")
        for real, tag in sorted(self.mapping.items(), key=lambda kv: -len(kv[0])):
            text = re.sub(re.escape(real), tag, text)
        for pat, tag in _PATTERNS:
            text = pat.sub(tag, text)
        return text

    def restore(self, text: str) -> str:
        for real, tag in self.mapping.items():
            text = text.replace(tag, real)
        return text
