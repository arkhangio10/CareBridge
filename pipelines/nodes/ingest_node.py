"""
VirtueConnect — Ingest Node

Reads the raw CSV, parses JSON array columns, normalises field names,
and outputs a list of RawFacilityRow dicts.
"""

from __future__ import annotations

import ast
import json
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from pipelines.state import PipelineState, RawFacilityRow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON array parser (handles messy CSV strings)
# ---------------------------------------------------------------------------

def _safe_parse_json_array(val: Any) -> List[str]:
    """Parse a JSON-like array stored as a CSV string."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    if isinstance(val, list):
        return [str(v) for v in val if v]

    s = str(val).strip()
    if not s or s.lower() in ("null", "[]", '[""]', "['']"):
        return []

    # Try JSON first
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(v) for v in parsed if v and str(v).strip()]
        return [str(parsed)] if parsed else []
    except (json.JSONDecodeError, TypeError):
        pass

    # Try Python literal
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return [str(v) for v in parsed if v and str(v).strip()]
        return [str(parsed)] if parsed else []
    except (ValueError, SyntaxError):
        pass

    # Fallback: treat as single string
    return [s] if s else []


def _safe_str(val: Any) -> Optional[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s if s and s.lower() != "null" else None


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------

def ingest_node(state: PipelineState) -> PipelineState:
    """
    Read the CSV and produce a list of normalised RawFacilityRow dicts.
    """
    csv_path = state["csv_path"]
    logger.info("Ingesting CSV: %s", csv_path)

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    logger.info("Loaded %d rows from CSV", len(df))

    raw_rows: List[RawFacilityRow] = []

    for _, row in df.iterrows():
        raw: RawFacilityRow = {
            "pk_unique_id": str(row.get("pk_unique_id", "")),
            "unique_id": str(row.get("unique_id", "")),
            "name": str(row.get("name", "")),
            "specialties": _safe_parse_json_array(row.get("specialties")),
            "procedure": _safe_parse_json_array(row.get("procedure")),
            "equipment": _safe_parse_json_array(row.get("equipment")),
            "capability": _safe_parse_json_array(row.get("capability")),
            "description": _safe_str(row.get("description")) or "",
            "facility_type": _safe_str(row.get("facilityTypeId")),
            "operator_type": _safe_str(row.get("operatorTypeId")),
            "organization_type": _safe_str(row.get("organization_type")),
            "region": _safe_str(row.get("address_stateOrRegion")),
            "district": _safe_str(row.get("address_city")),
            "phone_numbers": _safe_parse_json_array(row.get("phone_numbers")),
            "email": _safe_str(row.get("email")),
            "website": _safe_str(row.get("officialWebsite")),
            "address_line1": _safe_str(row.get("address_line1")),
            "source_url": _safe_str(row.get("source_url")),
        }
        raw_rows.append(raw)

    logger.info("Parsed %d raw rows", len(raw_rows))
    state["raw_rows"] = raw_rows
    return state
