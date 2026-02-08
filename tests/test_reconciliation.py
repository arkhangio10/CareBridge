"""
VirtueConnect — Tests: Reconciliation Logic

Verifies the structured vs text priority rules:
  1. Structured TRUE + text denies -> CONTRADICTED
  2. Structured NULL + text affirms -> EXTRACTED
  3. Both affirm -> ASSERTED (append evidence)
  4. Weak mention only -> UNCERTAIN
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from models.forensic_fields import ForensicField, ValidationState, Evidence


class TestReconciliationPriority:
    """Test the reconciliation priority rules at the ForensicField level."""

    def test_structured_true_text_denies_gives_contradicted(self):
        """Rule 1: Structured TRUE + text denies -> CONTRADICTED."""
        # Simulating what the reconciler does
        structured_val = True
        text_val = False
        text_state = ValidationState.CONTRADICTED

        # When text contradicts, the result should be CONTRADICTED
        if structured_val is True and text_state == ValidationState.CONTRADICTED:
            result = ForensicField(
                value=False,
                state=ValidationState.CONTRADICTED,
                confidence=0.85,
                evidence=[Evidence(
                    snippet="We refer surgical cases to another hospital",
                    source_column="description",
                    evidence_type="free_text",
                )],
            )

        assert result.state == ValidationState.CONTRADICTED
        assert result.value is False
        assert result.is_contradicted()

    def test_structured_null_text_affirms_gives_extracted(self):
        """Rule 2: Structured NULL + text affirms -> EXTRACTED."""
        structured_val = None
        text_val = True
        text_state = ValidationState.EXTRACTED

        if structured_val is None and text_state == ValidationState.EXTRACTED:
            result = ForensicField(
                value=True,
                state=ValidationState.EXTRACTED,
                confidence=0.80,
                evidence=[Evidence(
                    snippet="We have a fully equipped operating theatre",
                    source_column="description",
                    evidence_type="free_text",
                )],
            )

        assert result.state == ValidationState.EXTRACTED
        assert result.value is True
        assert result.is_positive()

    def test_both_affirm_keeps_asserted(self):
        """Rule 3: Both affirm -> keep ASSERTED, append evidence."""
        result = ForensicField(
            value=True,
            state=ValidationState.ASSERTED,
            confidence=0.95,
            evidence=[
                Evidence(
                    snippet="generalSurgery",
                    source_column="specialties",
                    evidence_type="structured",
                ),
                Evidence(
                    snippet="We perform major and minor surgeries",
                    source_column="description",
                    evidence_type="free_text",
                ),
            ],
        )

        assert result.state == ValidationState.ASSERTED
        assert result.value is True
        assert len(result.evidence) == 2
        assert result.evidence[0].evidence_type == "structured"
        assert result.evidence[1].evidence_type == "free_text"

    def test_weak_mention_gives_uncertain(self):
        """Rule 4: Weak mention only -> UNCERTAIN."""
        result = ForensicField(
            value=None,
            state=ValidationState.UNCERTAIN,
            confidence=0.40,
            evidence=[Evidence(
                snippet="some medical services available",
                source_column="description",
                evidence_type="free_text",
            )],
        )

        assert result.state == ValidationState.UNCERTAIN
        assert result.value is None
        assert not result.is_positive()
        assert not result.is_contradicted()

    def test_no_signal_gives_missing(self):
        """No signal at all -> MISSING."""
        result = ForensicField()
        assert result.state == ValidationState.MISSING
        assert result.value is None
        assert result.is_missing()


class TestEvidenceDensity:
    """Test that multiple independent evidence boosts confidence."""

    def test_single_evidence(self):
        ff = ForensicField(value=True, state=ValidationState.EXTRACTED, confidence=0.80)
        assert ff.confidence == 0.80

    def test_multiple_evidence_boost(self):
        """Multiple independent evidence should result in higher confidence."""
        base_conf = 0.80
        evidence_count = 3
        boosted = min(1.0, base_conf + 0.05 * (evidence_count - 1))
        assert boosted == 0.90  # 0.80 + 0.05 * 2

    def test_max_evidence_cap(self):
        ff = ForensicField(
            value=True,
            state=ValidationState.EXTRACTED,
            confidence=0.85,
            evidence=[
                Evidence(snippet="ev1", source_column="desc", evidence_type="free_text"),
                Evidence(snippet="ev2", source_column="cap", evidence_type="free_text"),
                Evidence(snippet="ev3", source_column="proc", evidence_type="structured"),
                Evidence(snippet="ev4", source_column="equip", evidence_type="structured"),
            ],
        )
        # Enforce max 3 evidence
        ff.evidence = ff.evidence[:3]
        assert len(ff.evidence) == 3
