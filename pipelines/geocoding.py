"""
VirtueConnect — Geocoding Utility

Geocodes facility addresses using:
  1. Built-in Ghana city/district coordinate table (instant, no API)
  2. Fallback to geopy Nominatim API (slow, rate-limited)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from models.facility import FacilityRecord

logger = logging.getLogger(__name__)

_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "geocache.json"

# ---------------------------------------------------------------------------
# Built-in Ghana coordinates (covers 90%+ of facilities, no API needed)
# ---------------------------------------------------------------------------

GHANA_COORDS: Dict[str, Tuple[float, float]] = {
    # Greater Accra
    "accra": (5.6037, -0.1870),
    "tema": (5.6698, -0.0166),
    "madina": (5.6735, -0.1674),
    "ashaiman": (5.6945, -0.0388),
    "teshie": (5.5794, -0.1069),
    "nungua": (5.5922, -0.0770),
    "dansoman": (5.5388, -0.2649),
    "osu": (5.5560, -0.1760),
    "east legon": (5.6350, -0.1580),
    "cantonments": (5.5745, -0.1739),
    "adenta": (5.7019, -0.1626),
    "dome": (5.6551, -0.2267),
    "achimota": (5.6148, -0.2279),
    "kasoa": (5.5342, -0.4219),
    "haatso": (5.6595, -0.2024),
    "spintex": (5.6381, -0.0801),
    "sakumono": (5.6282, -0.0396),
    "weija": (5.5618, -0.3344),
    "dodowa": (5.8819, -0.0944),
    "pokuase": (5.6965, -0.2989),
    "amasaman": (5.7039, -0.2869),
    "accra newtown": (5.5637, -0.2102),
    "kaneshie": (5.5703, -0.2398),
    "lapaz": (5.6089, -0.2559),
    "adabraka": (5.5574, -0.2123),
    "ridge": (5.5636, -0.2048),
    "dzorwulu": (5.6090, -0.1974),
    "abelemkpe": (5.5960, -0.2030),
    "tantra hill": (5.6380, -0.2397),
    "ashongman": (5.6900, -0.2100),
    "lakeside": (5.6726, -0.1276),
    "kpone": (5.6888, 0.0547),
    "prampram": (5.7170, 0.1171),
    "ada": (5.7860, 0.6264),
    "oyarifa": (5.7070, -0.1430),
    "taifa": (5.6590, -0.2448),
    "north legon": (5.6580, -0.1890),

    # Ashanti
    "kumasi": (6.6885, -1.6244),
    "obuasi": (6.2064, -1.6651),
    "ejisu": (6.7279, -1.4700),
    "konongo": (6.6174, -1.2147),
    "mampong": (7.0653, -1.3993),
    "agogo": (6.7945, -1.0797),
    "bekwai": (6.4545, -1.5776),
    "effiduase": (6.8214, -1.3971),
    "abuakwa": (6.7155, -1.5300),
    "ahodwo": (6.6680, -1.6360),
    "nkawkaw": (6.5514, -0.7680),
    "kasei": (7.0800, -1.4200),
    "krofrom": (6.7100, -1.6300),
    "ahenema kokoben": (6.6580, -1.6570),
    "nsuta": (6.8800, -1.5100),

    # Western
    "takoradi": (4.8920, -1.7554),
    "sekondi": (4.9348, -1.7132),
    "tarkwa": (5.3011, -1.9928),
    "axim": (4.8689, -2.2408),
    "apremdo": (4.9200, -1.7600),
    "prestea": (5.4333, -2.1458),
    "bogoso": (5.5418, -2.0900),
    "agona nkwanta": (5.0600, -1.3800),
    "daboase": (5.1500, -1.6200),
    "shama": (5.0003, -1.6335),

    # Eastern
    "koforidua": (6.0894, -0.2586),
    "akosombo": (6.2935, 0.0486),
    "akim oda": (5.9246, -0.9865),
    "somanya": (6.1020, 0.0153),
    "kibi": (6.1629, -0.5521),
    "asamankese": (5.8638, -0.6673),
    "begoro": (6.3880, -0.3790),
    "nsawam": (5.8059, -0.3490),
    "suhum": (6.0403, -0.4473),
    "akropong": (5.9808, -0.0890),

    # Central
    "cape coast": (5.1036, -1.2466),
    "winneba": (5.3530, -0.6240),
    "mankessim": (5.2747, -1.0197),
    "saltpond": (5.2094, -1.0620),
    "elmina": (5.0843, -1.3511),
    "agona swedru": (5.5354, -0.6977),
    "dunkwa": (5.9643, -1.7769),
    "abura": (5.1100, -1.2300),
    "assin fosu": (5.7312, -1.2333),

    # Northern
    "tamale": (9.4034, -0.8393),
    "yendi": (9.4427, -0.0099),
    "savelugu": (9.6255, -0.8268),
    "gushegu": (9.8677, -0.1791),
    "bimbilla": (8.8540, -0.0490),
    "damongo": (9.0808, -1.8217),

    # Volta
    "ho": (6.6028, 0.4712),
    "keta": (5.9265, 0.9798),
    "aflao": (6.1192, 1.1919),
    "hohoe": (7.1512, 0.4744),
    "kpando": (6.9986, 0.2990),
    "sogakope": (6.0085, 0.5932),
    "akatsi": (6.1262, 0.8014),
    "adidome": (6.1000, 0.4900),

    # Bono
    "sunyani": (7.3367, -2.3286),
    "berekum": (7.4528, -2.5834),
    "dormaa ahenkro": (7.3500, -2.9600),
    "wenchi": (7.7375, -2.1016),

    # Bono East
    "techiman": (7.5870, -1.9373),
    "kintampo": (8.0574, -1.7302),
    "nkoranza": (7.5539, -1.7075),
    "atebubu": (7.7512, -0.9826),

    # Upper East
    "bolgatanga": (10.7854, -0.8480),
    "navrongo": (10.8936, -1.0920),
    "bawku": (11.0611, -0.2405),
    "zebilla": (10.8869, -0.4630),

    # Upper West
    "wa": (10.0613, -2.5019),
    "tumu": (10.8844, -1.9847),
    "lawra": (10.6400, -2.9000),
    "jirapa": (10.5891, -2.7171),

    # Oti
    "worawora": (7.5236, 0.3700),
    "jasikan": (7.3965, 0.4477),
    "nkwanta": (8.2600, 0.0800),
    "dambai": (7.9700, 0.1700),

    # Ahafo
    "goaso": (6.8014, -2.5178),
    "bechem": (7.0933, -2.0216),

    # Western North
    "bibiani": (6.4594, -2.3272),
    "sefwi wiawso": (6.2100, -2.4800),
    "enchi": (5.8250, -2.8200),

    # Savannah
    "bole": (9.0328, -2.4844),
    "sawla": (9.2800, -2.4000),

    # North East
    "nalerigu": (10.5200, -0.3700),
    "gambaga": (10.5300, -0.4400),
    "walewale": (10.3600, -0.8000),

    # Zabzugu Tatale
    "zabzugu tatale": (9.6600, 0.0400),
    "zabzugu": (9.6600, 0.0400),

    # Lamboya
    "lamboya": (10.8000, -0.4500),
}


def _get_geocoder():
    """Lazy import geopy Nominatim."""
    try:
        from geopy.geocoders import Nominatim
        return Nominatim(user_agent="virtueconnect-hackathon-v1", timeout=10)
    except ImportError:
        return None


def _load_cache() -> Dict[str, Tuple[Optional[float], Optional[float]]]:
    """Load geocode cache from disk."""
    if _CACHE_PATH.exists():
        try:
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {k: tuple(v) for k, v in data.items()}
        except Exception:
            pass
    return {}


def _save_cache(cache: Dict[str, Tuple[Optional[float], Optional[float]]]) -> None:
    """Save geocode cache to disk."""
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump({k: list(v) for k, v in cache.items()}, f, indent=2)


def _lookup_builtin(record: FacilityRecord) -> Tuple[Optional[float], Optional[float]]:
    """
    Look up coordinates from the built-in Ghana city table.
    Tries district, then address_line1, then facility name.
    """
    # Try district
    if record.district:
        key = record.district.strip().lower()
        if key in GHANA_COORDS:
            return GHANA_COORDS[key]

    # Try address_line1
    if record.address_line1:
        for city, coords in GHANA_COORDS.items():
            if city in record.address_line1.lower():
                return coords

    # Try facility name
    if record.name:
        name_lower = record.name.lower()
        for city, coords in GHANA_COORDS.items():
            if city in name_lower:
                return coords

    return None, None


def geocode_facility(
    record: FacilityRecord,
    cache: Dict[str, Tuple[Optional[float], Optional[float]]],
    use_api: bool = False,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Geocode a single facility. Returns (lat, lon) or (None, None).

    Strategy:
    1. Built-in Ghana coordinate table (instant)
    2. Cache lookup
    3. Nominatim API (optional, slow)
    """
    # Phase 1: Built-in lookup (instant)
    lat, lon = _lookup_builtin(record)
    if lat is not None:
        return lat, lon

    # Build query key for cache/API
    parts = []
    if record.district:
        parts.append(record.district)
    if record.region:
        parts.append(record.region)
    parts.append("Ghana")
    query = ", ".join(parts)

    if not query or query == "Ghana":
        return None, None

    # Phase 2: Cache lookup
    if query in cache:
        return cache[query]

    # Phase 3: API fallback (only if enabled)
    if not use_api:
        return None, None

    geocoder = _get_geocoder()
    if geocoder is None:
        return None, None

    try:
        location = geocoder.geocode(query)
        if location:
            result = (location.latitude, location.longitude)
        else:
            result = (None, None)
    except Exception as e:
        logger.warning("Geocoding API failed for '%s': %s", query, e)
        result = (None, None)

    cache[query] = result

    # Respect Nominatim rate limit (1 req/sec)
    time.sleep(1.1)

    return result


def geocode_all_facilities(
    facilities: Dict[str, FacilityRecord],
    max_facilities: Optional[int] = None,
) -> int:
    """
    Geocode all facilities that lack lat/lon.
    Mutates FacilityRecord objects in place.

    Args:
        facilities: Dict of facility_id -> FacilityRecord
        max_facilities: Optional limit (for rate limiting during dev)

    Returns:
        Number of facilities successfully geocoded.
    """
    cache = _load_cache()
    geocoded = 0
    total = 0

    for fid, record in facilities.items():
        if record.lat is not None and record.lon is not None:
            continue

        if max_facilities and total >= max_facilities:
            break

        total += 1
        lat, lon = geocode_facility(record, cache)
        if lat is not None and lon is not None:
            record.lat = lat
            record.lon = lon
            geocoded += 1

        # Save cache periodically
        if total % 50 == 0:
            _save_cache(cache)
            logger.info("Geocoded %d / %d facilities so far", geocoded, total)

    _save_cache(cache)
    logger.info(
        "Geocoding complete: %d / %d facilities geocoded (%d cached queries)",
        geocoded, total, len(cache),
    )
    return geocoded
