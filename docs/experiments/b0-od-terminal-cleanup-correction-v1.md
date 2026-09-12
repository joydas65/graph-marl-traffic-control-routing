# Evidence-gated B0 native terminal cleanup correction

Date: 13 September 2026. Engineering correction and offline evidence only.
Accepted base: `215ff23487df71fc1fa4d701e7e7959c43a9cf70`.

## Observed failure, not a host-cause claim

The retained original harmless P2 attempt and its separately authorized single
instrumented diagnostic both remain **FAIL**. In the diagnostic, the fixture's
child wait returned before TERM. After TERM/grace, a non-consuming observation
reported the retained worker terminal; the subsequent group-KILL raised
`PermissionError`, newly recording errno 1. Ordinary worker wait then returned
zero. A separate scope-query observation failed. Raw local process/path traces,
helper sources, reports and inventories remain private and unchanged.

The exact kernel/policy cause is unresolved. This patch does not treat EPERM as
ESRCH, suppress PermissionError, or claim that worker exit proves group absence.
It avoids unnecessary final escalation only when sufficient ownership evidence
already exists. No native revalidation has been performed.

## Exact eligibility and handoff boundary

Normal ownership establishment, TERM, grace and the single absolute cleanup
deadline remain. Before final KILL, all of the following must hold:

1. The originally verified worker object and original PID remain retained and
   unreaped, under the existing exclusive/default-SIGCHLD-reaper requirement.
2. A timely, complete DONE handoff matches the current plan, run, condition,
   origin, output identity, sole previously reported child and worker PID. A
   fresh per-GO token prevents stale attempt correlation. Receipt/grant shapes
   and identities are checked in memory; scientific byte readback remains after
   cleanup. A token is correlation, not authentication of malicious worker code.
3. The trusted worker's sole child was launched once and its retained process
   wrapper recorded an actual returned integer wait result for that exact child.
   This agrees with the existing finalization process EXITED/code evidence.
   Neither a caller boolean nor a cached target exit hint alone qualifies.
4. Nonblocking, non-reaping `waitid(P_PID, retained_pid,
   WEXITED | WNOHANG | WNOWAIT)` reports that same worker terminal. Only valid
   exited/killed/dumped status is accepted; no-status, stopped or continued
   observations are not terminal proof. No unresolved ownership contradiction
   or child remains.

Eligible cleanup records `KILL_SKIPPED_VERIFIED_CHILD_WAIT_AND_TERMINAL_WORKER`,
permanently disables future signalling for that handle, and performs the
ordinary bounded final reap and descriptor close. Earlier failures survive.
Failed or late reap cannot restore signalling or establish bounded cleanup;
contradictory terminal/reap exit codes retain failure. Actual reaping and timely
accepted reaping are recorded separately.

The in-memory cleanup handoff is derived by the production worker from its
existing process/wait and finalization observations. An absent handoff preserves
ordinary failure-result handling but earns no shortcut or positive child-scope
claim. Present malformed, stale or contradictory handoffs are rejected.
Post-cleanup failed result readback clears the positive child-scope claim without
undoing past actions or signalling again.

## Conservative paths and limits

- Missing/unavailable waitid supplies no terminal proof; conservative escalation
  retains its prior exclusive-reaper limitations. No additional consuming wait,
  polling reaper, process census or global signal handler is introduced.
- ECHILD, wrong PID (including an unexpected zero PID), changed handle identity,
  cached reaping or a changed reaper disposition disables further signalling.
  Ownership-lost paths do not accept a subsequent wait as successful reaping;
  descriptors are still closed and scope remains unresolved.
- A live or unresolved child, an incomplete handoff, timeout, cancellation or
  late result does not earn terminal-cleanup success. Actual attempted signal
  failures retain the signal name, exception class and numeric errno when
  available; private exception messages and tracebacks are not public output.
- The trusted production worker has one fixed inherited-scope child. This is
  not an attestation service for a compromised worker or proof about arbitrary
  escaping descendants. Full scientific receipt validation is not moved into
  the cleanup-critical path.
- Initial OS bootstrap is still not hard-deadline-interruptible. Real process,
  signal, wait, socket, client, listening-scope and SUMO behavior remain outside
  this offline correction's evidence.

The historical harmless helper's boolean-only DONE does not satisfy the new
handoff. Its preserved bytes are not rewritten to obtain a passing history.
Any later native validation needs a separately reviewed current-handoff fixture
and fresh execution authorization; neither is supplied or executed here.

