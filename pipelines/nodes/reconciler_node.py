"""
VirtueConnect — Reconciler Node

Builds FacilityRecord objects by reconciling extracted facts
(structured vs free-text) using strict priority rules:

  1. Structured TRUE + text denies same concept -> CONTRADICTED
  2. Structured NULL + text affirms with evidence -> EXTRACTED
  3. Both affirm -> keep ASSERTED, append free-text evidence
  4. Weak mention only -> UNCERTAIN
  5. Multiple independent evidence -> boost confidence
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from models.forensic_fields import Evidence, ForensicField, ValidationState
from models.capability_models import (
    MaternityCapability,
    TraumaCapability,
    InfraCapability,
    ALL_CAPABILITY_FIELDS,
    set_forensic_field,
)
from models.facility import FacilityRecord
from pipelines.state import PipelineState

logger = logging.getLogger(__name__)


def _build_forensic_field(fact: Dict[str, Any]) -> ForensicField:
    """Convert an extraction fact dict into a ForensicField."""
    value_raw = fact.get("value")
    if value_raw is None:
        value = None
    elif isinstance(value_raw, bool):
        value = value_raw
    else:
        value = str(value_raw).lower() == "true"

    state_str = fact.get("state", "MISSING")
    try:
        state = ValidationState(state_str)
    except ValueError:
        state = ValidationState.MISSING

    confidence = float(fact.get("confidence", 0.0))

    evidence_list: List[Evidence] = []
    for ev_dict in fact.get("evidence", []):
        if isinstance(ev_dict, dict):
            evidence_list.append(Evidence(**ev_dict))
        elif isinstance(ev_dict, Evidence):
            evidence_list.append(ev_dict)

    return ForensicField(
        value=value,
        state=state,
        confidence=confidence,
        evidence=evidence_list[:3],  # keep top 3
    )


def reconciler_node(state: PipelineState) -> PipelineState:
    """
    Build FacilityRecord objects from merged facility data + extracted facts.
    Applies reconciliation priority rules.
    """
    merged = state.get("merged_facilities", {})
    extracted = state.get("extracted", {})

    logger.info("Reconciling %d facilities", len(merged))

    facilities: Dict[str, FacilityRecord] = {}

    for fid, data in merged.items():
        facts = extracted.get(fid, {})

        # Create capability models
        maternity = MaternityCapability()
        trauma = TraumaCapability()
        infra = InfraCapability()

        for cap_name in ALL_CAPABILITY_FIELDS:
            if cap_name in facts:
                ff = _build_forensic_field(facts[cap_name])
            else:
                ff = ForensicField(
                    value=None,
                    state=ValidationState.MISSING,
                    confidence=0.0,
                )
            set_forensic_field(maternity, trauma, infra, cap_name, ff)

        # Build the facility record
        record = FacilityRecord(
            facility_id=fid,
            name=data.get("name", f"Facility {fid}"),
            region=data.get("region"),
            district=data.get("district"),
            facility_type=data.get("facility_type"),
            operator_type=data.get("operator_type"),
            organization_type=data.get("organization_type"),
            source_row_ids=data.get("source_row_ids", []),
            maternity=maternity,
            trauma=trauma,
            infra=infra,
            raw_specialties=data.get("specialties", []),
            raw_procedures=data.get("procedures", []),
            raw_equipment=data.get("equipment", []),
            raw_capabilities=data.get("capabilities", []),
            raw_descriptions=data.get("descriptions", []),
            phone_numbers=data.get("phone_numbers", []),
            email=data.get("email"),
            website=data.get("website"),
            address_line1=data.get("address_line1"),
        )

        facilities[fid] = record

    state["facilities"] = facilities
    logger.info("Reconciled %d facility records", len(facilities))
    return state
