"""
VirtueConnect — Negation & Referral Detection

Concept-specific negation: "refer trauma cases" negates trauma_surgery
but does NOT negate maternity capabilities.

Operates at sentence/window level.
"""

from __future__ import annotations

import re
from typing import List, Literal, Tuple

from models.forensic_fields import Polarity


# ---------------------------------------------------------------------------
# Lexicons
# ---------------------------------------------------------------------------

NEGATION_TERMS: List[str] = [
    "no",
    "not",
    "not available",
    "without",
    "lack",
    "lacks",
    "lacking",
    "don't",
    "doesn't",
    "does not",
    "do not",
    "unable to",
    "cannot",
    "can't",
    "never",
    "none",
    "absent",
    "unavailable",
    "not functioning",
    "out of service",
    "not operational",
    "non-functional",
    "closed",
]

REFERRAL_TERMS: List[str] = [
    "refer",
    "refers",
    "referred",
    "referral",
    "transfer",
    "transfers",
    "transferred",
    "send to",
    "sends to",
    "sent to",
    "redirect",
    "redirects",
    "redirected",
    "refer out",
    "referred out",
]

# Compiled patterns (longest-first)
_NEG_PATTERNS = [
    re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE)
    for t in sorted(NEGATION_TERMS, key=len, reverse=True)
]
_REF_PATTERNS = [
    re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE)
    for t in sorted(REFERRAL_TERMS, key=len, reverse=True)
]


# ---------------------------------------------------------------------------
# Sentence splitter (simple regex-based)
# ---------------------------------------------------------------------------

_SENT_RE = re.compile(r"(?<=[.!?;])\s+|(?<=\n)\s*")


def split_sentences(text: str) -> List[str]:
    """Split text into sentence-like chunks."""
    sents = _SENT_RE.split(text.strip())
    return [s.strip() for s in sents if s.strip()]


# ---------------------------------------------------------------------------
# Core polarity detection
# ---------------------------------------------------------------------------

def _has_negation(sentence: str) -> bool:
    """Check if any negation keyword appears in the sentence."""
    for pat in _NEG_PATTERNS:
        if pat.search(sentence):
            return True
    return False


def _has_referral(sentence: str) -> bool:
    """Check if any referral keyword appears in the sentence."""
    for pat in _REF_PATTERNS:
        if pat.search(sentence):
            return True
    return False


def detect_polarity(
    chunk: str,
    concept_term: str,
    window_chars: int = 200,
) -> Polarity:
    """
    Detect the polarity of a concept mention within a chunk of text.

    The concept_term should be the **matched text** (not the canonical name).
    Searches a character window around the mention for negation/referral cues.

    Returns:
        Polarity.AFFIRM     — positive mention, no negation/referral nearby
        Polarity.DENY       — negation keyword in the same window
        Polarity.REFER_OUT  — referral keyword in the same window
        Polarity.UNKNOWN    — concept not found in chunk
    """
    lower_chunk = chunk.lower()
    lower_concept = concept_term.lower()

    idx = lower_chunk.find(lower_concept)
    if idx == -1:
        return Polarity.UNKNOWN

    # Extract the window around the mention
    window_start = max(0, idx - window_chars)
    window_end = min(len(chunk), idx + len(concept_term) + window_chars)
    window = chunk[window_start:window_end]

    # Check referral first (takes priority over simple negation)
    if _has_referral(window):
        return Polarity.REFER_OUT

    if _has_negation(window):
        return Polarity.DENY

    return Polarity.AFFIRM


def detect_polarity_in_sentence(
    sentence: str,
    concept_term: str,
) -> Polarity:
    """
    Sentence-level polarity detection.
    Simpler variant: the entire sentence IS the window.
    """
    lower = sentence.lower()
    if concept_term.lower() not in lower:
        return Polarity.UNKNOWN

    if _has_referral(sentence):
        return Polarity.REFER_OUT
    if _has_negation(sentence):
        return Polarity.DENY
    return Polarity.AFFIRM


def analyze_chunks_for_concept(
    chunks: List[str],
    concept_term: str,
) -> List[Tuple[int, Polarity]]:
    """
    Analyze a list of chunks and return (chunk_index, polarity) for each
    chunk that mentions the concept.
    """
    results: List[Tuple[int, Polarity]] = []
    for i, chunk in enumerate(chunks):
        pol = detect_polarity_in_sentence(chunk, concept_term)
        if pol != Polarity.UNKNOWN:
            results.append((i, pol))
    return results
