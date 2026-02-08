"""Try to create a Volume and upload to it"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / "configs" / ".env")

host = os.environ.get("DATABRICKS_HOST")
token = os.environ.get("DATABRICKS_TOKEN")

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

w = WorkspaceClient(host=host, token=token)

print(f"🔗 Checking Volumes on {host}")

warehouse = list(w.warehouses.list())[0]
warehouse_id = warehouse.id

catalog = "virtueconnect" # The one existing in hive_metastore
schema = "gold"

# Create Volume (Unity Catalog feature, may fail in hive_metastore)
# But let's try. If failing, we are stuck with Workspace files + spark script.

sql = f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.uploads"
print(f"📝 {sql}")

try:
    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="50s"
    )
    if resp.status.state == StatementState.SUCCEEDED:
        print("✅ Volume created!")
        
        # Upload a test file
        test_path = f"/Volumes/{catalog}/{schema}/uploads/test.txt"
        print(f"Uploading to {test_path}")
        w.files.upload(test_path, contents=b"test data", overwrite=True)
        print("✅ Upload success!")
        
    else:
        print(f"❌ Failed: {resp.status.error}")
        
except Exception as e:
    print(f"❌ Error: {e}")
