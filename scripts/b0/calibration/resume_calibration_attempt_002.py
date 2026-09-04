#!/usr/bin/env python3
"""Resume the frozen calibration after attempt-001's pre-SUMO socket failure.

This driver changes no scientific input or decision rule.  It reuses the
hash-frozen attempt-001 module and inputs, writes only attempt-002 run/check
directories, and preserves the complete failed attempt as immutable evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import run_calibration as calibration


RETRY_IDENTITY = "B0_CALIBRATION_OPERATIONAL_RETRY_ATTEMPT_002"
RETRY_DRIVER_PATH = Path(__file__).resolve().relative_to(Path.cwd().resolve())
PRIOR_CHECKS = Path("checks/attempt-001")
PRIOR_FAILED_RUN = Path("runs/2x/seed-20260904/n0-cal/attempt-001")
ATTEMPT_002_CHECKS = Path("checks/attempt-002")


def verify_retry_preconditions() -> None:
    if Path.cwd().resolve() != calibration.BUNDLE_ROOT:
        raise AssertionError("retry driver must start in the calibration bundle")
    if ATTEMPT_002_CHECKS.exists():
        raise AssertionError("attempt-002 checks already exist")
    if Path("selection").exists() or Path("freeze").exists():
        raise AssertionError("selection or freeze exists before attempt-002")
    if list(Path("runs").rglob("attempt-002")):
        raise AssertionError("an attempt-002 run directory already exists")

    failure = json.loads((PRIOR_CHECKS / "bundle-failure.json").read_text())
    technical = json.loads((PRIOR_FAILED_RUN / "technical-failure.json").read_text())
    expected_failure = {
        "exception_type": "TypeError",
        "message": "'NoneType' object cannot be interpreted as an integer",
    }
    if any(failure.get(key) != value for key, value in expected_failure.items()):
        raise AssertionError("attempt-001 is not the recorded localhost-port failure")
    if any(technical.get(key) != value for key, value in expected_failure.items()):
        raise AssertionError("attempt-001 run failure differs from the sealed failure")
    forbidden_observation_artifacts = {
        "step-trace.csv",
        "final-metrics.json",
        "vehicle-ledger.json",
        "tripinfo.xml",
        "exposure-summary.json",
    }
    if any((PRIOR_FAILED_RUN / name).exists() for name in forbidden_observation_artifacts):
        raise AssertionError("attempt-001 advanced far enough to produce observations")


def reuse_frozen_inputs() -> dict[str, Any]:
    prior = json.loads(
        (PRIOR_CHECKS / "pre-execution-input-freeze.json").read_text()
    )
    original_frozen = dict(prior["all_preexecution_frozen_input_sha256"])
    calibration.FROZEN_INPUT_HASHES = dict(original_frozen)
    calibration.verify_all_frozen_input_hashes()

    prior_manifest = json.loads(
        (PRIOR_CHECKS / "artifact-sha256.json").read_text()
    )
    if prior_manifest.get("self_hash_included") is not False:
        raise AssertionError("attempt-001 artifact manifest has unexpected semantics")
    sealed_attempt_hashes = prior_manifest.get("sha256")
    if not isinstance(sealed_attempt_hashes, dict) or not sealed_attempt_hashes:
        raise AssertionError("attempt-001 artifact manifest is empty or malformed")
    for relative_name, expected_hash in sorted(sealed_attempt_hashes.items()):
        path = Path(relative_name)
        if not path.is_file() or calibration.sha256(path) != expected_hash:
            raise AssertionError(
                f"attempt-001 sealed artifact changed or disappeared: {relative_name}"
            )

    preserved_attempt_files = sorted(
        path
        for root in (PRIOR_CHECKS, PRIOR_FAILED_RUN)
        for path in root.rglob("*")
        if path.is_file()
    )
    preserved_hashes = {
        path.as_posix(): calibration.sha256(path) for path in preserved_attempt_files
    }
    retry_driver_hash = calibration.sha256(RETRY_DRIVER_PATH)
    calibration.FROZEN_INPUT_HASHES.update(preserved_hashes)
    calibration.FROZEN_INPUT_HASHES[RETRY_DRIVER_PATH.as_posix()] = retry_driver_hash
    calibration.verify_all_frozen_input_hashes()

    receipt = {
        "status": "PASS",
        "retry_identity": RETRY_IDENTITY,
        "reason": "ATTEMPT_001_TRACI_LOCALHOST_PORT_ALLOCATION_UNAVAILABLE_IN_SANDBOX",
        "attempt_001_produced_scientific_observations": False,
        "scientific_inputs_or_decision_rules_changed": False,
        "attempt_001_preexecution_input_sha256": original_frozen,
        "attempt_001_sealed_manifest_verified_sha256": sealed_attempt_hashes,
        "attempt_001_preserved_artifact_sha256": preserved_hashes,
        "retry_driver_identity": RETRY_DRIVER_PATH.as_posix(),
        "retry_driver_sha256": retry_driver_hash,
        "execution_environment_change_only": (
            "ALLOW_LOCALHOST_TRACI_SOCKET_OUTSIDE_THE_RESTRICTED_SANDBOX"
        ),
    }
    calibration.write_json_once(
        ATTEMPT_002_CHECKS / "pre-execution-input-reuse.json", receipt
    )
    calibration.write_bytes_once(
        ATTEMPT_002_CHECKS / "resume_calibration_attempt_002.executed.py",
        RETRY_DRIVER_PATH.read_bytes(),
    )
    return prior


def main() -> None:
    verify_retry_preconditions()
    calibration.RUN_ATTEMPT = 2
    calibration.ATTEMPT_CHECKS = ATTEMPT_002_CHECKS
    calibration.ATTEMPT_INITIALIZED = False
    calibration.verify_pristine_execution_targets = verify_retry_preconditions
    calibration.prepare_frozen_inputs = reuse_frozen_inputs
    calibration.main()


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        calibration.seal_failure(error)
        raise
