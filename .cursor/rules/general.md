# VirtueConnect — Cursor Rules (Forensic Truth Layer)
You are a Principal AI Engineer specializing in Healthcare IDP (Intelligent Document Parsing) and Databricks Architectures.
Your mission is to build **VirtueConnect**, a system that transforms unstructured medical facility reports into an **Evidence-Backed Forensic Truth Layer** for NGOs:
- Extract capabilities from messy text (description/notes)
- Reconcile with structured schema columns
- Validate clinically (bundles)
- Identify medical deserts
- Route patients safely (no diagnosis)
- Provide row-level + step-level traceability

---

## 0) Non-Negotiables (Read First)
1. **Evidence Over Invention**
   - NEVER hallucinate capabilities.
   - Every EXTRACTED or CONTRADICTED claim MUST include verbatim evidence snippet(s).
2. **Tri-State Truth + Null Value**
   - Truth is not boolean-only. Use `value: Optional[bool]` AND `state`.
3. **Concept-Specific Negation**
   - "refer/transfer" does NOT globally negate all capabilities.
   - Negation/referral must be tied to a specific concept (same sentence or window).
4. **Clinical Safety**
   - NEVER diagnose or prescribe.
   - Always apply "Clinical Bundles" for safety validation (e.g., C-section requires OT + anesthesia/anesthetist).
5. **Traceability**
   - Every user-facing output must be traceable to:
     - `facility_id`
     - `row_id`
     - `source_column`
     - `step_name`
     - evidence snippet (+ optional offsets)
6. **Deterministic Where Possible**
   - Prefer rules + constrained extraction + Pydantic schemas over free-form generation.

---

## 1) Tech Stack (STRICT)
### Orchestration: LangGraph
- Use `langgraph` and `StateGraph`.
- Nodes MUST include:
  - `ingest_node`
  - `chunk_node`
  - `extractor_node`
  - `evidence_locator_node`
  - `reconciler_node`
  - `validator_node`
  - `confidence_calibrator_node`
  - `persist_node`

### Text2SQL: Databricks Genie
- Data stored in Delta tables.
- Planner queries must be Databricks SQL dialect.
- Maintain **WIDE Gold table** with comments to help Genie.
- Also maintain **LONG Forensic table** for evidence/audit.

### RAG/Indexing: Databricks Vector Search
- DO NOT use FAISS locally.
- Index must store *chunk-level* embeddings (sentence/paragraph chunks), not full description.
- Metadata filters: `facility_id`, `region`, `row_id`, `source_column`.

### Observability: MLflow
- Wrap each agent run in `mlflow.start_run()`.
- Log structured JSON for steps (contract below).
- UI “Why?” must render from these logs (not re-running the model).

### Frontend: Streamlit
- NGO View: map + “Action Plan Cards”
- PatientSafe: triage + routing + trace evidence expander
- Safety alerts: immediate RED alert for red-flag symptoms

---

## 2) Project Structure (Recommended)
- `app/`
  - `streamlit_app.py`
  - `components/`
    - `action_card.py`
    - `trace_view.py`
- `pipelines/`
  - `run_langgraph_pipeline.py`
  - `ingest_delta.py`
  - `build_vector_index.py`
- `models/`
  - `forensic_fields.py`
  - `capability_models.py`
  - `bundle_rules.py`
- `ontology/`
  - `ontology.py`
  - `synonyms.py`
- `sql/`
  - `ddl_gold_wide.sql`
  - `ddl_gold_long.sql`
- `configs/`
  - `bundles.yaml`
  - `capability_catalog.yaml`
- `tests/`
  - `test_negation_scope.py`
  - `test_bundle_validation.py`
  - `test_reconciliation.py`

---

