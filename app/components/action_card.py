"""
VirtueConnect — Action Plan Card Component

Renders a diagnostic card when clicking on a medical desert or
specific facility/region, showing:
  - Gap analysis (what's missing)
  - Impact estimate
  - Candidate facility for intervention
  - Suggested intervention
  - Cost-effectiveness rating
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from models.capability_models import ALL_CAPABILITY_FIELDS


# ---------------------------------------------------------------------------
# Ghana region population estimates (approximate, for impact calculation)
# ---------------------------------------------------------------------------

REGION_POPULATION = {
    "Greater Accra": 5_455_000,
    "Ashanti": 5_792_000,
    "Western": 2_376_000,
    "Eastern": 2_633_000,
    "Central": 2_859_000,
    "Northern": 2_310_000,
    "Volta": 1_907_000,
    "Brong Ahafo": 2_310_000,
    "Upper East": 1_301_000,
    "Upper West": 901_000,
    "Western North": 850_000,
    "Ahafo": 564_000,
    "Bono East": 1_200_000,
    "Oti": 760_000,
    "North East": 650_000,
    "Savannah": 590_000,
}


def _count_missing_capabilities(
    df_wide: pd.DataFrame,
    region: str,
    capability: str,
) -> int:
    """Count facilities in a region missing a specific capability."""
    region_df = df_wide[df_wide["region"].str.lower() == region.lower()]
    col = f"{capability}_value"
    if col not in region_df.columns:
        return 0
    missing = region_df[region_df[col] != True]
    return len(missing)


def _find_candidate_facility(
    df_wide: pd.DataFrame,
    region: str,
    missing_capability: str,
) -> Optional[Dict]:
    """
    Find the best candidate facility for intervention:
    one that has partial infrastructure but lacks the specific capability.
    """
    region_df = df_wide[df_wide["region"].str.lower() == region.lower()].copy()
    cap_col = f"{missing_capability}_value"

    if cap_col not in region_df.columns:
        return None

    # Facilities missing this capability
    candidates = region_df[region_df[cap_col] != True].copy()
    if candidates.empty:
        return None

    # Score candidates by existing infrastructure
    infra_cols = [
        c for c in region_df.columns
        if c.endswith("_value") and c != cap_col
    ]
    candidates["infra_score"] = candidates[infra_cols].apply(
        lambda row: sum(1 for v in row if v is True), axis=1
    )

    # Pick facility with most existing infrastructure
    best = candidates.sort_values("infra_score", ascending=False).iloc[0]
    return best.to_dict()


def render_action_card(
    df_wide: pd.DataFrame,
    region: str,
    gap_capability: str,
) -> None:
    """
    Render an Action Plan Card for a regional gap.

    Args:
        df_wide: WIDE gold table DataFrame
        region: Region name
        gap_capability: The missing capability to address
    """
    st.markdown(f"### Regional Diagnosis: **{region}**")

    # Gap
    missing_count = _count_missing_capabilities(df_wide, region, gap_capability)
    total_in_region = len(df_wide[df_wide["region"].str.lower() == region.lower()])
    cap_label = gap_capability.replace("_", " ").title()

    st.markdown(f"**Critical Gap:** {cap_label}")
    st.metric(
        label=f"Facilities without {cap_label}",
        value=f"{missing_count} / {total_in_region}",
    )

    # Impact
    pop = REGION_POPULATION.get(region, 500_000)
    women_estimate = int(pop * 0.25)  # rough: 25% women of childbearing age
    st.markdown(f"**Estimated Impact:** ~{women_estimate:,} women without access in < 2h")

    # Candidate facility
    candidate = _find_candidate_facility(df_wide, region, gap_capability)
    if candidate:
        st.markdown("---")
        st.markdown(f"**Candidate Facility:** {candidate.get('name', 'Unknown')}")
        st.markdown(f"- Type: {candidate.get('facility_type', 'N/A')}")
        st.markdown(f"- District: {candidate.get('district', 'N/A')}")

        # Show existing capabilities
        existing = []
        for cap in ALL_CAPABILITY_FIELDS:
            if candidate.get(f"{cap}_value") is True:
                existing.append(cap.replace("_", " ").title())
        if existing:
            st.markdown(f"- Existing capabilities: {', '.join(existing)}")

        # Intervention
        st.markdown("---")
        interventions = {
            "ultrasound_ob": "Equip with 1 portable USG device + training",
            "blood_bank": "Establish blood bank partnership or cold storage",
            "operating_room": "Upgrade to major theatre (surgical suite)",
            "anesthesia": "Provision anesthesia equipment + training",
            "anesthetist": "Deploy trained anesthetist (CRNA program)",
            "xray": "Install X-ray imaging unit",
            "oxygen_supply": "Install oxygen concentrator/plant",
            "generator_backup": "Install backup generator",
            "ambulance": "Allocate emergency transport vehicle",
            "lab_basic": "Equip basic diagnostic laboratory",
            "pharmacy": "Establish on-site pharmacy/dispensary",
        }
        intervention = interventions.get(
            gap_capability,
            f"Establish {cap_label} capability",
        )
        st.markdown(f"**Suggested Intervention:** {intervention}")

        # Cost-effectiveness
        infra_score = sum(
            1 for cap in ALL_CAPABILITY_FIELDS
            if candidate.get(f"{cap}_value") is True
        )
        if infra_score >= 5:
            effectiveness = "HIGH (infrastructure exists)"
            color = "green"
        elif infra_score >= 2:
            effectiveness = "MEDIUM (partial infrastructure)"
            color = "orange"
        else:
            effectiveness = "LOW (major build-out required)"
            color = "red"

        st.markdown(f"**Cost-Effectiveness:** :{color}[{effectiveness}]")
    else:
        st.info("No candidate facility found in this region.")


def render_region_gaps_summary(df_wide: pd.DataFrame) -> None:
    """
    Render a summary of gaps across all regions.
    Identifies "medical deserts" for key capabilities.
    """
    st.markdown("### Medical Desert Analysis")

    key_caps = [
        "c_section", "blood_bank", "ultrasound_ob",
        "operating_room", "emergency_24_7", "xray",
    ]

    regions = df_wide["region"].dropna().unique()
    gaps_data = []

    for region in sorted(regions):
        region_df = df_wide[df_wide["region"] == region]
        row = {"Region": region, "Total Facilities": len(region_df)}
        for cap in key_caps:
            col = f"{cap}_value"
            if col in region_df.columns:
                has_cap = region_df[col].sum() if region_df[col].dtype == bool else 0
                row[cap.replace("_", " ").title()] = int(has_cap)
            else:
                row[cap.replace("_", " ").title()] = 0
        gaps_data.append(row)

    df_gaps = pd.DataFrame(gaps_data)
    st.dataframe(df_gaps, use_container_width=True, hide_index=True)
