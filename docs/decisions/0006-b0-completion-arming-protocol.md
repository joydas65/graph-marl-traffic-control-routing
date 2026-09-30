# B0 completion-arming protocol

Date: 29 September 2026. Classification: operational correction with injected
offline evidence, not native validation or a scientific result.

Accepted base: `c7689d6376bf23d1002614c140713d4679be610c`; tree:
`aa8ae6d5a29937bb2a5413463e8f81ec9e237a57`.

## Original ordering and correction

The retained V3 L1 attempt failed its completion-lifecycle predicates despite
complete DONE reception, verified child-wait handoff and successful synthetic
result readback. Its original receipt remains WORKER_COMPLETED, with no parent
first failure, terminal cleanup false and the reported-child/worker-reaped
scope. The worker recorded a pre-arm TERM and ABORT_RESERVED; its returned
wait was -9 rather than the required completed TERM exit 0.

Before modification, deterministic injected scheduling reproduced this ordering
through actual worker entry, lifecycle, control, executor, collector, assessment,
writer/readback and supervisor. Both direct control and the exact reviewed
observation wrapper were exercised. Parent TERM was injected while DONE was
readable but before arming. The resumed worker conservatively reserved. This
does not identify the exact historical interrupted instruction, establish native
scheduling, or turn the injected KILL/reap observations into native evidence.
The original reproduction and source binding remain local and unpublished.

The new ordering in
[`native_supervisor.py`](../../scripts/b0/od_integration_v1/native_supervisor.py)
is:

1. Fully publish DONE under the existing forward/shutdown checks.
2. Successfully arm the existing COMPLETED_HANDOFF lifecycle state.
3. Publish the bounded COMPLETION_ARMED notification.
4. Parent verifies it against its provisional DONE under the same FINALIZE and
   overall deadline before normal completion becomes eligible for TERM cleanup.

No pre-arm TERM is ignored, blocked or reclassified. An unsuccessful DONE
publication or arming cannot publish a valid notification. The notification proves local
arming only for the source-bound genuine worker, not parent acceptance of
science, child closure or an attestation against arbitrary worker code.

## Version and correlation boundary

The explicit operational identity is `B0_WORKER_COMPLETION_ARMED_V1`. GO carries
`completion_protocol`; a current worker rejects an absent/different identity
before execution. The marker has exactly `type`, `protocol`, `version` (integer
1), `run_id`, `worker_pid`, `token`, `binding_sha256` and `candidate_sha256`.
The token is the current GO cleanup token. The two hashes cover canonical JSON
of the complete plan binding and full DONE candidate, respectively. The marker
is capped at 1,024 bytes and uses existing bounded pipe writes; it does not
duplicate scientific output.

The parent retains DONE as `provisional_result`. Only an exact, ordered marker
permits `worker_result` and `normal_finalization`. The operational receipt is
version 2, independently of unchanged schema-2 scientific evidence and the
existing worker-result receipt. Invalid, missing, late, stale or contradictory
messages cannot promote provisional evidence. Cancellation revokes completion
eligibility without erasing the provisional candidate or first failure.

During the original TERM grace, the parent observes the owned status pipe.
Observed trailing bytes, including a duplicate, partial message or ERROR, revoke
completion/shortcut eligibility; observation failures remain failures. EOF proves
only pipe closure, and QUIET only the absence of observed trailing bytes during
that bounded observation. Neither proves process absence or excludes arbitrary
future traffic. The original grace and cleanup endpoints remain authoritative.

## Preserved boundaries

Same-run child-wait validation, exact retained worker ownership, non-consuming
terminal observation, disable-before-reap and actual bounded reap agreement are
still separate requirements. The marker is not an abort-cleanup acknowledgement.
No scientific acceptance is cached: the worker's actual writer still precedes
publication, and fresh source-checked readback and independent assessment
recomputation remain required after cleanup.
Completed scientific FAIL and INCONCLUSIVE retain their original meanings.

Legacy DONE-only live exchanges are not silently upgraded to this protocol.
Existing raw receipts, consumed V2/V3 attempts, preparation packages and dated
decisions remain unchanged; historical records cannot supply a missing marker.
Prospective fixtures explicitly use the new protocol. This task prepares or
rebinds no native fixture.

Scientific Contract V1, Adapter V2, allocations, fixed routes, measurement and
qualification rules, thresholds, active-membership optimization and all native
deadlines are unchanged. Parent loss, fatal failures, external signals and
indefinitely blocked OS calls remain outside universal guarantees. No promise
is made that this correction will pass a later native attempt.

## Offline validation and remaining gate

Final unchanged-harness, frozen-source validation passed:

| Offline surface | Tests | Subtests |
| --- | ---: | ---: |
| Integration (`new`) | 456 | 744 |
| Existing B0/Adapter (`existing`) | 153 | 175 |

Both reported zero failures, errors, skips, collection errors and forbidden-access
attempts, with unchanged source hashes. Focused subsets are included, not added
again. The full 56,943,083-byte synthetic C4 selection passed actual bounded
write/readback. In-memory compilation of 33 Python files, all 60 current/frozen
manifest identity entries (including eleven scientific dependencies), whitespace
and protocol-note links passed. These are offline results only.

Current production SHA-256 (`native_supervisor.py`):
`785963747bab8c713eaefbb03e582be4fc7490261f11d6a9c0a7c3b634eb41e5`.
Current projection-manifest SHA-256:
`6ecb1fec06486d6cba379a49684a1ec30543814bba2a43b997d7adda144d2dd8`.

Deterministic injected checks cover the actual worker's arm-before-marker edge
and the actual supervisor's marker-before-cleanup edge. Genuine worker messages,
collector/assessment, writer and independent readback are used for scientific
acceptance cases. Nested call-stack composition additionally starts from the
armed park and feeds the actual TERM handler and park return into parent
observation/reap. This is component-composed coverage: it is not one concurrent
whole-path execution with both call stacks suspended at DONE visibility, and it
does not establish native scheduling behavior.

An earlier compatibility-development run passed its assertions but failed the
source-stability guard while test development was still in progress; it is not
accepted validation. The first full prepublication integration run had 456 tests
and 744 subtests, with one stale current projection-test hash failure. Its source
hashes were stable and it recorded no forbidden-access attempt. Only the stale
current manifest entry was refreshed before the final rerun; historical entries
and production code were unchanged. Both unsuccessful runs remain retained
separately, not relabelled as passing evidence.

Current source/test identities and the complete prior map are recorded separately
in the [projection manifest](../../tests/reference/b0_od_integration_v1_projection.json).
No raw process evidence, local machine paths, private mappings or correspondence
are included in this public checkpoint.

Historical V3 L1 and V2 L1 remain FAIL; L2/L3 remain NOT_ATTEMPTED. This task runs
no native worker, real signal installation, wait/signal/socket probe, installed
client, simulator or calibration. Overall native gate, live integration and
readiness remain NO. Publication is one normal commit and draft PR only, with
no merge or formal approval claim.

Next gate: `REVIEW_COMPLETION_ARMING_PROTOCOL_CORRECTION`; not executed here.
