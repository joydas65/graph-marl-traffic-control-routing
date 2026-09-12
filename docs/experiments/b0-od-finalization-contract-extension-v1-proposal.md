# B0 OD finalization V1 — reviewed contract extension

2026-09-06 proposal; 2026-09-07 **accepted for implementation with the review
amendments below**. The original characterization remains historical evidence.
Implementation and current verification are recorded in the
[schema-2 implementation checkpoint](b0-od-finalization-extension-v1-implementation.md).
Checkpoint-relative call sites and the original proposal-only status below are
historical; the accepted amendments and implementation record supersede them.
Addendum to the [preserved stop note](b0-od-live-binding-v1-stop-note.md).
HEAD/main/local origin/main: `c0be5ca5c0116179f901bd00410c74e581799c87`;
branch: `feature/b0-od-live-binding-v1`. Existing uncommitted work is preserved.

## 1. Information-loss boundary and evidence limits

All source locations below refer to that checkpoint or the unchanged local
[seven-case reproducer](../../tests/test_od_live_binding_finalization_boundary.py).
`FinalizationDouble.close` (lines 36–46) **assigns** synthetic completion,
exit-code 1 and contradiction flags. It does not wait for a real process,
inspect logs, or compare actual file identities. `finalize_output` (48–54)
obtains fake XML after fake close and either raises or returns it. Thus the
seven passing characterization cases establish information loss and current
control flow, **not verified output-identity findings or live compatibility**.
The stop note's “known contradiction” means the injected test premise only.

Keep five sources distinct: an owned-process wait result; finalized diagnostic
streams; availability of the designated output bytes; parsing those bytes;
and identity/integrity checks binding them to the intended run. Neither a
successful parse nor process exit 0 proves all five. The matrix in section 5
maps every characterization case; proposed FAIL requires the witness rules below,
not the existing fixture's boolean or exception name.

## 2. One proposed interface

Propose `collector.finalize_output(result: FinalizationResultV1) -> None`
**for opt-in run schema 2 only**. Integration owns this small result object;
the collector fills it incrementally, preserving findings even if acquisition
throws. Call once after cutoff capture and the connection-close attempt; no
retry, new step or launch. Initially use NOT_ATTEMPTED/UNOBSERVED/UNAVAILABLE,
null counts/references, NOT_ATTEMPTED parsing, UNVERIFIED identity and no findings.
Set INTERRUPTED before entering the collector, COMPLETED only on normal return;
never erase established findings on a later error; deep-copy the finished record.
The closed JSON-compatible fields are:

| Field | Type and allowed values |
| --- | --- |
| `version` | Exact integer `1` (not boolean). |
| `collection_state` | `NOT_ATTEMPTED`, `INTERRUPTED`, `COMPLETED`; integration-owned. Completion means the bounded collection procedure returned, not that evidence was clean/complete. |
| `process` | `{state, exit_code}`; state `UNOBSERVED`, `NOT_EXITED`, `EXITED`; exit code integer only for `EXITED`, otherwise null. Negative signal exits are retained. |
| `diagnostics` | `{coverage, counts}`; coverage `UNAVAILABLE`, `INCOMPLETE`, `COMPLETE`; counts has exactly `collisions`, `invalid_routes`, `simulator_errors`, each nonnegative integer or null for unknown. |
| `tripinfo` | `{availability, parsing, identity}`; availability `UNOBSERVED`, `MISSING`, `UNREADABLE`, `AVAILABLE`; parsing `NOT_ATTEMPTED`, `PARSED`, `UNPARSEABLE`; identity `UNVERIFIED`, `MATCH`, `CONTRADICTED`. |
| `findings` | Ordered list of `{code, evidence_keys}`; codes are from the closed list below, and evidence keys identify retained supporting items in `output_identity`. No severity, PASS/FAIL, `verified=true` or arbitrary exception text field. |
| `output_identity` | `{output_directory, artifacts, output_observations}`. Directory uses the existing workspace-relative receipt convention and is supplied by the owner. Artifacts has exactly `tripinfo`, `diagnostics`, `capture`, each null or an `ArtifactRef`. Output observations are `{expected, observed}`, each null or `{device, inode, byte_count, sha256}`; device/inode are nonnegative integers, byte count/hash both null or a bounded count and digest. |

