# B0 pre-completion worker abort lifecycle

Date: 18 September 2026. Classification: operational implementation with offline
evidence only, not a scientific result or a proven repair of historical P3.

Accepted base: `43a7c42d69ddac6f7d4fc26265cd870016945500`; tree:
`22484b05142fee3348e72635834e2163418dea00`.

## Decision and exact scope

The genuine [`worker_main`](../../scripts/b0/od_integration_v1/native_supervisor.py)
now owns a small pre-completion lifecycle. No child-cleanup acknowledgement,
parent acceptance protocol, second supervisor, reaper, thread or census is added.
The supervisor coordination, P2 eligibility, phase/grace/cleanup deadlines,
signal-error recording and disable-before-reap ordering are unchanged.

| State | Transition |
| --- | --- |
| PRE_COMPLETION | Normal setup, GO and worker execution. A pre-arm TERM or ordinary exception enters ABORT_RESERVED. |
| ABORT_RESERVED | Sticky. No new forward work or completed handoff; discard queued control bytes without executing a late GO, and retain the leader while the parent control channel remains available. |
| COMPLETED_HANDOFF | Enter only after all DONE bytes were emitted and no pre-arm shutdown was latched. A subsequent TERM allows ordinary exit 0. This is not parent acceptance or scientific success. |
| ORDINARY_EXIT | Parent EOF/control error exits 1; completed-handoff TERM exits 0. No child-absence claim follows either exit. |

A caught SIGTERM handler is installed inside the genuine worker before setup,
READY and GO. It only latches the phase at the first TERM: no exception, I/O,
wait, lock or cleanup. Importing the module installs nothing. No SIG_IGN,
blocked TERM mask, preexec function, SIGCHLD change or child detachment is added.
The inherited-scope Popen configuration is unchanged. Source/configuration
checks and doubles do not establish actual exec-time signal inheritance.

Shutdown before, during, or after the final DONE write but **before arming**
wins conservatively. A second check reconciles a TERM between the first check
and the state assignment. Once reserved, later successful cleanup/reporting
cannot arm completion. A fully emitted DONE may consequently be visible to
the parent while the worker remains reserved; it must not be represented as an
accepted cleanup shortcut. Post-arm TERM takes the separate completed path.

## Ordinary checkpoints and acquisition ownership

[`execute_worker`](../../scripts/b0/od_integration_v1/native_worker.py) receives
the worker-local shutdown predicate. Checks gate acquisition, connection, RUN
exchange beginnings, assessment, result writing, independent readback and
returned handoff. Returned process/connection resources are retained before
shutdown rejection; existing bounded cleanup then remains usable. FINALIZE,
close, returned waits and `check_total()` do not acquire a blanket shutdown veto.
The chronological first failure is preserved through cleanup/reporting errors.

`_spawn_native` allocates a small cleanup-compatible adapter before calling
Popen and stores the actual returned raw handle immediately, before constructor
or shutdown checks. If normal adapter construction fails, the original error
retains that same handle through the fallback adapter. Its terminate/kill
methods use raw Popen's no-timeout signatures; its wait uses the existing
remaining timeout and preserves actual returned exit evidence. Existing
`clean_unreturned` performs bounded exact-handle cleanup without relaunch.
No reliable handle or returned-wait evidence is fabricated when creation has
not returned.

The ordinary control loop uses at most 0.1-second observation intervals,
recomputing the same interval after InterruptedError. Reads/writes are
nonblocking after setup; writes are additionally capped at PIPE_BUF so an
early setup failure cannot cause a large blocking error write. ERROR reporting
gets one finite write observation; partial/unavailable reporting is not retried
as a new budget. It cannot bypass reservation. The healthy parent remains the
authority for the worker's lifetime; polling is not a new execution deadline.

## Compatibility and unsupported cases

An abort may prospectively be reaped with a SIGKILL exit rather than the old
fixture's ordinary zero exit. Actual exit values are never coerced. The accepted
P2 same-run child-wait/terminal-worker predicate remains unchanged and is tested
through the actual worker, collector, writer/readback and supervisor with
injected operations. Shutdown arriving before completion arming conservatively
retains the worker even if DONE's last byte was already emitted.

