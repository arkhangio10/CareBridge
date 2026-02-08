"""
VirtueConnect — Main Streamlit Application

Two views:
  1. NGO View: Map + 3 command buttons + Action Plan Cards
  2. PatientSafe View: Chat-based facility finder with evidence

Usage:
    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Ensure project root is on path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from app.components.map_view import render_map, render_facility_selector
from app.components.action_card import render_action_card, render_region_gaps_summary
from app.components.trace_view import render_forensic_evidence, render_anomalies
from app.components.patient_safe import render_patient_safe

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_OUTPUT_DIR = _PROJECT_ROOT / "data" / "output"
_WIDE_CSV = _OUTPUT_DIR / "gold_facilities_wide.csv"
_LONG_CSV = _OUTPUT_DIR / "gold_facilities_long.csv"
_FULL_JSON = _OUTPUT_DIR / "facilities_full.json"
_ANOMALIES_CSV = _OUTPUT_DIR / "anomalies.csv"


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="VirtueConnect — Healthcare Truth Layer",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data
def load_wide_table() -> pd.DataFrame:
    if not _WIDE_CSV.exists():
        st.error(
            f"WIDE table not found at `{_WIDE_CSV}`. "
            "Run the pipeline first: `python -m pipelines.run_langgraph_pipeline`"
        )
        return pd.DataFrame()
    df = pd.read_csv(_WIDE_CSV)
    # Convert boolean columns
    for col in df.columns:
        if col.endswith("_value"):
            df[col] = df[col].map({"True": True, "False": False, True: True, False: False})
    return df


@st.cache_data
def load_long_table() -> pd.DataFrame:
    if not _LONG_CSV.exists():
        return pd.DataFrame()
    return pd.read_csv(_LONG_CSV)


@st.cache_data
def load_facilities_json() -> dict:
    if not _FULL_JSON.exists():
        return {}
    with open(_FULL_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_anomalies() -> pd.DataFrame:
    if not _ANOMALIES_CSV.exists():
        return pd.DataFrame()
    return pd.read_csv(_ANOMALIES_CSV)


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.title("🏥 VirtueConnect")
st.sidebar.markdown("*The Forensic Truth Layer for Healthcare*")

view = st.sidebar.radio(
    "Select View",
    ["NGO Dashboard", "PatientSafe"],
    index=0,
)

# Load data
df_wide = load_wide_table()
df_long = load_long_table()
facilities_data = load_facilities_json()
df_anomalies = load_anomalies()

if df_wide.empty:
    st.warning(
        "No pipeline output found. Please run the extraction pipeline first:\n\n"
        "```bash\npython -m pipelines.run_langgraph_pipeline\n```"
    )
    st.stop()


# ---------------------------------------------------------------------------
# NGO Dashboard View
# ---------------------------------------------------------------------------

if view == "NGO Dashboard":
    st.title("VirtueConnect — NGO Dashboard")
    st.markdown("Evidence-backed healthcare capability mapping for Ghana")

    # -- Sidebar filters --
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Filters")

    regions = ["All"] + sorted(df_wide["region"].dropna().unique().tolist())
    region_filter = st.sidebar.selectbox("Region", regions, index=0)

    service_filter = st.sidebar.selectbox(
        "Service Layer",
        ["All", "maternity", "trauma", "infrastructure"],
        index=0,
    )
    if service_filter == "All":
        service_filter = None

    # -- 3 Command Buttons --
    st.markdown("### Quick Commands")
    cmd_col1, cmd_col2, cmd_col3 = st.columns(3)

    with cmd_col1:
        cmd1 = st.button(
            "📊 Resource Distribution",
            help="Count facilities with Safe C-Section by Region",
            use_container_width=True,
        )
    with cmd_col2:
        cmd2 = st.button(
            "🗺️ Cold Spots",
            help="Identify medical deserts for key capabilities",
            use_container_width=True,
        )
    with cmd_col3:
        cmd3 = st.button(
            "⚠️ Validation Report",
            help="List facilities with High Risk Anomalies",
            use_container_width=True,
        )

    # -- Command 1: Resource Distribution --
    if cmd1:
        st.markdown("### Resource Distribution: Safe C-Section by Region")
        st.markdown(
            "*Facilities where c_section=TRUE and no ANOMALY_HIGH flag*"
        )

        df_filtered = df_wide.copy()
        if region_filter and region_filter != "All":
            df_filtered = df_filtered[df_filtered["region"] == region_filter]

        # Safe C-section: c_section_value=True AND has_anomaly_high != True
        safe_mask = (
            (df_filtered["c_section_value"] == True) &
            (df_filtered["has_anomaly_high"] != True)
        )
        df_safe = df_filtered[safe_mask]

        if df_safe.empty:
            st.info("No facilities with verified safe C-section capability found.")
        else:
            # Group by region
            region_counts = df_safe.groupby("region").size().reset_index(name="count")
            region_counts = region_counts.sort_values("count", ascending=False)

            st.bar_chart(region_counts.set_index("region")["count"])
            st.dataframe(region_counts, use_container_width=True, hide_index=True)

            st.markdown(f"**Total:** {len(df_safe)} facilities with safe C-section")

    # -- Command 2: Cold Spots --
    if cmd2:
        st.markdown("### Cold Spots — Medical Desert Analysis")
        render_region_gaps_summary(df_wide)

        # Show action card for selected region + capability
        st.markdown("---")
        st.markdown("### Generate Action Plan")
        ac_col1, ac_col2 = st.columns(2)
        with ac_col1:
            ac_region = st.selectbox(
                "Region for Action Plan",
                sorted(df_wide["region"].dropna().unique().tolist()),
                key="ac_region",
            )
        with ac_col2:
            ac_cap = st.selectbox(
                "Gap Capability",
                [
                    "ultrasound_ob", "blood_bank", "c_section",
                    "operating_room", "xray", "emergency_24_7",
                    "lab_basic", "pharmacy", "ambulance",
                ],
                key="ac_cap",
            )
        if ac_region and ac_cap:
            render_action_card(df_wide, ac_region, ac_cap)

    # -- Command 3: Validation Report --
    if cmd3:
        st.markdown("### Validation Report — High Risk Anomalies")

        if df_anomalies.empty:
            st.info("No anomalies found. Run the pipeline to generate validation results.")
        else:
            df_anom_filtered = df_anomalies.copy()
            if region_filter and region_filter != "All":
                # Join with wide table to get region
                fid_region = df_wide[["facility_id", "region"]].drop_duplicates()
                df_anom_filtered = df_anom_filtered.merge(
                    fid_region, on="facility_id", how="left"
                )
                df_anom_filtered = df_anom_filtered[
                    df_anom_filtered["region"] == region_filter
                ]

            # Summary metrics
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Total Anomalies", len(df_anom_filtered))
            with m2:
                high = len(df_anom_filtered[df_anom_filtered["anomaly_type"] == "ANOMALY_HIGH"])
                st.metric("ANOMALY_HIGH", high)
            with m3:
                risk = len(df_anom_filtered[df_anom_filtered["anomaly_type"] == "RISK_HIGH"])
                st.metric("RISK_HIGH", risk)

            st.dataframe(
                df_anom_filtered[[
                    "facility_id", "facility_name", "bundle_name",
                    "anomaly_type", "severity", "reason", "required_missing",
                ]],
                use_container_width=True,
                hide_index=True,
            )

            # CSV export
            csv = df_anom_filtered.to_csv(index=False)
            st.download_button(
                "📥 Download Anomalies CSV",
                csv, "anomalies_report.csv", "text/csv",
            )

    # -- Map --
    st.markdown("---")
    st.markdown("### Facility Map")
    render_map(df_wide, service_filter=service_filter, region_filter=region_filter)

    # -- Facility Detail --
    st.markdown("---")
    st.markdown("### Facility Detail")
    selected_fid = render_facility_selector(df_wide)

    if selected_fid and str(selected_fid) in facilities_data:
        fdata = facilities_data[str(selected_fid)]
        st.markdown(f"**{fdata.get('name', 'Unknown')}** — {fdata.get('region', '')}")

        tab1, tab2, tab3 = st.tabs([
            "Forensic Evidence", "Anomalies", "Raw Data",
        ])

        with tab1:
            render_forensic_evidence(fdata, selected_fid)

        with tab2:
            render_anomalies(fdata.get("anomalies", []))

        with tab3:
            st.json(fdata)


# ---------------------------------------------------------------------------
# PatientSafe View
# ---------------------------------------------------------------------------

elif view == "PatientSafe":
    render_patient_safe(
        df_wide,
        facilities_json_path=str(_FULL_JSON) if _FULL_JSON.exists() else None,
    )