`ArtifactRef` is `{name, byte_count, sha256}` using existing `evidence.NAME`,
nonnegative byte counts bounded by `MAX_BYTES`, and `evidence.SHA256` conventions.
All integer fields exclude booleans; unknown keys/enums are rejected.
These are **dependency references, not new completion receipts**. Empty diagnostic
streams may have zero bytes. Capture is canonical JSON with exactly `run_id`,
`condition_label`, `binding_sha256`, `process`, `output_observations`; the latter
two use the types above. The binding digest uses existing `integration.digest`.
Capture binds the collector's observations to the run, not to an arbitrary path.

Only these finding codes are proposed:
`OUTPUT_OBJECT_MISMATCH`, `OUTPUT_BYTES_CHANGED`, `COLLISION_OBSERVED`,
`INVALID_ROUTE_OBSERVED`, `UNEXPLAINED_SIMULATOR_ERROR`,
`PROCESS_WAIT_UNAVAILABLE`, `PROCESS_NONZERO_EXIT`, `DIAGNOSTICS_UNAVAILABLE`,
`TRIPINFO_MISSING`, `TRIPINFO_UNREADABLE`, `TRIPINFO_UNPARSEABLE`, `TRIPINFO_ID_CONTRADICTION`,
`FINALIZER_EXCEPTION`. Order is discovery order, not an invented wall-clock or
simulator timestamp. At most one entry per code; evidence keys are drawn only
from `tripinfo`, `diagnostics`, `capture`, `output_observations`.

### Witness and validation rules

- The collector owns bounded wait/output acquisition and captures the intended
  output object's identity when established, then the actual read object's
  identity. Missing expected identity is **unverified**, not a mismatch. Content
  baselines are captured only after process finalization: normal growth of a
  running output file is not OUTPUT_BYTES_CHANGED. It
  retains original bytes; it never fabricates missing trips or edits sentinels.
  Available output for accounting requires an observed process exit; non-exit
  must not be represented as finalized output. A successful collection may still
  report missing output or an incomplete diagnostic stream.
- `OUTPUT_OBJECT_MISMATCH` requires two non-null unequal object tokens, an
  intended-output anchor recorded by the reviewed launcher, and matching capture
  context. `OUTPUT_BYTES_CHANGED` compares captured expected/observed content
  snapshots. The artifact reference always binds the actually retained observed
  bytes; it must NOT deliberately contain a bad hash to represent this finding.
  This allows a genuine mismatch witness to persist, while a later artifact/hash
  mismatch remains independent readback corruption. An arbitrary expected digest
  or filename supplied after the fact is not an anchor. Unknown identity instead
  contributes a deficiency. Device/inode facts alone do not prove authenticity.
- Diagnostic counts must be reproduced from the referenced finalized stream
  by the fixed reviewed collector's version-specific mapping. Only an explicit
  collision, invalid-route finding, or unexplained simulator-error observation
  supporting the corresponding frozen zero-tolerance rule establishes an
  integrity contradiction. No new message-pattern mapping is invented here:
  implementing/reviewing that SUMO mapping remains part of the later binding.
  Its implementation identity must be source-bound before use; absent or
  unsupported mapping cannot certify COMPLETE coverage.
  Unknown messages/missing coverage remain incomplete; known positive findings
  retain precedence even with incomplete coverage. Warnings are retained in
  diagnostic evidence but are not automatically errors. Exit code 1 or a timeout
  alone establishes neither an integrity contradiction nor a new BLOCKED class.
