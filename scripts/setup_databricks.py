"""
VirtueConnect — Databricks Setup Script (Final)

Creates schema and tables in the existing virtueconnect catalog.

Usage:
    python scripts/setup_databricks.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "configs" / ".env")


def setup_databricks():
    """Setup Databricks tables in virtueconnect catalog."""
    
    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")
    catalog = "virtueconnect"  # Your catalog exists!
    schema = "gold"
    
    if not host or not token:
        print("❌ ERROR: DATABRICKS_HOST and DATABRICKS_TOKEN must be set")
        sys.exit(1)
    
    print(f"🔗 Connecting to Databricks: {host}")
    print(f"📦 Catalog: {catalog}")
    print(f"📂 Schema: {schema}")
    
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.sql import StatementState
        
        w = WorkspaceClient(host=host, token=token)
        
        warehouses = list(w.warehouses.list())
        if not warehouses:
            print("❌ No SQL Warehouses found")
            sys.exit(1)
        
        warehouse_id = warehouses[0].id
        print(f"🏭 Using SQL Warehouse: {warehouses[0].name}")
        
        def run_sql(sql, description):
            """Execute SQL with error handling"""
            print(f"\n📝 {description}")
            try:
                response = w.statement_execution.execute_statement(
                    warehouse_id=warehouse_id,
                    statement=sql,
                    wait_timeout="50s"
                )
                if response.status.state == StatementState.SUCCEEDED:
                    print(f"   ✅ Success")
                    return True
                else:
                    error = str(response.status.error)[:200] if response.status.error else "Unknown"
                    print(f"   ❌ Failed: {error}")
                    return False
            except Exception as e:
                print(f"   ⚠️ Error: {str(e)[:200]}")
                return False
        
        success_count = 0
        total = 0
        
        # 1. Use the catalog
        total += 1
        if run_sql(f"USE CATALOG {catalog}", f"USE CATALOG {catalog}"):
            success_count += 1
        
        # 2. Create schema
        total += 1
        if run_sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}", 
                   f"CREATE SCHEMA {schema}"):
            success_count += 1
        
        # 3. Use schema
        total += 1
        if run_sql(f"USE SCHEMA {catalog}.{schema}", f"USE SCHEMA {schema}"):
            success_count += 1
        
        # 4. Create Gold Wide Table
        total += 1
        if run_sql(f"""
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.gold_facilities_wide (
                facility_id STRING,
                name STRING,
                region STRING,
                district STRING,
                facility_type STRING,
                lat DOUBLE,
                lon DOUBLE,
                c_section_value BOOLEAN,
                c_section_status STRING,
                blood_bank_value BOOLEAN,
                blood_bank_status STRING,
                operating_room_value BOOLEAN,
                anesthesia_value BOOLEAN,
                emergency_24_7_value BOOLEAN,
                ambulance_value BOOLEAN,
                pharmacy_value BOOLEAN,
                lab_basic_value BOOLEAN,
                has_anomaly_high BOOLEAN,
                anomaly_count INT,
                last_updated TIMESTAMP
            )
            COMMENT 'Healthcare facilities with extracted capabilities'
        """, "CREATE TABLE gold_facilities_wide"):
            success_count += 1
        
        # 5. Create Gold Long Table
        total += 1
        if run_sql(f"""
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.gold_facilities_long (
                facility_id STRING,
                facility_name STRING,
                capability_id STRING,
                capability_category STRING,
                value BOOLEAN,
                status STRING,
                confidence DOUBLE,
                evidence_text STRING,
                last_updated TIMESTAMP
            )
            COMMENT 'Forensic evidence for each capability extraction'
        """, "CREATE TABLE gold_facilities_long"):
            success_count += 1
        
        # 6. Create Anomalies Table
        total += 1
        if run_sql(f"""
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.anomalies (
                facility_id STRING,
                facility_name STRING,
                bundle_name STRING,
                anomaly_type STRING,
                severity STRING,
                reason STRING,
                detected_at TIMESTAMP
            )
            COMMENT 'Clinical bundle validation anomalies'
        """, "CREATE TABLE anomalies"):
            success_count += 1
        
        # Summary
        print("\n" + "="*60)
        print(f"✅ Setup complete! ({success_count}/{total} operations succeeded)")
        print("="*60)
        
        if success_count >= 4:
            print(f"\n📊 Tables created in: {catalog}.{schema}")
            print("   • gold_facilities_wide")
            print("   • gold_facilities_long")
            print("   • anomalies")
            print("\n🚀 Next steps:")
            print("   1. Wait for your pipeline to finish running")
            print("   2. Run: python -m pipelines.ingest_delta --all")
            print("   3. Check your data in Databricks SQL Editor!")
        else:
            print("\n⚠️ Some operations failed. Check the errors above.")
            print("   You may need elevated permissions in Databricks.")
        
    except ImportError:
        print("❌ databricks-sdk not installed. Run: pip install databricks-sdk")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    setup_databricks()
