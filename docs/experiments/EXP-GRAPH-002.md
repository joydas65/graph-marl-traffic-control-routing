# EXP-GRAPH-002: Minimal Runtime Characterization

## Status

Stage 1 isolation harness implemented and validated with synthetic dummy probes on 7 August 2026. Candidate-specific runtime characterization has not started.

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

The Python audit hook cannot govern writes performed directly by native extensions. Simulator smoke probes therefore remain blocked until an operating-system or container read-only boundary is reviewed.

## Next gate

Review the harness and documentation. After approval, resolve one exact CPU-only environment and implement Level 1 synthetic model-only probes as a separate stage. Do not begin fake-world or simulator probes at the same time.
