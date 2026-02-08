-- ==========================================================================
-- VirtueConnect — WIDE Gold Table (Databricks SQL / Delta)
-- One row per facility.  Designed for Genie Text2SQL + fast filters.
-- ==========================================================================

CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.gold_facilities_wide (
  -- Identity
  facility_id         STRING        COMMENT 'Primary key — pk_unique_id from source CSV',
  name                STRING        COMMENT 'Facility name (longest from merged sources)',
  region              STRING        COMMENT 'State or region (e.g., Ashanti, Greater Accra)',
  district            STRING        COMMENT 'City or district',
  lat                 DOUBLE        COMMENT 'Latitude (geocoded)',
  lon                 DOUBLE        COMMENT 'Longitude (geocoded)',
  facility_type       STRING        COMMENT 'clinic | hospital | health_centre | etc.',
  operator_type       STRING        COMMENT 'private | public | government | faith-tradition',

  -- ===================== MATERNITY =====================
  c_section_value             BOOLEAN   COMMENT 'Can perform C-section? TRUE/FALSE/NULL',
  c_section_state             STRING    COMMENT 'ASSERTED | EXTRACTED | CONTRADICTED | UNCERTAIN | MISSING',
  c_section_confidence        DOUBLE    COMMENT 'Confidence score 0.0-1.0',

  delivery_natural_value      BOOLEAN   COMMENT 'Natural / vaginal delivery capability',
  delivery_natural_state      STRING    COMMENT 'Validation state',
  delivery_natural_confidence DOUBLE    COMMENT 'Confidence score',

  ultrasound_ob_value         BOOLEAN   COMMENT 'Obstetric ultrasound available',
  ultrasound_ob_state         STRING    COMMENT 'Validation state',
  ultrasound_ob_confidence    DOUBLE    COMMENT 'Confidence score',

  incubator_value             BOOLEAN   COMMENT 'Neonatal incubator available',
  incubator_state             STRING    COMMENT 'Validation state',
  incubator_confidence        DOUBLE    COMMENT 'Confidence score',

  blood_bank_value            BOOLEAN   COMMENT 'On-site blood bank / reliable supply',
  blood_bank_state            STRING    COMMENT 'Validation state',
  blood_bank_confidence       DOUBLE    COMMENT 'Confidence score',

  anesthesia_value            BOOLEAN   COMMENT 'Anesthesia capability available',
  anesthesia_state            STRING    COMMENT 'Validation state',
  anesthesia_confidence       DOUBLE    COMMENT 'Confidence score',

  anesthetist_value           BOOLEAN   COMMENT 'Trained anesthetist on staff',
  anesthetist_state           STRING    COMMENT 'Validation state',
  anesthetist_confidence      DOUBLE    COMMENT 'Confidence score',

  operating_room_value        BOOLEAN   COMMENT 'Major operating theatre available',
  operating_room_state        STRING    COMMENT 'Validation state',
  operating_room_confidence   DOUBLE    COMMENT 'Confidence score',

  -- ===================== TRAUMA =====================
  trauma_surgery_value        BOOLEAN   COMMENT 'Trauma / emergency surgery capability',
  trauma_surgery_state        STRING    COMMENT 'Validation state',
  trauma_surgery_confidence   DOUBLE    COMMENT 'Confidence score',

  general_surgery_value       BOOLEAN   COMMENT 'General surgery capability',
  general_surgery_state       STRING    COMMENT 'Validation state',
  general_surgery_confidence  DOUBLE    COMMENT 'Confidence score',

  xray_value                  BOOLEAN   COMMENT 'X-ray imaging available',
  xray_state                  STRING    COMMENT 'Validation state',
  xray_confidence             DOUBLE    COMMENT 'Confidence score',

  ambulance_value             BOOLEAN   COMMENT 'Ambulance / emergency transport',
  ambulance_state             STRING    COMMENT 'Validation state',
  ambulance_confidence        DOUBLE    COMMENT 'Confidence score',

  emergency_24_7_value        BOOLEAN   COMMENT '24/7 emergency services',
  emergency_24_7_state        STRING    COMMENT 'Validation state',
  emergency_24_7_confidence   DOUBLE    COMMENT 'Confidence score',

  -- ===================== INFRASTRUCTURE =====================
  oxygen_supply_value         BOOLEAN   COMMENT 'Medical oxygen supply',
  oxygen_supply_state         STRING    COMMENT 'Validation state',
  oxygen_supply_confidence    DOUBLE    COMMENT 'Confidence score',

  generator_backup_value      BOOLEAN   COMMENT 'Backup generator',
  generator_backup_state      STRING    COMMENT 'Validation state',
  generator_backup_confidence DOUBLE    COMMENT 'Confidence score',

  water_supply_value          BOOLEAN   COMMENT 'Clean water supply',
  water_supply_state          STRING    COMMENT 'Validation state',
  water_supply_confidence     DOUBLE    COMMENT 'Confidence score',

  lab_basic_value             BOOLEAN   COMMENT 'Basic laboratory on site',
  lab_basic_state             STRING    COMMENT 'Validation state',
  lab_basic_confidence        DOUBLE    COMMENT 'Confidence score',

  pharmacy_value              BOOLEAN   COMMENT 'On-site pharmacy / dispensary',
  pharmacy_state              STRING    COMMENT 'Validation state',
  pharmacy_confidence         DOUBLE    COMMENT 'Confidence score',

  -- ===================== FLAGS =====================
  has_anomaly_high  BOOLEAN COMMENT 'TRUE if any ANOMALY_HIGH bundle triggered',
  has_risk_high     BOOLEAN COMMENT 'TRUE if any RISK_HIGH bundle triggered'
)
USING DELTA
COMMENT 'VirtueConnect WIDE gold table — one row per facility with all forensic capabilities. Use for Genie queries.'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true'
);
