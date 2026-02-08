"""
VirtueConnect — Extractor Node (OpenAI GPT-4o)

Two-phase extraction:
  1. Rule-based pre-extraction using synonym patterns + negation detection
  2. LLM-based extraction via GPT-4o with constrained JSON output
     for ambiguous or complex cases

Also includes the Evidence Locator logic (char offsets).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from models.forensic_fields import Evidence, ForensicField, ValidationState, Polarity
from ontology.ontology import CAPABILITY_NAMES
from ontology.synonyms import (
    find_concepts_in_text,
    SPECIALTY_TO_CAPABILITIES,
    SYNONYM_MAP,
)
from ontology.negation import detect_polarity_in_sentence
from pipelines.state import Chunk, PipelineState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Extraction result (per capability, per facility)
# ---------------------------------------------------------------------------

class ExtractionFact:
    """Intermediate extraction result before reconciliation."""

    def __init__(
        self,
        capability: str,
        value: Optional[bool],
        state: ValidationState,
        confidence: float,
        evidence: List[Evidence],
        source: str = "rule",  # "rule" or "llm"
    ):
        self.capability = capability
        self.value = value
        self.state = state
        self.confidence = confidence
        self.evidence = evidence
        self.source = source

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability": self.capability,
            "value": self.value,
            "state": self.state.value,
            "confidence": self.confidence,
            "evidence": [e.model_dump() for e in self.evidence],
            "source": self.source,
        }


# ---------------------------------------------------------------------------
# Phase 1: Rule-based extraction
# ---------------------------------------------------------------------------

def _extract_from_structured(
    facility_data: Dict[str, Any],
    chunks: List[Chunk],
) -> Dict[str, ExtractionFact]:
    """
    Extract facts from structured columns (specialties, procedure, equipment).
    These get ASSERTED state.
    """
    facts: Dict[str, ExtractionFact] = {}

    # From specialties -> capabilities mapping
    specialties = facility_data.get("specialties", [])
    for spec in specialties:
        caps = SPECIALTY_TO_CAPABILITIES.get(spec, [])
        for cap in caps:
            if cap not in facts:
                facts[cap] = ExtractionFact(
                    capability=cap,
                    value=True,
                    state=ValidationState.ASSERTED,
                    confidence=0.85,
                    evidence=[Evidence(
                        row_id=facility_data.get("source_row_ids", [""])[0],
                        source_column="specialties",
                        snippet=spec,
                        evidence_type="structured",
                    )],
                    source="rule",
                )

    # From procedure/equipment/capability chunks (structured arrays)
    # NOTE: capability column is also structured data from the source
    for chunk in chunks:
        if chunk["source_column"] not in ("procedure", "equipment", "capability"):
            continue

        text = chunk["text"]
        concepts = find_concepts_in_text(text)

        for canonical, matched_term, start, end in concepts:
            # Handle FALSE indicators
            if canonical.endswith("_FALSE"):
                real_cap = canonical.replace("_FALSE", "")
                if real_cap in CAPABILITY_NAMES:
                    facts[real_cap] = ExtractionFact(
                        capability=real_cap,
                        value=False,
                        state=ValidationState.CONTRADICTED,
                        confidence=0.90,
                        evidence=[Evidence(
                            row_id=chunk["row_id"],
                            source_column=chunk["source_column"],
                            snippet=text,
                            evidence_type="structured",
                            char_start=start,
                            char_end=end,
                        )],
                        source="rule",
                    )
                continue

            if canonical not in CAPABILITY_NAMES:
                continue

            if canonical not in facts:
                facts[canonical] = ExtractionFact(
                    capability=canonical,
                    value=True,
                    state=ValidationState.ASSERTED,
                    confidence=0.90,
                    evidence=[Evidence(
                        row_id=chunk["row_id"],
                        source_column=chunk["source_column"],
                        snippet=text,
                        evidence_type="structured",
                        char_start=start,
                        char_end=end,
                    )],
                    source="rule",
                )

    # Direct string matching for common capability column values
    # (these are short phrases that may not match synonyms)
    capability_items = facility_data.get("capabilities", [])
    for item in capability_items:
        item_lower = item.strip().lower()

        # Direct keyword matches for capability array items
        direct_matches = {
            "always open": ("emergency_24_7", True),
            "has 24-hour emergency department": ("emergency_24_7", True),
            "24/7": ("emergency_24_7", True),
            "24 hours": ("emergency_24_7", True),
            "has operating theatre": ("operating_room", True),
            "has laboratory": ("lab_basic", True),
            "has laboratory services": ("lab_basic", True),
            "laboratory": ("lab_basic", True),
            "has pharmacy": ("pharmacy", True),
            "pharmacy": ("pharmacy", True),
            "has ambulance": ("ambulance", True),
            "ambulance": ("ambulance", True),
            "has x-ray": ("xray", True),
            "x-ray": ("xray", True),
            "has ultrasound": ("ultrasound_ob", True),
            "ultrasound": ("ultrasound_ob", True),
            "has blood bank": ("blood_bank", True),
            "blood bank": ("blood_bank", True),
            "has incubator": ("incubator", True),
            "incubator": ("incubator", True),
            "nicu": ("incubator", True),
            "has generator": ("generator_backup", True),
            "generator": ("generator_backup", True),
            "has oxygen": ("oxygen_supply", True),
            "oxygen": ("oxygen_supply", True),
            "has water supply": ("water_supply", True),
            "surgery": ("general_surgery", True),
            "surgical services": ("general_surgery", True),
            "maternity": ("delivery_natural", True),
            "delivery": ("delivery_natural", True),
            "anesthesia": ("anesthesia", True),
            "anaesthesia": ("anesthesia", True),
        }

        for keyword, (cap, value) in direct_matches.items():
            if keyword in item_lower and cap not in facts:
                facts[cap] = ExtractionFact(
                    capability=cap,
                    value=value,
                    state=ValidationState.ASSERTED,
                    confidence=0.85,
                    evidence=[Evidence(
                        row_id=facility_data.get("source_row_ids", [""])[0],
                        source_column="capability",
                        snippet=item,
                        evidence_type="structured",
                    )],
                    source="rule",
                )

    return facts


def _extract_from_freetext(
    chunks: List[Chunk],
) -> Dict[str, List[ExtractionFact]]:
    """
    Extract facts from free-text chunks (capability, description).
    Uses synonym matching + negation/referral detection.
    Returns multiple facts per capability (to be merged later).
    """
    facts: Dict[str, List[ExtractionFact]] = {}

    for chunk in chunks:
        if chunk["source_column"] not in ("capability", "description"):
            continue

        text = chunk["text"]
        concepts = find_concepts_in_text(text)

        for canonical, matched_term, start, end in concepts:
            # Handle FALSE indicators
            if canonical.endswith("_FALSE"):
                real_cap = canonical.replace("_FALSE", "")
                if real_cap in CAPABILITY_NAMES:
                    fact = ExtractionFact(
                        capability=real_cap,
                        value=False,
                        state=ValidationState.CONTRADICTED,
                        confidence=0.88,
                        evidence=[Evidence(
                            row_id=chunk["row_id"],
                            source_column=chunk["source_column"],
                            snippet=text,
                            evidence_type="free_text",
                            char_start=start,
                            char_end=end,
                        )],
                        source="rule",
                    )
                    facts.setdefault(real_cap, []).append(fact)
                continue

            if canonical not in CAPABILITY_NAMES:
                continue

            # Detect polarity
            polarity = detect_polarity_in_sentence(text, matched_term)

            if polarity == Polarity.DENY:
                value = False
                state = ValidationState.CONTRADICTED
                conf = 0.85
            elif polarity == Polarity.REFER_OUT:
                value = False
                state = ValidationState.CONTRADICTED
                conf = 0.88
            elif polarity == Polarity.AFFIRM:
                value = True
                state = ValidationState.EXTRACTED
                conf = 0.80
            else:
                value = None
                state = ValidationState.UNCERTAIN
                conf = 0.40

            fact = ExtractionFact(
                capability=canonical,
                value=value,
                state=state,
                confidence=conf,
                evidence=[Evidence(
                    row_id=chunk["row_id"],
                    source_column=chunk["source_column"],
                    snippet=text,
                    evidence_type="free_text",
                    char_start=start,
                    char_end=end,
                )],
                source="rule",
            )
            facts.setdefault(canonical, []).append(fact)

    return facts


# ---------------------------------------------------------------------------
# Phase 2: LLM-based extraction (for ambiguous cases)
# ---------------------------------------------------------------------------

_LLM_PROMPT_TEMPLATE = """You are a medical facility capability extractor for VirtueConnect, analysing healthcare facilities in Ghana.

