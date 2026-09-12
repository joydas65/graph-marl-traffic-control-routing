# B0 OD finalization V1 — schema-2 implementation checkpoint

8 September 2026. Local, uncommitted implementation on
`feature/b0-od-live-binding-v1`, based on
`c0be5ca5c0116179f901bd00410c74e581799c87` (tree
`3bf64d0607cd3e7b3ce446c145c92d178be4fb11`). This is synthetic offline
implementation evidence, not a simulator result or approval to run calibration.

## Implemented interface and review amendments

The [accepted proposal with review amendments](b0-od-finalization-contract-extension-v1-proposal.md)
is implemented through `collector.finalize_output(result) -> None`, called once
after the existing cutoff/cleanup and connection-close attempt. `result` is the
closed JSON-compatible FinalizationResultV1 dictionary initialized by
`finalization.new_result`. The collector supplies observations incrementally.
Integration sets `collection_state` (`NOT_ATTEMPTED`, `INTERRUPTED`, `COMPLETED`)
and derives parsing from the referenced original bytes; collector writes to
these two fields cannot control the recorded result. Normal return is not proof
of complete or clean evidence. Interrupted collection cannot qualify.

Every new run, selection and JSON envelope is explicitly schema 2. The terminal
object is version 1; persistence markers, pending latches and receipts remain
schema 1. The evidence writer checks the envelope/contained-record relationship.
There is no automatic legacy fallback, upgrade or schema inference.

`references=` is passed explicitly through observation, assessment, pair gates,
session/repeat replay, persistence and independent readback. A `ReferenceContext`
contains exact owner-supplied `ReferenceGrant` entries: run, condition, binding
digest, workspace-relative directory and original-output anchor. The owner may
explicitly authorize an additional exact grant before collection. No record
can grant its own scope. There is no filesystem discovery, fallback or network
retrieval; no context means unavailable support, never success.

The one shared validator checks all accessible artifacts before deciding
whether support is deficient or contradictory. It reuses the writer's anchored
no-follow, single-link regular-file and size-bounded reader. Nonblocking open
prevents a substituted FIFO from hanging before the regular-file check; this
does not alter the completion protocol. Artifact hashes bind retained bytes,
whereas captured device/inode tokens describe the original output object, not
the copied evidence file. Capture context and the externally supplied anchor
must agree. Content mismatches are distinct from object-token mismatches.

Only `B0_SYNTHETIC_TERMINAL_DIAGNOSTICS_V1` is implemented: canonical synthetic
JSON with explicit events for collisions, invalid routes, simulator errors,
warnings and incomplete/unknown coverage. Known positives survive incomplete
coverage. Unreviewed/native mappings cannot certify COMPLETE coverage.
The mapping implementation is included in the current source-hash binding.
Process facts and acquisition provenance remain synthetic fixture premises;
hash-consistent coherent fabrication is not authenticated by this design.

## First failure, final status and evidence persistence

- The chronological first observation/cleanup failure and operational abort
  remain unchanged. A close error becomes the first EVIDENCE failure only when
  no earlier failure exists; its cleanup record is also retained.
- A collector-recorded supported finding precedes a later acquisition exception.
  Findings derived only after interruption do not invent an earlier chronology.
  A deep copy preserves collected evidence against subsequent collector mutation.
- A validated late contradiction yields FAIL, including after a supported abort,
  with missing TripInfo, or before a later finalizer exception. Omitting its code
  cannot suppress the independently derived witness.
- Supported unchanged-clock/prefix abort without an independent contradiction
  remains BLOCKED. Full-H measurement stays unusable. No new abort taxonomy,
  retries or higher-level search is added.
- Complete observations with unavailable or interrupted finalization are
  INCONCLUSIVE, not scientific nonqualification. A stored terminal severity label
  cannot replace a witness that is no longer accessible. Earlier independently
  checked observation contradictions retain FAIL precedence.
