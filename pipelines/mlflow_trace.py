"""
VirtueConnect — MLflow Trace Helpers

Enforces the step-level JSON traceability contract from the cursor rules.
Every pipeline node should call `log_step()` to produce an auditable trace.

Schema:
{
  "run_id": "...",
  "facility_id": "gh-123",
  "step_name": "extractor_node",
  "inputs": { ... },
  "outputs": { ... },
  "evidence": [ ... ]
}
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_LOCAL_TRACE_DIR = Path(__file__).resolve().parent.parent / "data" / "traces"


# ---------------------------------------------------------------------------
# Step log record
# ---------------------------------------------------------------------------

class StepLog:
    """A single step-level trace record."""

    def __init__(
        self,
        run_id: str,
        facility_id: str,
        step_name: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        evidence: List[Dict[str, Any]],
    ):
        self.run_id = run_id
        self.facility_id = facility_id
        self.step_name = step_name
        self.inputs = inputs
        self.outputs = outputs
        self.evidence = evidence
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "facility_id": self.facility_id,
            "step_name": self.step_name,
            "timestamp": self.timestamp,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "evidence": self.evidence,
        }


# ---------------------------------------------------------------------------
# MLflow integration
# ---------------------------------------------------------------------------

def _get_mlflow():
    """Lazy import MLflow."""
    try:
        import mlflow
        return mlflow
    except ImportError:
        return None


def start_pipeline_run(experiment_name: Optional[str] = None) -> Optional[str]:
    """
    Start an MLflow run for the pipeline.
    Returns the run_id or None if MLflow is not available.
    """
    mlflow = _get_mlflow()
    if mlflow is None:
        logger.info("MLflow not available, traces will be stored locally only")
        return None

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)

    exp_name = experiment_name or os.environ.get(
        "MLFLOW_EXPERIMENT_NAME", "virtueconnect-pipeline"
    )

    try:
        mlflow.set_experiment(exp_name)
        run = mlflow.start_run()
        run_id = run.info.run_id
        logger.info("Started MLflow run: %s", run_id)
        return run_id
    except Exception as e:
        logger.warning("Failed to start MLflow run: %s", e)
        return None


def end_pipeline_run() -> None:
    """End the current MLflow run."""
    mlflow = _get_mlflow()
    if mlflow:
        try:
            mlflow.end_run()
        except Exception:
            pass


def log_step(
    run_id: Optional[str],
    facility_id: str,
    step_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    evidence: List[Dict[str, Any]],
) -> StepLog:
    """
    Log a pipeline step. Writes to MLflow (if available) and local JSON.

    Args:
        run_id: MLflow run ID (or a local session ID)
        facility_id: The facility being processed
        step_name: Name of the pipeline node
        inputs: Input data for this step
        outputs: Output data from this step
        evidence: Evidence records produced

    Returns:
        The StepLog record
    """
    effective_run_id = run_id or "local-run"

    step = StepLog(
        run_id=effective_run_id,
        facility_id=facility_id,
        step_name=step_name,
        inputs=inputs,
        outputs=outputs,
        evidence=evidence,
    )

    # Log to MLflow
    mlflow = _get_mlflow()
    if mlflow and run_id:
        try:
            mlflow.log_dict(
                step.to_dict(),
                f"traces/{facility_id}/{step_name}.json",
            )
        except Exception as e:
            logger.debug("MLflow log_dict failed: %s", e)

    # Always log locally
    _log_local(step)

    return step


def _log_local(step: StepLog) -> None:
    """Write step log to local JSON file."""
    facility_dir = _LOCAL_TRACE_DIR / step.facility_id
    facility_dir.mkdir(parents=True, exist_ok=True)

    path = facility_dir / f"{step.step_name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(step.to_dict(), f, indent=2, ensure_ascii=False)


def load_trace(facility_id: str, step_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load trace logs for a facility (for the UI "View Forensic Evidence" button).

    Args:
        facility_id: The facility to load traces for
        step_name: Optional filter to a specific step

    Returns:
        List of step log dicts
    """
    facility_dir = _LOCAL_TRACE_DIR / facility_id
    if not facility_dir.exists():
        return []

    logs: List[Dict[str, Any]] = []

    if step_name:
        path = facility_dir / f"{step_name}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                logs.append(json.load(f))
    else:
        for path in sorted(facility_dir.glob("*.json")):
            with open(path, "r", encoding="utf-8") as f:
                logs.append(json.load(f))

    return logs
