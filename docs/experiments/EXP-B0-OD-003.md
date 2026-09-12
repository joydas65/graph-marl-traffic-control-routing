# EXP-B0-OD-003 — finalization and native-binding draft pre-run checkpoint

Date: 12 September 2026. Classification: offline implementation/publication
checkpoint, not a traffic experiment, native validation or execution permission.
This note supplies the publication state; earlier implementation reports retain
their historical validation counts, source identities and then-current gates.

## Question, scope and provenance

Can the reviewed schema-2 finalization and concrete native-binding package be
published without behavioral changes, preserving its scientific contract and
honest offline-only evidence boundaries?

Publication uses the existing `feature/b0-od-live-binding-v1` branch. The accepted
base and freshly fetched `origin/main` are
`c0be5ca5c0116179f901bd00410c74e581799c87`; no rebase, history rewrite, retained-ref
change or recreation from main is involved.

The reviewed 36-entry archive was recorded with SHA-256
`75a52955f7d01fe2ebb30ae4b2a288d465209823a059ebdab71d3c7215e58481`.
At publication preparation, the ZIP itself is absent from its recorded local
location; no fresh archive-byte verification or recreation is claimed. Its
preserved inventory matches the previously verified identity
`3e319930ebcc95c2aee455e007d1195d93d23b4b1040b6b0ef472500400c76e0`.
All 35 listed rows were rechecked: 33 repository files plus the preserved focused
diff and validation summary. All 33 repository files matched before the explicit
publication adjustments below. The local export records remain unchanged and
are not committed.

**User-reported independent review:** the actual archive received source review
with no new blocking defect within its declared offline scope. The reviewer
reran 112 supplied tests/194 subtests covering supervisor, transport, ownership
and native mapping. This was a subset, not a full 463-test rerun, native
execution, formal GitHub approval or faculty approval. This report does not
independently authenticate the external review or add its counts to local runs.

## Implemented package and unchanged science

The package contains the schema-2 finalizer/reference reader and legacy audit;
thin exact-input plan/collector; native representations; owned runtime; concrete
supervisor, worker and transport; explicit origin handling; qualification and
strict evidence writer; focused tests and small synthetic fixtures.

| Concrete entry point | Boundary |
| --- | --- |
| `native_supervisor.run_native` | One independently verified worker/session before GO; absolute phase/exchange/total deadlines, scoped cleanup and separate operational receipt. |
| `native_worker.execute_worker` | One child acquisition within the owned scope; existing collector, schema-2 assessment, persistence and explicit reference handoff. |
| `native_transport.connect_native` | Pinned installed client and actual remaining-budget socket operations inside the later-authorized worker. |

Scientific Contract V1, Adapter V2, all eleven frozen dependencies, twelve
540-trip allocations, seeds, simulation timing, thresholds, first-qualifying
selection, repeat/accounting rules, 24+2 budget and 64 MiB writer limit are
unchanged. Chronological first failure and supported late-integrity FAIL
precedence remain intact. Persistence success is not experiment success;
partial/invalid measurements cannot qualify. Synthetic fixtures are not actual
traffic observations. No concentration is selected and dissertation delta
remains unset.

## Exact publication adjustments

Only three files inside the reviewed 33-file inventory change:

1. `scripts/b0/od_integration_v1/finalization.py`: opening docstring only, replacing
   the stale synthetic-only description with the reviewed native-mapping support
   and explicit unvalidated-native-runtime limitation. All bytes after the
   docstring and the executable AST are unchanged. This file is **not**
   byte-identical to the reviewed export.
2. `tests/test_b0_od_integration_projection.py`: additional publication identity
   assertions in the existing test; no scientific assertions removed or weakened.
3. `tests/reference/b0_od_integration_v1_projection.json`: current hashes updated;
   all 27 reviewed source/test hashes, reviewed archive/inventory/manifest
   identities and the docstring-only adjustment are recorded separately.

| Identity | Reviewed SHA-256 | Publication SHA-256 |
| --- | --- | --- |
| `finalization.py` | `990a2faf8ddd0029fd644e13101e1958eba50ed50c1486cd1b77d3ca6e5b2d86` | `a3da71244f6e8a9bd63a8b324dd85be186b4847023440e7b87df735dac75d4a8` |
| Projection test | `77f1cca87997bab204eaf73d3d6c532420031d25d896a5c52a956cafd162e228` | `387457b9512e79c4e778ffb77d2d88a21d77358e8500c54b695e65ac32998dca` |
| Projection manifest | `75e530eae0267328abdd937d04e1f151cf1a68e008b6db3220a0065b3154445b` | `10b46e05bb29ea43f66caa55fd492e705d8bdd6eb556efdf899ed92286b66c7b` |

The other 30 review files retain their bytes, including both implementation
reports, proposal, stop note and decision record. Separately, publication adds
this note, updates root/documentation navigation, and appends progress history.
Those navigation/progress changes were excluded from the ZIP and receive
publication-specific inspection. No unrelated implementation or private material
is added. The current source identity inventory is the
[projection manifest](../../tests/reference/b0_od_integration_v1_projection.json).

## Publication file inventory

The proposed commit contains only these 37 public-safe files. Review exports,
raw outputs and local privacy configuration are excluded.

