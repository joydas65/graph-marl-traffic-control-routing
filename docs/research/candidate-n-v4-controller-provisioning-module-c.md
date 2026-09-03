# Candidate N V4 Controller Provisioning Module C

## Status and purpose

> Module C accepts only a normalized offline description that exactly matches
> the preregistered A/B apparatus contract. ACCEPTED is not an AWS or
> provisioning approval.

`CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_C_CHANGESET_REVIEWER_V1` is the
public, source-safe semantic reviewer for five synthetic controller-provisioning
change-set operations: S0, M0, S1, M1, and M2. It is bound exactly to
`CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_A_V1`,
`CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_B_V1`, and
`CANDIDATE_N_V4_CLOUDFORMATION_PHASE_AND_CHANGESET_CLARIFICATION_V1`.

Module C derives phase transitions and protected resources from Module A and
resource types, staging structure, and metadata ownership from Module B. It does
not duplicate either module's authoritative registry, transition table, phase
sets, type table, condition model, or staging topology.

## Normalized review boundary

The reviewer accepts immutable normalized resource changes and immutable
synthetic change-set views. Its closed types describe operation, stack kind,
change-set type, action, replacement, scope, semantic modification role,
creation status, execution status, and staging state. Review returns an immutable
result with only `ACCEPTED` or `BLOCKED` disposition and a closed reason.

A view is eligible for acceptance only when its version bindings, operation,
stack, change-set type, source and destination states, status fields, and
complete-page-set marker match the relevant contract. Logical-resource order
has no semantic meaning: comparison is order-independent, returned identifiers
are deterministic, and duplicate logical IDs are rejected.

Module C does not accept raw `DescribeChangeSet` responses and implements no AWS
pagination, provider normalization, cloud client, or live adapter.

## Accepted operation contracts

| Operation | Stack and type | State transition | Exact accepted mutation |
| --- | --- | --- | --- |
| S0 | Staging `CREATE` | Nonexistent to upload-only | Add the two Module B staging resources |
| M0 | Main `CREATE` | Nonexistent to foundation | Add the eight persistent resources derived from Modules A and B |
| S1 | Staging `UPDATE` | Upload-only to host exact-object-read | Modify only `StagingBucketPolicy`, with replacement false, `Properties` scope, and the staging-policy semantic role |
| M1 | Main `UPDATE` | Foundation to compute | Add exactly the four compute/bootstrap resources derived from Module A; no Modify or Remove |
| M2 | Main `UPDATE` | Compute to sealed | Remove the two bootstrap resources and modify only `ControllerInstance`, with replacement false, `Metadata` scope, and `CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL` |

The eight persistent foundation/evidence resources derived from Module A are
protected during accepted updates. Any M1 or M2 attempt to add, modify, remove,
or replace one of them is blocked.

S2, D0, deployable templates, IAM/KMS policy implementation, bootstrap or user
data, and live change-set execution are outside this module.

## Rejection and verification surface

Closed rejection reasons cover invalid DTO combinations, dependency-binding
mismatch, wrong operation topology, stack/type/state/status mismatch, incomplete
page sets, duplicates, missing or unexpected changes, protected-resource
changes, wrong resource types or actions, replacement risk, wrong scope or
semantic role, and sensitive input.

The public tests cover all five accepted fixtures, immutable DTO validation,
exact A/B binding, order independence, the completeness and protected-resource
gates, strict S1/M1/M2 behavior, the 64 named negative-fixture semantics, a
systematic mutation audit, semantic-duplication checks, and repeated
mixed-operation determinism.

The sensitive-input check is a bounded accidental-leakage guard rather than a
complete data-loss-prevention system. Artificial credential-shaped test values
are assembled at runtime from harmless fragments; no credential-shaped literal,
real cloud identifier, private path, or private source identity is committed.

## Research claim boundary

Supported by this publication:

- preregistered offline mutation review is implemented for S0, M0, S1, M1, and
  M2;
- expected mutations are derived from the published Modules A and B;
- mismatches receive deterministic closed classifications;
- change ordering does not affect the decision;
- protected resources cannot be silently changed by an accepted update; and
- the implementation remains independent of AWS and private Candidate source.

Not supported by this publication:

- correctness of an actual AWS change set or service pagination;
- AWS acceptance or controller provisioning;
- IAM, KMS, bootstrap, or deployable-template correctness;
- readiness to provision the controller;
- Candidate N runtime behavior;
- traffic-control performance or paper reproduction; or
- methodological superiority or PhD-level generality.

Module C is research apparatus for controlling infrastructure-change semantics,
not a graph-MARL contribution or experiment result.
