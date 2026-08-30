# Candidate N V3→V4 Research Checkpoint — August 2026

## Purpose and coverage

This checkpoint closes the public-documentation gap from 22–30 August 2026. Earlier August work is already recorded through the 21 August V3 checkpoint in the [monthly effort log](../progress/monthly-effort-log.md); it is not repeated here except where needed to explain later decisions.

The research cutoff is the authoritative Candidate N V4 RMSprop dependency and complete-architecture reconciliation. All V4 results below are static contracts, architecture decisions, synthetic evidence, or authorized private-static findings. V4 has not been implemented or executed. The later subject-role/model-setup reconciliation is outside this checkpoint and remains pending here.

## Executive summary

Late-August work established that the frozen V3 machinery was source-free and reproducible at its documented validation boundary, but still lacked a reviewed production path connecting activation, Candidate-facing adapters, evidence mapping, cleanup, and durable reporting. A renewed execution attempt therefore stopped before private-source transfer or capability creation and remained correctly classified as `BLOCKED`, not as a Candidate N failure.

Static reconciliation then defined a V4 successor architecture. It preserves Candidate-owned replay and update behavior on one shared primary subject, narrows the admissible real-runtime evidence to directly observable objects, fixes the primary endpoint oracle at an order-invariant mean-MSE loss of `43.88`, and separates experiment, mapping, writing, and final-controller outcomes. Authorized read-only inspections established that Candidate N owns genuine RMSprop and mean-reduced MSELoss and that its pre-mutation access surface supports a temporary optimizer-slot guard and transparent criterion wrapper.

The dependency-provider seam is resolved, but complete V4 readiness is not. Subject-role/model-setup cardinality, the independent controller host, the native filesystem primitive, the controller receipt channel and security review, implementation, integrated validation, and later private-execution authorization remain outstanding.

## Work completed during the checkpoint period

The completed work comprised four evidence classes:

- **Source-free validation:** the frozen V3 package, launcher, public-root handoff, and source-lifecycle machinery were revalidated without Candidate N source.
- **Synthetic-only validation:** controlled stand-ins exercised the V3/V4-facing adapter boundaries and retained hidden learning intermediates that cannot be claimed as directly observed Candidate runtime values.
- **Private-static findings:** two narrowly authorized, read-only and non-executing inspections resolved optimizer, criterion, and pre-guard access behavior.
- **Architecture reconciliation:** V4 contracts were specified for shared replay/update ownership, reduced evidence, endpoint oracles, lifecycle receipts, activation, external control, mapping, and durable readback.

No V4 source package was authored or frozen during this work.

## AWS and execution-gate findings

The V3 source-free regression completed with:

- V3 source-free suite: `301 passed`;
- public regression suite: `55 passed`;
- collection errors: `0`.

The corrected native Linux source-lifecycle boundary also passed its bounded checks. It retained a root-only staging location, used a separate traversal-only exposure parent, established a read-only bind, allowed the intended unprivileged read, rejected file and directory mutation, matched pre/post integrity, completed cleanup, and verified final source absence. The final abbreviated pre-source decision was `GO_FOR_V3_PRIVATE_SOURCE_STAGE=YES`.

A subsequent renewed execution workflow nevertheless stopped before private-source upload, capability creation or consumption, private loading, or Candidate execution. The missing prerequisite was a frozen, reviewed end-to-end one-shot driver capable of connecting activation, C2, evidence mapping, cleanup, and final reporting without an improvised execution path. The outcome remained `BLOCKED`, and the remaining bounded execution authorization was not consumed. This result identifies an orchestration gap; it is not evidence of Candidate N incompatibility.

No AWS activity occurs as part of this documentation checkpoint.

## V3 limitations and transition to V4

Static analysis identified limits that could not be repaired honestly while holding V3 fixed:

- production-shaped activation still depended on test-only request and dependency-provider boundaries;
- honest production dependency and intermediate-reader inputs were unavailable;
- the primary replay adapter and guarded-update adapter operated on separate subjects;
- preserving V3 would therefore require either direct Candidate-method invocation outside the reviewed adapters or duplicated/manufactured replay state.

Both alternatives were rejected because they would weaken provenance and could change or reproduce Candidate behavior outside the approved boundary. V4 became necessary as an architectural correction. This is not a Candidate algorithm-defect finding.

## V4 shared replay/update design

The resolved coordinator contract retains one primary Candidate subject, lifecycle session, online/target models, and replay container across:

1. two reviewed replay stores;
2. replay identity validation and Candidate-defined batch construction;
3. one guarded update;
4. one controlled pre-mutation stop; and
5. one cleanup.

