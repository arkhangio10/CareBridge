"""
VirtueConnect — Clinical Bundle Validator

Bundles encode clinical safety rules (e.g., "C-section requires OT +
anesthesia").  The validator flags anomalies when facilities claim
capabilities they cannot safely deliver.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from models.forensic_fields import Evidence, ForensicField, ValidationState
from models.capability_models import (
    MaternityCapability,
    TraumaCapability,
    InfraCapability,
    get_forensic_field,
)


# ---------------------------------------------------------------------------
# Anomaly Record
# ---------------------------------------------------------------------------

class AnomalyRecord(BaseModel):
    """A single anomaly / clinical flag raised by bundle validation."""
    facility_id: str
    bundle_name: str
    anomaly_type: str          # e.g. "ANOMALY_HIGH", "RISK_HIGH"
    severity: str              # "HIGH", "MEDIUM", "LOW"
    reason: str
    required_missing: List[str] = Field(default_factory=list)
    evidence_rows: List[Evidence] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Bundle Definition
# ---------------------------------------------------------------------------

class BundleDef(BaseModel):
    """Schema for a single bundle from bundles.yaml."""
    requires_all: List[str] = Field(default_factory=list)
    requires_any: List[List[str]] = Field(default_factory=list)
    failure_flag: str = "ANOMALY_HIGH"
    failure_reason: str = ""
    trigger_capability: Optional[str] = None  # only check when this cap is True
    trigger_text: Optional[List[str]] = None  # text-trigger variant
    action: Optional[str] = None
    scope: Optional[str] = None


# ---------------------------------------------------------------------------
# Bundle Validator
# ---------------------------------------------------------------------------

class BundleValidator:
    """
    Loads clinical bundle rules from YAML and validates a facility's
    capability set against them.
    """

    def __init__(self, bundles_path: str | Path | None = None):
        self.bundles: Dict[str, BundleDef] = {}
        if bundles_path:
            self.load(bundles_path)

    # -- loading ----------------------------------------------------------

    def load(self, path: str | Path) -> None:
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            raw: Dict[str, Any] = yaml.safe_load(f) or {}
        for name, cfg in raw.get("bundles", {}).items():
            self.bundles[name] = BundleDef(**cfg)

    # -- validation -------------------------------------------------------

    def validate(
        self,
        facility_id: str,
        maternity: MaternityCapability,
        trauma: TraumaCapability,
        infra: InfraCapability,
    ) -> List[AnomalyRecord]:
        """Run all bundles against a facility and return anomaly records."""
        anomalies: List[AnomalyRecord] = []
        for name, bundle in self.bundles.items():
            # Skip text-trigger bundles (handled separately)
            if bundle.trigger_text is not None:
                continue

            anomaly = self._check_bundle(
                facility_id, name, bundle, maternity, trauma, infra
            )
            if anomaly is not None:
                anomalies.append(anomaly)
        return anomalies

    def _check_bundle(
        self,
        facility_id: str,
        name: str,
        bundle: BundleDef,
        maternity: MaternityCapability,
        trauma: TraumaCapability,
        infra: InfraCapability,
    ) -> Optional[AnomalyRecord]:
        """Check a single bundle.  Returns an anomaly or None."""

        # If there is a trigger capability, only check when it is True
        if bundle.trigger_capability:
            trigger_ff = get_forensic_field(
                maternity, trauma, infra, bundle.trigger_capability
            )
            if trigger_ff is None or not trigger_ff.is_positive():
                return None

        # Also auto-infer trigger from first requires_all entry
        if not bundle.trigger_capability and bundle.requires_all:
            trigger_ff = get_forensic_field(
                maternity, trauma, infra, bundle.requires_all[0]
            )
            if trigger_ff is None or not trigger_ff.is_positive():
                return None

        # Check requires_all (skip the trigger itself)
        missing: List[str] = []
        evidence_rows: List[Evidence] = []

        for cap_name in bundle.requires_all:
            ff = get_forensic_field(maternity, trauma, infra, cap_name)
            if ff is None or not ff.is_positive():
                missing.append(cap_name)
            elif ff.evidence:
                evidence_rows.extend(ff.evidence)

        # Check requires_any — at least one from each group must be True
        for group in bundle.requires_any:
            group_ok = False
            for cap_name in group:
                ff = get_forensic_field(maternity, trauma, infra, cap_name)
                if ff is not None and ff.is_positive():
                    group_ok = True
                    if ff.evidence:
                        evidence_rows.extend(ff.evidence)
                    break
            if not group_ok:
                missing.append(f"one_of({','.join(group)})")

        if missing:
            return AnomalyRecord(
                facility_id=facility_id,
                bundle_name=name,
                anomaly_type=bundle.failure_flag,
                severity="HIGH" if "HIGH" in bundle.failure_flag else "MEDIUM",
                reason=bundle.failure_reason,
                required_missing=missing,
                evidence_rows=evidence_rows,
            )
        return None
