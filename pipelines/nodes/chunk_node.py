"""
VirtueConnect — Chunk Node

Splits merged facility text (descriptions, capabilities, procedures,
equipment) into sentence-level chunks with full metadata for
downstream extraction and evidence locating.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List

from pipelines.state import Chunk, PipelineState

logger = logging.getLogger(__name__)

# Regex-based sentence splitter (avoids spaCy dependency for speed)
_SENT_SPLIT = re.compile(
    r"(?<=[.!?;])\s+"     # split after sentence-ending punctuation
    r"|(?<=\n)\s*"         # or after newlines
    r"|(?<=\d\.)\s+"       # or after numbered list items
)


def _split_text(text: str) -> List[str]:
    """Split text into sentence-level chunks."""
    if not text or not text.strip():
        return []
    sents = _SENT_SPLIT.split(text.strip())
    return [s.strip() for s in sents if s.strip() and len(s.strip()) > 5]


def _make_chunk_id(facility_id: str, source_column: str, idx: int) -> str:
    """Deterministic chunk ID."""
    raw = f"{facility_id}:{source_column}:{idx}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _find_offsets(full_text: str, snippet: str) -> tuple[int, int]:
    """Find char_start and char_end of snippet in full_text."""
    idx = full_text.find(snippet)
    if idx >= 0:
        return idx, idx + len(snippet)
    # Case-insensitive fallback
    idx = full_text.lower().find(snippet.lower())
    if idx >= 0:
        return idx, idx + len(snippet)
    return 0, len(snippet)


def chunk_node(state: PipelineState) -> PipelineState:
    """
    Create sentence-level chunks from all text fields of each facility.
    Also creates "structured chunks" from JSON array items.
    """
    merged = state.get("merged_facilities", {})
    logger.info("Chunking text for %d facilities", len(merged))

    all_chunks: Dict[str, List[Chunk]] = {}

    for fid, data in merged.items():
        facility_chunks: List[Chunk] = []

        # 1. Structured chunks from JSON arrays
        for source_col, key in [
            ("procedure", "procedures"),
            ("equipment", "equipment"),
            ("capability", "capabilities"),
            ("specialties", "specialties"),
        ]:
            items: List[str] = data.get(key, [])
            for i, item in enumerate(items):
                if not item.strip():
                    continue
                chunk: Chunk = {
                    "chunk_id": _make_chunk_id(fid, source_col, i),
                    "facility_id": fid,
                    "row_id": data.get("source_row_ids", [""])[0] if data.get("source_row_ids") else "",
                    "source_column": source_col,
                    "text": item.strip(),
                    "char_start": 0,
                    "char_end": len(item.strip()),
                }
                facility_chunks.append(chunk)

        # 2. Free-text chunks from descriptions
        descriptions: List[str] = data.get("descriptions", [])
        full_desc = " ".join(descriptions)
        sentences = _split_text(full_desc)
        for i, sent in enumerate(sentences):
            start, end = _find_offsets(full_desc, sent)
            chunk = {
                "chunk_id": _make_chunk_id(fid, "description", i),
                "facility_id": fid,
                "row_id": data.get("source_row_ids", [""])[0] if data.get("source_row_ids") else "",
                "source_column": "description",
                "text": sent,
                "char_start": start,
                "char_end": end,
            }
            facility_chunks.append(chunk)

        all_chunks[fid] = facility_chunks

    total = sum(len(v) for v in all_chunks.values())
    logger.info("Created %d chunks for %d facilities", total, len(all_chunks))
    state["chunks"] = all_chunks
    return state
