"""
VirtueConnect — Vector Search Indexing Pipeline

Chunks facility text at sentence level, embeds with OpenAI
text-embedding-3-small, and indexes into Databricks Delta Table (Parquet).

This script performs two main steps:
1. Build local embeddings from processed data (facilities_full.json).
2. Upload embeddings to Databricks (virtueconnect.gold.embeddings) using Unity Catalog Volumes.

Usage:
    python -m pipelines.build_vector_index --local --upload
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_OUTPUT_DIR = _PROJECT_ROOT / "data" / "output"
_EMBEDDINGS_JSON_PATH = _OUTPUT_DIR / "chunk_embeddings.json"
_EMBEDDINGS_PARQUET_PATH = _OUTPUT_DIR / "chunk_embeddings.parquet"

load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv(_PROJECT_ROOT / "configs" / ".env")


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def _embed_texts(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """Embed texts using OpenAI text-embedding-3-small."""
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key)
    all_embeddings: List[List[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=batch,
            )
            for item in response.data:
                all_embeddings.append(item.embedding)
            logger.info("Embedded batch %d-%d / %d", i, i + len(batch), len(texts))
        except Exception as e:
            logger.error("Error embedding batch %d: %s", i, e)
            # Fill with zeros or handle gracefully? For now, re-raise
            raise e

    return all_embeddings


# ---------------------------------------------------------------------------
# Build index records from pipeline output
# ---------------------------------------------------------------------------

def build_chunk_records(
    facilities_json_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Build chunk records for indexing from the pipeline output.
    Uses the JSON output to get facility-level text chunks.
    """
    if facilities_json_path is None:
        facilities_json_path = str(_OUTPUT_DIR / "facilities_full.json")

    if not Path(facilities_json_path).exists():
        logger.error("Facilities JSON not found: %s", facilities_json_path)
        return []

    with open(facilities_json_path, "r", encoding="utf-8") as f:
        facilities = json.load(f)

    records: List[Dict[str, Any]] = []

    for fid, fdata in facilities.items():
        # Build chunks from raw text fields
        texts_to_index = []

        # Raw descriptions
        for desc in fdata.get("raw_descriptions", []):
            if desc and desc.strip():
                texts_to_index.append({
                    "text": desc.strip(),
                    "source_column": "description",
                })

        # Raw capabilities
        for cap in fdata.get("raw_capabilities", []):
            if cap and cap.strip():
                texts_to_index.append({
                    "text": cap.strip(),
                    "source_column": "capability",
                })

        # Raw procedures
        for proc in fdata.get("raw_procedures", []):
            if proc and proc.strip():
                texts_to_index.append({
                    "text": proc.strip(),
                    "source_column": "procedure",
                })

        for item in texts_to_index:
            records.append({
                "facility_id": fid,
                "facility_name": fdata.get("name", ""),
                "region": fdata.get("region", ""),
                "district": fdata.get("district", ""),
                "source_column": item["source_column"],
                "text": item["text"],
            })

    logger.info("Built %d chunk records from %d facilities", len(records), len(facilities))
    return records


# ---------------------------------------------------------------------------
# Local Embeddings Generation
# ---------------------------------------------------------------------------

def generate_local_embeddings(records: List[Dict[str, Any]]) -> Property:
    """Generate embeddings locally and save to Parquet and JSON."""
    if not records:
        logger.warning("No records to index")
        return

    texts = [r["text"] for r in records]
    logger.info("Embedding %d chunks...", len(texts))
    
    # Check if we already have embeddings to avoid re-cost
    if _EMBEDDINGS_PARQUET_PATH.exists():
        logger.info("Found existing embeddings at %s, skipping generation.", _EMBEDDINGS_PARQUET_PATH)
        return

    embeddings = _embed_texts(texts)

    # Combine records with embeddings
    indexed = []
    for i, (record, embedding) in enumerate(zip(records, embeddings)):
        indexed.append({
            **record,
            "embedding": embedding,
            "chunk_id": i,
        })

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save as JSON (for local dev/compatibility)
    with open(_EMBEDDINGS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(indexed, f, ensure_ascii=False)
    
    # Save as Parquet (for Databricks upload - preserves array types!)
    df = pd.DataFrame(indexed)
    df.to_parquet(_EMBEDDINGS_PARQUET_PATH, index=False)

    logger.info("Wrote local embeddings: %s (%d chunks)", _EMBEDDINGS_PARQUET_PATH, len(indexed))


# ---------------------------------------------------------------------------
# Upload to Databricks (Volumes + CTAS Parquet)
# ---------------------------------------------------------------------------

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


def upload_embeddings_to_databricks() -> None:
    """Upload the generated Parquet embeddings to Databricks."""
    if not _EMBEDDINGS_PARQUET_PATH.exists():
        logger.error("Embeddings Parquet not found. Run with --local first.")
        return

    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")
    catalog = os.environ.get("DATABRICKS_CATALOG", "virtueconnect")
    schema = os.environ.get("DATABRICKS_SCHEMA", "gold")
    volume = "uploads"
    table_name = "gold_embeddings"

    if not host or not token:
        logger.error("DATABRICKS_HOST/TOKEN not set")
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
        
        # 1. Ensure volume
        if not ensure_volume(w, warehouse_id, catalog, schema, volume):
            return
            
        # 2. Upload Parquet to Volume
        filename = "chunk_embeddings.parquet"
        volume_path = f"/Volumes/{catalog}/{schema}/{volume}/{filename}"
        
        logger.info("Uploading embeddings to Volume: %s", volume_path)
        
        try:
            with open(_EMBEDDINGS_PARQUET_PATH, "rb") as f:
                w.files.upload(volume_path, f, overwrite=True)
            logger.info("✅ Uploaded %s", volume_path)
        except Exception as e:
            logger.error("Failed to upload: %s", e)
            return

        # 3. Create table using CTAS with Parquet format
        full_table = f"{catalog}.{schema}.{table_name}"
        logger.info("Creating embeddings table %s from Parquet...", full_table)
        
        # read_files with parquet automatically infers array types correctly
        sql = f"""
        CREATE OR REPLACE TABLE {full_table}
        AS SELECT * FROM read_files(
          '{volume_path}',
          format => 'parquet'
        )
        """
        
        resp = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql,
            wait_timeout="50s"
        )
        
        if resp.status.state == StatementState.SUCCEEDED:
            logger.info("✅ Embeddings table created successfully!")
            logger.info("   Schema should have 'embedding' as ARRAY<FLOAT>")
        else:
            logger.error("❌ Failed to create table: %s", resp.status.error)

    except ImportError:
        logger.error("databricks-sdk not installed")
    except Exception as e:
        logger.error("Error: %s", e)
        import traceback
        traceback.print_exc()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Build VirtueConnect vector index")
    parser.add_argument("--local", action="store_true", help="Generate local embeddings (JSON/Parquet)")
    parser.add_argument("--upload", action="store_true", help="Upload embeddings to Databricks")
    args = parser.parse_args()

    if args.local:
        records = build_chunk_records()
        generate_local_embeddings(records)

    if args.upload:
        upload_embeddings_to_databricks()
        
    if not args.local and not args.upload:
        parser.print_help()


if __name__ == "__main__":
    main()