- Integration reads available original TripInfo bytes through the bounded
  reference reader and runs unchanged `adapter.parse_tripinfo_xml`. The collector
  leaves `parsing=NOT_ATTEMPTED`; integration fills the derived parsing value
  and existing `observations.tripinfo_records`. Readback reparses the same bytes
  and compares the rows. Missing/unreadable/truncated XML is deficiency absent
  an independently established contradiction. Do not infer severity solely from
  `ValueError`. For parseable TripInfo with empty/duplicate IDs, the exact existing
  predicate in `cutoff_measurement.parse_tripinfo_xml` (267–280) independently
  supports TRIPINFO_ID_CONTRADICTION; wrong/unsupported XML structure alone is
  unparseable evidence. Unchanged Adapter checks govern successfully parsed rows.
- Integration/readback check closed types, code/witness consistency, run/binding
  association, reference hashes, parsing and the diagnostic mapping. A claimed
  clean result, MATCH or integrity code with absent required reference fields,
  inconsistent available facts, or an unsupported code is rejected
  as invalid evidence (`FAIL` of record validation, **not proof of the claimed
  simulator defect**). Well-formed references that cannot currently be read
  instead give unavailable support/deficiency, not an invented contradiction.
  Terminal first-failure labels alone cannot override this independent assessment.
  Hash-consistent, entirely fabricated capture records cannot be authenticated
  by this scheme; process ownership and acquisition provenance remain collector
  obligations requiring subsequent live validation. Origin labels authorize nothing.

The reference reader is narrowly scoped to the existing isolated evidence
workspace, with explicitly supplied authorized directory context, existing
no-follow/regular-file/size checks, and no network, path discovery or fallback.
It may use the existing `_directory`/`_read` primitives; it is not a new writer or
general evidence service. Run-envelope completion remains data + verified marker
and no pending latch, with referenced bytes checked before completion and again at
readback. Missing references never receive success-by-default. Raw logs and
exception details stay in excluded local evidence; public diagnostics contain
only the bounded codes. No new raw-artifact or process acquisition occurs here.

## 3. Existing precedence, applied to terminal evidence

This table applies [Scientific Contract V1](../../configs/b0/od-concentration-v1/calibration-contract.json)
`future_status_contract` (531–543); it is not a second scientific-status authority.
Apply integrity checks first, including checks independent of the supported
abort. Only the existing three consequential missing-tail errors may be excluded
by verified-prefix assessment; terminal contradictions are never excluded.

| Case | Required evidence | Run / original pair outcome; ladder consequence |
| --- | --- | --- |
| A. Otherwise complete + late integrity contradiction | Validated terminal witness, not a flag | `FAIL`; no qualification; session stops. |
| B. Supported abort + late contradiction | Existing unchanged-clock/prefix proof **and** validated terminal witness | `FAIL`; retain original abort/first failure and later finding; session stops. |
| C. Supported abort without contradiction | Existing prefix proof; finalization clean or explicitly unavailable | `BLOCKED`; partial full-H measurement remains invalid; no qualification/ladder advance. |
| D. Complete + required evidence unavailable | Honest missing/unreadable/incomplete evidence; no independent contradiction | `EVIDENCE_DEFICIENCY` / `INCONCLUSIVE`; no original-pair qualification; session stops. Nonzero exit alone follows this unresolved-evidence path, not automatic FAIL/BLOCKED. |
| E. Valid observations + valid finalization | Exit 0, covered diagnostics with no established errors, bound complete parseable output, existing controls/accounting valid | Existing qualification may run; neither finalization nor persistence grants automatic PASS. |
| F. Earlier contradiction + later clean finalization | Existing verified integrity error | Remain `FAIL`; later success cannot erase it. |

Chronological first failure and decisive status are separate. For schema 2,
never alter a non-null `failure` or `operational_abort`. Preserve all existing
cleanup records. If no primary failure exists, the first encountered close/
acquisition failure becomes `failure` with the existing EVIDENCE kind; retain its
cleanup entry too. A first terminal integrity finding uses INTEGRITY only after
its witness validates. Generic finalizer exceptions become interrupted acquisition
with `FINALIZER_EXCEPTION`, not severity inferred from their class; capture any
earlier established terminal findings before that interruption. Later findings
remain in `finalization` even when an earlier failure already exists.

