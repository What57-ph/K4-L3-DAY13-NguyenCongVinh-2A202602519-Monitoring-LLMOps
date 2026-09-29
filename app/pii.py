from __future__ import annotations

import hashlib
import re

PII_PATTERNS: dict[str, str] = {
    "email": r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
    # Vietnamese mobile numbers, both domestic and +84/0084 forms, with
    # common separators. The card detector runs first to avoid partial matches.
    "phone_vn": r"(?<!\d)(?:(?:\+84|0084)[ .-]?0?[135789](?:[ .-]?\d){8}|0[135789](?:[ .-]?\d){8})(?!\d)",
    "cccd": r"(?<!\d)\d{12}(?!\d)",
    "credit_card": r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)",
}


def scrub_text(text: str) -> str:
    safe = text
    # Redact longer numeric identifiers before shorter phone/CCCD matches.
    for name in ("email", "credit_card", "cccd", "phone_vn"):
        pattern = PII_PATTERNS[name]
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