- Unsupported assertions are invalid record evidence, not proof of a simulator
  defect. Strict structured RUN/FAILURE/SELECTION persistence rejects them.
  Uninterpreted rejected material may use the existing raw FAILURE path with
  `run=None`, without claiming a validated run status.
- Every schema-2 FAILURE containing a run carries the freshly assessed
  `experiment_status`. Successful persistence is only VERIFIED persistence; a
  previously revalidated experiment FAIL survives later persistence I/O failure.

Unchanged Adapter V2 parses/accounts the actual retained XML. Truncation and
unsupported structure are deficiencies; the exact missing/empty/duplicate ID
predicate is an integrity contradiction. Missing scheduled rows are handled by
existing accounting, including the existing proven-undeparted rule. No timestamp,
arrival, native-waiting sentinel, missing trip or scientific metric is invented.

## Compatibility and preserved provenance

`audit_legacy_run(record, revision=...)` is the only public legacy entry point.
It accepts the exact accepted checkpoint's four-module source tuple, recomputes
unchanged scientific bindings, and reports `LEGACY_FINALIZATION_UNVERIFIED`.
It is read-only and cannot enter new selection or persistence. Tests construct
explicitly synthetic V1-shaped fixtures with that known tuple; they do not
execute archived source, monkeypatch current source hashes or claim to replay
historical runs. Mixed run versions and selection/repeat histories are rejected.

The [projection manifest](../../tests/reference/b0_od_integration_v1_projection.json)
retains original validated, initial-publication and accepted-checkpoint hashes
and adjustments, alongside current hashes and new additions. It also pins all
eleven frozen dependencies and the unchanged stop-note/reproducer identities.
Scientific Contract V1, OD Adapter V2, historical evidence, all allocations,
thresholds, seeds, nine repeat families and six recursive exclusions remain
unchanged. In particular `collection_state` is not the excluded key `attempt`.
The 64 MiB writer/artifact limit and 24+2 future simulation budget are unchanged.

Existing integration tests now use retained synthetic artifact fixtures and
explicit reference arguments; envelopes use schema 2 and failure payloads supply
the required experiment status. Their scientific assertions remain intact.
The original seven-case characterization file and stop note are unchanged,
historical descriptions of the old interface—not new schema-2 acceptance tests.
They are not executed against the new interface or counted as new acceptance.

## Offline validation

Final offline validation **passed** on the exact source identities below using
CPython 3.12.14, Darwin arm64. Commands (with that standard-library interpreter):

```sh
python3 -I -S -B tests/run_b0_od_integration_offline.py new
python3 -I -S -B tests/run_b0_od_integration_offline.py existing
```

| Final nonoverlapping surface | Tests passed | Subtests | Failures/errors/skips/collection errors | Harness elapsed |
| --- | ---: | ---: | --- | ---: |
| Integration, including new finalization acceptance | 124 | 206 | 0 / 0 / 0 / 0 | 384.113 s |
| Existing B0/Adapter | 153 | 175 | 0 / 0 / 0 / 0 | 1.569 s |

Both runs reported unchanged source/manifest hashes and zero forbidden-access
attempts. All thirteen relevant Python files compiled in memory; whitespace,
local document links, current projection identities, eleven frozen dependency
hashes and preserved characterization hashes passed. Source/test changes were
reviewed; existing scientific assertions were not weakened. No source, test or
manifest changed after these final runs; only the documentation was completed.

The final C4 fixture's 26-record payload is **56,929,485 bytes**, below the
unchanged 67,108,864-byte bound. Actual write, independent bytes/hash readback and
selection finalization pass. Synthetic artifacts are confined to the existing
`.local-evidence/b0-od-integration-public-v1/synthetic-test-outputs` area; no
historical raw evidence is read. This fixture is not execution of the scientific
simulation budget. Focused/development runs below are not added to final totals.

An initial focused development run passed 33 of 34 cases with 57 subtests;
one new test guessed a missing-row reason code. The unchanged Adapter reported
its exact three deficiencies; the test assertion was corrected. There were no
runtime-access attempts and source hashes remained stable. A prior three-name
smoke invocation also had one test-loader error from an incorrect class name;
its other two tests passed. Neither development invocation is final acceptance.

