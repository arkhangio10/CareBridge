"""
VirtueConnect — PatientSafe Chat View

Chat interface for patient routing with:
  - Red-flag symptom detection (immediate alert)
  - NL intent mapping (symptoms -> capability needs)
  - Top 3 facility recommendations with evidence
  - "View Forensic Evidence" expander
  - NEVER diagnose or prescribe
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from models.capability_models import ALL_CAPABILITY_FIELDS


# ---------------------------------------------------------------------------
# Red-flag keywords (immediate emergency alert)
# ---------------------------------------------------------------------------

RED_FLAGS = {
    "bleeding": "Possible hemorrhage — seek emergency care immediately",
    "haemorrhage": "Possible hemorrhage — seek emergency care immediately",
    "hemorrhage": "Possible hemorrhage — seek emergency care immediately",
    "unconscious": "Loss of consciousness — call emergency services NOW",
    "not breathing": "Respiratory emergency — call emergency services NOW",
    "difficulty breathing": "Respiratory distress — seek emergency care immediately",
    "can't breathe": "Respiratory distress — seek emergency care immediately",
    "chest pain": "Possible cardiac emergency — seek emergency care immediately",
    "severe chest pain": "Possible cardiac emergency — call emergency services NOW",
    "seizure": "Seizure activity — seek emergency care immediately",
    "convulsion": "Seizure activity — seek emergency care immediately",
    "head injury": "Possible traumatic brain injury — seek emergency care immediately",
    "severe bleeding": "Severe hemorrhage — call emergency services NOW",
    "labor": "Active labor — proceed to nearest maternity facility",
    "contractions": "Possible labor — contact your maternity care provider",
    "water broke": "Possible membrane rupture — proceed to maternity facility",
}

# ---------------------------------------------------------------------------
# Symptom -> Capability needs mapping
# ---------------------------------------------------------------------------

INTENT_MAP: Dict[str, List[str]] = {
    # Maternity
    "pregnant": ["delivery_natural", "ultrasound_ob", "blood_bank"],
    "pregnancy": ["delivery_natural", "ultrasound_ob", "blood_bank"],
    "baby": ["delivery_natural", "incubator"],
    "delivery": ["delivery_natural", "operating_room"],
    "c-section": ["c_section", "operating_room", "anesthesia"],
    "caesarean": ["c_section", "operating_room", "anesthesia"],
    "ultrasound": ["ultrasound_ob"],
    "prenatal": ["delivery_natural", "ultrasound_ob"],

    # Trauma
    "accident": ["trauma_surgery", "xray", "emergency_24_7", "blood_bank"],
    "broken": ["xray", "general_surgery"],
    "fracture": ["xray", "general_surgery"],
    "wound": ["general_surgery", "emergency_24_7"],
    "surgery": ["general_surgery", "operating_room", "anesthesia"],
    "emergency": ["emergency_24_7", "ambulance"],

    # General
    "lab": ["lab_basic"],
    "test": ["lab_basic"],
    "blood test": ["lab_basic"],
    "medicine": ["pharmacy"],
    "medication": ["pharmacy"],
    "prescription": ["pharmacy"],
    "x-ray": ["xray"],
    "xray": ["xray"],
}


def _detect_red_flags(text: str) -> List[str]:
    """Check text for red-flag keywords. Returns list of alert messages."""
    alerts = []
    lower = text.lower()
    for keyword, message in RED_FLAGS.items():
        if keyword in lower:
            alerts.append(message)
    return list(set(alerts))  # deduplicate


def _detect_intent(text: str) -> List[str]:
    """Map user text to required capabilities."""
    lower = text.lower()
    needed: List[str] = []
    for keyword, caps in INTENT_MAP.items():
        if keyword in lower:
            needed.extend(caps)
    return list(set(needed))


def _score_facility(
    facility: pd.Series,
    needed_caps: List[str],
) -> Tuple[float, List[str], List[str]]:
    """
    Score a facility against needed capabilities.
    Returns (score, matched_caps, missing_caps).
    """
    matched = []
    missing = []

    for cap in needed_caps:
        col = f"{cap}_value"
        if col in facility.index and facility[col] is True:
            matched.append(cap)
        else:
            missing.append(cap)

    if not needed_caps:
        return 0.0, matched, missing

    score = len(matched) / len(needed_caps)

    # Bonus for 24/7 emergency
    if facility.get("emergency_24_7_value") is True:
        score += 0.1

    # Penalty for anomalies
    if facility.get("has_anomaly_high") or facility.get("has_risk_high"):
        score -= 0.2

    return min(1.0, max(0.0, score)), matched, missing


def _find_recommendations(
    df_wide: pd.DataFrame,
    needed_caps: List[str],
    region_filter: Optional[str] = None,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """Find top-K facility recommendations for the patient's needs."""
    df = df_wide.copy()

    if region_filter and region_filter != "All":
        df = df[df["region"].str.lower() == region_filter.lower()]

    results = []
    for _, row in df.iterrows():
        score, matched, missing = _score_facility(row, needed_caps)
        if score > 0:
            results.append({
                "facility_id": row["facility_id"],
                "name": row["name"],
                "region": row.get("region", "Unknown"),
                "district": row.get("district", "Unknown"),
                "facility_type": row.get("facility_type", "N/A"),
                "score": score,
                "matched_caps": matched,
                "missing_caps": missing,
                "has_anomaly": bool(row.get("has_anomaly_high") or row.get("has_risk_high")),
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_patient_safe(
    df_wide: pd.DataFrame,
    facilities_json_path: Optional[str] = None,
) -> None:
    """
    Render the PatientSafe chat interface.

    Args:
        df_wide: WIDE gold table DataFrame
        facilities_json_path: Path to facilities_full.json for evidence lookups
    """
    st.markdown("## PatientSafe — Facility Finder")
    st.markdown(
        "*Describe your situation and we'll help you find the right facility. "
        "We do **not** provide medical diagnoses or prescriptions.*"
    )

    # Region filter
    regions = ["All"] + sorted(df_wide["region"].dropna().unique().tolist())
    region = st.selectbox("Your region (optional)", regions, index=0)

    # Chat interface
    if "patient_messages" not in st.session_state:
        st.session_state.patient_messages = []

    # Display chat history
    for msg in st.session_state.patient_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # User input
    user_input = st.chat_input("Describe your situation (e.g., 'My wife is pregnant and needs an ultrasound')")

    if user_input:
        # Add user message
        st.session_state.patient_messages.append({
            "role": "user",
            "content": user_input,
        })
        with st.chat_message("user"):
            st.markdown(user_input)

        # Process
        with st.chat_message("assistant"):
            # 1. Red-flag detection
            red_flags = _detect_red_flags(user_input)
            if red_flags:
                for alert in red_flags:
                    st.error(f"🚨 **EMERGENCY ALERT:** {alert}")
                st.markdown(
                    "**Call emergency services immediately.** "
                    "While waiting, here are the nearest facilities:"
                )

            # 2. Intent detection
            needed_caps = _detect_intent(user_input)

            if not needed_caps and not red_flags:
                response = (
                    "I understand you need medical assistance. "
                    "Could you provide more details about your symptoms or needs? "
                    "For example: 'I need an ultrasound' or 'I had an accident'."
                )
                st.markdown(response)
                st.session_state.patient_messages.append({
                    "role": "assistant",
                    "content": response,
                })
                return

            if not needed_caps and red_flags:
                needed_caps = ["emergency_24_7", "ambulance"]

            # Show what we understood
            cap_labels = [c.replace("_", " ").title() for c in needed_caps]
            st.markdown(
                f"**Understanding:** Looking for facilities with: "
                f"{', '.join(cap_labels)}"
            )

            # 3. Find recommendations
            recs = _find_recommendations(
                df_wide, needed_caps,
                region_filter=region if region != "All" else None,
            )

            if not recs:
                st.warning("No matching facilities found in your region. Try expanding your search area.")
                return

            # 4. Display recommendations
            for i, rec in enumerate(recs):
                is_top = i == 0
                container = st.container(border=True)
                with container:
                    # Header
                    if is_top:
                        st.markdown(f"### 🏥 {rec['name']} **(Recommended)**")
                    else:
                        st.markdown(f"### {rec['name']}")

                    # Capability match
                    matched_labels = [
                        f"✅ {c.replace('_', ' ').title()}" for c in rec["matched_caps"]
                    ]
                    missing_labels = [
                        f"❌ {c.replace('_', ' ').title()}" for c in rec["missing_caps"]
                    ]

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Capabilities:**")
                        for label in matched_labels:
                            st.markdown(label)
                    with col2:
                        if missing_labels:
                            st.markdown("**Not confirmed:**")
                            for label in missing_labels:
                                st.markdown(label)

                    # Safety info
                    if rec["has_anomaly"]:
                        st.warning("⚠️ This facility has unresolved safety anomalies")

                    # Location
                    st.markdown(
                        f"📍 {rec['district'] or ''}, {rec['region']} | "
                        f"Type: {rec['facility_type'] or 'N/A'} | "
                        f"Match: {rec['score']:.0%}"
                    )

                    # Evidence expander
                    _render_evidence_expander(rec["facility_id"], facilities_json_path)

            # Save response
            response_text = f"Found {len(recs)} matching facilities."
            st.session_state.patient_messages.append({
                "role": "assistant",
                "content": response_text,
            })


def _render_evidence_expander(
    facility_id: str,
    facilities_json_path: Optional[str],
) -> None:
    """Render the 'View Forensic Evidence' expander for a recommendation."""
    with st.expander("🔍 View Forensic Evidence"):
        if not facilities_json_path or not Path(facilities_json_path).exists():
            st.info("Evidence data not loaded. Run the pipeline first.")
            return

        try:
            with open(facilities_json_path, "r", encoding="utf-8") as f:
                all_data = json.load(f)

            fdata = all_data.get(str(facility_id))
            if not fdata:
                st.info("No detailed evidence available for this facility.")
                return

            # Show key capabilities with evidence
            for domain_key in ("maternity", "trauma", "infra"):
                domain_data = fdata.get(domain_key, {})
                for cap_name, cap_data in domain_data.items():
                    if not isinstance(cap_data, dict):
                        continue
                    if cap_data.get("state") in ("MISSING", None):
                        continue

                    state = cap_data.get("state", "MISSING")
                    confidence = cap_data.get("confidence", 0.0)
                    value = cap_data.get("value")

                    # State badge
                    badges = {
                        "ASSERTED": "🟢",
                        "EXTRACTED": "🟡",
                        "CONTRADICTED": "🔴",
                        "UNCERTAIN": "🟠",
                    }
                    badge = badges.get(state, "⚪")

                    val_str = "TRUE" if value is True else "FALSE" if value is False else "?"
                    cap_label = cap_name.replace("_", " ").title()
                    st.markdown(
                        f"{badge} **{cap_label}**: {val_str} "
                        f"(conf: {confidence:.0%}, state: {state})"
                    )

                    # Evidence snippets
                    for ev in cap_data.get("evidence", []):
                        if isinstance(ev, dict) and ev.get("snippet"):
                            source = ev.get("source_column", "?")
                            st.markdown(f"> *[{source}]* \"{ev['snippet']}\"")

        except Exception as e:
            st.error(f"Error loading evidence: {e}")