Placeholder replay insertion and externally manufactured records are prohibited. Terminal-false, terminal-true, deterministic-action, isolated hard-sync, and passive graph observations remain fresh and isolated from the primary update subject. The frozen public `run_integrated_contract(...)` interface can remain unchanged. Neither the external driver nor dependency-provider layer requires direct Candidate method access, and no layer may duplicate Candidate replay, batching, action, update, synchronization, or graph-processing algorithms.

One topology discrepancy remains unresolved at this cutoff. An earlier coordinator assumption applied model setup broadly across six sessions, while the later role-minimal proposal constructs models only for roles that use them. The exact subject-role/model-setup cardinality requires a dedicated reconciliation before implementation.

## V4 evidence, lifecycle, and controller architecture

The reduced runtime-evidence contract permits future retention only of directly observable values:

- update-selected replay records and delegated update batch;
- actions and rewards actually used by the update;
- target-model output and ordered first/second online-model outputs;
- final criterion prediction, target, and genuine criterion loss;
- call counts and ordering;
- guard and mutation evidence; and
- source-integrity and cleanup outcomes.

Bootstrap maxima, the hidden temporal-difference target tensor, and the detached target-base matrix cannot honestly be claimed as directly observed real Candidate runtime objects without source modification or observer-side reconstruction. They remain synthetic-instrumentation evidence only. Narrowing the evidence domain improves research integrity: the endpoint claim is tied to observable inputs and outputs rather than reconstructed hidden state.

The broader static architecture also resolves a one-shot reduced reader, non-circular oracle selection, typed reports without raw tensor or runtime-object escape, C2 cleanup before lifecycle-receipt creation, and activation transport only after C2 cleanup. Source lifecycle, cloud cleanup, and authoritative instance stop have separate receipts. Aggregate status uses `FAIL > BLOCKED > INCONCLUSIVE > PASS`, while chronological first-non-PASS evidence remains separately preserved.

The external controller owns final orchestration. Authoritative instance stop precedes strict mapping and durable writing. Experiment status, mapping status, durable-write status, and final-controller status remain distinct. Canonical mapping is public-safe and non-self-referential; durable publication requires readback; and the complete path is one-shot with no retry.

These are static contracts, not evidence that the external controller or writer has been implemented.

## Replay order and endpoint oracle

The corrected primary replay contract uses two reviewed records:

| Stored record | Actions | Rewards |
|---|---|---|
| First | `[0, 1, 0]` | `[0, 1, 2]` |
| Second | `[1, 0, 1]` | `[10, 11, 12]` |

Terminal inputs are accepted by storage but omitted from the visible replay record. Candidate sampling selects both records and may return either permutation. Flattening is selected-sample-major and then node-major, producing exactly two admissible ordered runtime batches.

The target oracle is keyed by `ORDER_0_1` and `ORDER_1_0`. Selection uses directly observed record-key order only; runtime code must not reconstruct hidden temporal-difference calculations to choose an oracle.

The corrected scalar endpoint oracle is `43.88`: genuine full-matrix mean MSE across twelve cells, checked with `atol=1e-6` and `rtol=1e-6`. It is invariant under the two permitted replay-order permutations. The value `3.355` remains valid only for the earlier independent synthetic temporal-difference fixture; it is not the shared-replay runtime oracle. This correction is a static contract correction, not a Candidate runtime failure.

## Optimizer and criterion findings

### P1: ownership and construction

P1 was an authorized, read-only, non-executing static inspection. It established that Candidate N owns and constructs genuine `torch.optim.RMSprop` with:

- learning rate `0.001`;
- `alpha=0.9`;
- `eps=1e-7`;
- `centered=False`;
- momentum `0`;
- weight decay `0`; and
- one parameter group.

The group contains all and only registered parameters of the final online model; target-model parameters are excluded. Because a later model replacement would stale-bind the optimizer, every intended replacement and deterministic model setup must complete before final parameter enumeration and optimizer construction.

Candidate N also owns genuine `torch.nn.MSELoss(reduction="mean")`. No setup-level criterion replacement or scaling was found.

### P2: pre-guard access surface

P2 was a separate authorized, bounded static inspection through the first optimizer `zero_grad()` attempt. The criterion is called once through normal module-call dispatch, using two positional arguments and no keywords. No criterion type, reduction, or state inspection occurs; no runtime scaling or transformation occurs; and the original loss remains unchanged.

