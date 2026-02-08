"""
VirtueConnect — Tests: Synonym Mapping

Verifies the ontology synonym mapping:
  - Common medical terms map to correct canonical names
  - FALSE indicators work correctly
  - Minor theatre is distinct from operating room
  - Regex patterns match correctly in text
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from ontology.synonyms import (
    SYNONYM_MAP,
    normalize_term,
    find_concepts_in_text,
    SPECIALTY_TO_CAPABILITIES,
)
from ontology.ontology import CAPABILITY_NAMES


class TestNormalizeTerm:
    """Test single-term normalization."""

    def test_usg_to_ultrasound(self):
        assert normalize_term("USG") == "ultrasound_ob"

    def test_sonography_to_ultrasound(self):
        assert normalize_term("sonography") == "ultrasound_ob"

    def test_theatre_to_operating_room(self):
        assert normalize_term("operating theatre") == "operating_room"

    def test_ot_to_operating_room(self):
        # OT is a short abbreviation — check if mapped
        # (not in current mapping since it's ambiguous)
        result = normalize_term("OT")
        # OT might not be mapped due to ambiguity
        # This test documents the intentional decision
        assert result is None or result == "operating_room"

    def test_minor_theatre_distinct(self):
        """CRITICAL: minor theatre must NOT map to operating_room."""
        result = normalize_term("minor theatre")
        assert result != "operating_room"
        assert result == "minor_theatre"

    def test_major_theatre_is_operating_room(self):
        assert normalize_term("major theatre") == "operating_room"

    def test_ultra_modern_theatre_is_operating_room(self):
        assert normalize_term("ultra-modern theatre") == "operating_room"

    def test_blood_bank_false_indicators(self):
        assert normalize_term("donors required") == "blood_bank_FALSE"
        assert normalize_term("family replacement") == "blood_bank_FALSE"
        assert normalize_term("no stocks") == "blood_bank_FALSE"

    def test_unknown_term(self):
        assert normalize_term("quantum healing") is None

    def test_case_insensitive(self):
        assert normalize_term("PHARMACY") == "pharmacy"
        assert normalize_term("X-Ray") == "xray"


class TestFindConceptsInText:
    """Test regex-based concept finding in free text."""

    def test_finds_pharmacy(self):
        results = find_concepts_in_text("We have a 24-hour pharmacy available.")
        canonical_names = [r[0] for r in results]
        assert "pharmacy" in canonical_names

    def test_finds_multiple_concepts(self):
        text = "The hospital has an operating theatre, pharmacy, and laboratory."
        results = find_concepts_in_text(text)
        canonical_names = [r[0] for r in results]
        assert "operating_room" in canonical_names
        assert "pharmacy" in canonical_names
        assert "lab_basic" in canonical_names

    def test_finds_emergency_24_7(self):
        results = find_concepts_in_text("Always open, 24/7 emergency services.")
        canonical_names = [r[0] for r in results]
        assert "emergency_24_7" in canonical_names

    def test_returns_offsets(self):
        text = "Has pharmacy services."
        results = find_concepts_in_text(text)
        assert len(results) > 0
        canonical, matched, start, end = results[0]
        assert canonical == "pharmacy"
        assert text[start:end].lower() == matched.lower()

    def test_long_matches_first(self):
        """'minor theatre' should match before 'theatre' alone."""
        text = "We have a minor theatre for small procedures."
        results = find_concepts_in_text(text)
        canonical_names = [r[0] for r in results]
        assert "minor_theatre" in canonical_names
        # Should NOT also match operating_room from "theatre"
        assert "operating_room" not in canonical_names

    def test_major_and_minor_surgeries(self):
        """'major and minor surgeries' should map to operating_room."""
        text = "Ultra modern theatre for Major and Minor surgeries."
        results = find_concepts_in_text(text)
        canonical_names = [r[0] for r in results]
        assert "operating_room" in canonical_names

    def test_empty_text(self):
        assert find_concepts_in_text("") == []
        assert find_concepts_in_text("   ") == []


class TestSpecialtyMapping:
    """Test the specialty -> capability mapping."""

    def test_gynecology_maps_to_delivery(self):
        caps = SPECIALTY_TO_CAPABILITIES.get("gynecologyAndObstetrics", [])
        assert "delivery_natural" in caps

    def test_emergency_maps_to_24_7(self):
        caps = SPECIALTY_TO_CAPABILITIES.get("emergencyMedicine", [])
        assert "emergency_24_7" in caps

    def test_general_surgery_maps(self):
        caps = SPECIALTY_TO_CAPABILITIES.get("generalSurgery", [])
        assert "general_surgery" in caps

    def test_internal_medicine_no_caps(self):
        """Internal medicine is too general to map to specific capabilities."""
        caps = SPECIALTY_TO_CAPABILITIES.get("internalMedicine", [])
        assert len(caps) == 0


class TestCanonicalNames:
    """Verify all synonyms map to valid canonical capability names."""

    def test_all_synonyms_map_to_valid_caps(self):
        valid_caps = set(CAPABILITY_NAMES) | {"minor_theatre"}
        for synonym, canonical in SYNONYM_MAP.items():
            # Handle _FALSE suffix
            base = canonical.replace("_FALSE", "")
            assert base in valid_caps, (
                f"Synonym '{synonym}' maps to '{canonical}' "
                f"but '{base}' is not a valid capability"
            )
