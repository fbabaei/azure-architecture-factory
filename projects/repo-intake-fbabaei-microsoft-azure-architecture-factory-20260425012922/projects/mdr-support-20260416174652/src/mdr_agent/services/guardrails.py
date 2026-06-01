"""Conversation guardrails for compliance-focused chat routes."""
from __future__ import annotations

import re

# Simple fallback blocklist for obvious non-compliance requests.
OFF_TOPIC_PATTERNS: tuple[str, ...] = (
    r"\b(recipe|cooking|bake|restaurant)\b",
    r"\b(football|soccer|nba|cricket|sports score)\b",
    r"\b(movie|netflix|celebrity|gossip)\b",
    r"\b(weather|forecast)\b",
)

# Positive signals for compliance intent; the Q&A model still handles nuance.
COMPLIANCE_HINTS: tuple[str, ...] = (
    "mdr",
    "dac6",
    "hallmark",
    "intermediary",
    "relevant taxpayer",
    "main benefit",
    "reportable",
    "disclosure",
    "jurisdiction",
    "cross-border",
    "arrangement",
)


def is_off_topic(message: str) -> bool:
    text = message.strip().lower()
    if not text:
        return True

    if any(re.search(pattern, text) for pattern in OFF_TOPIC_PATTERNS):
        return True

    # If no clear compliance hint is present, treat pure small-talk as off-topic.
    if len(text.split()) <= 6 and not any(hint in text for hint in COMPLIANCE_HINTS):
        return True

    return False


def off_topic_reply() -> str:
    return (
        "I can only help with MDR/DAC6 compliance topics, such as hallmarks, "
        "reporting obligations, and arrangement drafting. "
        "Please ask a compliance-related question."
    )