## 4. Exact change sites proposed, not changed

Locations are in `scripts/b0/od_integration_v1/` unless indicated otherwise.

- **`integration.py`:** `RUN_KEYS` (25), `observe_run` (246; construction 269,
  cleanup 395–398, finalizer/accounting 399–406): explicit schema-2 opt-in and one
  integration-owned `finalization` result; preserve incremental evidence on
  exceptions. Set `output_finalized`
  from observed process exit plus complete acquisition/parse, not merely a
  returned object; it is still not evidence of scientific validity. Retain first
  failure, later findings and raw references separately. No change to stepping,
  cutoff capture, lane operations or `_account`'s Adapter arithmetic (410).
- **`_validate_run` (415, especially 448–486 and 583–584), `validate_run` (588),
  `assess_run` (593):** share one narrow finalization-witness validator in full
  and prefix modes. Add terminal integrity/deficiency reason codes to the freshly
  validated result; retain the stored Adapter measurement verbatim. Derive stop
  status once here; the prefix path at 603–609 cannot overwrite terminal FAIL.
  Reference-reading context must propagate through these calls; no reader means
  coverage unavailable, never clean. Malformed asserted evidence is rejected.
- **`qualification.py`:** `_pair` (39; assessment 52; guards 62–76),
  `qualify_pair` (122), `SelectionSession.add_level` (168; precedence 195–205),
  `add_repeats` (211), `to_record` (249), `finalize` (258),
  `validate_selection_record` (277): pass the same authorized read context,
  dispatch schema and retain the finalization field in copied runs. Reuse existing
  stop branches and replay, without a second severity calculation. Existing
  repeat behavior stays exact: BLOCKED remains BLOCKED; every other non-QUALIFIES
  repeat, including deficient evidence, stops as `FAIL / SELECTED_REPEAT_FAILED`
  (225–246). This does not relabel a deficient original pair as integrity failure.
- **Repeat comparison:** `integration.normalized_scientific` (616) retains the
  nine frozen families. `add_repeats` (233–241) still compares whole records after
  only the six frozen operational exclusions. References/object tokens live
  under `output_identity`, already excluded at Contract lines 521–527; validate
  them independently **before** comparison. Coverage, process exit, counts and
  findings are not hidden there. No new exclusion or raw-XML normalization.
- **`evidence.py`:** `_base` (94), `_validate_payload` (100), `_checked_data`
  (213), `_verify` (225), `_write` (256), `readback` (316): schema dispatch and
  bounded referenced-evidence rechecks using existing read primitives. Schema-2
  FAILURE with a run requires `experiment_status` equal to fresh `assess_run`,
  and measurement status equal to fresh `validate_run`; RUN still requires VALID.
  A contradictory witness is retained inside the run, not only uninterpreted
  `raw_evidence`. Invalid assertions cannot be saved as verified RUN evidence;
  existing raw FAILURE with `run=None` may retain rejected material without a
  validated run status. Serialization/readback contradictions are FAIL; an I/O
  persistence BLOCKED cannot erase an already established experiment FAIL.
  Successful persistence remains only `persistence_status=VERIFIED`.

## 5. Characterization → future regression acceptance matrix

Case names below are exact methods on `FinalizationBoundaryCharacterization`.
“Derived” means static tracing, **not an additional executed assertion**. None of
the seven tests calls `SelectionSession`. Session predictions assume a properly
ordered level with otherwise qualifying seed pairs. No tests are implemented or
rerun for this specification.

