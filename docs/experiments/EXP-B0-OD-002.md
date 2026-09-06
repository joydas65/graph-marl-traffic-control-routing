# EXP-B0-OD-002: offline integration pre-run checkpoint

**Date:** 6 September 2026. **Identity:** `B0_OD_INTEGRATION_LAYER_V1`.
**Classification:** synthetic implementation evidence; draft independent review pending.

## Question, base and claim boundary

Can the published OD Adapter V2, unchanged Scientific Contract V1, observation,
qualification, first-qualifying selection and strict writer work together through
one offline core with injected fake connections?

Publication base was freshly fetched and fast-forward-only verified as main
`b9cccd5cf8fe129711e6e9b36089312525e1fc01`, tree
`9964753414c9fd1d22a5bb3683141b925a5c2b0e`.
The contract's `eccc2bb2a3318ac364396a828a4d0a0106d9e764` remains historical
source provenance, not a checkout/reset requirement.

This checkpoint subsequently implements components that were absent in
[EXP-B0-OD-001](EXP-B0-OD-001.md) and the
[publication-hygiene snapshot](../decisions/0003-repository-publication-privacy.md).
Those older records remain unchanged historical snapshots. No OD calibration,
selected concentration, treatment or dissertation-hypothesis result is created.
Candidate N remains parked; historical privacy cleanup remains incomplete.

## Implemented interfaces and unchanged dependencies

- [`integration.py`](../../scripts/b0/od_integration_v1/integration.py):
  `build_binding`, `materialize_input`, `observe_run`, `validate_run`,
  `normalized_scientific`. Reuses public OD generation/XML validation, the
  cutoff observer, supplied-tripinfo parsing and actual Adapter V2 accounting.
- [`qualification.py`](../../scripts/b0/od_integration_v1/qualification.py):
  `qualify_pair`, `SelectionSession` and full selection-record revalidation.
  Reuses published completion and local-response helpers after measurement validation.
- [`evidence.py`](../../scripts/b0/od_integration_v1/evidence.py):
  `write_once`, `write_input_once`, `readback`, strict synthetic envelopes.

The [projection manifest](../../tests/reference/b0_od_integration_v1_projection.json)
records nine original/public source pairs, exact SHA-256 identities, every
projection adjustment and eleven accepted dependency/input hashes. The package
initializer, integration and qualification sources are byte-identical to their
validated originals. The only production-byte change is the writer's WORKSPACE
expression: a new repository-relative isolated output directory. It reads no
original ignored implementation or historical raw evidence.

Test changes are public package/fixture imports, output paths and parent-directory
creation, public discovery/source inventory, and printing measured C4 payload size.
Two publication-only tests add import/source-identity and oversize-rejection
checks; no old assertion is weakened. Their additional source identity is
[`tests/test_b0_od_integration_projection.py`](../../tests/test_b0_od_integration_projection.py), SHA-256
`25b8b3e89f05df10453db2f7be68db440ce6b7c5d13889297898374b77a30ccd`.

Scientific Contract V1 and Adapter V2 remain unchanged. So do all 540 scheduled
trips, twelve frozen allocations, IDs/departures, route geometries, three seeds,
held-out-location exclusions, H=1500, t=300/600 intervention, thresholds and
24-plus-two future simulation budget. No duplicate allocation table was added.

## Observation and decision semantics

The caller supplies a connection/collector; this package never launches a
simulator. One before/advance/after callback sequence covers each second through
1500. The pre-activation endpoint is retained, D0 permission operations precede
the next interval's observation/advance at 300 and 600, N0 applies no restriction,
and cutoff populations are captured before cleanup. Output is parsed only after
the supplied output-finalization step. Independent restoration/close attempts
preserve the first failure and record cleanup errors without retry.

Recomputed integrity failures stop as FAIL before any scientific gate. Required
measurement EVIDENCE_DEFICIENCY stops INCONCLUSIVE; missing data never becomes
zero or ordinary traffic nonqualification. A prior technical failure does not
override a contradictory Adapter result; its original category/stage is retained.
Otherwise-valid measurements use definitive scientific failure before required
unknowns, then qualification. A legitimate NOT_IDENTIFIABLE local diagnostic
is distinct from invalid/deficient primary measurement.

Inclusive completion, actual observed event-entry exposure, zero
teleport/collision/invalid-route counts, visit-based lane compliance and unchanged
controls are required. Mean comparison uses all-scheduled restricted-time sums;
queue comparison is exact cross-multiplication, with zero baseline queue unknown.
Censored lower bounds never become completed traversal durations.

C1→C4 requires all three ordered seed pairs per level. The first qualifier locks
higher levels, requires exact first-seed N0/D0 repeats, and remains provisional
until readback. All nine scientific families and remaining record fields are
compared, excluding only six contract-listed operational fields. Repeat/readback
failure stops; no extra levels, seeds or automatic retries are authorized.
Four trustworthy definitive failures yield NO_QUALIFYING_OD_CONCENTRATION.