Before the stopping boundary, Candidate creates no optimizer alias and performs no optimizer type or identity check. It does not access defaults, parameter groups, state, `state_dict`, learning-rate/configuration fields, or `step`. The first `zero_grad()` call has no positional or keyword arguments, supplies no `set_to_none`, captures no bound method, and does not use the return value. No optimizer, parameter, or gradient mutation occurs before that point.

This surface is statically compatible with temporary replacement of the subject optimizer slot by a narrow guard. Genuine RMSprop remains separately authoritative, its real `zero_grad()` is not delegated, and it is restored after the controlled stop. A transparent wrapper around genuine mean-MSE is likewise compatible. These findings do not establish backward, gradient, or optimizer-step compatibility.

## Superseded assumptions

| Earlier interpretation | Authoritative treatment at this cutoff |
|---|---|
| Source-free SGD provider proposal | Preserved historically but superseded by exact genuine RMSprop and mean-MSE. |
| SGD-positive provider tests | Historical only; future authoritative tests must bind to RMSprop. |
| `3.355` as the primary update endpoint | Synthetic-fixture evidence only; the primary shared-replay loss oracle is `43.88`. |
| Hidden temporal-difference intermediates as real-runtime evidence | Restricted to synthetic instrumentation. |
| Model setup across all six sessions | Still an unresolved coordinator-versus-role-minimal discrepancy at this cutoff. |

No implemented or frozen V4 provider package was rewritten because none existed. The historical SGD proposal remains available as design provenance, while future manifests and tests must carry the explicit RMSprop supersession.

## Research-integrity and privacy record

During P1 component identification, a neighbouring non-approved constructor/setup region was briefly opened. Inspection stopped immediately. No update body or unrelated runtime region there was inspected, and no information from that access was retained, used, or disclosed. It supplied none of the P1 findings. P2 used the exact approved reference directly and had no scope deviation.

This is recorded as a scope-selection deviation rather than an exception-free privacy pass. No identity for the neighbouring component, private location, source excerpt, correspondence, authorization record, or private integrity value is included here.

The checkpoint contains sanitized conclusions only. It does not copy or link private reports, commit private source, or expose private execution artifacts or sensitive cloud identifiers.

## Dissertation relevance

The August work contributes methodological evidence for the dissertation: paper-to-code provenance analysis, reproducibility discipline, compatibility-environment reconstruction, controlled experiment design, separation of synthetic and real evidence, conservative handling of `BLOCKED`, `FAIL`, and `INCONCLUSIVE`, preservation of negative results, threats-to-validity analysis, and safe execution planning.

This is substantial research-engineering progress, but it is not the final empirical evaluation. Simulator experiments, baseline comparisons, quantitative traffic metrics, ablations, convergence analysis, training stability, and performance evaluation remain future work.

## Current readiness and blockers

Resolved static seams include:

- shared replay/update coordinator;
- reduced real-runtime evidence and provenance contracts;
- order-indexed target oracle and scalar loss oracle `43.88`;
- reduced reader, activation bridge, and C2 cleanup/lifecycle receipt;
- controller receipt and final-status topology;
- strict evidence mapping and durable write/readback contracts;
- exact genuine RMSprop/MSE provider seam; and
- pre-guard optimizer-guard and criterion-wrapper compatibility.

Not resolved or not ready:

- exact subject-role/model-setup topology reconciliation;
- a qualifying independent external Linux controller host;
- native filesystem syscall primitive and ABI validation;
- controller-host security and receipt-channel review;
- implementation of every V4 package;
- integrated source-free V4 validation; and
- V4 private-execution authorization reconfirmation.

Therefore:

- `COMPLETE_V4_ARCHITECTURE_RECONCILED=NO`;
- `READY_TO_BEGIN_V4_IMPLEMENTATION=NO`.

## Next research task

The immediate next task is `RECONCILE_V4_SUBJECT_ROLE_AND_MODEL_SETUP_TOPOLOGY`.

After that reconciliation, the next infrastructure task is `SELECT_AND_REVIEW_V4_EXTERNAL_CONTROLLER_HOST_AND_RECEIPT_CHANNEL`.

Neither task is executed by this documentation checkpoint.

## Claims explicitly not made

This checkpoint does not establish:

- Candidate N end-to-end runtime compatibility under V4;
- optimizer-step, backward, gradient, or training correctness;
- terminal-handling correctness;
- simulator integration;
- convergence or traffic-control performance;
- algorithmic superiority;
- historical-environment reproduction; or
- paper reproduction.

No V4 implementation was completed, and no V4 Candidate runtime execution occurred. No private source is committed, and no AWS activity or execution-capability creation occurs in this documentation task.
