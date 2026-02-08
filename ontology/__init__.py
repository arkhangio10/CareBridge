"""VirtueConnect ontology — capability catalog, synonyms, negation."""

from ontology.ontology import (
    CapabilityCategory,
    CapabilityDef,
    CAPABILITY_CATALOG,
    CAPABILITY_NAMES,
    MATERNITY_CAPS,
    TRAUMA_CAPS,
    INFRA_CAPS,
)
from ontology.synonyms import (
    SYNONYM_MAP,
    SPECIALTY_TO_CAPABILITIES,
    COMPILED_PATTERNS,
    find_concepts_in_text,
    normalize_term,
)
from ontology.negation import (
    NEGATION_TERMS,
    REFERRAL_TERMS,
    split_sentences,
    detect_polarity,
    detect_polarity_in_sentence,
    analyze_chunks_for_concept,
)