TASK: Read ALL text chunks below about a facility and extract every capability you can find from this catalog:

CAPABILITIES TO LOOK FOR:
- c_section: caesarean section / CS delivery
- delivery_natural: vaginal delivery, maternity services, obstetrics & gynecology, labour ward, pregnancy and child birth
- ultrasound_ob: ultrasound scan, USG, sonography, echo
- incubator: neonatal incubator, NICU, neonatal care
- blood_bank: blood bank, blood transfusion, blood supply (FALSE if "donors required" / "family replacement")
- anesthesia: anesthesia/anaesthesia equipment
- anesthetist: anesthetist/anaesthetist/anesthesiologist on staff
- operating_room: operating theatre, major theatre, ultra-modern theatre, surgical suite (NOT "minor theatre")
- trauma_surgery: trauma surgery, emergency surgery, trauma care
- general_surgery: general surgery, surgical procedures, surgery department, "all aspects of surgical procedures"
- xray: X-ray, radiography, diagnostic imaging, radiology
- ambulance: ambulance, emergency transport
- emergency_24_7: 24/7, 24 hours, "always open", "round the clock", 24-hour emergency
- oxygen_supply: oxygen, medical oxygen, oxygen concentrator
- generator_backup: generator, backup generator, power backup
- water_supply: water supply, clean water, borehole
- lab_basic: laboratory, lab, laboratory services, lab testing, diagnostic lab, "conducts investigations"
- pharmacy: pharmacy, dispensary, pharmacy services, "dispensing drugs"

