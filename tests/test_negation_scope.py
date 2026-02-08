"""
VirtueConnect — Tests: Negation Scope

Verifies that concept-specific negation works correctly:
  - "refer trauma cases" negates trauma but NOT maternity
  - "no blood bank" negates blood_bank but not other caps
  - Window/sentence boundary is respected
"""

import sys
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from models.forensic_fields import Polarity
from ontology.negation import (
    detect_polarity,
    detect_polarity_in_sentence,
    split_sentences,
    analyze_chunks_for_concept,
)


class TestNegationDetection:
    """Test basic negation keyword detection."""

    def test_simple_negation(self):
        pol = detect_polarity_in_sentence(
            "No blood bank available at this facility.",
            "blood bank",
        )
        assert pol == Polarity.DENY

    def test_not_available(self):
        pol = detect_polarity_in_sentence(
            "X-ray is not available.",
            "X-ray",
        )
        assert pol == Polarity.DENY

    def test_without(self):
        pol = detect_polarity_in_sentence(
            "The facility operates without an operating theatre.",
            "operating theatre",
        )
        assert pol == Polarity.DENY

    def test_affirmation(self):
        pol = detect_polarity_in_sentence(
            "The hospital has a fully equipped operating theatre.",
            "operating theatre",
        )
        assert pol == Polarity.AFFIRM

    def test_concept_not_found(self):
        pol = detect_polarity_in_sentence(
            "The hospital has a pharmacy.",
            "operating theatre",
        )
        assert pol == Polarity.UNKNOWN


class TestReferralDetection:
    """Test that referral keywords produce REFER_OUT polarity."""

    def test_refer_trauma(self):
        pol = detect_polarity_in_sentence(
            "We refer trauma cases to the regional hospital.",
            "trauma",
        )
        assert pol == Polarity.REFER_OUT

    def test_transfer_emergency(self):
        pol = detect_polarity_in_sentence(
            "Emergency cases are transferred to the district hospital.",
            "Emergency",
        )
        assert pol == Polarity.REFER_OUT

    def test_send_to(self):
        pol = detect_polarity_in_sentence(
            "Complex surgeries are sent to Korle Bu Teaching Hospital.",
            "surgeries",
        )
        assert pol == Polarity.REFER_OUT


class TestConceptSpecificNegation:
    """
    CRITICAL: Verify that negation/referral is concept-specific.
    "Refer trauma" should NOT negate maternity capabilities.
    """

    def test_refer_trauma_does_not_negate_maternity(self):
        text = "We refer trauma cases to regional hospital."

        # Trauma should be REFER_OUT
        pol_trauma = detect_polarity_in_sentence(text, "trauma")
        assert pol_trauma == Polarity.REFER_OUT

        # "maternity" is not in this sentence -> UNKNOWN (not negated)
        pol_maternity = detect_polarity_in_sentence(text, "maternity")
        assert pol_maternity == Polarity.UNKNOWN

    def test_no_blood_does_not_negate_pharmacy(self):
        text = "No blood bank. We have a 24-hour pharmacy."
        sentences = split_sentences(text)

        # Blood bank mention in first sentence -> DENY
        pol_blood = detect_polarity_in_sentence(sentences[0], "blood bank")
        assert pol_blood == Polarity.DENY

        # Pharmacy mention in second sentence -> AFFIRM
        pol_pharmacy = detect_polarity_in_sentence(sentences[1], "pharmacy")
        assert pol_pharmacy == Polarity.AFFIRM

    def test_multi_chunk_independence(self):
        chunks = [
            "We transfer emergency surgical cases.",
            "We have a well-equipped maternity ward.",
            "24/7 pharmacy services available.",
        ]

        results = analyze_chunks_for_concept(chunks, "surgical")
        assert len(results) == 1
        assert results[0][1] == Polarity.REFER_OUT

        results_maternity = analyze_chunks_for_concept(chunks, "maternity")
        assert len(results_maternity) == 1
        assert results_maternity[0][1] == Polarity.AFFIRM


class TestSentenceSplitting:
    """Test the regex sentence splitter."""

    def test_basic_split(self):
        text = "First sentence. Second sentence. Third."
        sents = split_sentences(text)
        assert len(sents) == 3

    def test_semicolon_split(self):
        text = "Has pharmacy; no blood bank"
        sents = split_sentences(text)
        assert len(sents) == 2

    def test_newline_split(self):
        text = "Line one\nLine two\nLine three"
        sents = split_sentences(text)
        assert len(sents) == 3


class TestWindowedPolarity:
    """Test the windowed polarity detection (character window)."""

    def test_window_nearby_negation(self):
        text = "This clinic does not have an operating theatre but has a pharmacy."
        pol = detect_polarity(text, "operating theatre", window_chars=50)
        assert pol == Polarity.DENY

    def test_window_far_negation_still_catches(self):
        # With large window, should still catch
        text = "The facility does not offer ultrasound services for pregnant women."
        pol = detect_polarity(text, "ultrasound", window_chars=200)
        assert pol == Polarity.DENY
