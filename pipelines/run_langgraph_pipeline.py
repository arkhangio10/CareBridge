"""
VirtueConnect — Main LangGraph Pipeline

Wires all nodes into a StateGraph and provides entry points for
running the full extraction pipeline.

Usage:
    python -m pipelines.run_langgraph_pipeline [--csv PATH]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from pipelines.state import PipelineState
from pipelines.mlflow_trace import log_step, start_pipeline_run, end_pipeline_run
from pipelines.nodes.ingest_node import ingest_node
from pipelines.nodes.dedup_merge_node import dedup_merge_node
from pipelines.nodes.chunk_node import chunk_node
from pipelines.nodes.extractor_node import extractor_node
from pipelines.nodes.reconciler_node import reconciler_node
from pipelines.nodes.validator_node import validator_node
from pipelines.nodes.persist_node import persist_node

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv(_PROJECT_ROOT / "configs" / ".env")


# ---------------------------------------------------------------------------
# Build the LangGraph pipeline
# ---------------------------------------------------------------------------

def build_pipeline() -> StateGraph:
    """
    Create the VirtueConnect extraction pipeline as a LangGraph StateGraph.

    Nodes (each wrapped with step-level MLflow tracing):
      ingest -> dedup_merge -> chunk -> extract -> reconcile -> validate -> persist
    """
    workflow = StateGraph(PipelineState)

    # Add nodes — each wrapped with _trace_node for step-level tracing
    workflow.add_node("ingest", lambda s: _trace_node(ingest_node, "ingest_node", s))
    workflow.add_node("dedup_merge", lambda s: _trace_node(dedup_merge_node, "dedup_merge_node", s))
    workflow.add_node("chunk", lambda s: _trace_node(chunk_node, "chunk_node", s))
    workflow.add_node("extract", lambda s: _trace_node(extractor_node, "extractor_node", s))
    workflow.add_node("reconcile", lambda s: _trace_node(reconciler_node, "reconciler_node", s))
    workflow.add_node("validate", lambda s: _trace_node(validator_node, "validator_node", s))
    workflow.add_node("persist", lambda s: _trace_node(persist_node, "persist_node", s))

    # Wire edges (linear pipeline)
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "dedup_merge")
    workflow.add_edge("dedup_merge", "chunk")
    workflow.add_edge("chunk", "extract")
    workflow.add_edge("extract", "reconcile")
    workflow.add_edge("reconcile", "validate")
    workflow.add_edge("validate", "persist")
    workflow.add_edge("persist", END)

    return workflow


def _summarize_state_key(state: PipelineState, key: str) -> str:
    """Produce a compact summary of a state key for tracing (avoid huge payloads)."""
    val = state.get(key)
    if val is None:
        return "null"
    if isinstance(val, dict):
        return f"dict({len(val)} keys)"
    if isinstance(val, list):
        return f"list({len(val)} items)"
    return str(val)[:200]


def _trace_node(node_fn, step_name: str, state: PipelineState) -> PipelineState:
    """Wrap a node call with MLflow step-level tracing."""
    run_id = state.get("run_id")
    before_keys = {k: _summarize_state_key(state, k) for k in state}

    # Execute the actual node
    result_state = node_fn(state)

    after_keys = {k: _summarize_state_key(result_state, k) for k in result_state}
    changed_keys = {k: after_keys[k] for k in after_keys if after_keys.get(k) != before_keys.get(k)}

    # Build evidence list from facilities if available
    evidence_list = []
    facilities = result_state.get("facilities", {})
    if isinstance(facilities, dict):
        for fid, record in list(facilities.items())[:3]:  # sample up to 3
            if hasattr(record, "anomalies") and record.anomalies:
                for a in record.anomalies[:2]:
                    evidence_list.append({
                        "facility_id": fid,
                        "anomaly_type": getattr(a, "anomaly_type", str(a)),
                        "severity": getattr(a, "severity", "unknown"),
                    })

    step_log = log_step(
        run_id=run_id,
        facility_id="pipeline",
        step_name=step_name,
        inputs=before_keys,
        outputs=changed_keys,
        evidence=evidence_list,
    )

    # Append to step_logs in state
    logs = list(result_state.get("step_logs", []))
    logs.append(step_log.to_dict())
    result_state["step_logs"] = logs

    logger.info("  [Trace] %s → changed: %s", step_name, list(changed_keys.keys()))
    return result_state


def run_pipeline(csv_path: str, run_id: Optional[str] = None) -> PipelineState:
    """
    Run the full VirtueConnect extraction pipeline.

    Args:
        csv_path: Path to the input CSV file.
        run_id: Optional MLflow run ID for traceability.

    Returns:
        Final pipeline state with all extracted/validated facility records.
    """
    logger.info("=" * 60)
    logger.info("VirtueConnect Pipeline — Starting")
    logger.info("CSV: %s", csv_path)
    logger.info("=" * 60)

    # Start MLflow run if available
    if not run_id:
        run_id = start_pipeline_run()

    workflow = build_pipeline()
    app = workflow.compile()

    initial_state: PipelineState = {
        "csv_path": csv_path,
        "run_id": run_id,
        "step_logs": [],
    }

    # Run the pipeline
    final_state = app.invoke(initial_state)

    # End MLflow run
    end_pipeline_run()

    # Summary
    facilities = final_state.get("facilities", {})
    total_anomalies = sum(
        len(r.anomalies) for r in facilities.values()
    )
    step_count = len(final_state.get("step_logs", []))
    logger.info("=" * 60)
    logger.info("Pipeline complete!")
    logger.info("  Facilities processed: %d", len(facilities))
    logger.info("  Total anomalies: %d", total_anomalies)
    logger.info("  Step traces logged: %d", step_count)
    logger.info("  Persisted: %s", final_state.get("persisted", False))
    logger.info("=" * 60)

    return final_state


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run the VirtueConnect extraction pipeline"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=os.environ.get(
            "CSV_PATH",
            str(_PROJECT_ROOT / "Virtue Foundation Ghana v0.3 - Sheet1.csv"),
        ),
        help="Path to the input CSV file",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="MLflow run ID for traceability",
    )
    args = parser.parse_args()

    if not Path(args.csv).exists():
        logger.error("CSV file not found: %s", args.csv)
        sys.exit(1)

    run_pipeline(args.csv, args.run_id)


if __name__ == "__main__":
    main()
