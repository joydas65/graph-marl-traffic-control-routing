# Candidate N V4 Controller Provisioning Module A

## Status and purpose

`CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_A_V1` is the public, source-safe finite-state contract for the Candidate N V4 controller-provisioning lifecycle. It fixes the phase conditions, logical-resource registry, legal forward transitions, transition deltas, and version binding needed by a later template builder. The module is pure Python and does not create templates, contact a cloud service, or provision infrastructure.

As research apparatus, the contract preregisters deployment-state semantics, makes apparatus state reproducible, prevents outcome-dependent changes to the phase model, provides deterministic negative-transition handling, and makes transition provenance auditable.

The contract is bound exactly to `CANDIDATE_N_V4_CLOUDFORMATION_PHASE_AND_CHANGESET_CLARIFICATION_V1`. Callers cannot supply replacement conditions, resource sets, transition results, or derived record fields.

## Phase model

The deployed phases and condition truth table are closed:

| Deployment phase | Controller present | Bootstrap signal active | Logical resources |
| --- | ---: | ---: | ---: |
| `FOUNDATION_ONLY` | false | false | 8 |
| `CONTROLLER_COMPUTE` | true | true | 12 |
| `SEALED_STOPPED` | true | false | 10 |

The separate main-stack state model also includes `NONEXISTENT`. Exactly three forward transitions are legal:

1. `NONEXISTENT` to `FOUNDATION_ONLY`
2. `FOUNDATION_ONLY` to `CONTROLLER_COMPUTE`
3. `CONTROLLER_COMPUTE` to `SEALED_STOPPED`

Repeats, skips, regressions, and all other state pairs are classified explicitly. Illegal reviews expose empty resource deltas and no metadata expectation.

## Logical-resource registry

The registry contains exactly twelve logical resources in four classes:

| Class | Logical resources | Phase behavior |
| --- | --- | --- |
| `FOUNDATION_PERSISTENT` | `ControllerBudget`, `ControllerSecurityGroup`, `ControllerHostRole`, `ExperimentRuntimeRole`, `ControllerInstanceProfile`, `ControllerCommandDocument` | Present in all deployed phases and protected from replacement |
| `RETAINED_EVIDENCE` | `EvidenceKey`, `EvidenceVolume` | Present in all deployed phases, protected from replacement, and marked as retained evidence |
| `COMPUTE_PHASE` | `ControllerInstance`, `EvidenceVolumeAttachment` | Present when the controller-present condition is true |
| `BOOTSTRAP_ONLY` | `BootstrapWaitHandle`, `BootstrapWaitCondition` | Present only while the bootstrap-signal condition is true |

The persistent eight-resource intersection is present in every deployed phase and no legal transition removes any member of it.

## Transition deltas

| Legal transition | Added | Removed | Unchanged | Metadata expectation |
| --- | --- | --- | ---: | --- |
| `NONEXISTENT` to `FOUNDATION_ONLY` | The eight persistent resources | None | 0 | `NONE` |
| `FOUNDATION_ONLY` to `CONTROLLER_COMPUTE` | The two compute and two bootstrap resources | None | 8 | `NONE` |
| `CONTROLLER_COMPUTE` to `SEALED_STOPPED` | None | The two bootstrap resources | 10 | `CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL` |

All returned resource tuples use deterministic logical-ID ordering. Phase profiles, resource records, and transition reviews are immutable and are constructed only from the closed contract.

## Verification surface

The public test suite checks the exact enums and truth table; all twelve resources and their class, presence, and protection semantics; all four stack states and sixteen ordered state pairs; all three deployed phase profiles; all thirty-six resource-by-phase presence cases; the three legal deltas; immutability; deterministic repeatability; fixed public errors; negative fixtures; and exact version binding.

## Research and implementation boundary

This module supports review of a deterministic provisioning-state specification. It is apparatus for a later bounded controller workflow, not a graph-MARL contribution and not experiment evidence.

Supported by this publication:

- Module A's finite deployment-state model is implemented.
- Its resource and phase invariants are exhaustively tested without private source.
- Illegal transitions receive deterministic, closed classifications.
- The production artifact uses only the Python standard library and is independent of AWS at runtime.

Not supported by this publication:

- deployable CloudFormation correctness or AWS CloudFormation behavior;
- IAM or KMS correctness;
- controller provisioning or live AWS validation;
- Candidate N runtime behavior;
- traffic-control performance or paper reproduction; or
- PhD-level generalization.

It also provides no provider SDK integration, controller commands, receipt handling, simulator integration, training, performance evidence, or claim of readiness to provision. Module B must consume this exact interface in a separate reviewed change; Module B is not part of this publication.
