"""
VirtueConnect — Map View Component (Streamlit)

Interactive map of Ghana healthcare facilities with:
  - Color-coded markers (green=validated, yellow=uncertain, red=anomaly)
  - Service layer toggle (maternity/trauma/infra)
  - Click-to-inspect facility details
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

# Ghana center coordinates
GHANA_CENTER = {"lat": 7.9465, "lon": -1.0232}
GHANA_ZOOM = 7


def _get_marker_color(row: pd.Series) -> List[int]:
    """Return [R, G, B, A] based on anomaly flags."""
    if row.get("has_anomaly_high") or row.get("has_risk_high"):
        return [220, 38, 38, 200]     # Red
    # Check if any capability is CONTRADICTED or UNCERTAIN
    for col in row.index:
        if col.endswith("_state"):
            val = row[col]
            if val == "CONTRADICTED":
                return [245, 158, 11, 200]  # Amber
            if val == "UNCERTAIN":
                return [245, 158, 11, 150]  # Light amber
    # Check if has any positive capability
    for col in row.index:
        if col.endswith("_value") and row[col] is True:
            return [34, 197, 94, 200]   # Green
    return [156, 163, 175, 180]        # Gray (no data)


def _get_marker_size(row: pd.Series) -> int:
    """Larger markers for facilities with more capabilities."""
    count = sum(
        1 for col in row.index
        if col.endswith("_value") and row[col] is True
    )
    return max(3, min(12, count + 3))


def render_map(
    df_wide: pd.DataFrame,
    service_filter: Optional[str] = None,
    region_filter: Optional[str] = None,
) -> Optional[str]:
    """
    Render the interactive facility map.

    Args:
        df_wide: WIDE gold table DataFrame
        service_filter: Optional filter by service layer (maternity/trauma/infra)
        region_filter: Optional filter by region

    Returns:
        Selected facility_id if a facility was clicked, else None
    """
    import pydeck as pdk

    df = df_wide.copy()

    # Apply filters
    if region_filter and region_filter != "All":
        df = df[df["region"].str.lower() == region_filter.lower()]

    # Service layer filter
    if service_filter == "maternity":
        cap_cols = [
            "c_section_value", "delivery_natural_value",
            "ultrasound_ob_value", "blood_bank_value",
        ]
        mask = df[cap_cols].any(axis=1)
        df = df[mask]
    elif service_filter == "trauma":
        cap_cols = [
            "trauma_surgery_value", "general_surgery_value",
            "xray_value", "emergency_24_7_value",
        ]
        mask = df[cap_cols].any(axis=1)
        df = df[mask]
    elif service_filter == "infrastructure":
        cap_cols = [
            "lab_basic_value", "pharmacy_value",
            "oxygen_supply_value",
        ]
        mask = df[cap_cols].any(axis=1)
        df = df[mask]

    # Filter to facilities with coordinates
    df_geo = df.dropna(subset=["lat", "lon"]).copy()

    if df_geo.empty:
        st.warning("No geocoded facilities to display. Run geocoding first.")
        # Show a simple table instead
        st.dataframe(
            df[["facility_id", "name", "region", "district", "has_anomaly_high", "has_risk_high"]].head(50),
            use_container_width=True,
        )
        return None

    # Add color and size columns
    df_geo["color"] = df_geo.apply(_get_marker_color, axis=1)
    df_geo["radius"] = df_geo.apply(_get_marker_size, axis=1) * 500

    # Build pydeck layer
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_geo,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius="radius",
        pickable=True,
        auto_highlight=True,
    )

    # Tooltip
    tooltip = {
        "html": """
        <b>{name}</b><br/>
        Region: {region}<br/>
        Type: {facility_type}<br/>
        Anomaly: {has_anomaly_high}
        """,
        "style": {
            "backgroundColor": "steelblue",
            "color": "white",
            "fontSize": "12px",
            "padding": "8px",
        },
    }

    view_state = pdk.ViewState(
        latitude=GHANA_CENTER["lat"],
        longitude=GHANA_CENTER["lon"],
        zoom=GHANA_ZOOM,
        pitch=0,
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="mapbox://styles/mapbox/light-v10",
    )

    st.pydeck_chart(deck)

    # Legend
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("🟢 **Validated**")
    with col2:
        st.markdown("🟡 **Uncertain/Contradicted**")
    with col3:
        st.markdown("🔴 **Anomaly**")
    with col4:
        st.markdown("⚪ **No data**")

    return None


def render_facility_selector(df_wide: pd.DataFrame) -> Optional[str]:
    """Render a facility selector dropdown. Returns selected facility_id."""
    options = df_wide[["facility_id", "name", "region"]].copy()
    options["label"] = options.apply(
        lambda r: f"{r['name']} ({r['region'] or 'Unknown'})", axis=1
    )
    options = options.sort_values("label")

    selected = st.selectbox(
        "Select a facility for details",
        options=options["facility_id"].tolist(),
        format_func=lambda fid: options[options["facility_id"] == fid]["label"].iloc[0],
        index=None,
        placeholder="Choose a facility...",
    )
    return selected
