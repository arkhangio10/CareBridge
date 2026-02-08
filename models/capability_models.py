"""
VirtueConnect — Capability Domain Models

Three domain groups (Maternity, Trauma, Infrastructure), each composed
of ForensicField attributes.  These are nested inside FacilityRecord.
"""

from __future__ import annotations

from pydantic import BaseModel

from models.forensic_fields import ForensicField, ValidationState


def _default_field() -> ForensicField:
    return ForensicField(value=None, state=ValidationState.MISSING, confidence=0.0)


# ---------------------------------------------------------------------------
# Maternity
# ---------------------------------------------------------------------------

class MaternityCapability(BaseModel):
    """Maternal / obstetric capabilities."""
    c_section: ForensicField = _default_field()
    delivery_natural: ForensicField = _default_field()
    ultrasound_ob: ForensicField = _default_field()
    incubator: ForensicField = _default_field()
    blood_bank: ForensicField = _default_field()
    anesthesia: ForensicField = _default_field()
    anesthetist: ForensicField = _default_field()
    operating_room: ForensicField = _default_field()


# ---------------------------------------------------------------------------
# Trauma / Surgery
# ---------------------------------------------------------------------------

class TraumaCapability(BaseModel):
    """Trauma and surgical capabilities."""
    trauma_surgery: ForensicField = _default_field()
    general_surgery: ForensicField = _default_field()
    xray: ForensicField = _default_field()
    ambulance: ForensicField = _default_field()
    emergency_24_7: ForensicField = _default_field()


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

class InfraCapability(BaseModel):
    """Core infrastructure indicators."""
    oxygen_supply: ForensicField = _default_field()
    generator_backup: ForensicField = _default_field()
    water_supply: ForensicField = _default_field()
    lab_basic: ForensicField = _default_field()
    pharmacy: ForensicField = _default_field()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_CAPABILITY_FIELDS: list[str] = (
    list(MaternityCapability.model_fields.keys())
    + list(TraumaCapability.model_fields.keys())
    + list(InfraCapability.model_fields.keys())
)


def get_forensic_field(
    maternity: MaternityCapability,
    trauma: TraumaCapability,
    infra: InfraCapability,
    field_name: str,
) -> ForensicField | None:
    """Look up a ForensicField by canonical name across all domain models."""
    for model in (maternity, trauma, infra):
        if field_name in type(model).model_fields:
            return getattr(model, field_name)
    return None


def set_forensic_field(
    maternity: MaternityCapability,
    trauma: TraumaCapability,
    infra: InfraCapability,
    field_name: str,
    field_value: ForensicField,
) -> bool:
    """Set a ForensicField by canonical name. Returns True on success."""
    for model in (maternity, trauma, infra):
        if field_name in type(model).model_fields:
            setattr(model, field_name, field_value)
            return True
    return False
