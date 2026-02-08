"""
VirtueConnect — Tests: Clinical Bundle Validation

Verifies that the bundle validator correctly:
  - Flags facilities claiming C-section without operating room
  - Flags trauma centers without blood bank
  - Does NOT flag when requirements are met
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from models.forensic_fields import ForensicField, ValidationState, Evidence
from models.capability_models import (
    MaternityCapability,
    TraumaCapability,
    InfraCapability,
)
from models.bundle_rules import BundleValidator, BundleDef


_BUNDLES_PATH = Path(__file__).resolve().parent.parent / "configs" / "bundles.yaml"


def _make_ff(value: bool, state: ValidationState = ValidationState.EXTRACTED) -> ForensicField:
    """Helper to create a ForensicField."""
    return ForensicField(value=value, state=state, confidence=0.9)


def _missing() -> ForensicField:
    return ForensicField(value=None, state=ValidationState.MISSING, confidence=0.0)


class TestCsectionSafeBundle:
    """Test the c_section_safe bundle rule."""

    def setup_method(self):
        self.validator = BundleValidator(_BUNDLES_PATH)

    def test_safe_csection_no_anomaly(self):
        """C-section + OR + anesthetist -> no anomaly."""
        mat = MaternityCapability(
            c_section=_make_ff(True, ValidationState.ASSERTED),
            operating_room=_make_ff(True),
            anesthetist=_make_ff(True),
        )
        trauma = TraumaCapability()
        infra = InfraCapability()

        anomalies = self.validator.validate("fac-1", mat, trauma, infra)
        csection_anomalies = [a for a in anomalies if a.bundle_name == "c_section_safe"]
        assert len(csection_anomalies) == 0

    def test_csection_without_or_flags_anomaly(self):
        """C-section claimed but no operating room -> ANOMALY_HIGH."""
        mat = MaternityCapability(
            c_section=_make_ff(True, ValidationState.EXTRACTED),
            operating_room=_missing(),
            anesthetist=_make_ff(True),
        )
        trauma = TraumaCapability()
        infra = InfraCapability()

        anomalies = self.validator.validate("fac-2", mat, trauma, infra)
        csection_anomalies = [a for a in anomalies if a.bundle_name == "c_section_safe"]
        assert len(csection_anomalies) == 1
        assert csection_anomalies[0].anomaly_type == "ANOMALY_HIGH"
        assert "operating_room" in csection_anomalies[0].required_missing

    def test_csection_without_anesthesia_flags_anomaly(self):
        """C-section + OR but no anesthesia/anesthetist -> ANOMALY_HIGH."""
        mat = MaternityCapability(
            c_section=_make_ff(True),
            operating_room=_make_ff(True),
            anesthesia=_missing(),
            anesthetist=_missing(),
        )
        trauma = TraumaCapability()
        infra = InfraCapability()

        anomalies = self.validator.validate("fac-3", mat, trauma, infra)
        csection_anomalies = [a for a in anomalies if a.bundle_name == "c_section_safe"]
        assert len(csection_anomalies) == 1
        assert "one_of(anesthesia,anesthetist)" in csection_anomalies[0].required_missing

    def test_no_csection_claim_no_validation(self):
        """If c_section is not claimed, bundle should not trigger."""
        mat = MaternityCapability(
            c_section=_missing(),
        )
        trauma = TraumaCapability()
        infra = InfraCapability()

        anomalies = self.validator.validate("fac-4", mat, trauma, infra)
        csection_anomalies = [a for a in anomalies if a.bundle_name == "c_section_safe"]
        assert len(csection_anomalies) == 0


class TestTraumaBundle:
    """Test the trauma_bundle rule."""

    def setup_method(self):
        self.validator = BundleValidator(_BUNDLES_PATH)

    def test_full_trauma_no_anomaly(self):
        mat = MaternityCapability()
        trauma = TraumaCapability(
            trauma_surgery=_make_ff(True),
            xray=_make_ff(True),
        )
        infra = InfraCapability()
        # blood_bank is in maternity model
        mat.blood_bank = _make_ff(True)

        anomalies = self.validator.validate("fac-5", mat, trauma, infra)
        trauma_anomalies = [a for a in anomalies if a.bundle_name == "trauma_bundle"]
        assert len(trauma_anomalies) == 0

    def test_trauma_without_blood_bank(self):
        mat = MaternityCapability(blood_bank=_missing())
        trauma = TraumaCapability(
            trauma_surgery=_make_ff(True),
            xray=_make_ff(True),
        )
        infra = InfraCapability()

        anomalies = self.validator.validate("fac-6", mat, trauma, infra)
        trauma_anomalies = [a for a in anomalies if a.bundle_name == "trauma_bundle"]
        assert len(trauma_anomalies) == 1
        assert trauma_anomalies[0].anomaly_type == "RISK_HIGH"

    def test_no_trauma_claim_no_trigger(self):
        mat = MaternityCapability()
        trauma = TraumaCapability(trauma_surgery=_missing())
        infra = InfraCapability()

        anomalies = self.validator.validate("fac-7", mat, trauma, infra)
        trauma_anomalies = [a for a in anomalies if a.bundle_name == "trauma_bundle"]
        assert len(trauma_anomalies) == 0


class TestBundleLoading:
    """Test that bundles.yaml loads correctly."""

    def test_loads_all_bundles(self):
        validator = BundleValidator(_BUNDLES_PATH)
        assert len(validator.bundles) >= 5  # we defined 6 bundles
        assert "c_section_safe" in validator.bundles
        assert "trauma_bundle" in validator.bundles
        assert "referral_only" in validator.bundles
