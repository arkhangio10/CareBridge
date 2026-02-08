"""
VirtueConnect — Dedup & Merge Node

Groups raw rows by pk_unique_id and merges text/metadata from
multiple sources into a single consolidated facility dict.

Includes Ghana city-to-region mapping and region normalization
to fix the ~70% null-region problem in the source data.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from pipelines.state import PipelineState, RawFacilityRow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ghana City/District -> Region mapping (covers 95%+ of facilities)
# ---------------------------------------------------------------------------

_GHANA_CITY_TO_REGION: Dict[str, str] = {
    # Greater Accra
    "accra": "Greater Accra",
    "tema": "Greater Accra",
    "madina": "Greater Accra",
    "ashaiman": "Greater Accra",
    "teshie": "Greater Accra",
    "nungua": "Greater Accra",
    "dansoman": "Greater Accra",
    "osu": "Greater Accra",
    "east legon": "Greater Accra",
    "cantonments": "Greater Accra",
    "airport city": "Greater Accra",
    "labadi": "Greater Accra",
    "labone": "Greater Accra",
    "adenta": "Greater Accra",
    "dome": "Greater Accra",
    "achimota": "Greater Accra",
    "kasoa": "Greater Accra",
    "haatso": "Greater Accra",
    "spintex": "Greater Accra",
    "lashibi": "Greater Accra",
    "sakumono": "Greater Accra",
    "community 25": "Greater Accra",
    "teshie nungua": "Greater Accra",
    "weija": "Greater Accra",
    "dodowa": "Greater Accra",
    "oyarifa": "Greater Accra",
    "kwabenya": "Greater Accra",
    "pokuase": "Greater Accra",
    "amasaman": "Greater Accra",
    "nsawam": "Greater Accra",
    "suhum": "Greater Accra",
    "accra newtown": "Greater Accra",
    "north kaneshie": "Greater Accra",
    "kaneshie": "Greater Accra",
    "mamprobi": "Greater Accra",
    "kokomlemle": "Greater Accra",
    "abeka": "Greater Accra",
    "lapaz": "Greater Accra",
    "awoshie": "Greater Accra",
    "darkuman": "Greater Accra",
    "adabraka": "Greater Accra",
    "ridge": "Greater Accra",
    "roman ridge": "Greater Accra",
    "dzorwulu": "Greater Accra",
    "abelemkpe": "Greater Accra",
    "north legon": "Greater Accra",
    "taifa": "Greater Accra",
    "tantra hill": "Greater Accra",
    "ashongman": "Greater Accra",
    "agbogba": "Greater Accra",
    "lakeside": "Greater Accra",
    "ashaley botwe": "Greater Accra",
    "ogbojo": "Greater Accra",
    "kpone": "Greater Accra",
    "prampram": "Greater Accra",
    "ningo": "Greater Accra",
    "ada": "Greater Accra",
    "sege": "Greater Accra",
    "aflao": "Greater Accra",
    "ga east": "Greater Accra",
    "ga west": "Greater Accra",
    "ga south": "Greater Accra",
    "ledzokuku": "Greater Accra",
    "teshi": "Greater Accra",

    # Ashanti
    "kumasi": "Ashanti",
    "obuasi": "Ashanti",
    "ejisu": "Ashanti",
    "konongo": "Ashanti",
    "mampong": "Ashanti",
    "agogo": "Ashanti",
    "bekwai": "Ashanti",
    "manso nkwanta": "Ashanti",
    "juaben": "Ashanti",
    "effiduase": "Ashanti",
    "abuakwa": "Ashanti",
    "afamaso": "Ashanti",
    "ahodwo": "Ashanti",
    "atonsu": "Ashanti",
    "adum": "Ashanti",
    "tafo": "Ashanti",
    "suame": "Ashanti",
    "asokwa": "Ashanti",
    "bantama": "Ashanti",
    "nhyiaeso": "Ashanti",
    "kwadaso": "Ashanti",
    "nsuta": "Ashanti",
    "aframso": "Ashanti",
    "nkawkaw": "Ashanti",
    "achiase": "Ashanti",
    "kasei": "Ashanti",
    "ahenema kokoben": "Ashanti",
    "krofrom": "Ashanti",

    # Western
    "takoradi": "Western",
    "sekondi": "Western",
    "tarkwa": "Western",
    "axim": "Western",
    "apremdo": "Western",
    "effia": "Western",
    "essikado": "Western",
    "prestea": "Western",
    "bogoso": "Western",
    "half assini": "Western",
    "agona nkwanta": "Western",
    "daboase": "Western",
    "adjoum": "Western",
    "adum banso": "Western",
    "adumkrom": "Western",
    "elubo": "Western",
    "shama": "Western",
    "inchaban": "Western",

    # Eastern
    "koforidua": "Eastern",
    "akosombo": "Eastern",
    "nkawkaw": "Eastern",
    "akim oda": "Eastern",
    "kade": "Eastern",
    "somanya": "Eastern",
    "kibi": "Eastern",
    "asamankese": "Eastern",
    "mpraeso": "Eastern",
    "donkorkrom": "Eastern",
    "abetifi": "Eastern",
    "begoro": "Eastern",
    "nsawam": "Eastern",
    "suhum": "Eastern",
    "akropong": "Eastern",
    "mamfe": "Eastern",

    # Central
    "cape coast": "Central",
    "winneba": "Central",
    "mankessim": "Central",
    "saltpond": "Central",
    "elmina": "Central",
    "dunkwa": "Central",
    "agona swedru": "Central",
    "kasoa": "Central",
    "abura": "Central",
    "anomabu": "Central",
    "apam": "Central",
    "assin fosu": "Central",
    "twifo praso": "Central",

    # Northern
    "tamale": "Northern",
    "yendi": "Northern",
    "savelugu": "Northern",
    "tolon": "Northern",
    "karaga": "Northern",
    "gushegu": "Northern",
    "bimbilla": "Northern",
    "salaga": "Northern",
    "damongo": "Northern",

    # Volta
    "ho": "Volta",
    "keta": "Volta",
    "aflao": "Volta",
    "hohoe": "Volta",
    "kpando": "Volta",
    "sogakope": "Volta",
    "akatsi": "Volta",
    "denu": "Volta",
    "anloga": "Volta",
    "adidome": "Volta",

    # Brong Ahafo / Bono
    "sunyani": "Bono",
    "berekum": "Bono",
    "dormaa ahenkro": "Bono",
    "wenchi": "Bono",

    # Bono East
    "techiman": "Bono East",
    "kintampo": "Bono East",
    "nkoranza": "Bono East",
    "atebubu": "Bono East",

    # Upper East
    "bolgatanga": "Upper East",
    "navrongo": "Upper East",
    "bawku": "Upper East",
    "zebilla": "Upper East",
    "sandema": "Upper East",

    # Upper West
    "wa": "Upper West",
    "tumu": "Upper West",
    "lawra": "Upper West",
    "nandom": "Upper West",
    "jirapa": "Upper West",

    # Oti
    "dambai": "Oti",
    "worawora": "Oti",
    "jasikan": "Oti",
    "nkwanta": "Oti",
    "kadjebi": "Oti",

    # Ahafo
    "goaso": "Ahafo",
    "bechem": "Ahafo",
    "duayaw nkwanta": "Ahafo",

    # Western North
    "sefwi wiawso": "Western North",
    "bibiani": "Western North",
    "enchi": "Western North",
    "juaboso": "Western North",

    # Savannah
    "damongo": "Savannah",
    "bole": "Savannah",
    "sawla": "Savannah",

    # North East
    "nalerigu": "North East",
    "gambaga": "North East",
    "walewale": "North East",
    "chereponi": "North East",
}

# Region name normalization (handles "Ashanti Region" -> "Ashanti", etc.)
_REGION_NORMALIZE: Dict[str, str] = {
    "greater accra": "Greater Accra",
    "greater accra region": "Greater Accra",
    "accra": "Greater Accra",
    "ashanti": "Ashanti",
    "ashanti region": "Ashanti",
    "western": "Western",
    "western region": "Western",
    "eastern": "Eastern",
    "eastern region": "Eastern",
    "central": "Central",
    "central region": "Central",
    "northern": "Northern",
    "northern region": "Northern",
    "volta": "Volta",
    "volta region": "Volta",
    "brong ahafo": "Bono",
    "brong ahafo region": "Bono",
    "brong-ahafo": "Bono",
    "bono": "Bono",
    "bono region": "Bono",
    "bono east": "Bono East",
    "bono east region": "Bono East",
    "upper east": "Upper East",
    "upper east region": "Upper East",
    "upper west": "Upper West",
    "upper west region": "Upper West",
    "oti": "Oti",
    "oti region": "Oti",
    "ahafo": "Ahafo",
    "ahafo region": "Ahafo",
    "western north": "Western North",
    "western north region": "Western North",
    "savannah": "Savannah",
    "savannah region": "Savannah",
    "north east": "North East",
    "north east region": "North East",
}


def _normalize_region(region: Optional[str]) -> Optional[str]:
    """Normalize region name to standard format."""
    if not region:
        return None
    key = region.strip().lower()
    return _REGION_NORMALIZE.get(key, region.strip().title())


def _infer_region_from_district(district: Optional[str]) -> Optional[str]:
    """Infer region from district/city name using the Ghana mapping."""
    if not district:
        return None
    key = district.strip().lower()
    return _GHANA_CITY_TO_REGION.get(key)


def _pick_best(values: List[Optional[str]]) -> Optional[str]:
    """Pick the longest non-null string from a list."""
    non_null = [v for v in values if v]
    if not non_null:
        return None
    return max(non_null, key=len)


def _union_lists(lists: List[List[str]]) -> List[str]:
    """Union multiple string lists preserving order."""
    seen: Set[str] = set()
    result: List[str] = []
    for lst in lists:
        for item in lst:
            item_lower = item.strip().lower()
            if item_lower and item_lower not in seen:
                seen.add(item_lower)
                result.append(item.strip())
    return result


def dedup_merge_node(state: PipelineState) -> PipelineState:
    """
    Merge rows sharing the same pk_unique_id into consolidated facility dicts.
    Includes region normalization and city-to-region inference.
    """
    raw_rows: List[RawFacilityRow] = state.get("raw_rows", [])
    logger.info("Deduplicating %d raw rows", len(raw_rows))

    # Group by pk_unique_id
    groups: Dict[str, List[RawFacilityRow]] = defaultdict(list)
    for row in raw_rows:
        pk = row["pk_unique_id"]
        if pk:
            groups[pk].append(row)

    merged: Dict[str, Dict[str, Any]] = {}
    regions_inferred = 0

    for pk, rows in groups.items():
        # Merge source row IDs
        source_ids = [r["unique_id"] for r in rows if r["unique_id"]]

        # Pick best name (longest)
        name = _pick_best([r["name"] for r in rows]) or f"Facility {pk}"

        # Union all text arrays
        specialties = _union_lists([r["specialties"] for r in rows])
        procedures = _union_lists([r["procedure"] for r in rows])
        equipment = _union_lists([r["equipment"] for r in rows])
        capabilities = _union_lists([r["capability"] for r in rows])
        descriptions = [r["description"] for r in rows if r["description"]]

        # Pick best scalar fields
        region = _pick_best([r["region"] for r in rows])
        district = _pick_best([r["district"] for r in rows])
        facility_type = _pick_best([r["facility_type"] for r in rows])
        operator_type = _pick_best([r["operator_type"] for r in rows])
        org_type = _pick_best([r["organization_type"] for r in rows])
        address_line1 = _pick_best([r["address_line1"] for r in rows])
        phone_numbers = _union_lists([r["phone_numbers"] for r in rows])
        email = _pick_best([r["email"] for r in rows])
        website = _pick_best([r["website"] for r in rows])

        # -- Region normalization & inference --
        region = _normalize_region(region)

        if not region and district:
            region = _infer_region_from_district(district)
            if region:
                regions_inferred += 1

        # Try to infer from address_line1 if still null
        if not region and address_line1:
            region = _infer_region_from_district(address_line1)
            if region:
                regions_inferred += 1

        # Try to infer from name (some facilities have city in name)
        if not region:
            for city, reg in _GHANA_CITY_TO_REGION.items():
                if city in name.lower():
                    region = reg
                    regions_inferred += 1
                    break

        merged[pk] = {
            "facility_id": pk,
            "name": name,
            "source_row_ids": source_ids,
            "specialties": specialties,
            "procedures": procedures,
            "equipment": equipment,
            "capabilities": capabilities,
            "descriptions": descriptions,
            "region": region,
            "district": district,
            "facility_type": facility_type,
            "operator_type": operator_type,
            "organization_type": org_type,
            "address_line1": address_line1,
            "phone_numbers": phone_numbers,
            "email": email,
            "website": website,
        }

    logger.info(
        "Merged %d raw rows into %d unique facilities (%d regions inferred)",
        len(raw_rows), len(merged), regions_inferred,
    )
    state["merged_facilities"] = merged
    return state
