"""
VirtueConnect — Persist Node

Writes validated FacilityRecords to:
  1. Local JSON (always, for offline/demo)
  2. Databricks Delta tables (if credentials are configured)

Produces both WIDE and LONG table formats.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List

import pandas as pd

from models.facility import FacilityRecord
from pipelines.state import PipelineState
from pipelines.geocoding import geocode_all_facilities

logger = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "output"


def _persist_local(facilities: Dict[str, FacilityRecord]) -> None:
    """Write WIDE and LONG tables as CSV + full JSON dump."""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # -- WIDE table --
    wide_rows = [record.to_wide_dict() for record in facilities.values()]
    df_wide = pd.DataFrame(wide_rows)
    wide_path = _OUTPUT_DIR / "gold_facilities_wide.csv"
    df_wide.to_csv(wide_path, index=False)
    logger.info("Wrote WIDE table: %s (%d rows)", wide_path, len(df_wide))

    # -- LONG table --
    long_rows: List[dict] = []
    for record in facilities.values():
        long_rows.extend(record.to_long_rows())
    df_long = pd.DataFrame(long_rows)
    long_path = _OUTPUT_DIR / "gold_facilities_long.csv"
    df_long.to_csv(long_path, index=False)
    logger.info("Wrote LONG table: %s (%d rows)", long_path, len(df_long))

    # -- Full JSON dump --
    json_path = _OUTPUT_DIR / "facilities_full.json"
    data = {
        fid: record.model_dump(mode="json")
        for fid, record in facilities.items()
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Wrote full JSON: %s", json_path)

    # -- Anomalies table --
    anomaly_rows = []
    for record in facilities.values():
        for a in record.anomalies:
            anomaly_rows.append({
                "facility_id": a.facility_id,
                "facility_name": record.name,
                "bundle_name": a.bundle_name,
                "anomaly_type": a.anomaly_type,
                "severity": a.severity,
                "reason": a.reason,
                "required_missing": ", ".join(a.required_missing),
            })
    if anomaly_rows:
        df_anomalies = pd.DataFrame(anomaly_rows)
        anomalies_path = _OUTPUT_DIR / "anomalies.csv"
        df_anomalies.to_csv(anomalies_path, index=False)
        logger.info("Wrote anomalies: %s (%d rows)", anomalies_path, len(df_anomalies))


def _persist_databricks(facilities: Dict[str, FacilityRecord]) -> None:
    """Write to Databricks Delta tables (requires databricks-sdk)."""
    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")
    catalog = os.environ.get("DATABRICKS_CATALOG", "virtueconnect")
    schema = os.environ.get("DATABRICKS_SCHEMA", "gold")

    if not host or not token:
        logger.info("Databricks credentials not set, skipping Delta write")
        return

    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.sql import StatementExecutionService

        logger.info("Writing to Databricks: %s.%s", catalog, schema)

        # WIDE table
        wide_rows = [record.to_wide_dict() for record in facilities.values()]
        df_wide = pd.DataFrame(wide_rows)

        # LONG table
        long_rows: List[dict] = []
        for record in facilities.values():
            long_rows.extend(record.to_long_rows())
        df_long = pd.DataFrame(long_rows)

        # Use Spark DataFrame via databricks-connect if available
        # For hackathon, we'll write CSVs to DBFS and create tables
        w = WorkspaceClient(host=host, token=token)

        # Upload CSVs to DBFS
        import io

        wide_csv = df_wide.to_csv(index=False).encode("utf-8")
        w.dbfs.put(
            f"/FileStore/virtueconnect/gold_facilities_wide.csv",
            io.BytesIO(wide_csv),
            overwrite=True,
        )

        long_csv = df_long.to_csv(index=False).encode("utf-8")
        w.dbfs.put(
            f"/FileStore/virtueconnect/gold_facilities_long.csv",
            io.BytesIO(long_csv),
            overwrite=True,
        )

        logger.info("Uploaded WIDE and LONG CSVs to DBFS")

    except ImportError:
        logger.warning("databricks-sdk not installed, skipping Databricks persist")
    except Exception as e:
        logger.error("Databricks persist failed: %s", e)


def persist_node(state: PipelineState) -> PipelineState:
    """Persist validated facility records to local files and Databricks."""
    facilities: Dict[str, FacilityRecord] = state.get("facilities", {})
    logger.info("Persisting %d facilities", len(facilities))

    # Geocode all facilities before persisting
    logger.info("Geocoding facilities...")
    geocoded = geocode_all_facilities(facilities)
    logger.info("Geocoded %d facilities", geocoded)

    # Always write local
    _persist_local(facilities)

    # Optionally write to Databricks
    _persist_databricks(facilities)

    state["persisted"] = True
    return state
