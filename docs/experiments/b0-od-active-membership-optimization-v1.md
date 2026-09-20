# B0 per-pass active-membership optimization V1

## Scope and decision

Accepted base: `736994bdf2ded68c4c0c2f432a599b1a796bada9`; tree:
`d46acb8f23563b4530f447a06aad0fe0cfc7013b`.

This checkpoint evaluates one computation-only change in
[`integration._validate_run`](../../scripts/b0/od_integration_v1/integration.py).
The original native L1 remains FAIL; L2/L3 remain NOT_ATTEMPTED. Its timeout
cause is not established by either the earlier offline profile or this new
comparison. Historical fixtures, the consumed native attempt and the original
profiling script, receipt and generated evidence remain unchanged.

The candidate showed equivalent outputs and consistent useful reductions on
the fixed offline workload below. This supports further review of this narrow
optimization, not a native deadline, live-readiness or scientific claim. No
second optimization was attempted.

## Exact computation and preserved boundaries

Previously, each control sample scanned the entire retained departure map to
construct vehicles satisfying `departure <= sample_time` and either no recorded
arrival or `sample_time < arrival`. The candidate builds one fresh call-local
event index, then adds/removes vehicles at each integer sample boundary.
Arrivals remain exclusive, including simultaneous departure/arrival. Departure
at zero is represented at the first sampled instant; missing arrivals remain
active through the horizon.

The fast path accepts only bounded plain dictionaries, string vehicle IDs,
single-element plain lists and exact integer or integral-float timestamps in
`[0, horizon]`. Map sizes are bounded by the independently recomputed ledger.
Unsupported or malformed evidence uses the unchanged original comprehension.
Eligibility does not raise early errors or derive expected membership from
the supplied `active_ids`. No input is mutated and no index survives a call.

All per-sample identity, duplicate, active/halting membership, queue, permission
and diagnostic checks remain, as does exposure replay. The change removes the
repeated whole-map scan; it does not make every validation operation linear.
Accounting, source checks, finalization, canonical persistence, independent
readback, unknown evidence handling and FAIL precedence remain unchanged.
Frozen Adapter V2, Scientific Contract V1, allocations, metrics, thresholds,
runtime bounds, worker/supervisor/transport and writer source are untouched.

## Differential and actual-component evidence

The focused guarded surface passed **13 tests / 51 subtests**. These tests are
included in the combined integration surface, not added again to its total.
The [oracle](../../tests/b0_active_membership_oracle.py) restores only the two
marked active-membership blocks in the current validator and verifies the
entire restored function AST against the accepted base. It does not execute
archived modules or bypass current source identities.

The [regressions](../../tests/test_b0_od_integration_active_membership.py)
compare complete validation/assessment outputs, statuses, reason codes,
ledger/metrics and input nonmutation. Coverage includes N0/D0 and repeats,
no departures, missing arrivals, cutoff-active vehicles, simultaneous and
multiple boundaries, zero/full horizons, supported prefixes, shuffled maps,
integral floats and numeric/container subclasses. Fractions, booleans,
nonfinite/huge values, missing/duplicate/empty events, contradictory ordering
and malformed containers retain reference behavior. Bad sample time/control
identity still precedes later malformed event evidence.

Actual injected worker execution independently validates four times: assessment,
writer prepublication, writer verification and explicit worker readback. Tests
verify fresh results at each boundary and reject observation changes introduced
at the writer or later independent readback; no earlier success hides them.
Supported BLOCKED prefixes and INCONCLUSIVE deficient evidence remain distinct
from independent contradictions that require FAIL.

## Fixed paired comparison

Evidence identity: `B0_ACTIVE_MEMBERSHIP_PAIRED_OFFLINE_V1_20260920`.
The protocol/source identities were frozen before the six measurements. Order
was fixed as baseline/candidate, candidate/baseline, baseline/candidate. Every
sample was retained; no warm-up forward, fastest-sample selection or retry was
used. All six executions completed.

Each fresh source-bound SYNTHETIC C1/N0 workload used seed `20260904`, **540
scheduled trips, 540 actually observed departures and 1,500 steps**, with the
same pinned CPython 3.13.5 interpreter/configuration. Input preparation, source
binding and prepared synthetic tripinfo construction were outside the timer;
ordinary source checks inside forward validation remained timed. Each run used
the genuine observation, assessment, `write_once` and worker readback, with
native operations injected under the unchanged denial harness.

Identical memory-only wrappers measured wall/process-CPU time. Fixture event
and profiling samples were not fsynced during timing; the genuine writer's
filesystem verification and fsync were retained. Conceptual FINALIZE begins
at the actual FINALIZE notice and ends at forward return; no native supervisor
or native FINALIZE timer ran. Validation times below are the **sum of four
complete `_validate_run` calls**, not isolated set-computation time. Each sample
performed **6,000 active-membership comparisons** across those four calls.

All values are seconds, shown as **wall / CPU**:

