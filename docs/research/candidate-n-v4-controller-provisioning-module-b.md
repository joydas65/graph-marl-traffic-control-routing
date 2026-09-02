# Candidate N V4 Controller Provisioning Module B

## Status and purpose

> Module B is a structural specification and offline validator. It is not a deployable CloudFormation template.

`CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_B_V1` publishes a deterministic,
public-safe representation of the controller and staging topology. It is bound
exactly to `CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_A_V1` and
`CANDIDATE_N_V4_CLOUDFORMATION_PHASE_AND_CHANGESET_CLARIFICATION_V1`. Every
profile carries `DEPLOYMENT_READINESS=NON_DEPLOYABLE_STRUCTURAL_SKELETON`.

This apparatus preregisters the intended topology before any privileged policy,
bootstrap, private manifest, or live-provider work. It contains structural
resource type labels and closed deferrals, but no deployable resource properties,
physical identifiers, cloud client, or execution path.

## Module A binding and main profiles

Module A remains authoritative for phases, conditions, the twelve logical
resources, phase-presence masks, and retained-evidence classification. Module B
checks the exact Module A version binding at import and derives rather than
duplicates the active-resource semantics.

| Main render profile | `ControllerPresent` | `BootstrapSignalActive` | Active resources |
| --- | ---: | ---: | ---: |
| `FOUNDATION_ONLY` | false | false | 8 |
| `CONTROLLER_COMPUTE` | true | true | 12 |
| `SEALED_STOPPED` | true | false | 10 |

The main structural model has exactly `AWSTemplateFormatVersion`, `Description`,
`Metadata`, `Parameters`, `Conditions`, and `Resources` as its top-level keys.
`ControllerDeploymentPhase` has the three Module A values and no default. The
resource registry is closed:

| Logical resource | Structural type | Presence |
| --- | --- | --- |
| `ControllerBudget` | `AWS::Budgets::Budget` | All profiles |
| `EvidenceKey` | `AWS::KMS::Key` | All profiles |
| `ControllerSecurityGroup` | `AWS::EC2::SecurityGroup` | All profiles |
| `ControllerHostRole` | `AWS::IAM::Role` | All profiles |
| `ExperimentRuntimeRole` | `AWS::IAM::Role` | All profiles |
| `ControllerInstanceProfile` | `AWS::IAM::InstanceProfile` | All profiles |
| `ControllerCommandDocument` | `AWS::SSM::Document` | All profiles |
| `EvidenceVolume` | `AWS::EC2::Volume` | All profiles |
| `ControllerInstance` | `AWS::EC2::Instance` | `ControllerPresent` |
| `EvidenceVolumeAttachment` | `AWS::EC2::VolumeAttachment` | `ControllerPresent` |
| `BootstrapWaitHandle` | `AWS::CloudFormation::WaitConditionHandle` | `BootstrapSignalActive` |
| `BootstrapWaitCondition` | `AWS::CloudFormation::WaitCondition` | `BootstrapSignalActive` |

Only `EvidenceKey` and `EvidenceVolume` carry both `DeletionPolicy=Retain` and
`UpdateReplacePolicy=Retain`. Stack policy, termination protection, and
`RetainExceptOnCreate` remain typed structural deferrals.

The dependency graph contains exactly these edges:

- `EvidenceVolumeAttachment` to `ControllerInstance`;
- `EvidenceVolumeAttachment` to `EvidenceVolume`; and
- `BootstrapWaitCondition` to `EvidenceVolumeAttachment`.

The bootstrap representation fixes a condition-scoped wait handle and a
condition-scoped wait condition with count `1`, timeout `28800`, and the final
dependency above. Controller metadata selects the wait-handle reference in the
compute profile and `SEALED_STOPPED` in the sealed profile. It includes no
physical signal URL, user data, shell command, or executable bootstrap.

Controller requirements are limited to closed roles for the frozen image
binding, `t3.small`, root mapping, subnet, instance profile, security group,
public-address profile, IMDSv2, and Standard credit mode. IAM, KMS, security
group, SSM, attachment, budget, and manifest details remain typed deferrals.

## Staging profiles

The staging model contains exactly `StagingBundleBucket` as
`AWS::S3::Bucket` and `StagingBucketPolicy` as `AWS::S3::BucketPolicy`.
`StagingAccessPhase` has two values and no default:

| Staging render profile | Structural policy state |
| --- | --- |
| `UPLOAD_ONLY` | No controller-host object-read grant |
| `HOST_EXACT_OBJECT_READ` | Exactly one future host exact-object-read grant expected |

The transition changes only `StagingBucketPolicy`; it adds, removes, and
replaces no resource. No bucket name or policy statement is implemented.

## Rendering and offline validation

Canonical rendering is compact UTF-8 JSON with recursively sorted keys, no
non-finite values, and exactly one trailing newline. The reader rejects
malformed, duplicate-key, and non-canonical encodings. Repeated rendering is
byte-identical for all three main and both staging profiles.

The validator returns only closed result reasons. Positive checks cover the
exact schema, version binding, conditions, resource types and presence,
retention, graph, bootstrap structure, staging transition, and Module A
consistency. All three main and both staging profiles are exhaustively validated.
Twenty-six in-memory negative fixtures cover missing or additional resources,
invalid types and conditions, retention errors, invalid graph edges and cycles,
forbidden template features, sensitive-looking values, deployable claims, and
invalid staging states. Generated private fixtures and freeze records are not
part of the publication.

> This is a bounded accidental-leakage guard, not a complete DLP system.

The scanner rejects defined shapes for credentials, cloud and network
identifiers, physical wait-handle URLs, private paths, usernames, and prohibited
physical bucket names. Scanner patterns and deliberately artificial negative
test values exercise that guard; they are test apparatus, not real identifiers.

## Research claim boundary

Supported by this publication:

- deterministic structural CloudFormation representation implemented;
- structural resource, Condition, retention, and DAG invariants validated offline;
- exact Module A consistency validated;
- negative structural cases deterministically rejected; and
- artifact remains independent of AWS.

Not supported by this publication:

- deployable CloudFormation correctness or AWS CloudFormation service semantics;
- IAM or KMS correctness;
- executable bootstrap, controller provisioning, or live infrastructure;
- Candidate runtime behavior or traffic performance;
- paper reproduction; or
- cross-system methodological superiority.

This is research apparatus, not a graph-MARL contribution, experiment result,
or demonstration of PhD-level generality. A future Module C may review synthetic
change-set structure offline, but it is a separate publication gate and is not
implemented here. Module B does not make the controller ready to provision.