## 3) Data Model (Forensic Pydantic Pattern) — REQUIRED
### 3.1 Enums
```python
from enum import Enum

class ValidationState(str, Enum):
    ASSERTED = "ASSERTED"           # from structured column (procedure/equipment)
    EXTRACTED = "EXTRACTED"         # from free-text with evidence
    CONTRADICTED = "CONTRADICTED"   # free-text explicitly denies the same concept
    UNCERTAIN = "UNCERTAIN"         # weak mention / ambiguous wording
    MISSING = "MISSING"             # no signal found
    OUT_OF_SCOPE = "OUT_OF_SCOPE"   # mention not about this facility or ambiguous entity
3.2 Evidence object (multi-source)
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

EvidenceType = Literal["structured", "free_text", "pdf", "web"]

class Evidence(BaseModel):
    row_id: Optional[str] = None
    source_column: Optional[str] = None
    snippet: Optional[str] = None
    evidence_type: EvidenceType = "free_text"
    char_start: Optional[int] = None
    char_end: Optional[int] = None
3.3 ForensicField object (nullable value)
from typing import Optional, List

class ForensicField(BaseModel):
    value: Optional[bool] = None
    state: ValidationState = ValidationState.MISSING
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: List[Evidence] = Field(default_factory=list)
3.4 Capability record (example)
class MaternityCapability(BaseModel):
    c_section: ForensicField
    operating_room: ForensicField
    anesthesia: ForensicField
    anesthetist: ForensicField
    ultrasound_ob: ForensicField
    blood_bank: ForensicField
4) Ontology & Synonyms (IDP Innovation)
4.1 Capability Catalog (Scope-Limited, High Impact)
Maternity: c_section, delivery_natural, ultrasound_ob, incubator, blood_bank

Trauma/Surgery: trauma_surgery, general_surgery, operating_room, xray, ambulance

Infrastructure: oxygen_supply, generator_backup, water_supply, lab_basic, emergency_24_7

4.2 Synonym Mapping
Synonyms must be defined in ontology/synonyms.py.

Normalize terms before extraction output.

Differentiation rules:

minor_theatre must not auto-map to operating_room=True unless explicitly “major/operative theatre”.

4.3 Concept-Specific Negation/Referral Lexicon
Negation keywords: "no", "not available", "without", "lack(s)"

Referral keywords: "refer", "transfer", "send to", "redirect"

IMPORTANT: apply referral/negation ONLY when tied to a concept (same sentence/window).

5) Extraction Logic — The “Cleaner” Agent
5.1 Chunking Rule
Split free-text into sentence/paragraph chunks.

Each chunk gets:

chunk_id, row_id, facility_id, source_column

5.2 Fact Extraction Rule
For each chunk:

detect candidate concepts via synonyms

detect polarity:

affirm / deny / refer_out / unknown

output ForensicField updates with evidence snippet = the sentence

5.3 Evidence Locator Node
Ensure Evidence.char_start and Evidence.char_end are set where possible.

Always keep the exact snippet verbatim.

5.4 No Blind Inference
Do not infer “operating_room=True” from “surgery” alone.

If ambiguous: state=UNCERTAIN, value=None (or value=True only if explicit and strong).

6) Reconciliation Logic — Structured vs Text
6.1 Priority rules
If structured says TRUE and free-text explicitly denies same concept → CONTRADICTED

If structured is NULL and free-text affirms with evidence → EXTRACTED

If both affirm → keep ASSERTED but append evidence from free-text

If only weak mention → UNCERTAIN

6.2 Multiple Evidence
Keep top-N evidence snippets per concept (e.g., N=3).

Confidence may increase with multiple independent evidence.

7) Validation Logic — The “Auditor” Agent (Clinical Bundles)
7.1 Bundles Must be Configurable (bundles.yaml)
Example:

bundles:
  c_section_safe:
    requires_all: ["c_section", "operating_room"]
    requires_any: [["anesthesia", "anesthetist"]]
    failure_flag: "ANOMALY_HIGH"
    failure_reason: "Unsafe C-Section Claim"

  trauma_bundle:
    requires_all: ["trauma_surgery", "xray", "blood_bank"]
    failure_flag: "RISK_HIGH"
    failure_reason: "Trauma Center without Blood"
7.2 Validation Output
Output anomalies table records:

facility_id, anomaly_type, severity, reason

required_missing list

evidence_rows list (from the related ForensicFields)

7.3 Referral-Only Logic (Concept-Specific)
If a chunk says “refer trauma cases”:

set trauma_surgery.value=False, state=CONTRADICTED

do NOT force unrelated maternity capabilities to false

8) Planner (NGO View) — Must-Have Commands
Provide 3 primary actions as buttons + NL chat fallback:

Resource Distribution

“Count facilities with [bundle] by region”

Cold Spots

“Districts > X minutes from facility with [capability/bundle]”

Validation

“List facilities with ANOMALY_HIGH / RISK_HIGH and show evidence”

All outputs MUST support:

filters by region

explainability (evidence snippets)

export (CSV)

9) Data Tables (Gold) — REQUIRED
9.1 WIDE table (for Genie + fast filters)
gold_facilities_wide

facility_id, name, region, district, lat, lon

Per capability:

{cap}_value (BOOLEAN nullable)

{cap}_state (STRING)

{cap}_confidence (DOUBLE)

Flags:

has_anomaly_high (BOOLEAN)

has_risk_high (BOOLEAN)

9.2 LONG table (for forensic audit)
gold_facilities_long

facility_id, capability_name

value, state, confidence

row_id, source_column

evidence_snippet, char_start, char_end

step_name, run_id (MLflow)

10) Vector Search (RAG) — REQUIRED
Index sentence-level chunks of:

description, notes, other free-text fields

Metadata filters: facility_id, region, source_column, row_id

Use cases:

“What services does Facility X offer?” → retrieve top chunks + show as evidence

“Show facilities mentioning ultrasound” → filter/semantic search

11) MLflow Trace Contract (Step-Level Traceability) — REQUIRED
Every step logs a JSON with this schema:

{
  "run_id": "...",
  "facility_id": "gh-123",
  "step_name": "extractor_node",
  "inputs": {
    "row_ids": ["452"],
    "source_columns": ["description"],
    "chunks": ["..."]
  },
  "outputs": {
    "facts": [{"capability":"ultrasound_ob","value":true,"state":"EXTRACTED","confidence":0.92}],
    "anomalies": []
  },
  "evidence": [
    {"row_id":"452","source_column":"description","snippet":"...","char_start":10,"char_end":55}
  ]
}
UI “Ver Evidencia Forense” must render from these logs.

12) UI Rules (Streamlit)
12.1 NGO View
Map showing deserts (service-layer toggle)

On click region: render “Action Plan Card”

Gap → Impact → Candidate Facility → Suggested Intervention → Evidence

12.2 PatientSafe View (Safety First)
NEVER diagnose.

ALWAYS show:

urgency (red flag)

recommended facilities (Top 3)

“Why?” expander showing evidence + validation bundle outcome

Red flags (immediate RED banner):

bleeding

unconscious

difficulty breathing

severe chest pain

13) Key Commands (Shortcuts)
!extract — generate LangGraph pipeline script (nodes + state + tables)

!validate — generate bundle validation engine + anomalies table write

!ontology — generate capability catalog + synonyms + negation/referral rules

!reconcile — generate reconciliation logic (structured vs text, contradictions, confidence)

!ui_card — generate Streamlit Action Plan Card + trace expander

!sql_genie — generate DDL for wide+long gold tables with comments for Genie

!vector_index — generate Vector Search indexing pipeline (chunking + metadata)

!mlflow_trace — generate MLflow logging helpers enforcing JSON contract

14) Output Discipline
When producing code:

Keep functions small and testable.

Include unit tests for:

negation scope

referral concept specificity

bundle validation

reconciliation precedence

When producing text for users:

Provide evidence and confidence.

Never claim certainty without evidence.


---

### 3 mejoras rápidas que te recomiendo aplicar YA en ese ruleset (si quieres afinar aún más)
1) **Añadir timestamps** (si tu CSV tiene “last updated” o “year”), para que reconciliación prefiera evidencia más reciente.  
2) **“Evidence density”**: subir confianza si hay 2+ snippets independientes.  
3) **Separar “capability” vs “specialty”** explícitamente (specialty ≠ capability) para evitar falsas conclusiones.

Si me dices “quiero que lo adapte 1:1 a mis archivos `free_form.py` y `facility_and_ngo_fields.py`”, te lo ajusto con nombres exactos de campos/estructuras que ya tienes y te dejo los comandos `!sql_genie` y `!extract` listos para ejecutar.
::contentReference[oaicite:0]{index=0}