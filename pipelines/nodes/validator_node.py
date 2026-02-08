"""
VirtueConnect — Validator Node (Clinical Bundles)

Runs all clinical bundle rules against each facility,
generating AnomalyRecords for facilities that claim capabilities
without the required supporting infrastructure.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from models.bundle_rules import BundleValidator
from models.facility import FacilityRecord
from pipelines.state import PipelineState

logger = logging.getLogger(__name__)

# Default bundles path
_DEFAULT_BUNDLES = Path(__file__).resolve().parent.parent.parent / "configs" / "bundles.yaml"


def validator_node(state: PipelineState) -> PipelineState:
    """
    Validate all facilities against clinical bundle rules.
    Adds anomalies to each FacilityRecord and recomputes flags.
    """
    facilities: Dict[str, FacilityRecord] = state.get("facilities", {})

    # Load bundle definitions
    bundles_path = _DEFAULT_BUNDLES
    validator = BundleValidator(bundles_path)
    logger.info(
        "Running %d bundle rules against %d facilities",
        len(validator.bundles), len(facilities),
    )

    total_anomalies = 0

    for fid, record in facilities.items():
        anomalies = validator.validate(
            facility_id=fid,
            maternity=record.maternity,
            trauma=record.trauma,
            infra=record.infra,
        )
        record.anomalies = anomalies
        record.compute_flags()
        total_anomalies += len(anomalies)

    logger.info(
        "Validation complete: %d anomalies across %d facilities",
        total_anomalies, len(facilities),
    )

    state["facilities"] = facilities
    return state
