# B0 native representations and explicit ownership boundary

Date: 2026-09-09. Working implementation decision, not native validation or
execution permission. See the [partial implementation checkpoint](../experiments/b0-od-thin-live-binding-v1-implementation.md).

Reuse the accepted OD generator, schema-2 integration, accounting, qualification
and evidence writer. Keep native representation work in a thin collector and
versioned mapping module, not in a second scientific stack.

- Preserve native option strings, TLS data and both permission-mask views; derive
  canonical controls from these observations and separately identified input
  files. Static contract labels are not runtime queries.
- Keep actual argument/queried path and port observations in the existing
  `output_identity` operational container. Revalidate them, but do not add repeat
  exclusions or change the nine scientific repeat families.
- Support explicit SYNTHETIC/LIVE origins through grants, capture, runs,
  selection and persistence. Test doubles remain SYNTHETIC. Origin is neither
  authentication nor authorization.
- Unknown/missing native diagnostics stay unavailable. Preserve accessible
  contradictions across sibling acquisition failures. Integration continues to
  own parsing, collection state and status precedence.
- Require explicit injected process/transport factories and finite deadline
  arguments. No native default is supplied: an injected timeout contract is not
  evidence that pre-handle process creation or blocking client I/O is bounded.

The unresolved issue is bounded native process/connection acquisition. Ordinary
process creation may outlast a requested timeout before an owned handle exists;
a timer checked after return does not solve that ownership interval.
[Python subprocess timeout semantics](https://docs.python.org/3.12/library/subprocess.html#subprocess.run).
Resolving this interface must precede any proposed native run. No new watchdog,
helper-process framework, authorization mechanism or cloud infrastructure is
introduced at this checkpoint. All scientific definitions and budgets remain
unchanged; Candidate N and routing remain outside this work.

## Narrow completion: 10 September 2026

The later authorized completion implements one per-run POSIX worker/session
with a READY/GO gate. Its supervisor verifies the worker scope before SUMO
acquisition, then independently enforces absolute startup, connection,
exchange, total and finalization deadlines. Native socket calls receive the
remaining complete-exchange budget; no installed package or research-process
global socket patch is used. Existing scientific modules remain unchanged.

The worker is not reaped before the final exact-group cleanup signal, preventing
PID reuse under the explicit exclusive-reaper assumption. One absolute cleanup
budget bounds escalation and worker reaping. Forced worker termination without
actual child-wait evidence leaves child scope unresolved; it is not proof of
process absence or completed scientific finalization.

This addresses the SUMO pre-handle ownership interval, not the initial
supervisor-to-worker OS bootstrap. That bootstrap is explicitly not
deadline-interruptible and receives no nested supervisor. Offline doubles
validate control flow only; real helper/OS/socket/SUMO behavior and listening
scope remain later authorized checks. See the current implementation note for
interfaces, timing boundaries, exact identities and validation results.

## Evidence-gated terminal cleanup correction: 13 September 2026

The [narrow correction](../experiments/b0-od-terminal-cleanup-correction-v1.md)
adds one exception to unconditional final escalation: a complete, current
run-bound child-wait handoff plus a non-reaping terminal observation of the
retained verified worker permits skipping KILL. Signalling is permanently
disabled before consuming worker status. Unknown child scope or unavailable
terminal evidence earns no shortcut, and actual signal failures remain visible.
Historical P2 results stay FAIL; this is an offline-only correction, not a
diagnosis of the host's permission denial or native revalidation.
