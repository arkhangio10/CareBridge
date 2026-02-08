"""Drop tables to allow schema inference on next load"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / "configs" / ".env")

host = os.environ.get("DATABRICKS_HOST")
token = os.environ.get("DATABRICKS_TOKEN")

from databricks.sdk import WorkspaceClient
w = WorkspaceClient(host=host, token=token)
warehouse = list(w.warehouses.list())[0]

tables = ["gold_facilities_wide", "gold_facilities_long", "anomalies"]
catalog = "virtueconnect"
schema = "gold"

print("🔥 Dropping tables to reset schema...")

for t in tables:
    sql = f"DROP TABLE IF EXISTS {catalog}.{schema}.{t}"
    print(f"Executing: {sql}")
    w.statement_execution.execute_statement(
        warehouse_id=warehouse.id,
        statement=sql,
        wait_timeout="30s"
    )
    
print("✅ Done. Now run ingest_delta.py again.")
