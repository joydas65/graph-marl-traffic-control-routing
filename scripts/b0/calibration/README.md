# B0 baseline-only demand calibration provenance

This directory publishes the minimum public-safe source package for
[`EXP-B0-CAL-001`](../../../docs/experiments/EXP-B0-CAL-001.md). The calibration
used the deterministic B0 substrate published in the preceding commit.

## Source roles

| File | Role | SHA-256 |
|---|---|---|
| `contracts/calibration-contract.json` | Frozen pre-execution calibration contract | `3e3cbc4f822b7bb75974e21064b62d54a076dd1db7c38119aad81ea7ba6f3382` |
| `run_calibration.py` | Byte-exact source executed for the demand ladder | `f44035eac421d428877c356ecfef8c5aa9e0388a820c4b1421997c6346c9c3b4` |
| `resume_calibration_attempt_002.py` | Byte-exact source executed to resume after the pre-simulation attempt-001 failure | `5eb23bcaff130249f8dbb142d5b9d927fc28a1b8bf9caca7e50c75b6eaf71446` |
| `provenance/calibration_logic_tests_executed.py` | Byte-exact 35-test source executed before calibration | `1623488c515cdaaf21f9bb6388886437bbc604147421d6e81b67a9406208af63` |

The runners preserve their historical evidence topology, repository-state
checks, and write-once lifecycle. They are provenance snapshots, not supported
entry points for the current repository revision. They have not been silently
refactored into a different implementation.

The active public test at
[`tests/test_b0_calibration_logic.py`](../../../tests/test_b0_calibration_logic.py)
supplies only inert import scaffolding. Its 35 test methods and assertions are
AST-identical to the executed test source, and importing it does not start SUMO.

## Publication boundary

The public package contains the frozen contract, exact executed sources, test
provenance, and concise aggregate experiment record. It excludes the raw
550-artifact calibration tree, simulator logs and XML outputs, per-vehicle
ledgers, environment receipts, failure tracebacks, and machine-specific data.

No demand level qualified, so no deterministic repeat or calibrated-scenario
freeze exists. No RL, routing, graph method, dissertation treatment, or
OD/corridor-concentration experiment was implemented or executed here.
