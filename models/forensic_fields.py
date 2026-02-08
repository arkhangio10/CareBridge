"""
VirtueConnect — Core Forensic Data Models

ForensicField is the atomic unit of truth in VirtueConnect.
Every capability claim carries its value, validation state,
confidence score, and verbatim evidence trail.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ValidationState(str, Enum):
    """Tri-state truth + extended states for the forensic layer."""
    ASSERTED = "ASSERTED"           # from structured column (procedure/equipment)
    EXTRACTED = "EXTRACTED"         # from free-text with evidence
    CONTRADICTED = "CONTRADICTED"   # free-text explicitly denies the same concept
    UNCERTAIN = "UNCERTAIN"         # weak mention / ambiguous wording
    MISSING = "MISSING"             # no signal found
    OUT_OF_SCOPE = "OUT_OF_SCOPE"   # mention not about this facility


class Polarity(str, Enum):
    """Detected polarity of a concept mention in text."""
    AFFIRM = "affirm"
    DENY = "deny"
    REFER_OUT = "refer_out"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

EvidenceType = Literal["structured", "free_text", "pdf", "web"]


class Evidence(BaseModel):
    """A single piece of evidence backing a ForensicField value."""
    row_id: Optional[str] = None
    source_column: Optional[str] = None
    snippet: Optional[str] = None
    evidence_type: EvidenceType = "free_text"
    char_start: Optional[int] = None
    char_end: Optional[int] = None

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# ForensicField
# ---------------------------------------------------------------------------

class ForensicField(BaseModel):
    """
    The atomic forensic unit.

    * ``value`` — True / False / None (unknown)
    * ``state`` — how the value was determined
    * ``confidence`` — calibrated score 0-1
    * ``evidence`` — ordered list of evidence snippets (top-N)
    """
    value: Optional[bool] = None
    state: ValidationState = ValidationState.MISSING
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: List[Evidence] = Field(default_factory=list)

    # Convenience helpers -------------------------------------------------

    def is_positive(self) -> bool:
        """True only when explicitly asserted/extracted as True."""
        return self.value is True and self.state in (
            ValidationState.ASSERTED,
            ValidationState.EXTRACTED,
        )

    def is_contradicted(self) -> bool:
        return self.state == ValidationState.CONTRADICTED

    def is_missing(self) -> bool:
        return self.state == ValidationState.MISSING

    def add_evidence(self, ev: Evidence, max_evidence: int = 3) -> None:
        """Append evidence, keeping at most *max_evidence* entries."""
        self.evidence.append(ev)
        if len(self.evidence) > max_evidence:
            self.evidence = self.evidence[-max_evidence:]