```text
README.md
docs/README.md
docs/decisions/0004-b0-native-representations-and-ownership.md
docs/experiments/EXP-B0-OD-003.md
docs/experiments/b0-od-finalization-contract-extension-v1-proposal.md
docs/experiments/b0-od-finalization-extension-v1-implementation.md
docs/experiments/b0-od-live-binding-v1-stop-note.md
docs/experiments/b0-od-thin-live-binding-v1-implementation.md
docs/progress/monthly-effort-log.md
scripts/b0/od_integration_v1/evidence.py
scripts/b0/od_integration_v1/finalization.py
scripts/b0/od_integration_v1/integration.py
scripts/b0/od_integration_v1/live_binding.py
scripts/b0/od_integration_v1/native_mapping.py
scripts/b0/od_integration_v1/native_supervisor.py
scripts/b0/od_integration_v1/native_transport.py
scripts/b0/od_integration_v1/native_worker.py
scripts/b0/od_integration_v1/owned_runtime.py
scripts/b0/od_integration_v1/qualification.py
tests/b0_od_integration_fixtures.py
tests/reference/b0_od_integration_v1_projection.json
tests/run_b0_od_integration_offline.py
tests/test_b0_od_integration_evidence.py
tests/test_b0_od_integration_finalization.py
tests/test_b0_od_integration_live_binding.py
tests/test_b0_od_integration_native_ipc.py
tests/test_b0_od_integration_native_mapping.py
tests/test_b0_od_integration_native_supervisor.py
tests/test_b0_od_integration_native_transport.py
tests/test_b0_od_integration_native_worker.py
tests/test_b0_od_integration_observation.py
tests/test_b0_od_integration_operational.py
tests/test_b0_od_integration_origin.py
tests/test_b0_od_integration_owned_runtime.py
tests/test_b0_od_integration_projection.py
tests/test_b0_od_integration_qualification.py
tests/test_od_live_binding_finalization_boundary.py
```

## Fresh complete offline validation

Both complete surfaces passed using Python 3.12.14 with `-I -S -B`:

| Command | Tests passed | Subtests | Harness seconds |
| --- | ---: | ---: | ---: |
| `tests/run_b0_od_integration_offline.py new` | 310 | 467 | 462.843 |
| `tests/run_b0_od_integration_offline.py existing` | 153 | 175 | 1.585 |

Both report zero failures, errors, skips, collection errors and forbidden-access
attempts, with stable source hashes throughout validation. Focused and external
review subsets are not added again. The existing full synthetic selection is
56,943,083 bytes and passes actual strict write/readback/finalization under the
unchanged 64 MiB writer limit. These are synthetic control-flow/serialization
checks, not traffic results or execution of the scientific simulation budget.

In-memory compilation, executable-AST and post-docstring byte equality,
whitespace, source/import-location projection checks, documentation-link
existence and all eleven frozen scientific dependency hashes pass. The source
manifest is frozen across both runs. No helper/SUMO process, native socket or
installed client was started or imported.

## Publication gate at local checkpoint preparation

Remote publication is blocked by authentication at this preparation checkpoint.
No draft PR has been created, and hosted content, rendered documentation,
checks and review status have not been verified for this proposed head. A local
offline pass is not a hosted-publication result. Restore the intended account's
repository access before the normal guarded push and draft creation; do not
change privacy policy or bypass hooks. The available main-branch read reported
no branch protection or active rules, but that is not review approval.

## Remaining native-validation requirements

- Initial supervisor-to-worker OS bootstrap is not deadline-interruptible.
  Ownership before SUMO acquisition does not satisfy a stronger pre-bootstrap
  hard deadline; arbitrary kernel/filesystem failure is not hard-real-time bounded.
- Exclusive worker reaping remains an environment requirement. Default SIGCHLD
  handling alone does not prove there is no competing reaper.
- Forced cleanup without actual child-reaping evidence leaves child scope
  `UNRESOLVED`. Signal delivery or worker reaping alone is not proof of SUMO
  absence or completed finalization.
- Real process inheritance/cancellation/reaping, socket timing, native callbacks,
  output/population semantics and actual server listening scope remain unverified.
  A loopback client destination does not prove loopback-only server binding.
- Six client source files are exact-hash pinned; the sibling helper closure is
  location-bound, not fully hash-pinned. Runtime compatibility remains unvalidated.
- Operational/interruption receipts are distinct from scientific evidence. No
  clean finalization, missing population or usable partial result is fabricated.

See the preserved [native implementation note](b0-od-thin-live-binding-v1-implementation.md#native-factory-completion--10-september-2026)
for exact enforcement details, and the [finalization checkpoint](b0-od-finalization-extension-v1-implementation.md)
for schema/reference boundaries. Their earlier next-task and publication flags
describe their dated checkpoints, not a new execution authorization.

```text
NATIVE_PROCESS_TEST_EXECUTED=NO
LIVE_INTEGRATION_VALIDATED=NO
OD_CALIBRATION_EXECUTED=NO
SELECTED_CALIBRATED_OD_CONCENTRATION=NONE
DISSERTATION_DELTA_REMAINS_UNSET=YES
READY_TO_RUN=NO
NEXT_TASK=FINAL_REVIEW_OF_NATIVE_BINDING_PUBLIC_CHECKPOINT_BEFORE_MERGE
```

Stop at a draft PR. Marking ready, merging and any bounded native validation
remain separate authorization gates; the next task is not executed here.