| Existing case / line | Observed synthetic premise and current retention/outcome | Future acceptance requirement |
| --- | --- | --- |
| `test_full_horizon_positive_terminal_contradiction_becomes_inconclusive` / 71 | 540 parseable fake rows exist outside run; finalizer raises. Only EVIDENCE failure retained; run/pair INCONCLUSIVE tested; session INCONCLUSIVE derived. | A: supply actual mismatching object/digest witnesses; retain available raw XML; run/pair/session FAIL, no qualification. Flag alone must not establish that finding. |
| `test_abort_retains_first_failure_but_terminal_contradiction_is_not_represented` / 83 | t=50 unchanged-clock abort, late flag/exception lost; run/pair BLOCKED tested; session BLOCKED derived. | B: witnessed late contradiction gives FAIL throughout; original OSError failure and abort readback unchanged; late witness survives. |
| `test_close_exception_does_not_provide_independent_fail_precedence` / 94 | Late flag plus close exception, XML returned. Cleanup code retained; full/aborted run INCONCLUSIVE/BLOCKED tested; same pair/session states derived. | A/B with verified identity evidence; close exception alone must still follow D/C, not invent integrity. |
| `test_returning_valid_xml_cannot_carry_the_missing_terminal_diagnostic` / 103 | Valid XML returned; late flag absent from run. VALID and pair qualification entry tested; no exact pair result or session result asserted. | A with witnessed contradiction even if XML parses; without a terminal assessment v2 cannot enter qualification. Existing bare flag is insufficient. |
| `test_observation_diagnostics_end_before_finalization` / 111 | Zero pre-close counts and close-before-output order tested on the complete/aborted shared fixtures; no finalized log analyzed. Outcomes are those of cases 1/2, not new assertions. | Recheck final stream and process evidence after close; prove pre-close zero cannot imply final clean; apply A/B for witnessed errors, E/C for clean cases. |
| `test_raw_evidence_persists_but_does_not_change_revalidated_status` / 121 | Arbitrary flag preserved in FAILURE raw_evidence with BLOCKED; forcing FAIL rejected. No session invoked; BLOCKED derived for its run. | Actual witnessed B persists/revalidates as FAIL; forced BLOCKED rejected. Flag-only/unsupported assertions rejected as evidence, not treated as genuine simulator findings. Persistence never upgrades status. |
| `test_arbitrary_run_extension_is_not_an_authorized_schema_workaround` / 143 | Adding terminal_evidence to v1 produces RUN_SCHEMA; no pair/session invoked; _pair would fail closed. | Explicit v2 field accepted only with correct schema/evidence; v1 unchanged, arbitrary extras still rejected. |
| Additional: abort + clean/unavailable finalization | Not separately established by these seven cases | C; invalid partial measurement, BLOCKED original pair/session/repeat, no retry/ladder advance. |
| Additional: missing/truncated/unreadable output | Do not substitute the reproducer's valid XML + exception for these cases | D, or C with supported abort; no fabricated integrity finding or zero waiting. Original pair INCONCLUSIVE, deficient repeat retains existing FAIL stop. |
| Additional: parseable missing/duplicate trip IDs | Recheck the exact existing Adapter ID predicate on retained XML | Established TRIPINFO_ID_CONTRADICTION gives FAIL, unlike mere truncation or unsupported structure. |
| Additional: earlier integrity + later clean | Separate fixture required | F; first failure and existing contradiction retained; pair/session/repeat FAIL. |
| Additional: ordinary completed case | No live/native acceptance follows from existing fake success | E; exact existing accounting/gates/repeat families unchanged; varied operational refs alone do not fail an otherwise exact repeat. |
| Additional: cross-run/seed/repeat precedence | Use actual qualification/session functions | Any independently established FAIL precedes BLOCKED; no failed/blocked level advances; no failed repeat searches higher. |
| Additional: serialization/forgery/coverage | Require original references plus actual reader, not PASS stubs | Missing bytes: unavailable; changed hash/foreign capture/forged MATCH or unsupported code: rejected; valid failure readback preserves both first failure and later witness. Distinguish record rejection from proof of the claimed traffic defect. |

## 6. Compatibility, bounds and review gate

### Accepted review amendments (7 September)

- `collection_state` replaces the proposed `attempt`: the frozen recursive
  operational exclusions remove `attempt`. Those exclusions and the nine
  scientific repeat families remain unchanged.
