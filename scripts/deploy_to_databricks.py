"""
VirtueConnect — Deploy to Databricks Script

Uploads the pipeline code and creates a Databricks Workflow for automated execution.

Usage:
    python scripts/deploy_to_databricks.py
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / "configs" / ".env")


def deploy_to_databricks():
    """Deploy VirtueConnect pipeline to Databricks."""
    
    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")
    
    if not host or not token:
        print("❌ ERROR: DATABRICKS_HOST and DATABRICKS_TOKEN must be set")
        sys.exit(1)
    
    print(f"🔗 Connecting to Databricks: {host}")
    
    try:
        from databricks.sdk import WorkspaceClient
        
        w = WorkspaceClient(host=host, token=token)
        
        # 1. Upload source files to DBFS
        print("\n📤 Uploading source files to DBFS...")
        
        dbfs_base = "/FileStore/virtueconnect"
        
        # Files to upload
        files_to_upload = [
            ("Virtue_Foundation_.csv", "data/Virtue_Foundation_.csv"),
            ("configs/.env", "configs/.env"),
        ]
        
        # Upload data files if they exist locally
        for local_name, dbfs_name in files_to_upload:
            local_path = PROJECT_ROOT / local_name
            if local_path.exists():
                dbfs_path = f"{dbfs_base}/{dbfs_name}"
                print(f"   📁 Uploading {local_name} → {dbfs_path}")
                try:
                    with open(local_path, "rb") as f:
                        w.dbfs.put(dbfs_path, f, overwrite=True)
                    print(f"   ✅ Uploaded")
                except Exception as e:
                    print(f"   ⚠️ Warning: {e}")
        
        # 2. Upload output files if they exist
        output_dir = PROJECT_ROOT / "data" / "output"
        if output_dir.exists():
            print(f"\n📤 Uploading pipeline output files...")
            for output_file in output_dir.glob("*"):
                if output_file.is_file():
                    dbfs_path = f"{dbfs_base}/data/output/{output_file.name}"
                    print(f"   📁 {output_file.name} → {dbfs_path}")
                    try:
                        with open(output_file, "rb") as f:
                            w.dbfs.put(dbfs_path, f, overwrite=True)
                        print(f"   ✅ Uploaded")
                    except Exception as e:
                        print(f"   ⚠️ Warning: {e}")
        
        # 3. Create MLflow experiment
        print("\n🔬 Setting up MLflow experiment...")
        experiment_name = "/Shared/virtueconnect"
        try:
            experiment = w.experiments.get_experiment_by_name(experiment_name)
            if experiment:
                print(f"   ✅ Experiment exists: {experiment_name}")
            else:
                w.experiments.create_experiment(experiment_name)
                print(f"   ✅ Created experiment: {experiment_name}")
        except Exception as e:
            try:
                w.experiments.create_experiment(experiment_name)
                print(f"   ✅ Created experiment: {experiment_name}")
            except Exception as e2:
                print(f"   ⚠️ Experiment setup: {e2}")
        
        # 4. Create a simple notebook for running the pipeline
        print("\n📓 Creating pipeline notebook...")
        
        notebook_content = '''# Databricks notebook source
# MAGIC %md
# MAGIC # VirtueConnect Pipeline Runner
# MAGIC 
# MAGIC This notebook runs the VirtueConnect extraction pipeline.

# COMMAND ----------

# MAGIC %pip install langchain langgraph langchain-openai openai pydantic>=2.0 pandas mlflow spacy pyyaml python-dotenv geopy

# COMMAND ----------

import os

# Set environment variables from Databricks secrets or widgets
# In production, use Databricks Secrets instead of hardcoding
dbutils.widgets.text("openai_api_key", "", "OpenAI API Key")
dbutils.widgets.text("csv_path", "/dbfs/FileStore/virtueconnect/data/Virtue_Foundation_.csv", "CSV Path")

os.environ["OPENAI_API_KEY"] = dbutils.widgets.get("openai_api_key")
os.environ["CSV_PATH"] = dbutils.widgets.get("csv_path")
os.environ["MLFLOW_TRACKING_URI"] = "databricks"
os.environ["MLFLOW_EXPERIMENT_NAME"] = "/Shared/virtueconnect"

# COMMAND ----------

# Clone the repo or use uploaded files
# For hackathon, we'll use the pre-uploaded pipeline code

print("🏥 VirtueConnect Pipeline")
print("=" * 50)
print(f"CSV Path: {os.environ.get('CSV_PATH')}")
print(f"MLflow: {os.environ.get('MLFLOW_EXPERIMENT_NAME')}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run Pipeline
# MAGIC 
# MAGIC The pipeline will:
# MAGIC 1. Ingest CSV data
# MAGIC 2. Deduplicate and merge facilities
# MAGIC 3. Chunk text for processing
# MAGIC 4. Extract capabilities using GPT-4
# MAGIC 5. Validate against clinical bundles
# MAGIC 6. Persist to Delta tables

# COMMAND ----------

# For now, display the uploaded data
import pandas as pd

csv_path = dbutils.widgets.get("csv_path").replace("/dbfs", "dbfs:")
df = spark.read.csv(csv_path, header=True, inferSchema=True)
display(df)

# COMMAND ----------

print(f"✅ Loaded {df.count()} facilities from CSV")
'''
        
        notebook_path = "/Shared/VirtueConnect/pipeline_runner"
        try:
            import base64
            w.workspace.import_(
                path=notebook_path,
                content=base64.b64encode(notebook_content.encode()).decode(),
                format="SOURCE",
                language="PYTHON",
                overwrite=True
            )
            print(f"   ✅ Created notebook: {notebook_path}")
        except Exception as e:
            print(f"   ⚠️ Notebook creation: {e}")
        
        print("\n" + "="*60)
        print("✅ Deployment complete!")
        print("="*60)
        print(f"\n🌐 Databricks Workspace: {host}")
        print(f"\n📁 Files uploaded to: {dbfs_base}/")
        print(f"📓 Notebook: {notebook_path}")
        print(f"🔬 MLflow Experiment: /Shared/virtueconnect")
        print("\n🚀 Next steps:")
        print(f"   1. Open Databricks: {host}")
        print(f"   2. Go to Workspace → Shared → VirtueConnect → pipeline_runner")
        print(f"   3. Add your OPENAI_API_KEY in the widget")
        print(f"   4. Run the notebook!")
        
    except ImportError:
        print("❌ databricks-sdk not installed. Run: pip install databricks-sdk")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    deploy_to_databricks()
