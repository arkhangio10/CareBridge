"""
VirtueConnect — Synonym Mapping & Regex Pattern Builder

Maps messy real-world terms (from CSVs, web scrapes, free text)
to canonical capability names.  Also builds compiled regex patterns
for fast scanning.
"""

from __future__ import annotations

import re
from typing import Dict, List, Pattern, Tuple

from ontology.ontology import CAPABILITY_NAMES


# ---------------------------------------------------------------------------
# Synonym -> Canonical mapping
# ---------------------------------------------------------------------------

SYNONYM_MAP: Dict[str, str] = {
    # --- Maternity ---------------------------------------------------------
    # c_section
    "caesarean": "c_section",
    "cesarean": "c_section",
    "c-section": "c_section",
    "c section": "c_section",
    "cs delivery": "c_section",
    "caesarean section": "c_section",
    "cesarean section": "c_section",
    "emergency caesarean": "c_section",

    # delivery_natural
    "natural delivery": "delivery_natural",
    "vaginal delivery": "delivery_natural",
    "normal delivery": "delivery_natural",
    "child delivery": "delivery_natural",
    "labour ward": "delivery_natural",
    "labor ward": "delivery_natural",
    "delivery room": "delivery_natural",
    "maternity services": "delivery_natural",
    "maternity care": "delivery_natural",
    "pregnancy and child birth": "delivery_natural",
    "obstetrics and gynecology services": "delivery_natural",
    "obstetrics and gynecology": "delivery_natural",
    "obstetrics & gynecology": "delivery_natural",

    # ultrasound_ob
    "ultrasound": "ultrasound_ob",
    "ultrasound scan": "ultrasound_ob",
    "ultrasound scanning": "ultrasound_ob",
    "usg": "ultrasound_ob",
    "sonography": "ultrasound_ob",
    "sonogram": "ultrasound_ob",
    "scan": "ultrasound_ob",
    "eco": "ultrasound_ob",
    "obstetric ultrasound": "ultrasound_ob",
    "ob ultrasound": "ultrasound_ob",

    # incubator
    "incubator": "incubator",
    "neonatal incubator": "incubator",
    "nicu": "incubator",
    "neonatal intensive care": "incubator",
    "newborn care": "incubator",

    # blood_bank
    "blood bank": "blood_bank",
    "blood supply": "blood_bank",
    "blood transfusion": "blood_bank",
    "blood storage": "blood_bank",

    # blood_bank FALSE indicators (special: suffix _FALSE)
    "donors required": "blood_bank_FALSE",
    "family replacement": "blood_bank_FALSE",
    "no blood": "blood_bank_FALSE",
    "no stocks": "blood_bank_FALSE",
    "blood not available": "blood_bank_FALSE",

    # anesthesia
    "anesthesia": "anesthesia",
    "anaesthesia": "anesthesia",
    "anesthetic": "anesthesia",
    "anaesthetic": "anesthesia",
    "general anesthesia": "anesthesia",
    "spinal anesthesia": "anesthesia",

    # anesthetist
    "anesthetist": "anesthetist",
    "anaesthetist": "anesthetist",
    "anesthesiologist": "anesthetist",
    "anaesthesiologist": "anesthetist",
    "nurse anesthetist": "anesthetist",
    "crna": "anesthetist",

    # operating_room
    "operating theatre": "operating_room",
    "operative theatre": "operating_room",
    "major theatre": "operating_room",
    "ultra-modern theatre": "operating_room",
    "ultra modern theatre": "operating_room",
    "surgical suite": "operating_room",
    "operating room": "operating_room",
    "major surgery": "operating_room",
    "major surgeries": "operating_room",
    "major and minor surgeries": "operating_room",

    # minor_theatre (does NOT map to operating_room)
    "minor theatre": "minor_theatre",
    "minor surgery": "minor_theatre",
    "minor procedures": "minor_theatre",

    # --- Trauma / Surgery --------------------------------------------------
    # trauma_surgery
    "trauma surgery": "trauma_surgery",
    "trauma care": "trauma_surgery",
    "emergency surgery": "trauma_surgery",

    # general_surgery
    "general surgery": "general_surgery",
    "surgical procedures": "general_surgery",
    "surgery department": "general_surgery",
    "surgical services": "general_surgery",

    # xray
    "x-ray": "xray",
    "x ray": "xray",
    "xray": "xray",
    "radiography": "xray",
    "diagnostic imaging": "xray",
    "radiology": "xray",
    "x-ray imaging": "xray",

    # ambulance
    "ambulance": "ambulance",
    "emergency transport": "ambulance",
    "patient transport": "ambulance",

    # emergency_24_7
    "24/7": "emergency_24_7",
    "24 hours": "emergency_24_7",
    "24-hour": "emergency_24_7",
    "24hr": "emergency_24_7",
    "24 hr": "emergency_24_7",
    "always open": "emergency_24_7",
    "round the clock": "emergency_24_7",
    "around the clock": "emergency_24_7",
    "24-hour emergency": "emergency_24_7",
    "emergency department": "emergency_24_7",

    # --- Infrastructure ----------------------------------------------------
    # oxygen_supply
    "oxygen": "oxygen_supply",
    "oxygen supply": "oxygen_supply",
    "medical oxygen": "oxygen_supply",
    "oxygen concentrator": "oxygen_supply",
    "oxygen plant": "oxygen_supply",

    # generator_backup
    "generator": "generator_backup",
    "backup generator": "generator_backup",
    "standby generator": "generator_backup",
    "power backup": "generator_backup",

    # water_supply
    "water supply": "water_supply",
    "clean water": "water_supply",
    "running water": "water_supply",
    "borehole": "water_supply",

    # lab_basic
    "laboratory": "lab_basic",
    "lab": "lab_basic",
    "laboratory services": "lab_basic",
    "laboratory testing": "lab_basic",
    "lab services": "lab_basic",
    "diagnostic lab": "lab_basic",
    "on-site laboratory": "lab_basic",
    "in-house laboratory": "lab_basic",

    # pharmacy
    "pharmacy": "pharmacy",
    "dispensary": "pharmacy",
    "on-site pharmacy": "pharmacy",
    "in-house pharmacy": "pharmacy",
    "pharmacy services": "pharmacy",
    "drug dispensing": "pharmacy",
    "dispensing drugs": "pharmacy",
    "24 / 7 dispensary": "pharmacy",
    "dispensary for all types of medications": "pharmacy",

    # Additional Ghana-specific terms found in the data
    "conducts investigations": "lab_basic",
    "laboratory test": "lab_basic",
    "laboratory tests": "lab_basic",
    "lab test": "lab_basic",
    "lab tests": "lab_basic",
    "performs laboratory testing": "lab_basic",
    "in-house laboratory services": "lab_basic",
    "on-site laboratory facilities": "lab_basic",
    "provides laboratory services": "lab_basic",

    "electrocardiogram": "lab_basic",
    "ecg": "lab_basic",

    "obstetrics and gynecology": "delivery_natural",
    "obs and gynae": "delivery_natural",
    "child welfare": "delivery_natural",
    "child welfare clinic": "delivery_natural",
    "maternity home": "delivery_natural",
    "maternity": "delivery_natural",
    "maternity clinic": "delivery_natural",
    "antenatal": "delivery_natural",
    "antenatal care": "delivery_natural",
    "postnatal": "delivery_natural",

    "dialysis": "lab_basic",
    "dialysis center": "lab_basic",

    "emergency department": "emergency_24_7",
    "24-hour emergency services": "emergency_24_7",
    "24-hour emergency department": "emergency_24_7",
    "provides 24-hour": "emergency_24_7",
    "24 hr services": "emergency_24_7",
    "operates 24/7": "emergency_24_7",
    "open 24 hours": "emergency_24_7",

    "surgical suite": "operating_room",
    "theatre for major": "operating_room",
    "ultra modern theatre for major and minor surgeries": "operating_room",

    "provides ultrasound scanning": "ultrasound_ob",
    "ultrasound scans": "ultrasound_ob",
    "performs ultrasound scans": "ultrasound_ob",
    "usg and ecg services": "ultrasound_ob",

    "provides x-ray imaging": "xray",
    "provides x-ray": "xray",
    "x-ray imaging": "xray",
}