- Integration owns collection state and derived parsing. Collector updates are
  incremental observations, not status authority. Interrupted collection cannot
  qualify even when otherwise populated; normal return cannot certify cleanliness.
- Every new run/selection/envelope is explicitly schema 2. Schema 1 is supported
  only by explicit read-only auditing against the exact accepted checkpoint
  tuple, labelled `LEGACY_FINALIZATION_UNVERIFIED`; no new selection or upgrade.
- One shared validator composes every accessible witness before deciding:
  missing support is not a contradiction, and cannot erase an independent one.
- Only an explicitly synthetic diagnostic mapping is implemented at this step.
  Native message mapping, process/transport ownership and live validation remain
  deferred. Exact authorized reference context is supplied by the caller; no
  path discovery or fallback. Completion markers/receipts stay schema 1.
- This task implements the accepted interface and tests it offline. The original
  seven-case reproducer and stop note remain byte-for-byte historical records.

Propose run and selection/envelope **schema 2**, retaining integration-family
identity and `finalization.version=1`. Schema 2 requires the field; omission is
invalid, never legacy inference. Completion markers/receipts remain the existing
persistence schema 1: their version describes the unchanged byte/completion
protocol, not terminal coverage. Envelope/contained-run versions must agree;
mixed v1/v2 pairs or selection histories are rejected. Synthetic evidence remains
the default and only supported origin until the separately reviewed origin
extension; this proposal neither labels real evidence synthetic nor enables live use.

Support the accepted checkpoint's well-formed completed and supported-abort v1
records in an **explicit legacy read-only validation mode**, with their existing
outcomes labelled `LEGACY_FINALIZATION_UNVERIFIED` in the returned audit context,
not inserted into historical records. They do not qualify as finalization-checked
v2 evidence and cannot enter a new v2 selection. No automatic upgrade. Other
historical schemas/source tuples remain unsupported unless separately reviewed.

`build_binding`/`checked_binding` (integration lines 44/76) currently bind to
current file hashes, so future code edits cannot simply revalidate old records
against new self-hashes. Propose exact, revision-keyed legacy identity lookup
from the existing reviewed projection data, used only by legacy validation and
its `scheduled`/`_account` calls. Recompute scientific inputs/dependency identities
unchanged; never accept arbitrary old hashes. New records use new current source
identities. Preserve historical manifest entries/reports and add distinct current
identities during implementation; no source-hash monkeypatch, execution of old
code, copied integration stack, or historical result rewrite.

Scientific Contract V1, Adapter V2, 540-trip allocations, native-time/sentinel
rules, metrics, thresholds, seeds, exact repeats, stopping rules and 24+2 budget
are unchanged. Retain the 64 MiB limit and completion protocol, including the
future full-selection payload check; referenced artifacts are also bounded.
No claim of crash durability or protection against coherent adversarial source/
capture replacement is added. Unsupported setup, permission and partial-advance
failures do not gain BLOCKED support. Bounded transport, native diagnostic mapping,
listening scope and actual simulator compatibility remain later binding/live
validation gates, not new permission or unresolved status-policy choices here.

### Original proposal-only verification (6 September; historical)

Verification in the proposal-only task: static source/call-site review and documentation checks
only; prior 7/86/153 test results are historical, not rerun or reclassified.

```text
SPECIFICATION_STATUS=PROPOSED_COMPLETE_FOR_REVIEW
FINALIZATION_EXTENSION_IMPLEMENTED=NO
THIN_LIVE_BINDING_IMPLEMENTED=NO
LIVE_PROCESS_STARTED=NO
LIVE_INTEGRATION_VALIDATED=NO
OD_CALIBRATION_EXECUTED=NO
COMMIT_CREATED=NO
PR_CREATED=NO
READY_TO_RUN=NO
NEXT_TASK=REVIEW_B0_OD_FINALIZATION_CONTRACT_EXTENSION
```
