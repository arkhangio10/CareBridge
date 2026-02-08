"""
VirtueConnect — Databricks Delta Ingestion (Unity Catalog Volumes + CTAS)

Uploads processed facility data to Databricks via Volumes and creates tables using CTAS.
Matches schema automatically using read_files().

Usage:
    python -m pipelines.ingest_delta [--wide] [--long]
"""

import argparse
import logging
import os
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_OUTPUT_DIR = _PROJECT_ROOT / "data" / "output"

load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv(_PROJECT_ROOT / "configs" / ".env")


def ensure_volume(w, warehouse_id, catalog, schema, volume="uploads"):
    """Ensure the upload volume exists."""
    from databricks.sdk.service.sql import StatementState
    
    volume_path = f"{catalog}.{schema}.{volume}"
    sql = f"CREATE VOLUME IF NOT EXISTS {volume_path}"
    
    try:
        resp = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql,
            wait_timeout="50s"
        )
        if resp.status.state == StatementState.SUCCEEDED:
            return True
        else:
            logger.error("Failed to create volume: %s", resp.status.error)
            return False
    except Exception as e:
        logger.error("Error creating volume: %s", e)
        return False


def upload_and_create_table(
    df: pd.DataFrame,
    table_name: str,
    filename: str,
) -> None:
    """
    Upload DataFrame to Volume and create Delta table using CTAS (Create Table As Select).
    """
    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")
    catalog = os.environ.get("DATABRICKS_CATALOG", "virtueconnect")
    schema = os.environ.get("DATABRICKS_SCHEMA", "gold")
    volume = "uploads"

    if not host or not token:
        logger.error("DATABRICKS_HOST and DATABRICKS_TOKEN must be set")
        return

    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.sql import StatementState

        w = WorkspaceClient(host=host, token=token)
        
        # Get warehouse
        warehouses = list(w.warehouses.list())
        if not warehouses:
            logger.error("No SQL Warehouses found")
            return
        warehouse_id = warehouses[0].id
        
        # 1. Ensure volume exists
        if not ensure_volume(w, warehouse_id, catalog, schema, volume):
            return
            
        # 2. Upload file to Volume
        volume_path = f"/Volumes/{catalog}/{schema}/{volume}/{filename}"
        
        logger.info("Uploading to Volume: %s", volume_path)
        
        # Use a temporary file for upload
        temp_file = f"temp_{filename}"
        df.to_csv(temp_file, index=False)
        
        try:
            with open(temp_file, "rb") as f:
                w.files.upload(volume_path, f, overwrite=True)
            logger.info("✅ Uploaded %s", volume_path)
        except Exception as e:
            logger.error("Failed to upload: %s", e)
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return
            
        if os.path.exists(temp_file):
            os.remove(temp_file)

        # 3. Create table using CTAS
        full_table = f"{catalog}.{schema}.{table_name}"
        logger.info("Creating table %s from file...", full_table)
        
        # Use read_files to infer schema and create table in one go
        sql = f"""
        CREATE OR REPLACE TABLE {full_table}
        AS SELECT * FROM read_files(
          '{volume_path}',
          format => 'csv',
          header => true,
          inferSchema => true
        )
        """
        
        resp = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql,
            wait_timeout="50s"
        )
        
        if resp.status.state == StatementState.SUCCEEDED:
            logger.info("✅ Table %s created and loaded successfully!", full_table)
        else:
            logger.error("❌ Failed to create table: %s", resp.status.error)

    except ImportError:
        logger.error("databricks-sdk not installed. Run: pip install databricks-sdk")
    except Exception as e:
        logger.error("Error: %s", e)
        import traceback
        traceback.print_exc()


def ingest_wide() -> None:
    wide_path = _OUTPUT_DIR / "gold_facilities_wide.csv"
    if not wide_path.exists():
        logger.error("WIDE table not found: %s", wide_path)
        return
    df = pd.read_csv(wide_path)
    upload_and_create_table(df, "gold_facilities_wide", "gold_facilities_wide.csv")


def ingest_long() -> None:
    long_path = _OUTPUT_DIR / "gold_facilities_long.csv"
    if not long_path.exists():
        logger.error("LONG table not found: %s", long_path)
        return
    df = pd.read_csv(long_path)
    upload_and_create_table(df, "gold_facilities_long", "gold_facilities_long.csv")


def ingest_anomalies() -> None:
    anom_path = _OUTPUT_DIR / "anomalies.csv"
    if not anom_path.exists():
        logger.warning("Anomalies table not found")
        return
    df = pd.read_csv(anom_path)
    upload_and_create_table(df, "anomalies", "anomalies.csv")


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Ingest data into Databricks Delta via Volumes + CTAS")
    parser.add_argument("--wide", action="store_true", help="Upload WIDE table")
    parser.add_argument("--long", action="store_true", help="Upload LONG table")
    parser.add_argument("--anomalies", action="store_true", help="Upload Anomalies table")
    parser.add_argument("--all", action="store_true", help="Upload all tables")
    args = parser.parse_args()

    if args.all or (not args.wide and not args.long and not args.anomalies):
        ingest_wide()
        ingest_long()
        ingest_anomalies()
    else:
        if args.wide:
            ingest_wide()
        if args.long:
            ingest_long()
        if args.anomalies:
            ingest_anomalies()


if __name__ == "__main__":
    main()
