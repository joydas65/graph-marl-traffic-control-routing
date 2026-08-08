# GCQN/GCAC Runtime-Probe Plan

## Purpose

`EXP-GRAPH-002` will characterize a small set of runtime invariants identified by the static semantic and dispatch audits. It is not a reproduction, training, repair, checkpoint-evaluation, or performance experiment.

Stage 1 establishes only a generic isolation harness. It does not import or execute either private handover, choose a research environment, or implement a GCQN/GCAC-specific probe.

## Evidence boundary

The public repository may contain:

- the generic harness and synthetic fixtures;
- symbolic shapes and sanitized aggregate probe results;
- probe status, elapsed time, and process exit status; and
- documentation of limitations and stop conditions.

Private source locations, configuration identities, detailed exceptions, checkpoints, datasets, logs, scenario identifiers, and unsanitized traces must remain outside Git.

## Stage 1 harness

The harness runs one Python probe at a time in a fresh subprocess with:

- Python isolated mode and bytecode generation disabled;
- a minimal environment with CPU-only visibility;
- a new temporary working directory;
- caller-declared allowed-write roots;
- a Python audit hook that rejects writes outside those roots;
- nested-process and network creation blocked;
- a configurable wall-clock timeout;
- captured and sanitized standard output and error;
- recursive sanitization of structured evidence; and
- deterministic JSON field ordering.

A probe exposes `probe(context)`. The context provides generic shape and call-count recorders for future model and framework boundaries. The harness recognizes four statuses:

- **pass:** the stated probe invariant was observed;
- **fail:** the probe reached its boundary and contradicted the invariant or raised an ordinary error;
- **inconclusive:** execution completed without enough evidence to decide; and
- **blocked:** an isolation control or resource limit prevented completion.

These statuses characterize a probe question. A failed invariant is not automatically a confirmed algorithm defect.

## Generic synthetic fixtures

The synthetic world contains only deterministic node, feature, action, reward, and done values implemented with Python built-ins. It is deliberately independent of Gym, PyTorch, SUMO, CityFlow, TraCI, and the private framework. It does not reproduce any private class or simulator behavior.

## Planned probe levels

### Level 1: synthetic model-only

Planned questions include scalar-versus-node graph alignment, batched edge-index use, actor/critic output shapes, return coverage, bootstrapping, and target-network calls. These probes remain unimplemented.

### Level 2: fake or minimal world

Planned questions include registry dispatch, observation/action/reward/replay shapes, terminal propagation, target-update hooks, and evaluation/checkpoint-loading dispatch. These probes remain unimplemented.

### Level 3: one-reset/one-step simulator smoke

Each approved candidate may later receive exactly one reset, one action selection, and one simulator step in a disposable runtime workspace. These probes remain unimplemented and require a separately reviewed environment and operating-system-level read-only boundary.

## Source-protection policy

- Private source must be exposed read-only.
- Mutable configuration and runtime output must be redirected to temporary storage.
- No candidate probe may train, call `backward()`, perform an optimizer step, load a checkpoint, or repair code.
- No private source or scenario material may be copied into Git.
- Pre/post source-integrity checks are required when private source is eventually accessed.

The Stage 1 audit hook governs Python operations that emit audit events. It is not a security boundary for native extensions or simulator processes. Level 3 therefore requires container or operating-system read-only enforcement before execution.

## Environment gate

Available environment evidence is conflicting and no final Python, PyTorch, graph-library, Gym, or simulator version has been selected. The local Python used to test this standard-library harness is not evidence of handover compatibility.

Before any candidate-specific import:

1. select and record one CPU-only environment candidate;
2. resolve exact compatible dependency versions without changing candidate source;
3. verify that private source can be mounted read-only;
4. validate the harness against synthetic probes in that environment; and
5. approve Level 1 separately from Levels 2 and 3.

## Current conclusion

The generic harness is available for review and its synthetic tests exercise success, timeout, write blocking, allowed temporary writes, network and nested-process blocking, sanitization across every result channel, deterministic schema, and dependency independence. No GCQN, GCAC, simulator, checkpoint, or model runtime evidence has been produced.