For each capability found, return a JSON object:
- "capability": the canonical name exactly as listed above
- "value": true (present), false (explicitly denied/referred), or null (ambiguous)
- "state": "EXTRACTED" if affirmed, "CONTRADICTED" if denied/referred/transferred, "UNCERTAIN" if vague
- "confidence": 0.0 to 1.0 (higher if explicit statement, lower if implied)
- "evidence_snippet": copy the EXACT text that supports your finding

CRITICAL RULES:
1. Be AGGRESSIVE in detection — if text says "Obstetrics and Gynecology services" that IS delivery_natural=true
2. If text says "Provides ultrasound scanning" or "USG and ECG Services" that IS ultrasound_ob=true
3. If text says "Laboratory" or "conducts investigations" that IS lab_basic=true
4. If text says "Pharmacy" or "dispensing drugs" or "Dispensary" that IS pharmacy=true
5. If text says "24/7" or "24 hours" or "Always open" that IS emergency_24_7=true
6. If text says "Surgery" with "theatre" or "operating" that IS both general_surgery=true AND operating_room=true
7. "refer/transfer" for a SPECIFIC service → that service is value=false, state=CONTRADICTED
8. "minor theatre" alone does NOT mean operating_room=true
9. Specialty "emergencyMedicine" → emergency_24_7=true
10. Specialty "gynecologyAndObstetrics" → delivery_natural=true
11. Specialty "generalSurgery" → general_surgery=true
12. Specialty "diagnosticRadiology" → xray=true
13. "NHIS accredited" is useful context but not a capability itself

Facility: {facility_name}

ALL DATA FOR THIS FACILITY:
{chunks_text}