Fully emitted/armed DONE does not prove parent acceptance. Late-result rejection
and later cancellation remain parent decisions; universal post-DONE reservation
is not implemented. Original timeout/cancellation stays first, partial data
cannot qualify, and attempted signal errors stay visible.

EOF before GO exits nonzero without acquisition. EOF or a persistent control
pipe error after acquisition may have begun also exits nonzero, without another
launch or fresh cleanup budget. No new recovery of an unknown child is attempted
on that path. If the parent disappears while execution is blocked, EOF may not
be observed until ordinary control flow resumes. Parent loss, fatal exits,
failures before handler installation, indefinitely blocked OS calls and the
check-to-native-call race remain outside stronger guarantees. In particular,
a returning Python signal handler is not immediate interruption of native code.

Leader survival, a group-signal return and worker reaping are distinct from
child closure. Without existing accepted closure evidence, production
`child_scope` remains UNRESOLVED. No claim is made that this policy eliminates
the historical PermissionError or makes P3 pass.

## Offline evidence and remaining gate

Frozen-source validation through the unchanged native-access denial harness:

| Command suffix for `python3 -I -S -B tests/run_b0_od_integration_offline.py` | Tests | Subtests | Result |
| --- | ---: | ---: | --- |
| `new` | 413 | 610 | PASS |
| `existing` | 153 | 175 | PASS |

Both reported zero failures, errors, skips, collection errors and forbidden
access attempts; source hashes were unchanged. Focused subsets and repeated
runs are not added to these counts. The new lifecycle/acquisition files supply
44 tests, included in the integration total. The actual synthetic C4 selection
remains 56,943,083 bytes, passing the unchanged writer bound and readback.
In-memory compilation of all 31 current source/test files, the eleven frozen
scientific dependency identities and whitespace checks passed. All supervisor
and IPC bytes preceding the worker entry helpers match the accepted base.

The [current projection manifest](../../tests/reference/b0_od_integration_v1_projection.json)
preserves pre-change source/test identities and historical validation separately
from the new current identities. SHA-256 at this checkpoint:

| File | SHA-256 |
| --- | --- |
| `scripts/b0/od_integration_v1/native_supervisor.py` | `44fea29280a66dbf8538180a5072aa7f445e0ea9487e0ca8edaee5629fda6c82` |
| `scripts/b0/od_integration_v1/native_worker.py` | `e857587229143845a42d73843b7fce1e3b8ea9ed2626f95b6e05412320bc35cb` |
| `tests/reference/b0_od_integration_v1_projection.json` | `3597dda8a20b31136d1d2c974900253502ddf1c502b9ada16cbcc28f360d6a50` |

Development findings are separate from final evidence: review corrected queued
GO causing premature reservation exit, early setup allowing a large blocking
error write, and a test exhaustion sentinel being swallowed as a pipe error.
The first lifecycle test run also used a truthiness assertion on a validator
whose successful return is None; that test assertion was corrected. A concurrent
development run hit the existing source-binding guard while sources were being
edited; the final runs above used frozen source bytes.

Future separately authorized native validation must exercise the genuine
updated lifecycle with harmless dependencies, check actual child TERM behavior,
pre-handle/unreported-child aborts, group signal and worker wait results, and
completed-handoff compatibility. The old P3 helper substitutes its own lifecycle
and therefore cannot validate this change merely by being rerun. All historical
helpers, attempts, latches, reports and verdicts remain unchanged.

Historical original and approved-context P3 remain FAIL; historical P4 remains
NOT_ATTEMPTED. P2 V2 and approved-context transport T1-T4 retain their historical
PASS results, not validation of this updated worker. Exact historical denial
cause remains unproven. No native attempt, simulator/client execution, OD
calibration or scientific-design change occurs here. Overall native gate,
live integration validation and readiness remain NO.

Next gate: `REVIEW_PRECOMPLETION_WORKER_LIFECYCLE_IMPLEMENTATION`; not executed
by this implementation task. Publication is draft-only; merge is not authorized.