| Pair/order | Variant | Validation, four calls | Conceptual FINALIZE | Complete forward |
|---|---|---:|---:|---:|
| 1 / first | Baseline | 1.023095 / 0.899610 | 1.353963 / 1.140951 | 2.658715 / 2.359624 |
| 1 / second | Candidate | 0.781079 / 0.656621 | 1.114261 / 0.908224 | 2.420642 / 2.134978 |
| 2 / first | Candidate | 0.783082 / 0.660829 | 1.116312 / 0.903400 | 2.468774 / 2.137227 |
| 2 / second | Baseline | 1.267470 / 0.938501 | 1.626229 / 1.202610 | 2.946143 / 2.438610 |
| 3 / first | Baseline | 1.029585 / 0.883554 | 1.361130 / 1.142822 | 2.806700 / 2.377419 |
| 3 / second | Candidate | 0.773832 / 0.648466 | 1.097263 / 0.890138 | 2.401182 / 2.107929 |

Within-pair reduction is `1 - candidate / baseline`, again **wall / CPU**:

| Pair | Validation reduction | FINALIZE reduction | Forward reduction |
|---|---:|---:|---:|
| 1 | 23.66% / 27.01% | 17.70% / 20.40% | 8.95% / 9.52% |
| 2 | 38.22% / 29.59% | 31.36% / 24.88% | 16.20% / 12.36% |
| 3 | 24.84% / 26.61% | 19.39% / 22.11% | 14.45% / 11.34% |

All six retained complete assessments and per-call validation results agreed.
Each worker's actual written payload equalled its explicit readback. The fifteen
cross-namespace comparison fields also agreed: full observations/accounting,
controls, exposure, lifecycle/failure state, finalization semantics, assessment
and validation results. Only fresh run/path identities and identity-bearing
finalization references were excluded from cross-namespace comparison; each
run's complete original references were independently validated, not rewritten.
Arithmetic was independently recomputed from retained nanosecond clocks/call
traces and per-sample receipts. All 49 bound source identities and 81 original
fixture/native/profile evidence files matched their premeasurement snapshots;
no forbidden access occurred.

Three instrumented pairs do not estimate a runtime percentile, establish the
historical interrupted checkpoint or explain its timeout. They omit native
IPC, process scheduling, signal handling and supervisor deadlines. No timing
threshold was added to correctness tests, no deadline changed, and no native
attempt was authorized or performed by this comparison.

## Identities and complete-suite gate

Current identities are recorded in the
[projection manifest](../../tests/reference/b0_od_integration_v1_projection.json),
with prior identities retained as historical provenance.

| Artifact | SHA-256 |
|---|---|
| `scripts/b0/od_integration_v1/integration.py` | `28d841460c8668fa05c7cee8e32661628344b9cd85b6a1298296e47c3ca119a1` |
| `tests/b0_active_membership_oracle.py` | `7ed3d4c2fcf3ee0194425abb643c8d105dcc7db52bfba3b98eb11c3e89292073` |
| `tests/test_b0_od_integration_active_membership.py` | `56ea0241805fd678d29b7fa12263ad1141ab4526fde634e73292bd3620c53bf7` |
| New offline `benchmark.py` | `da096bba87bebb3c91e8237f7333bedb1b9eeb6fb7b17aed57f194130002dc65` |
| Frozen offline `PROTOCOL.md` | `8d65b34c8a6bfbbe4db35053e1687596fdfdae0fc2c1745dfbaea94e5f759656` |

The benchmark, protocol and raw machine receipts remain in the ignored evidence
namespace under the named evidence identity; no raw private evidence is
published here. The original profile remains unchanged and is not relabelled
as a baseline measurement from this comparison.

After equivalence and useful benefit were established, the unchanged guarded
commands passed **426 integration tests / 663 subtests** and **153 existing
B0/Adapter tests / 175 subtests**. Both reported zero failures, errors, skips,
collection errors or forbidden-access attempts, with stable source hashes.
The 13-test focused subset is included, not added again. The earlier 11-test /
47-subtest development PASS remains a separate retained result, not an extra
acceptance count. The 56,943,083-byte synthetic C4 selection passed actual
write/readback within the unchanged bound. In-memory compilation of 33 Python
files, projection/frozen-dependency checks, whitespace and note links passed.

All 88 snapshotted historical-evidence, frozen-adapter, denial-harness and local
privacy-control files remained unchanged. The checkpoint is prepared for one
focused normal commit and draft-only PR. Remote publication is currently
blocked by an authenticated GitHub API Conditional Access denial (HTTP 403);
no push, created PR or hosted-byte verification is claimed. No formal approval,
merge, policy change or native revalidation is claimed. Raw machine receipts
stay ignored.

```text
ORIGINAL_L1_STATUS=FAIL
L2_STATUS=NOT_ATTEMPTED
L3_STATUS=NOT_ATTEMPTED
NEW_NATIVE_ATTEMPTS=0
DEADLINES_CHANGED=NO
ACCEPTANCE_SEMANTICS_CHANGED=NO
FROZEN_ADAPTER_V2_CHANGED=NO
INDEPENDENT_VERIFICATION_BOUNDARIES_PRESERVED=YES
OVERALL_NATIVE_GATE_SATISFIED=NO
LIVE_INTEGRATION_VALIDATED=NO
SUMO_PROCESS_STARTED=NO
OD_CALIBRATION_EXECUTED=NO
SCIENTIFIC_SIMULATIONS_CONSUMED=0
READY_TO_RUN=NO
PR_MERGED=NO
NEXT_TASK=REVIEW_ACTIVE_MEMBERSHIP_OPTIMIZATION_AND_PAIRED_OFFLINE_EVIDENCE
```

The next task is independent review, not execution of another native attempt.