Return a JSON object with key "capabilities" containing an array of findings. Extract EVERY capability you find evidence for. If nothing found, return {{"capabilities": []}}.
"""


def _llm_extract(
    facility_name: str,
    chunks: List[Chunk],
    client: Optional[OpenAI] = None,
) -> List[Dict[str, Any]]:
    """Call GPT-4o for extraction — sends ALL chunks for maximum coverage."""
    if client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("No OPENAI_API_KEY set, skipping LLM extraction")
            return []
        client = OpenAI(api_key=api_key)

    # Send ALL chunk types for maximum extraction coverage
    if not chunks:
        return []

    # Group chunks by source column for structured presentation
    chunks_by_source: Dict[str, List[str]] = {}
    for c in chunks:
        src = c["source_column"]
        chunks_by_source.setdefault(src, []).append(c["text"])

    chunks_text_parts = []
    for src, texts in chunks_by_source.items():
        chunks_text_parts.append(f"--- {src.upper()} ---")
        for t in texts:
            chunks_text_parts.append(f"  • {t}")
    chunks_text = "\n".join(chunks_text_parts)

    # Truncate to avoid token limits (keep under ~3000 tokens input)
    if len(chunks_text) > 6000:
        chunks_text = chunks_text[:6000] + "\n... [truncated]"

    prompt = _LLM_PROMPT_TEMPLATE.format(
        facility_name=facility_name,
        chunks_text=chunks_text,
    )

    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=2000,
        )
        content = response.choices[0].message.content or "{}"
        # Strip markdown code fences if present (```json ... ```)
        content = content.strip()
        if content.startswith("```"):
            # Remove opening fence
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline + 1:]
            # Remove closing fence
            if content.endswith("```"):
                content = content[:-3].strip()
        parsed = json.loads(content)
        # Handle {"capabilities": [...]} format (prompted)
        if isinstance(parsed, dict):
            return parsed.get("capabilities", parsed.get("results", []))
        if isinstance(parsed, list):
            return parsed
        return []
    except Exception as e:
        logger.error("LLM extraction failed for %s: %s", facility_name, e)
        return []


def _llm_facts_to_extraction(
    llm_results: List[Dict[str, Any]],
    chunks: List[Chunk],
) -> Dict[str, ExtractionFact]:
    """Convert LLM JSON results into ExtractionFact objects."""
    facts: Dict[str, ExtractionFact] = {}

    for item in llm_results:
        cap = item.get("capability", "")
        if cap not in CAPABILITY_NAMES:
            continue

        value_raw = item.get("value")
        if value_raw is None:
            value = None
        elif isinstance(value_raw, bool):
            value = value_raw
        else:
            value = str(value_raw).lower() == "true"

        state_str = item.get("state", "EXTRACTED")
        try:
            state = ValidationState(state_str)
        except ValueError:
            state = ValidationState.EXTRACTED

        confidence = float(item.get("confidence", 0.7))
        snippet = item.get("evidence_snippet", "")

        # Find the chunk that contains the snippet for offsets
        evidence = Evidence(
            row_id=chunks[0]["row_id"] if chunks else None,
            source_column="description",
            snippet=snippet,
            evidence_type="free_text",
        )

        for chunk in chunks:
            if snippet and snippet.lower() in chunk["text"].lower():
                idx = chunk["text"].lower().find(snippet.lower())
                evidence = Evidence(
                    row_id=chunk["row_id"],
                    source_column=chunk["source_column"],
                    snippet=snippet,
                    evidence_type="free_text",
                    char_start=chunk["char_start"] + idx,
                    char_end=chunk["char_start"] + idx + len(snippet),
                )
                break

        facts[cap] = ExtractionFact(
            capability=cap,
            value=value,
            state=state,
            confidence=confidence,
            evidence=[evidence],
            source="llm",
        )

    return facts


# ---------------------------------------------------------------------------
# Evidence Locator (enrich char offsets)
# ---------------------------------------------------------------------------

def _locate_evidence(
    facts: Dict[str, ExtractionFact],
    chunks: List[Chunk],
) -> None:
    """
    Ensure all evidence snippets have char_start / char_end set.
    Mutates facts in place.
    """
    for cap, fact in facts.items():
        for ev in fact.evidence:
            if ev.char_start is not None and ev.char_end is not None:
                continue  # already set
            if not ev.snippet:
                continue
            # Search through chunks for the snippet
            for chunk in chunks:
                if chunk["source_column"] == ev.source_column:
                    idx = chunk["text"].lower().find(ev.snippet.lower())
                    if idx >= 0:
                        # Create new evidence with offsets (Evidence is frozen)
                        ev_new = Evidence(
                            row_id=ev.row_id or chunk["row_id"],
                            source_column=ev.source_column,
                            snippet=ev.snippet,
                            evidence_type=ev.evidence_type,
                            char_start=chunk["char_start"] + idx,
                            char_end=chunk["char_start"] + idx + len(ev.snippet),
                        )
                        # Replace in list
                        fact.evidence = [
                            ev_new if e is ev else e for e in fact.evidence
                        ]
                        break


# ---------------------------------------------------------------------------
# Main node function
# ---------------------------------------------------------------------------

def extractor_node(state: PipelineState) -> PipelineState:
    """
    Two-phase extraction:
    1. Rule-based (synonym + negation) on all facilities
    2. LLM-based on facilities with text chunks (for extra coverage)

    Outputs extracted facts per facility.
    """
    merged = state.get("merged_facilities", {})
    all_chunks = state.get("chunks", {})
    use_llm = bool(os.environ.get("OPENAI_API_KEY"))

    logger.info(
        "Extracting capabilities for %d facilities (LLM=%s)",
        len(merged), use_llm,
    )

    openai_client = None
    if use_llm:
        openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    extracted: Dict[str, Dict[str, Any]] = {}

    for fid, data in merged.items():
        chunks = all_chunks.get(fid, [])

        # Phase 1: Rule-based structured extraction
        structured_facts = _extract_from_structured(data, chunks)

        # Phase 1b: Rule-based free-text extraction
        freetext_facts_multi = _extract_from_freetext(chunks)

        # Merge free-text facts (pick strongest signal per capability)
        freetext_facts: Dict[str, ExtractionFact] = {}
        for cap, fact_list in freetext_facts_multi.items():
            # Prefer CONTRADICTED > EXTRACTED > UNCERTAIN
            best = max(
                fact_list,
                key=lambda f: (
                    3 if f.state == ValidationState.CONTRADICTED else
                    2 if f.state == ValidationState.EXTRACTED else
                    1 if f.state == ValidationState.UNCERTAIN else 0,
                    f.confidence,
                ),
            )
            # Collect all evidence
            all_ev = []
            for f in fact_list:
                all_ev.extend(f.evidence)
            best.evidence = all_ev[:3]  # keep top 3

            # Boost confidence for multiple independent evidence
            if len(fact_list) > 1 and best.state == ValidationState.EXTRACTED:
                best.confidence = min(1.0, best.confidence + 0.05 * (len(fact_list) - 1))

            freetext_facts[cap] = best

        # Phase 2: LLM extraction (if enabled, for extra coverage)
        # Send ALL chunks to LLM for maximum extraction coverage
        llm_facts: Dict[str, ExtractionFact] = {}
        if use_llm and chunks:
            try:
                llm_results = _llm_extract(
                    data.get("name", f"Facility {fid}"),
                    chunks,  # send ALL chunks, not just text-only
                    openai_client,
                )
                llm_facts = _llm_facts_to_extraction(llm_results, chunks)
            except Exception as e:
                logger.error("LLM phase failed for %s: %s", fid, e)

        # Merge all facts: structured > rule-freetext > LLM
        combined: Dict[str, ExtractionFact] = {}

        # Start with LLM (lowest priority)
        combined.update(llm_facts)

        # Override with rule-based freetext
        for cap, fact in freetext_facts.items():
            if cap in combined:
                # Keep higher-priority source
                combined[cap] = fact
            else:
                combined[cap] = fact

        # Override with structured (highest priority for ASSERTED)
        for cap, fact in structured_facts.items():
            if cap in combined:
                existing = combined[cap]
                # Structured ASSERTED + freetext info -> keep asserted, add evidence
                fact.evidence = (fact.evidence + existing.evidence)[:3]
                if existing.state == ValidationState.CONTRADICTED:
                    # Free-text contradicts structured -> flag it
                    fact.state = ValidationState.CONTRADICTED
                    fact.value = False
                    fact.confidence = max(fact.confidence, existing.confidence)
            combined[cap] = fact

        # Locate evidence offsets
        _locate_evidence(combined, chunks)

        # Store as serializable dict
        extracted[fid] = {
            cap: fact.to_dict() for cap, fact in combined.items()
        }

    state["extracted"] = extracted
    logger.info("Extracted capabilities for %d facilities", len(extracted))
    return state
