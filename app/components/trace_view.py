"""
VirtueConnect — Trace View Component

Renders the forensic evidence trail for a facility:
  - Extract step: what was detected + confidence
  - Validate step: bundle validation result
  - Source: row_id, column, snippet with highlights
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

from models.forensic_fields import ValidationState
from models.capability_models import ALL_CAPABILITY_FIELDS


_TRACE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "traces"


def _state_badge(state: str) -> str:
    """Return a colored badge for the validation state."""
    badges = {
        "ASSERTED": "🟢 ASSERTED",
        "EXTRACTED": "🟡 EXTRACTED",
        "CONTRADICTED": "🔴 CONTRADICTED",
        "UNCERTAIN": "🟠 UNCERTAIN",
        "MISSING": "⚪ MISSING",
        "OUT_OF_SCOPE": "⚫ OUT_OF_SCOPE",
    }
    return badges.get(state, f"❓ {state}")


def render_forensic_evidence(
    facility_data: Dict[str, Any],
    facility_id: str,
) -> None:
    """
    Render the full forensic evidence panel for a facility.

    Args:
        facility_data: Full facility record dict (from JSON)
        facility_id: The facility ID
    """
    st.markdown("### Forensic Evidence Trail")

    # Show capabilities with evidence
    for domain_name, domain_key in [
        ("Maternity", "maternity"),
        ("Trauma / Surgery", "trauma"),
        ("Infrastructure", "infra"),
    ]:
        domain_data = facility_data.get(domain_key, {})
        if not domain_data:
            continue

        with st.expander(f"**{domain_name}**", expanded=True):
            for cap_name, cap_data in domain_data.items():
                if not isinstance(cap_data, dict):
                    continue

                value = cap_data.get("value")
                state = cap_data.get("state", "MISSING")
                confidence = cap_data.get("confidence", 0.0)
                evidence_list = cap_data.get("evidence", [])

                # Format value
                if value is True:
                    val_str = "TRUE"
                elif value is False:
                    val_str = "FALSE"
                else:
                    val_str = "UNKNOWN"

                # Capability header
                cap_label = cap_name.replace("_", " ").title()
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    st.markdown(f"**{cap_label}**: {val_str}")
                with col2:
                    st.markdown(_state_badge(state))
                with col3:
                    st.progress(confidence, text=f"{confidence:.0%}")

                # Evidence snippets
                if evidence_list:
                    for ev in evidence_list:
                        if isinstance(ev, dict) and ev.get("snippet"):
                            source = ev.get("source_column", "unknown")
                            ev_type = ev.get("evidence_type", "free_text")
                            snippet = ev["snippet"]

                            st.markdown(
                                f"> 📝 *[{source} / {ev_type}]* \"{snippet}\""
                            )
                elif state != "MISSING":
                    st.caption("No evidence snippet available")

                st.markdown("---")


def render_trace_logs(facility_id: str) -> None:
    """
    Render MLflow/local trace logs for a facility.
    Shows the step-by-step pipeline execution.
    """
    trace_dir = _TRACE_DIR / facility_id
    if not trace_dir.exists():
        st.info("No pipeline trace logs available for this facility.")
        return

    st.markdown("### Pipeline Trace Logs")

    for path in sorted(trace_dir.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            log = json.load(f)

        step_name = log.get("step_name", path.stem)
        timestamp = log.get("timestamp", "")

        with st.expander(f"Step: **{step_name}** ({timestamp})"):
            # Inputs
            inputs = log.get("inputs", {})
            if inputs:
                st.markdown("**Inputs:**")
                st.json(inputs)

            # Outputs
            outputs = log.get("outputs", {})
            if outputs:
                st.markdown("**Outputs:**")
                st.json(outputs)

            # Evidence
            evidence = log.get("evidence", [])
            if evidence:
                st.markdown("**Evidence:**")
                for ev in evidence:
                    if isinstance(ev, dict):
                        snippet = ev.get("snippet", "N/A")
                        source = ev.get("source_column", "unknown")
                        st.markdown(f"> [{source}] \"{snippet}\"")


def render_anomalies(anomalies: List[Dict[str, Any]]) -> None:
    """Render anomaly records for a facility."""
    if not anomalies:
        st.success("No anomalies detected.")
        return

    st.markdown("### Anomalies & Flags")

    for anomaly in anomalies:
        severity = anomaly.get("severity", "MEDIUM")
        if severity == "HIGH":
            icon = "🚨"
        else:
            icon = "⚠️"

        st.markdown(
            f"{icon} **{anomaly.get('bundle_name', 'Unknown Bundle')}** — "
            f"{anomaly.get('reason', 'No reason provided')}"
        )

        missing = anomaly.get("required_missing", [])
        if missing:
            st.markdown(f"  Missing: {', '.join(missing)}")
