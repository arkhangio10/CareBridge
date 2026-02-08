# CareBridge — The Forensic Truth Layer for Healthcare

CareBridge transforms unstructured medical facility reports into an **evidence-backed forensic truth layer** for NGOs. Built for the Virtue Foundation hackathon, it targets healthcare facilities across Ghana.

## Key Features

- **Tri-State Truth Matrix**: Every capability is tagged as ASSERTED, EXTRACTED, CONTRADICTED, UNCERTAIN, MISSING, or OUT_OF_SCOPE — with verbatim evidence snippets.
- **Clinical Bundle Validation**: Safety rules (e.g., "C-section requires operating room + anesthesia") flag anomalies automatically.
- **Concept-Specific Negation**: "Refer trauma cases" negates trauma capability — not maternity.
- **Action Plan Cards**: Click a medical desert on the map to see gap analysis, impact, and intervention suggestions.
- **PatientSafe Chat**: Natural-language patient routing with red-flag detection and full forensic traceability.

## Architecture

```
LangGraph Pipeline (8 nodes)
  ingest -> dedup_merge -> chunk -> extract (GPT-4o) -> evidence_locator -> reconcile -> validate -> persist

Storage: Databricks Delta (WIDE + LONG gold tables) + Vector Search
Observability: MLflow (step-level JSON traces)
Frontend: Streamlit (NGO View + PatientSafe View)
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 2. Configure environment
cp configs/.env.example .env
# Edit .env with your keys

# 3. Run extraction pipeline
python -m pipelines.run_langgraph_pipeline

# 4. Launch Streamlit
streamlit run app/streamlit_app.py
```

## Project Structure

```
app/                  # Streamlit UI
  components/         # Action cards, map, patient chat, trace view
pipelines/            # LangGraph pipeline nodes
models/               # Pydantic data models (ForensicField, Evidence, etc.)
ontology/             # Capability catalog, synonyms, negation lexicon
sql/                  # DDL for Databricks gold tables
configs/              # YAML configs + .env
tests/                # Unit tests
```

## License

MIT
