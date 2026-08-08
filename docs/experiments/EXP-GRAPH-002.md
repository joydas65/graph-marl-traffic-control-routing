# EXP-GRAPH-002: Minimal Runtime Characterization

## Status

Stage 1 isolation harness implemented and validated with synthetic dummy probes on 7 August 2026. The compute-environment roles and Level-1 installation-test candidate were documented on 8 August 2026. No candidate environment has been provisioned or validated, and candidate-specific runtime characterization has not started.

## Question

Can narrowly scoped, non-training probes determine the effective dispatch, tensor, batching, return, terminal, target-network, and evaluation behavior of the GCQN and GCAC candidates without modifying private source or making reproduction claims?

## Stage 1 scope

Implemented:

- a standard-library subprocess harness;
- CPU-only child-process environment settings;
- temporary working-directory isolation;
- explicit allowed-write roots and Python audit-hook enforcement;
- timeout and process-exit capture;
- recursive path sanitization for output and structured evidence;
- pass, fail, inconclusive, and blocked statuses;
- generic shape and call-count evidence hooks;
- generic deterministic synthetic-world fixtures; and
- ten synthetic unit tests.

Explicitly excluded:

- private handover access or import;
- GCQN or GCAC candidate probes;
- dependency installation or environment selection;
- PyTorch, Gym, SUMO, CityFlow, or TraCI execution;
- simulators, models, checkpoints, training, optimization, and repair.

## Evidence identity

- **Branch:** `plan/exp-graph-002-runtime-probes`
- **Base commit:** `c8c7871b179e42ff61fc043e9ce005ca59c21174`
- **Implementation dependencies:** Python standard library only
- **Harness-test runtime:** local Python 3.13.5; this is not a selected or validated handover environment
- **Seeds:** not applicable
- **Training configuration:** not applicable
- **Private evidence:** none generated in Stage 1

## Validation

Synthetic tests cover:

1. successful isolated execution and evidence hooks;
2. timeout termination;
3. rejected writes outside allowed roots;
4. allowed writes inside the temporary workspace;
5. sanitized standard output, standard error, exceptions, and structured values;
6. rejected network creation;
7. rejected nested subprocess creation;
8. stable result schema without external research dependencies; and
9. deterministic generic-world behavior.

## Interpretation

Stage 1 establishes orchestration and Python-level isolation only. It provides no evidence that either handover imports, executes, matches the paper, loads a checkpoint, or produces a valid action or result.

The Python audit hook cannot govern writes performed directly by native extensions. Simulator smoke probes therefore remain blocked until an operating-system-level read-only boundary is reviewed in an approved execution environment.

## Compute-environment decision

[Decision 0002](../decisions/0002-compute-and-experiment-environments.md) distinguishes the Apple Silicon development host from the reconstructed compatibility-validation environment, canonical dissertation infrastructure, and optional exploratory compute.

The compatibility candidate for future installation testing remains native Linux x86-64, CPython 3.10.13, PyTorch 1.11.0+cpu, the approved Torch-1.11-compatible PyG dependency closure, and CPU-only execution. Testing will use dedicated native Linux x86-64 remote or cloud infrastructure. No provider, machine type, canonical experiment environment, or GPU has been selected.

This compatibility-selected stack is not claimed as the original paper environment. Future success would characterize the visible source under a defensible reconstructed environment and would not, by itself, establish historical reproduction.

## Next gate

Under separate approval, provision a disposable native Linux x86-64 instance for the selected CPU-only compatibility candidate. First rerun the Stage 1 synthetic harness, then perform dependency-import smoke tests without private source, and only afterwards consider candidate-specific Level-1 probes. Do not begin fake-world or simulator probes at the same time.
