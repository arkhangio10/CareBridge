"""Check Workspace Files access"""
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

print(f"🔗 Checking Workspace Files on {host}")

try:
    print("\nListing /Workspace/Users:")
    for f in w.workspace.list("/Users"):
        print(f" - {f.path}")
        
    print("\nTrying to write to /Workspace/Users/me/test.txt")
    me = w.current_user.me()
    user_path = f"/Users/{me.user_name}"
    print(f"User: {me.user_name} -> {user_path}")
    
    test_path = f"{user_path}/test_write.txt"
    import base64
    content = base64.b64encode(b"test").decode("utf-8")
    w.workspace.import_(
        path=test_path,
        content=content,
        format="AUTO",
        overwrite=True
    )
    print(f"✅ Success writing to {test_path}")
    
except Exception as e:
    print(f"❌ Error: {e}")