# ---------------------------------------------------------------------------
# Specialty -> Capability mapping (for the 'specialties' JSON array column)
# ---------------------------------------------------------------------------

SPECIALTY_TO_CAPABILITIES: Dict[str, List[str]] = {
    # Maternity
    "gynecologyAndObstetrics": ["delivery_natural"],
    "obstetricsAndMaternityCare": ["delivery_natural"],
    "maternalFetalMedicineOrPerinatology": ["delivery_natural"],
    "reproductiveEndocrinologyAndInfertility": ["delivery_natural"],

    # Surgery
    "generalSurgery": ["general_surgery"],
    "orthopedicSurgery": ["general_surgery"],
    "urology": ["general_surgery"],
    "hepatopancreatobiliarySurgery": ["general_surgery"],
    "gynecologicalOncology": ["general_surgery"],
    "cataractAndAnteriorSegmentSurgery": [],
    "oculoplasticsAndReconstructiveOrbitalSurgery": [],

    # Emergency / Trauma
    "emergencyMedicine": ["emergency_24_7"],

    # Radiology / Imaging
    "diagnosticRadiology": ["xray"],
    "radiology": ["xray"],

    # Pathology / Lab
    "pathology": ["lab_basic"],
    "clinicalPathology": ["lab_basic"],

    # Others (tracked but not direct capabilities)
    "ophthalmology": [],
    "pediatrics": [],
    "internalMedicine": [],
    "dentistry": [],
    "psychiatry": [],
    "dermatology": [],
    "cardiology": [],
    "nephrology": [],
    "otolaryngology": [],
    "dietetics": [],
    "clinicalPsychology": [],
    "sportsMedicinePMR": [],
    "physicalMedicineAndRehabilitation": [],
    "addictionPsychiatry": [],
    "communityAndPublicPsychiatry": [],
    "publicHealth": [],
    "socialAndBehavioralSciences": [],
    "globalHealthAndInternationalHealth": [],
    "infectiousDiseases": [],
    "hospiceAndPalliativeInternalMedicine": [],
    "medicalOncology": [],
    "retinaAndVitreoretinalOphthalmology": [],
    "glaucomaOphthalmology": [],
    "corneaOphthalmology": [],
    "refractiveSurgeryOphthalmology": [],
    "eyeTraumaAndEmergencyEyeCare": [],
}


