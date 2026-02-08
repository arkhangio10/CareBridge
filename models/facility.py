"""
VirtueConnect — Facility Record (top-level per-facility model)

Each FacilityRecord represents a single deduplicated healthcare facility
with all forensic capability data, anomalies, and metadata.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from models.forensic_fields import ForensicField
from models.capability_models import (
    MaternityCapability,
    TraumaCapability,
    InfraCapability,
    get_forensic_field,
    ALL_CAPABILITY_FIELDS,
)
from models.bundle_rules import AnomalyRecord


class FacilityRecord(BaseModel):
    """
    Deduplicated, fully-validated representation of a single healthcare
    facility.  Created by the pipeline after ingest -> merge -> extract
    -> reconcile -> validate.
    """
    # Identity
    facility_id: str                              # pk_unique_id
    name: str
    region: Optional[str] = None                  # address_stateOrRegion
    district: Optional[str] = None                # address_city
    lat: Optional[float] = None                   # geocoded
    lon: Optional[float] = None                   # geocoded
    facility_type: Optional[str] = None           # facilityTypeId
    operator_type: Optional[str] = None           # operatorTypeId
    organization_type: Optional[str] = None       # facility | ngo
    source_row_ids: List[str] = Field(default_factory=list)

    # Capabilities (forensic)
    maternity: MaternityCapability = Field(default_factory=MaternityCapability)
    trauma: TraumaCapability = Field(default_factory=TraumaCapability)
    infra: InfraCapability = Field(default_factory=InfraCapability)

    # Anomalies from bundle validation
    anomalies: List[AnomalyRecord] = Field(default_factory=list)

    # Raw source arrays (preserved for audit)
    raw_specialties: List[str] = Field(default_factory=list)
    raw_procedures: List[str] = Field(default_factory=list)
    raw_equipment: List[str] = Field(default_factory=list)
    raw_capabilities: List[str] = Field(default_factory=list)
    raw_descriptions: List[str] = Field(default_factory=list)

    # Contact
    phone_numbers: List[str] = Field(default_factory=list)
    email: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None

    # Flags (computed from anomalies)
    has_anomaly_high: bool = False
    has_risk_high: bool = False

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def get_field(self, cap_name: str) -> Optional[ForensicField]:
        return get_forensic_field(self.maternity, self.trauma, self.infra, cap_name)

    def compute_flags(self) -> None:
        """Recompute anomaly flag booleans from the anomalies list."""
        self.has_anomaly_high = any(
            a.anomaly_type == "ANOMALY_HIGH" for a in self.anomalies
        )
        self.has_risk_high = any(
            a.anomaly_type == "RISK_HIGH" for a in self.anomalies
        )

    def to_wide_dict(self) -> Dict:
        """Flatten into a dict suitable for the WIDE gold table."""
        row: Dict = {
            "facility_id": self.facility_id,
            "name": self.name,
            "region": self.region,
            "district": self.district,
            "lat": self.lat,
            "lon": self.lon,
            "facility_type": self.facility_type,
            "operator_type": self.operator_type,
        }
        for cap_name in ALL_CAPABILITY_FIELDS:
            ff = self.get_field(cap_name)
            if ff:
                row[f"{cap_name}_value"] = ff.value
                row[f"{cap_name}_state"] = ff.state.value
                row[f"{cap_name}_confidence"] = ff.confidence
            else:
                row[f"{cap_name}_value"] = None
                row[f"{cap_name}_state"] = "MISSING"
                row[f"{cap_name}_confidence"] = 0.0
        row["has_anomaly_high"] = self.has_anomaly_high
        row["has_risk_high"] = self.has_risk_high
        return row

    def to_long_rows(self) -> List[Dict]:
        """Expand into rows for the LONG forensic table (one row per cap-evidence pair)."""
        rows: List[Dict] = []
        for cap_name in ALL_CAPABILITY_FIELDS:
            ff = self.get_field(cap_name)
            if ff is None:
                continue
            if not ff.evidence:
                rows.append({
                    "facility_id": self.facility_id,
                    "capability_name": cap_name,
                    "value": ff.value,
                    "state": ff.state.value,
                    "confidence": ff.confidence,
                    "row_id": None,
                    "source_column": None,
                    "evidence_snippet": None,
                    "char_start": None,
                    "char_end": None,
                })
            else:
                for ev in ff.evidence:
                    rows.append({
                        "facility_id": self.facility_id,
                        "capability_name": cap_name,
                        "value": ff.value,
                        "state": ff.state.value,
                        "confidence": ff.confidence,
                        "row_id": ev.row_id,
                        "source_column": ev.source_column,
                        "evidence_snippet": ev.snippet,
                        "char_start": ev.char_start,
                        "char_end": ev.char_end,
                    })
        return rows
