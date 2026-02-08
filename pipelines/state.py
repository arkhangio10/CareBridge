"""
VirtueConnect — LangGraph Pipeline State

Defines the TypedDict that flows through all nodes in the pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from models.facility import FacilityRecord


class Chunk(TypedDict):
    """A single text chunk with metadata."""
    chunk_id: str
    facility_id: str
    row_id: str
    source_column: str
    text: str
    char_start: int
    char_end: int


class RawFacilityRow(TypedDict):
    """Raw row from the CSV before dedup/merge."""
    pk_unique_id: str
    unique_id: str
    name: str
    specialties: List[str]
    procedure: List[str]
    equipment: List[str]
    capability: List[str]
    description: str
    facility_type: Optional[str]
    operator_type: Optional[str]
    organization_type: Optional[str]
    region: Optional[str]
    district: Optional[str]
    phone_numbers: List[str]
    email: Optional[str]
    website: Optional[str]
    address_line1: Optional[str]
    source_url: Optional[str]


class PipelineState(TypedDict, total=False):
    """
    State that flows through the LangGraph pipeline.
    Each node reads/writes specific keys.
    """
    # --- ingest_node output ---
    raw_rows: List[RawFacilityRow]

    # --- dedup_merge_node output ---
    merged_facilities: Dict[str, Dict[str, Any]]  # pk_unique_id -> merged data

    # --- chunk_node output ---
    chunks: Dict[str, List[Chunk]]  # facility_id -> list of chunks

    # --- extractor_node output ---
    extracted: Dict[str, Dict[str, Any]]  # facility_id -> extracted capabilities

    # --- reconciler_node output ---
    facilities: Dict[str, FacilityRecord]  # facility_id -> validated record

    # --- validator_node output ---
    # (modifies facilities in place, adding anomalies)

    # --- persist_node output ---
    persisted: bool

    # --- metadata ---
    csv_path: str
    run_id: Optional[str]
    step_logs: List[Dict[str, Any]]
