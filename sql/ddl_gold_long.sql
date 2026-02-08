-- ==========================================================================
-- VirtueConnect — LONG Forensic Table (Databricks SQL / Delta)
-- One row per facility × capability × evidence.
-- Designed for forensic audit, traceability, and drill-down.
-- ==========================================================================

CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.gold_facilities_long (
  -- Identity
  facility_id       STRING    COMMENT 'Foreign key to gold_facilities_wide.facility_id',
  capability_name   STRING    COMMENT 'Canonical capability name (e.g., c_section, blood_bank)',

  -- Forensic value
  value             BOOLEAN   COMMENT 'TRUE / FALSE / NULL',
  state             STRING    COMMENT 'ASSERTED | EXTRACTED | CONTRADICTED | UNCERTAIN | MISSING',
  confidence        DOUBLE    COMMENT 'Confidence score 0.0-1.0',

  -- Evidence trail
  row_id            STRING    COMMENT 'Source row unique_id from CSV',
  source_column     STRING    COMMENT 'Column the evidence came from (description, procedure, equipment, etc.)',
  evidence_snippet  STRING    COMMENT 'Verbatim text snippet supporting this fact',
  char_start        INT       COMMENT 'Character offset start in the source text',
  char_end          INT       COMMENT 'Character offset end in the source text',

  -- Traceability
  step_name         STRING    COMMENT 'Pipeline step that produced this record (extractor, reconciler, etc.)',
  run_id            STRING    COMMENT 'MLflow run ID for full pipeline trace'
)
USING DELTA
COMMENT 'VirtueConnect LONG forensic table — one row per capability-evidence pair. Use for audit, drill-down, and "Why?" views.'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true'
);

-- Useful partition hint for queries filtering by facility
-- ALTER TABLE ${catalog}.${schema}.gold_facilities_long
--   SET TBLPROPERTIES ('delta.dataSkippingNumIndexedCols' = '5');