## Validation and identities

Changed files are limited to:

- Production: [`native_supervisor.py`](../../scripts/b0/od_integration_v1/native_supervisor.py)
  and [`native_worker.py`](../../scripts/b0/od_integration_v1/native_worker.py).
- Offline regressions: [`test_b0_od_integration_terminal_cleanup.py`](../../tests/test_b0_od_integration_terminal_cleanup.py),
  [`test_b0_od_integration_native_supervisor.py`](../../tests/test_b0_od_integration_native_supervisor.py),
  [`test_b0_od_integration_native_ipc.py`](../../tests/test_b0_od_integration_native_ipc.py),
  [`test_b0_od_integration_native_worker.py`](../../tests/test_b0_od_integration_native_worker.py),
  [`test_b0_od_integration_projection.py`](../../tests/test_b0_od_integration_projection.py)
  and the existing [`offline harness`](../../tests/run_b0_od_integration_offline.py).
- The [projection manifest](../../tests/reference/b0_od_integration_v1_projection.json),
  this note, the [ownership decision addendum](../decisions/0004-b0-native-representations-and-ownership.md),
  [documentation index](../README.md) and [monthly effort log](../progress/monthly-effort-log.md).

Current source/test identities and preserved prior identities are recorded in
[`b0_od_integration_v1_projection.json`](../../tests/reference/b0_od_integration_v1_projection.json).
The dedicated regressions use production coordination with injected
process/wait/clock operations. The offline harness additionally denies real
signal/wait/scope calls that do not reliably produce Python audit events.
Focused development subsets are not added to full-suite totals.

Final frozen-source validation used the existing commands:

```sh
python3 -I -S -B tests/run_b0_od_integration_offline.py new
python3 -I -S -B tests/run_b0_od_integration_offline.py existing
```

| Surface | Tests passed | Subtests |
| --- | ---: | ---: |
| Complete integration, including new cleanup regressions | 361 | 536 |
| Existing B0/Adapter | 153 | 175 |
| Disjoint combined total | 514 | 711 |

Zero failures, errors, skips, collection errors or forbidden-access attempts;
source hashes remained unchanged. The new 51-test/66-subtest focused run is
included in the integration total, not added again. In-memory compilation of
28 Python files, whitespace, documentation links and all eleven frozen
scientific dependency identities passed. The 56,943,083-byte full synthetic C4
selection passed the unchanged 64 MiB bound and write/readback/finalization.

A preceding 70-test development subset exposed one new handoff-validator
vocabulary error: it initially used an invalid generic measurement-status name.
The validator was corrected to the existing VALID/EVIDENCE_DEFICIENCY/
INTEGRITY_FAILURE vocabulary before the final freeze. That development error
and the earlier passing focused run are not additional final acceptance counts.

Current production SHA-256 values:

| Source | SHA-256 |
| --- | --- |
| `native_supervisor.py` | `6f3a18c2acf3d1b4651946b391c07b37e3c24829fc912cb96fd8942e5a504863` |
| `native_worker.py` | `d6504c1b2c13ecc7fb297561844b9732d6a649ab41838f7842c336472d545b64` |

The current projection manifest SHA-256 is
`fb0adcffa5b288e228185dae0c1a4c495e762c9d08058b87973540dd8f289080`.
Prior published source/test identities are retained in its separate historical
section. These identities establish this offline checkpoint, not native success.

## Research boundary

Scientific Contract V1, Adapter V2, finalization schema 2, allocations,
thresholds, stopping/repeat rules, prior results and the 24+2 future simulation
budget are unchanged. No concentration is selected and dissertation delta
remains unset. Candidate N and routing remain parked. Draft publication is not
native validation, formal faculty approval or execution permission.

```text
ORIGINAL_P2_STATUS=FAIL
DIAGNOSTIC_P2_STATUS=FAIL
EXACT_NATIVE_DENIAL_CAUSE_PROVEN=NO
NATIVE_REVALIDATION_EXECUTED=NO
SUMO_PROCESS_STARTED=NO
OD_CALIBRATION_EXECUTED=NO
READY_TO_RUN=NO
NEXT_TASK=REVIEW_TERMINAL_CLEANUP_CORRECTION_BEFORE_NATIVE_REVALIDATION
```

The next task is not executed by this checkpoint.