## Writer and preserved size-correction history

The initial 32 MiB (33,554,432-byte) limit rejected the legitimate full
26-record synthetic bundle during development. That exploratory run had 69
passes and one size assertion failure; a concurrent late test edit also changed
its source inventory, so final acceptance used a fresh frozen-source rerun.
The prior correction raised only the operational bound to 64 MiB
(67,108,864 bytes); publication does not change it.

The largest-record-count fixture measured **56,899,689 bytes** in this
public validation. `test_first_qualifier_at_each_level_has_exact_bounded_evidence_counts`
checks all four first-qualifier outcomes and, for C4, the complete 26-record
serialization, size allowance, actual write, independent bytes/hash readback and
finalization. `test_oversize_json_is_rejected_without_completed_record` separately
proves the retained limit fails explicitly before data/completion publication.
This bounds the tested fixture, not every possible future trajectory.

Whole-payload schema/scientific validation and strict deterministic UTF-8 JSON
(allow_nan=False, one newline) precede publication. Exclusive creation and
no-follow directory traversal reject overwrite, unsafe paths and symlinks.
Writes are fsynced and read back; byte count/hash and payload validity are
rechecked. Completion requires verified data, its verified marker, **and absence
of the pending latch**. The latch is removed only after required writes, reads
and descriptor closes succeed. A marker alone never establishes completion.

Invalid measurements may persist only as FAILURE records, without changing
their status. Raw NaN/Infinity is neither stripped nor stringified; serialization
fails, with a separate bounded failure receipt where safely possible.
Interrupted/short writes, fsync/close/latch failures, conflicts and corruption
cannot become completed successful results under the tested conditions.
Environmental I/O failures map to BLOCKED; schema/readback contradictions to FAIL.
No power-loss, cross-platform or adversarial-concurrency guarantee is claimed.

## Public offline validation

Run from the repository root with a suitable standard-library Python:

```sh
python3 -I -S -B tests/run_b0_od_integration_offline.py new
python3 -I -S -B tests/run_b0_od_integration_offline.py existing
```

The harness uses public imports, denies real runtime/process/socket access and
reading other ignored evidence, and confines generated temporary outputs to its
new isolated directory. Tests remove their temporary bundles. No bulky bundle,
original ignored package, machine receipt or historical simulation output is published.

| Surface | Tests passed | Subtests | Failures/errors/skips/collection errors | Harness elapsed |
| --- | ---: | ---: | --- | ---: |
| New public integration | 74 | 94 | 0 / 0 / 0 / 0 | 207.857 s |
| Existing B0/adapter | 153 | 175 | 0 / 0 / 0 / 0 | 1.42 s |

The original 72/85 integration surface is retained; two publication tests add
nine source-identity subtests, yielding 74/94. CPython 3.12.14, Darwin arm64;
these timings are local test costs, not traffic-performance benchmarks.
All ten new Python files compile in memory. Both suites retained exact source
hashes throughout and reported zero forbidden-access attempts.

Coverage includes twelve input reconstruction/readbacks, complete and censored
accounting, the exact waiting-overflow counterexample, measurement rejection,
numerical boundaries/unknown precedence, callback ordering, cleanup failure,
first qualifier at each level, no qualifier, repeat locks, strict FAILURE/RUN
roundtrips and full real-component synthetic C1/C4 end-to-end paths. The complete
hand fixture independently expects 540 arrivals, N0/D0 means 101/102 seconds
and queues 540/567. Those are synthetic answers, not calibrated traffic results.

## Remaining boundary and review gate

The thin live launcher/collector is **absent**. A separately authorized binding
must supply actual loaded input identities (not echo expected hashes), runtime
settings/TLS definitions, diagnostics, pending populations and finalized output
to this same core. Actual SUMO timing, callback/permission semantics, settings
readback and output-finalization behavior remain unvalidated. The current
record/writer path is deliberately synthetic-only.

Codex self-review and offline tests are not independent source review, simulator
acceptance, faculty approval or scientific superiority. The 26 fake records do
not consume or complete the future 24 scientific simulations plus two repeats.

```text
OUTPUT_WRITER_IMPLEMENTED=YES
QUALIFICATION_INTEGRATION_IMPLEMENTED=YES
OFFLINE_INTEGRATION_VALIDATED=YES
LIVE_INTEGRATION_VALIDATED=NO
OD_CALIBRATION_EXECUTED=NO
SELECTED_CALIBRATED_OD_CONCENTRATION=NONE
DISSERTATION_DELTA_REMAINS_UNSET=YES
READY_TO_RUN=NO
```

Next gate: INDEPENDENTLY_REVIEW_B0_OD_INTEGRATION_PUBLIC_PR_BEFORE_MERGE.
No merge or live validation is part of this checkpoint.
