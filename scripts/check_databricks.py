"""Quick check of available catalogs and schemas in Databricks"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / "configs" / ".env")

host = os.environ.get("DATABRICKS_HOST")
token = os.environ.get("DATABRICKS_TOKEN")

print(f"🔗 Connecting to: {host}")

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

w = WorkspaceClient(host=host, token=token)

# Get warehouse
warehouses = list(w.warehouses.list())
if not warehouses:
    print("❌ No SQL Warehouses")
    sys.exit(1)
    
warehouse_id = warehouses[0].id
print(f"🏭 Warehouse: {warehouses[0].name}")

def run_sql(sql):
    """Execute SQL and return result"""
    try:
        response = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql,
            wait_timeout="50s"
        )
        if response.status.state == StatementState.SUCCEEDED:
            if response.result and response.result.data_array:
                return response.result.data_array
        else:
            print(f"   Error: {response.status.error}")
    except Exception as e:
        print(f"   Exception: {e}")
    return None

# Check newly created tables
print("\n📊 Checking loaded tables in virtueconnect.gold:")
tables = ["gold_facilities_wide", "gold_facilities_long", "anomalies"]
schema = "virtueconnect.gold"

for t in tables:
    full_table = f"{schema}.{t}"
    print(f"\n   🔍 Table: {full_table}")
    try:
        count_res = run_sql(f"SELECT COUNT(*) FROM {full_table}")
        if count_res:
             count = count_res[0][0]
             print(f"      Rows: {count}")
             
             # Show sample
             sample = run_sql(f"SELECT * FROM {full_table} LIMIT 1")
             if sample:
                 print(f"      Sample: {sample[0]}")
        else:
            print("      ⚠️ Empty or not found")
    except Exception as e:
        print(f"      ❌ Error: {e}")

print("\n✅ Verification complete!")
