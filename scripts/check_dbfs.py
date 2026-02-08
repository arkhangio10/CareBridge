"""Check DBFS permissions and listing"""
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

print(f"🔗 Checking DBFS on {host}")

try:
    print("\nRoot listing:")
    for f in w.dbfs.list("/"):
        print(f" - {f.path} ({'dir' if f.is_dir else 'file'})")
        
    print("\nTrying to create a test file in /tmp/test_write.txt")
    import base64
    content = base64.b64encode(b"test").decode("utf-8")
    w.dbfs.put("/tmp/test_write.txt", contents=content, overwrite=True)
    print("✅ Success writing to /tmp")
    
except Exception as e:
    print(f"❌ Error: {e}")
