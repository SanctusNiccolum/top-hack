"""PII-scrubbing.

Applied to every collected message before it goes into the output JSON, so
that raw phone numbers / emails / @-mentions of third parties never leave
the machine, regardless of how short or long the message is.
"""
from __future__ import annotations

import re

# Email addresses, matched and removed as a single token. This must run
# BEFORE the mention regex below: without it, "test@mail.ru" only has its
# "@mail" part eaten by the mention pattern, leaving a mangled, half-PII
# remainder like "test.ru" in the cleaned text instead of a clean removal.
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b")

# Telegram usernames/mentions: @ followed by 3-32 word characters.
_MENTION_RE = re.compile(r"@\w{3,32}")

# Heuristic phone-number matcher: 7+ digits, optionally grouped with
# spaces / dashes / parentheses / a leading "+". This is intentionally
# permissive rather than a strict E.164 parser — false positives (rare;
# would strip some other long digit sequence) are an acceptable trade-off
# against false negatives (a real phone number slipping through).
_PHONE_CANDIDATE_RE = re.compile(r"(?<!\w)(\+?\d[\d\-\s()]{6,}\d)(?!\w)")

_WHITESPACE_RE = re.compile(r"\s+")


def _looks_like_phone(candidate: str) -> bool:
    """Decide whether a digit-ish candidate span is actually a phone number.

    Plain digit runs with no grouping (no space/dash/parens) are ambiguous:
    an 8-digit run is just as likely to be a DDMMYYYY date, an order/ticket
    number, or a short internal ID as a phone number typed with zero
    formatting. Requiring 10+ digits for the no-separator case targets the
    lengths that are actually phone-shaped (RU mobile = 11 digits, E.164 up
    to 15) while leaving shorter unformatted numbers -- the false positives
    seen in practice (dates, order numbers) -- untouched. Numbers that DO
    contain a separator keep the original permissive rule, since deliberate
    grouping is itself a strong signal of a real phone number.
    """
    has_separator = any(c in "-() " for c in candidate)
    if has_separator:
        return True
    digits = re.sub(r"\D", "", candidate)
    return len(digits) >= 10


def clean_message_text(text: str | None) -> str | None:
    """Scrub PII from a message's text.

    Returns the cleaned text, or ``None`` only if there was no text at all
    to begin with (e.g. a bare sticker with no caption). Unlike an earlier
    version of this function, messages are no longer dropped for being
    short — every actual message the user wrote is kept, just PII-scrubbed.
    """
    if not text:
        return None

    cleaned = _EMAIL_RE.sub("", text)
    cleaned = _MENTION_RE.sub("", cleaned)
    cleaned = _PHONE_CANDIDATE_RE.sub(
        lambda m: "" if _looks_like_phone(m.group(1)) else m.group(0),
        cleaned,
    )
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()

    return cleaned or None