# ---------------------------------------------------------------------------
# Compiled Regex Patterns (for fast text scanning)
# ---------------------------------------------------------------------------

def _build_regex_patterns() -> List[Tuple[Pattern, str]]:
    """
    Build compiled regex patterns sorted longest-first to avoid
    partial matches (e.g., 'minor theatre' before 'theatre').
    Returns list of (compiled_pattern, canonical_name).
    """
    # Sort by length descending so longer patterns match first
    sorted_terms = sorted(SYNONYM_MAP.keys(), key=len, reverse=True)
    patterns: List[Tuple[Pattern, str]] = []
    for term in sorted_terms:
        canonical = SYNONYM_MAP[term]
        # Word-boundary regex, case-insensitive
        pat = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        patterns.append((pat, canonical))
    return patterns


COMPILED_PATTERNS: List[Tuple[Pattern, str]] = _build_regex_patterns()


def find_concepts_in_text(text: str) -> List[Tuple[str, str, int, int]]:
    """
    Scan text for all synonym matches.

    Returns list of (canonical_name, matched_term, start, end).
    """
    results: List[Tuple[str, str, int, int]] = []
    seen_spans: set = set()

    for pattern, canonical in COMPILED_PATTERNS:
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            # Skip overlapping matches
            if any(s <= span[0] < e or s < span[1] <= e for s, e in seen_spans):
                continue
            seen_spans.add(span)
            results.append((canonical, match.group(), span[0], span[1]))

    return sorted(results, key=lambda x: x[2])


def normalize_term(term: str) -> str | None:
    """Normalize a single term to its canonical name, or None if unknown."""
    lower = term.strip().lower()
    return SYNONYM_MAP.get(lower)
