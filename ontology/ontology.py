"""
VirtueConnect — Capability Catalog (Ontology)

Defines the canonical set of capabilities that VirtueConnect tracks,
organised into domain categories.  Each capability has a description
and differentiation notes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class CapabilityCategory(str, Enum):
    MATERNITY = "maternity"
    TRAUMA = "trauma"
    INFRASTRUCTURE = "infrastructure"


@dataclass(frozen=True)
class CapabilityDef:
    """Definition of a single canonical capability."""
    canonical_name: str
    category: CapabilityCategory
    description: str
    differentiation_notes: str = ""


# ---------------------------------------------------------------------------
# Canonical Capability Catalog
# ---------------------------------------------------------------------------

CAPABILITY_CATALOG: Dict[str, CapabilityDef] = {
    # -- Maternity ----------------------------------------------------------
    "c_section": CapabilityDef(
        canonical_name="c_section",
        category=CapabilityCategory.MATERNITY,
        description="Ability to perform caesarean section surgery.",
        differentiation_notes="Must have operating room + anesthesia to be safe.",
    ),
    "delivery_natural": CapabilityDef(
        canonical_name="delivery_natural",
        category=CapabilityCategory.MATERNITY,
        description="Ability to assist normal / natural vaginal delivery.",
    ),
    "ultrasound_ob": CapabilityDef(
        canonical_name="ultrasound_ob",
        category=CapabilityCategory.MATERNITY,
        description="Obstetric ultrasound capability (USG / sonography).",
        differentiation_notes="General ultrasound also counts if used for OB.",
    ),
    "incubator": CapabilityDef(
        canonical_name="incubator",
        category=CapabilityCategory.MATERNITY,
        description="Neonatal incubator available.",
    ),
    "blood_bank": CapabilityDef(
        canonical_name="blood_bank",
        category=CapabilityCategory.MATERNITY,
        description="On-site blood bank or reliable blood supply.",
        differentiation_notes=(
            "'Donors required' / 'family replacement' indicates NO blood bank."
        ),
    ),
    "anesthesia": CapabilityDef(
        canonical_name="anesthesia",
        category=CapabilityCategory.MATERNITY,
        description="Anesthesia capability / equipment available.",
    ),
    "anesthetist": CapabilityDef(
        canonical_name="anesthetist",
        category=CapabilityCategory.MATERNITY,
        description="Trained anesthetist on staff.",
    ),
    "operating_room": CapabilityDef(
        canonical_name="operating_room",
        category=CapabilityCategory.MATERNITY,
        description="Major operating theatre / surgical suite.",
        differentiation_notes=(
            "'Minor theatre' does NOT qualify as operating_room. "
            "Only 'major theatre', 'operative theatre', 'ultra-modern theatre' qualify."
        ),
    ),

    # -- Trauma / Surgery ---------------------------------------------------
    "trauma_surgery": CapabilityDef(
        canonical_name="trauma_surgery",
        category=CapabilityCategory.TRAUMA,
        description="Can perform trauma / emergency surgical procedures.",
    ),
    "general_surgery": CapabilityDef(
        canonical_name="general_surgery",
        category=CapabilityCategory.TRAUMA,
        description="General surgical capability.",
    ),
    "xray": CapabilityDef(
        canonical_name="xray",
        category=CapabilityCategory.TRAUMA,
        description="X-ray imaging available.",
    ),
    "ambulance": CapabilityDef(
        canonical_name="ambulance",
        category=CapabilityCategory.TRAUMA,
        description="Ambulance or emergency transport available.",
    ),
    "emergency_24_7": CapabilityDef(
        canonical_name="emergency_24_7",
        category=CapabilityCategory.TRAUMA,
        description="24/7 emergency services available.",
    ),

    # -- Infrastructure -----------------------------------------------------
    "oxygen_supply": CapabilityDef(
        canonical_name="oxygen_supply",
        category=CapabilityCategory.INFRASTRUCTURE,
        description="Reliable medical oxygen supply.",
    ),
    "generator_backup": CapabilityDef(
        canonical_name="generator_backup",
        category=CapabilityCategory.INFRASTRUCTURE,
        description="Backup generator for power outages.",
    ),
    "water_supply": CapabilityDef(
        canonical_name="water_supply",
        category=CapabilityCategory.INFRASTRUCTURE,
        description="Reliable clean water supply.",
    ),
    "lab_basic": CapabilityDef(
        canonical_name="lab_basic",
        category=CapabilityCategory.INFRASTRUCTURE,
        description="Basic laboratory / diagnostics on site.",
    ),
    "pharmacy": CapabilityDef(
        canonical_name="pharmacy",
        category=CapabilityCategory.INFRASTRUCTURE,
        description="On-site pharmacy / dispensary.",
    ),
}

# Quick look-ups
CAPABILITY_NAMES: List[str] = list(CAPABILITY_CATALOG.keys())

MATERNITY_CAPS = [c for c, d in CAPABILITY_CATALOG.items() if d.category == CapabilityCategory.MATERNITY]
TRAUMA_CAPS = [c for c, d in CAPABILITY_CATALOG.items() if d.category == CapabilityCategory.TRAUMA]
INFRA_CAPS = [c for c, d in CAPABILITY_CATALOG.items() if d.category == CapabilityCategory.INFRASTRUCTURE]