A subsequent development run passed all 123 integration tests/206 subtests and
153 B0/Adapter tests/175 subtests. Final source review then found a non-string
collector finding code could raise an unhashable-key TypeError while retaining
the first acquisition failure. One isolated regression reproduced that error;
a narrow string-type guard now retains the interrupted record and rejects its
malformed assertion through normal validation. Final acceptance reruns include
this regression and use the newly frozen source identities below.

## Changed files and exact current source identities

| Production file | SHA-256 |
| --- | --- |
| [`integration.py`](../../scripts/b0/od_integration_v1/integration.py) | `3b0b6cf8e50e80c0ce3f894f1ab70412f643e60bcf5b7e6953126ae4806ec767` |
| [`qualification.py`](../../scripts/b0/od_integration_v1/qualification.py) | `1714474bde733113268f3b4e831939f64c6487eff3cd521fb02cf407fcfe9182` |
| [`evidence.py`](../../scripts/b0/od_integration_v1/evidence.py) | `673c9627ac6c2b8797e222d8497fd580b02c55f6e69b2883c3bf94f89d36f09f` |
| [`finalization.py`](../../scripts/b0/od_integration_v1/finalization.py) (new) | `1e8d2cabab7e973347b4e0ba962b8dfc45d571404b45fc08284e148fff5b2a58` |

Other files changed in this task:

- [Synthetic fixture](../../tests/b0_od_integration_fixtures.py),
  [offline harness](../../tests/run_b0_od_integration_offline.py) and
  [projection manifest](../../tests/reference/b0_od_integration_v1_projection.json).
- [New finalization acceptance tests](../../tests/test_b0_od_integration_finalization.py),
  [observation tests](../../tests/test_b0_od_integration_observation.py),
  [qualification tests](../../tests/test_b0_od_integration_qualification.py),
  [operational-abort tests](../../tests/test_b0_od_integration_operational.py),
  [writer tests](../../tests/test_b0_od_integration_evidence.py) and
  [projection tests](../../tests/test_b0_od_integration_projection.py).
- [Amended proposal](b0-od-finalization-contract-extension-v1-proposal.md), this
  implementation record, [documentation index](../README.md) and
  [monthly effort log](../progress/monthly-effort-log.md).

The manifest carries full current fixture/test/harness hashes, the exact legacy
source tuple, and preserved historical identities. The stop note and original
seven-case test remain present but are **not changed in this task**. No file is
staged and HEAD remains the accepted checkpoint; these are working-tree identities,
not a new commit, published checkpoint or formal approval.

## Native/live limitations and authorization boundary

No native launcher/transport, process wait implementation, SUMO message mapping,
real output anchoring, client binding or live-execution capability was added.
Synthetic process observations do not prove live compatibility or provenance.
No simulator/client import, process/socket operation inside tests, calibration,
AWS, Candidate N/private material, RL, routing or treatment work occurred.
No commit, push, PR, merge, history rewrite, policy/hook change or retained-ref
operation is part of this checkpoint. Candidate N remains parked, no OD
concentration is selected, dissertation delta is unset, and readiness is false.

```text
FINALIZATION_EXTENSION_IMPLEMENTED=YES
FINALIZATION_OFFLINE_VALIDATION=PASS
THIN_LIVE_BINDING_IMPLEMENTED=NO
LIVE_PROCESS_STARTED=NO
LIVE_INTEGRATION_VALIDATED=NO
OD_CALIBRATION_EXECUTED=NO
SELECTED_CALIBRATED_OD_CONCENTRATION=NONE
DISSERTATION_DELTA_REMAINS_UNSET=YES
COMMIT_CREATED=NO
PR_CREATED=NO
READY_TO_RUN=NO
NEXT_TASK=REVIEW_FINALIZATION_EXTENSION_IMPLEMENTATION_AND_RESUME_THIN_LIVE_BINDING
```

The recommended next task has **not** been executed.
