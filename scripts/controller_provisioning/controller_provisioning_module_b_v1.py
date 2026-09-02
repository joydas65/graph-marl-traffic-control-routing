"""Offline, deliberately non-deployable structural templates for Module B."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
import ipaddress
import json
import re
from typing import Final, final

from scripts.controller_provisioning import controller_provisioning_module_a_v1 as module_a


_MODULE_B_VERSION: Final[str] = (
    "CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_B_V1"
)
_MODULE_A_VERSION: Final[str] = (
    "CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_A_V1"
)
_CLARIFICATION_VERSION: Final[str] = (
    "CANDIDATE_N_V4_CLOUDFORMATION_PHASE_AND_CHANGESET_CLARIFICATION_V1"
)
_DEPLOYMENT_READINESS: Final[str] = "NON_DEPLOYABLE_STRUCTURAL_SKELETON"
_VERSION_BINDING: Final[tuple[str, str, str]] = (
    _MODULE_B_VERSION,
    _MODULE_A_VERSION,
    _CLARIFICATION_VERSION,
)


@final
class ModuleBValidationErrorV1(ValueError):
    """Fixed public exception for programmer misuse or integration failure."""


_EXPECTED_MODULE_A_BINDING: Final[tuple[str, str]] = (
    _MODULE_A_VERSION,
    _CLARIFICATION_VERSION,
)
if module_a.module_a_version_binding_v1() != _EXPECTED_MODULE_A_BINDING:
    raise ModuleBValidationErrorV1("MODULE_B_MODULE_A_BINDING_MISMATCH")
module_a.require_module_a_version_binding_v1(*_EXPECTED_MODULE_A_BINDING)


@unique
class StructuralTemplateKindV1(Enum):
    MAIN = "MAIN"
    STAGING = "STAGING"


@unique
class DeploymentReadinessV1(Enum):
    NON_DEPLOYABLE_STRUCTURAL_SKELETON = _DEPLOYMENT_READINESS


@unique
class StagingAccessPhaseV1(Enum):
    UPLOAD_ONLY = "UPLOAD_ONLY"
    HOST_EXACT_OBJECT_READ = "HOST_EXACT_OBJECT_READ"


@unique
class StagingPolicyStateV1(Enum):
    NO_CONTROLLER_HOST_OBJECT_READ_GRANT = (
        "NO_CONTROLLER_HOST_OBJECT_READ_GRANT"
    )
    EXACTLY_ONE_FUTURE_HOST_EXACT_OBJECT_READ_GRANT = (
        "EXACTLY_ONE_FUTURE_HOST_EXACT_OBJECT_READ_GRANT"
    )


@unique
class DeferredResolutionV1(Enum):
    STRUCTURE_ONLY = "STRUCTURE_ONLY"
    REQUIRES_PRIVILEGED_POLICY_MODULE = "REQUIRES_PRIVILEGED_POLICY_MODULE"
    REQUIRES_BOOTSTRAP_MODULE = "REQUIRES_BOOTSTRAP_MODULE"
    REQUIRES_PRIVATE_MANIFEST_BINDING = "REQUIRES_PRIVATE_MANIFEST_BINDING"
    IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE = (
        "IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE"
    )
    REQUIRED_LATER_NOT_IMPLEMENTED = "REQUIRED_LATER_NOT_IMPLEMENTED"


@unique
class ModuleBValidationReasonV1(Enum):
    VALID = "VALID"
    INVALID_INPUT = "INVALID_INPUT"
    MALFORMED_JSON = "MALFORMED_JSON"
    DUPLICATE_JSON_KEY = "DUPLICATE_JSON_KEY"
    NON_CANONICAL_JSON = "NON_CANONICAL_JSON"
    SENSITIVE_WAIT_HANDLE_URL = "SENSITIVE_WAIT_HANDLE_URL"
    SENSITIVE_ACCESS_KEY = "SENSITIVE_ACCESS_KEY"
    SENSITIVE_SECRET_OR_SESSION_TOKEN = "SENSITIVE_SECRET_OR_SESSION_TOKEN"
    SENSITIVE_ARN = "SENSITIVE_ARN"
    SENSITIVE_AMI_PHYSICAL_ID = "SENSITIVE_AMI_PHYSICAL_ID"
    SENSITIVE_NETWORK_PHYSICAL_ID = "SENSITIVE_NETWORK_PHYSICAL_ID"
    SENSITIVE_KMS_KEY_ID = "SENSITIVE_KMS_KEY_ID"
    SENSITIVE_AWS_ACCOUNT_NUMBER = "SENSITIVE_AWS_ACCOUNT_NUMBER"
    SENSITIVE_IP_LITERAL = "SENSITIVE_IP_LITERAL"
    SENSITIVE_BUCKET_PHYSICAL_NAME = "SENSITIVE_BUCKET_PHYSICAL_NAME"
    SENSITIVE_PRIVATE_PATH = "SENSITIVE_PRIVATE_PATH"
    SENSITIVE_USERNAME = "SENSITIVE_USERNAME"
    DEPLOYMENT_READINESS_CLAIM_FORBIDDEN = (
        "DEPLOYMENT_READINESS_CLAIM_FORBIDDEN"
    )
    FORBIDDEN_OUTPUT_SECTION = "FORBIDDEN_OUTPUT_SECTION"
    FORBIDDEN_TRANSFORM = "FORBIDDEN_TRANSFORM"
    FORBIDDEN_MACRO = "FORBIDDEN_MACRO"
    FORBIDDEN_NESTED_STACK = "FORBIDDEN_NESTED_STACK"
    FORBIDDEN_CUSTOM_RESOURCE = "FORBIDDEN_CUSTOM_RESOURCE"
    MISSING_TOP_LEVEL_KEY = "MISSING_TOP_LEVEL_KEY"
    UNKNOWN_TOP_LEVEL_KEY = "UNKNOWN_TOP_LEVEL_KEY"
    VERSION_BINDING_MISMATCH = "VERSION_BINDING_MISMATCH"
    METADATA_CONTRACT_MISMATCH = "METADATA_CONTRACT_MISMATCH"
    NONDEPLOYABLE_MARKER_MISMATCH = "NONDEPLOYABLE_MARKER_MISMATCH"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    UNKNOWN_PARAMETER = "UNKNOWN_PARAMETER"
    PARAMETER_CONTRACT_MISMATCH = "PARAMETER_CONTRACT_MISMATCH"
    MISSING_CONDITION = "MISSING_CONDITION"
    UNKNOWN_CONDITION = "UNKNOWN_CONDITION"
    CONDITION_EXPRESSION_INVALID = "CONDITION_EXPRESSION_INVALID"
    CONDITION_TRUTH_TABLE_MISMATCH = "CONDITION_TRUTH_TABLE_MISMATCH"
    CONDITION_EXPRESSION_NONCANONICAL = "CONDITION_EXPRESSION_NONCANONICAL"
    UNEXPECTED_LOGICAL_RESOURCE = "UNEXPECTED_LOGICAL_RESOURCE"
    MISSING_PROTECTED_RESOURCE = "MISSING_PROTECTED_RESOURCE"
    MISSING_LOGICAL_RESOURCE = "MISSING_LOGICAL_RESOURCE"
    RESOURCE_NODE_SCHEMA_MISMATCH = "RESOURCE_NODE_SCHEMA_MISMATCH"
    RESOURCE_TYPE_MISMATCH = "RESOURCE_TYPE_MISMATCH"
    UNKNOWN_RESOURCE_CONDITION = "UNKNOWN_RESOURCE_CONDITION"
    RESOURCE_CONDITION_MISMATCH = "RESOURCE_CONDITION_MISMATCH"
    DELETION_POLICY_MISMATCH = "DELETION_POLICY_MISMATCH"
    UPDATE_REPLACE_POLICY_MISMATCH = "UPDATE_REPLACE_POLICY_MISMATCH"
    UNEXPECTED_RETENTION_ATTRIBUTE = "UNEXPECTED_RETENTION_ATTRIBUTE"
    PRIVILEGED_CONTENT_PRESENT = "PRIVILEGED_CONTENT_PRESENT"
    FREE_FORM_PLACEHOLDER_FORBIDDEN = "FREE_FORM_PLACEHOLDER_FORBIDDEN"
    STRUCTURAL_PLACEHOLDER_MISMATCH = "STRUCTURAL_PLACEHOLDER_MISMATCH"
    BOOTSTRAP_STRUCTURE_MISMATCH = "BOOTSTRAP_STRUCTURE_MISMATCH"
    CONTROLLER_METADATA_MISMATCH = "CONTROLLER_METADATA_MISMATCH"
    DEPENDENCY_FORMAT_INVALID = "DEPENDENCY_FORMAT_INVALID"
    DEPENDENCY_TARGET_UNKNOWN = "DEPENDENCY_TARGET_UNKNOWN"
    DEPENDENCY_SELF_REFERENCE = "DEPENDENCY_SELF_REFERENCE"
    DEPENDENCY_CYCLE = "DEPENDENCY_CYCLE"
    DEPENDENCY_EDGE_MISMATCH = "DEPENDENCY_EDGE_MISMATCH"
    DEPENDENCY_PHASE_INCOMPATIBLE = "DEPENDENCY_PHASE_INCOMPATIBLE"
    MODULE_A_ACTIVE_RESOURCE_SET_MISMATCH = (
        "MODULE_A_ACTIVE_RESOURCE_SET_MISMATCH"
    )
    MODULE_A_RESOURCE_COUNT_MISMATCH = "MODULE_A_RESOURCE_COUNT_MISMATCH"
    MODULE_A_CONDITION_MISMATCH = "MODULE_A_CONDITION_MISMATCH"
    STAGING_ACCESS_POLICY_STATE_MISMATCH = (
        "STAGING_ACCESS_POLICY_STATE_MISMATCH"
    )
    STAGING_DELTA_MISMATCH = "STAGING_DELTA_MISMATCH"
    UNRESTRICTED_EXTENSION_FIELD = "UNRESTRICTED_EXTENSION_FIELD"


@final
@dataclass(frozen=True, slots=True)
class ModuleBValidationResultV1:
    is_valid: bool
    reason: ModuleBValidationReasonV1

    def __post_init__(self) -> None:
        valid = (
            type(self.is_valid) is bool
            and type(self.reason) is ModuleBValidationReasonV1
            and self.is_valid
            is (self.reason is ModuleBValidationReasonV1.VALID)
        )
        if not valid:
            raise ModuleBValidationErrorV1("MODULE_B_INVALID_VALIDATION_RESULT")

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise ModuleBValidationErrorV1("MODULE_B_VALIDATION_RESULT_IS_FINAL")


@final
@dataclass(frozen=True, slots=True)
class StagingStructuralDeltaV1:
    create_added_logical_ids: tuple[str, ...]
    update_added_logical_ids: tuple[str, ...]
    update_removed_logical_ids: tuple[str, ...]
    update_modified_logical_ids: tuple[str, ...]
    update_replaced_logical_ids: tuple[str, ...]

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise ModuleBValidationErrorV1("MODULE_B_STAGING_DELTA_IS_FINAL")


_MAIN_RESOURCE_TYPE_ROWS: Final[
    tuple[tuple[module_a.ControllerLogicalResourceIdV1, str], ...]
] = (
    (
        module_a.ControllerLogicalResourceIdV1.CONTROLLER_BUDGET,
        "AWS::Budgets::Budget",
    ),
    (
        module_a.ControllerLogicalResourceIdV1.CONTROLLER_SECURITY_GROUP,
        "AWS::EC2::SecurityGroup",
    ),
    (
        module_a.ControllerLogicalResourceIdV1.CONTROLLER_HOST_ROLE,
        "AWS::IAM::Role",
    ),
    (
        module_a.ControllerLogicalResourceIdV1.EXPERIMENT_RUNTIME_ROLE,
        "AWS::IAM::Role",
    ),
    (
        module_a.ControllerLogicalResourceIdV1.CONTROLLER_INSTANCE_PROFILE,
        "AWS::IAM::InstanceProfile",
    ),
    (
        module_a.ControllerLogicalResourceIdV1.CONTROLLER_COMMAND_DOCUMENT,
        "AWS::SSM::Document",
    ),
    (
        module_a.ControllerLogicalResourceIdV1.EVIDENCE_KEY,
        "AWS::KMS::Key",
    ),
    (
        module_a.ControllerLogicalResourceIdV1.EVIDENCE_VOLUME,
        "AWS::EC2::Volume",
    ),
    (
        module_a.ControllerLogicalResourceIdV1.CONTROLLER_INSTANCE,
        "AWS::EC2::Instance",
    ),
    (
        module_a.ControllerLogicalResourceIdV1.EVIDENCE_VOLUME_ATTACHMENT,
        "AWS::EC2::VolumeAttachment",
    ),
    (
        module_a.ControllerLogicalResourceIdV1.BOOTSTRAP_WAIT_HANDLE,
        "AWS::CloudFormation::WaitConditionHandle",
    ),
    (
        module_a.ControllerLogicalResourceIdV1.BOOTSTRAP_WAIT_CONDITION,
        "AWS::CloudFormation::WaitCondition",
    ),
)
_MODULE_A_REGISTRY_IDS: Final[frozenset[module_a.ControllerLogicalResourceIdV1]] = (
    frozenset(record.logical_id for record in module_a.logical_resource_registry_v1())
)
_MODULE_A_RETAINED_IDS: Final[frozenset[str]] = frozenset(
    record.logical_id.value
    for record in module_a.logical_resource_registry_v1()
    if record.retained_evidence_protected
)
if frozenset(row[0] for row in _MAIN_RESOURCE_TYPE_ROWS) != _MODULE_A_REGISTRY_IDS:
    raise ModuleBValidationErrorV1("MODULE_B_MODULE_A_REGISTRY_MISMATCH")


_MAIN_TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "AWSTemplateFormatVersion",
        "Description",
        "Metadata",
        "Parameters",
        "Conditions",
        "Resources",
    }
)
_STAGING_TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "AWSTemplateFormatVersion",
        "Description",
        "Metadata",
        "Parameters",
        "Resources",
    }
)
_STAGING_RESOURCE_IDS: Final[tuple[str, str]] = (
    "StagingBundleBucket",
    "StagingBucketPolicy",
)
_SENSITIVE_REASON_PRIORITY: Final[tuple[ModuleBValidationReasonV1, ...]] = (
    ModuleBValidationReasonV1.SENSITIVE_WAIT_HANDLE_URL,
    ModuleBValidationReasonV1.SENSITIVE_ACCESS_KEY,
    ModuleBValidationReasonV1.SENSITIVE_SECRET_OR_SESSION_TOKEN,
    ModuleBValidationReasonV1.SENSITIVE_ARN,
    ModuleBValidationReasonV1.SENSITIVE_AMI_PHYSICAL_ID,
    ModuleBValidationReasonV1.SENSITIVE_NETWORK_PHYSICAL_ID,
    ModuleBValidationReasonV1.SENSITIVE_KMS_KEY_ID,
    ModuleBValidationReasonV1.SENSITIVE_AWS_ACCOUNT_NUMBER,
    ModuleBValidationReasonV1.SENSITIVE_IP_LITERAL,
    ModuleBValidationReasonV1.SENSITIVE_BUCKET_PHYSICAL_NAME,
    ModuleBValidationReasonV1.SENSITIVE_PRIVATE_PATH,
    ModuleBValidationReasonV1.SENSITIVE_USERNAME,
)
_CLOSED_PLACEHOLDER_VALUES: Final[frozenset[str]] = frozenset(
    member.value for member in DeferredResolutionV1
)
_INVALID_CONDITION_VALUE: Final[object] = object()


def _valid_result() -> ModuleBValidationResultV1:
    return ModuleBValidationResultV1(True, ModuleBValidationReasonV1.VALID)


def _invalid_result(reason: ModuleBValidationReasonV1) -> ModuleBValidationResultV1:
    return ModuleBValidationResultV1(False, reason)


def _require_template_kind(value: object) -> StructuralTemplateKindV1:
    if type(value) is not StructuralTemplateKindV1:
        raise ModuleBValidationErrorV1("MODULE_B_INVALID_TEMPLATE_KIND")
    return value


def _require_main_phase(value: object) -> module_a.ControllerDeploymentPhaseV1:
    if type(value) is not module_a.ControllerDeploymentPhaseV1:
        raise ModuleBValidationErrorV1("MODULE_B_INVALID_MAIN_PHASE")
    return value


def _require_staging_phase(value: object) -> StagingAccessPhaseV1:
    if type(value) is not StagingAccessPhaseV1:
        raise ModuleBValidationErrorV1("MODULE_B_INVALID_STAGING_PHASE")
    return value


def module_b_version_binding_v1() -> tuple[str, str, str]:
    return _VERSION_BINDING


def require_module_b_version_binding_v1(
    module_b_version: object,
    module_a_version: object,
    clarification_version: object,
    /,
) -> tuple[str, str, str]:
    if (
        type(module_b_version) is not str
        or type(module_a_version) is not str
        or type(clarification_version) is not str
        or (module_b_version, module_a_version, clarification_version)
        != _VERSION_BINDING
    ):
        raise ModuleBValidationErrorV1("MODULE_B_VERSION_BINDING_MISMATCH")
    module_a.require_module_a_version_binding_v1(
        module_a_version,
        clarification_version,
    )
    return _VERSION_BINDING


def _resource_type(logical_id: module_a.ControllerLogicalResourceIdV1) -> str:
    for candidate_id, resource_type in _MAIN_RESOURCE_TYPE_ROWS:
        if candidate_id is logical_id:
            return resource_type
    raise ModuleBValidationErrorV1("MODULE_B_RESOURCE_TYPE_REGISTRY_INCOMPLETE")


def _condition_expression_for_true_phases(
    true_phases: tuple[module_a.ControllerDeploymentPhaseV1, ...],
) -> dict[str, object]:
    equalities = [
        {
            "Fn::Equals": [
                {"Ref": "ControllerDeploymentPhase"},
                phase.value,
            ]
        }
        for phase in true_phases
    ]
    if len(equalities) == 1:
        return equalities[0]
    return {"Fn::Or": equalities}


def _main_conditions() -> dict[str, object]:
    phases = tuple(module_a.ControllerDeploymentPhaseV1)
    controller_phases = tuple(
        phase for phase in phases if module_a.controller_present_v1(phase)
    )
    bootstrap_phases = tuple(
        phase for phase in phases if module_a.bootstrap_signal_active_v1(phase)
    )
    return {
        "BootstrapSignalActive": _condition_expression_for_true_phases(
            bootstrap_phases
        ),
        "ControllerPresent": _condition_expression_for_true_phases(controller_phases),
    }


def _condition_for_record(record: object) -> str | None:
    phases = tuple(module_a.ControllerDeploymentPhaseV1)
    all_phases = frozenset(phases)
    controller_phases = frozenset(
        phase for phase in phases if module_a.controller_present_v1(phase)
    )
    bootstrap_phases = frozenset(
        phase for phase in phases if module_a.bootstrap_signal_active_v1(phase)
    )
    mask = record.phase_presence_mask
    if mask == all_phases:
        return None
    if mask == controller_phases:
        return "ControllerPresent"
    if mask == bootstrap_phases:
        return "BootstrapSignalActive"
    raise ModuleBValidationErrorV1("MODULE_B_UNSUPPORTED_MODULE_A_PRESENCE_MASK")


def _deferred_content(
    logical_id: module_a.ControllerLogicalResourceIdV1,
) -> dict[str, str]:
    role = DeferredResolutionV1
    if logical_id is module_a.ControllerLogicalResourceIdV1.CONTROLLER_BUDGET:
        return {
            "BudgetNotificationDestinations": role.REQUIRES_PRIVILEGED_POLICY_MODULE.value
        }
    if logical_id is module_a.ControllerLogicalResourceIdV1.CONTROLLER_SECURITY_GROUP:
        return {
            "SecurityGroupEgressDetails": role.REQUIRES_PRIVILEGED_POLICY_MODULE.value
        }
    if logical_id in (
        module_a.ControllerLogicalResourceIdV1.CONTROLLER_HOST_ROLE,
        module_a.ControllerLogicalResourceIdV1.EXPERIMENT_RUNTIME_ROLE,
    ):
        return {
            "IamPermissionPolicyBody": role.REQUIRES_PRIVILEGED_POLICY_MODULE.value,
            "IamTrustPolicyBody": role.REQUIRES_PRIVILEGED_POLICY_MODULE.value,
        }
    if logical_id is module_a.ControllerLogicalResourceIdV1.CONTROLLER_INSTANCE_PROFILE:
        return {
            "RoleBinding": role.IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE.value
        }
    if logical_id is module_a.ControllerLogicalResourceIdV1.CONTROLLER_COMMAND_DOCUMENT:
        return {"SsmDocumentBody": role.REQUIRES_BOOTSTRAP_MODULE.value}
    if logical_id is module_a.ControllerLogicalResourceIdV1.EVIDENCE_KEY:
        return {"KmsKeyPolicy": role.REQUIRES_PRIVILEGED_POLICY_MODULE.value}
    if logical_id is module_a.ControllerLogicalResourceIdV1.EVIDENCE_VOLUME:
        return {
            "AvailabilityZoneBinding": role.REQUIRES_PRIVATE_MANIFEST_BINDING.value,
            "EncryptionKeyBinding": role.IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE.value,
        }
    if logical_id is module_a.ControllerLogicalResourceIdV1.CONTROLLER_INSTANCE:
        return {"Ec2UserData": role.REQUIRES_BOOTSTRAP_MODULE.value}
    if logical_id is module_a.ControllerLogicalResourceIdV1.EVIDENCE_VOLUME_ATTACHMENT:
        return {
            "AttachmentDevice": role.IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE.value,
            "InstanceAndVolumeBindings": role.IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE.value,
        }
    return {}


def _controller_structural_requirements() -> dict[str, object]:
    role = DeferredResolutionV1
    return {
        "ExactFrozenAmi": role.REQUIRES_PRIVATE_MANIFEST_BINDING.value,
        "ImdsV2Controls": role.IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE.value,
        "InstanceClass": {
            "RequiredValue": "t3.small",
            "Resolution": role.IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE.value,
        },
        "InstanceProfileBinding": role.IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE.value,
        "PublicAddressProfile": role.REQUIRES_PRIVATE_MANIFEST_BINDING.value,
        "RootBlockDeviceMapping": role.IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE.value,
        "SecurityGroupBinding": role.IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE.value,
        "StandardCreditMode": role.IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE.value,
        "SubnetBinding": role.REQUIRES_PRIVATE_MANIFEST_BINDING.value,
    }


def _main_resource_metadata(record: object) -> dict[str, object]:
    logical_id = record.logical_id
    metadata: dict[str, object] = {
        "StructuralClass": record.resource_class.value,
    }
    deferred = _deferred_content(logical_id)
    if deferred:
        metadata["DeferredContent"] = deferred
    if logical_id is module_a.ControllerLogicalResourceIdV1.CONTROLLER_INSTANCE:
        metadata["CandidateNBootstrapSignalUrl"] = {
            "Fn::If": [
                "BootstrapSignalActive",
                {
                    "Ref": module_a.ControllerLogicalResourceIdV1.BOOTSTRAP_WAIT_HANDLE.value
                },
                module_a.ControllerDeploymentPhaseV1.SEALED_STOPPED.value,
            ]
        }
        metadata["StructuralRequirements"] = _controller_structural_requirements()
    elif logical_id is module_a.ControllerLogicalResourceIdV1.BOOTSTRAP_WAIT_HANDLE:
        metadata["StructuralExpectations"] = {
            "PhysicalSignalUrlRendered": False,
        }
    elif logical_id is module_a.ControllerLogicalResourceIdV1.BOOTSTRAP_WAIT_CONDITION:
        metadata["StructuralExpectations"] = {
            "Count": 1,
            "TimeoutSeconds": 28800,
        }
    return metadata


def _main_resource_dependencies(
    logical_id: module_a.ControllerLogicalResourceIdV1,
) -> tuple[str, ...]:
    if logical_id is module_a.ControllerLogicalResourceIdV1.EVIDENCE_VOLUME_ATTACHMENT:
        return (
            module_a.ControllerLogicalResourceIdV1.CONTROLLER_INSTANCE.value,
            module_a.ControllerLogicalResourceIdV1.EVIDENCE_VOLUME.value,
        )
    if logical_id is module_a.ControllerLogicalResourceIdV1.BOOTSTRAP_WAIT_CONDITION:
        return (
            module_a.ControllerLogicalResourceIdV1.EVIDENCE_VOLUME_ATTACHMENT.value,
        )
    return ()


def _main_metadata(
    phase: module_a.ControllerDeploymentPhaseV1,
) -> dict[str, object]:
    later = DeferredResolutionV1.REQUIRED_LATER_NOT_IMPLEMENTED.value
    return {
        "Artifact": {
            "DeploymentReadiness": _DEPLOYMENT_READINESS,
            "ModuleABinding": _MODULE_A_VERSION,
            "ModuleBVersion": _MODULE_B_VERSION,
            "PhaseClarificationBinding": _CLARIFICATION_VERSION,
            "RenderProfile": phase.value,
            "TemplateKind": StructuralTemplateKindV1.MAIN.value,
        },
        "DeferredControls": {
            "RetainExceptOnCreate": later,
            "StackPolicy": later,
            "TerminationProtection": later,
        },
    }


def _staging_metadata(phase: StagingAccessPhaseV1) -> dict[str, object]:
    _require_staging_phase(phase)
    return {
        "Artifact": {
            "DeploymentReadiness": _DEPLOYMENT_READINESS,
            "ModuleABinding": _MODULE_A_VERSION,
            "ModuleBVersion": _MODULE_B_VERSION,
            "PhaseClarificationBinding": _CLARIFICATION_VERSION,
            "TemplateKind": StructuralTemplateKindV1.STAGING.value,
        }
    }


def build_main_structural_model_v1(
    phase: object,
    /,
) -> dict[str, object]:
    checked_phase = _require_main_phase(phase)
    resources: dict[str, object] = {}
    for record in module_a.logical_resource_registry_v1():
        node: dict[str, object] = {
            "Metadata": _main_resource_metadata(record),
            "Type": _resource_type(record.logical_id),
        }
        condition = _condition_for_record(record)
        if condition is not None:
            node["Condition"] = condition
        dependencies = _main_resource_dependencies(record.logical_id)
        if dependencies:
            node["DependsOn"] = list(dependencies)
        if record.retained_evidence_protected:
            node["DeletionPolicy"] = "Retain"
            node["UpdateReplacePolicy"] = "Retain"
        resources[record.logical_id.value] = node
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Conditions": _main_conditions(),
        "Description": "Source-free controller topology; intentionally non-deployable.",
        "Metadata": _main_metadata(checked_phase),
        "Parameters": {
            "ControllerDeploymentPhase": {
                "AllowedValues": [
                    item.value for item in module_a.ControllerDeploymentPhaseV1
                ],
                "Type": "String",
            }
        },
        "Resources": resources,
    }


def _staging_policy_state(phase: StagingAccessPhaseV1) -> StagingPolicyStateV1:
    if phase is StagingAccessPhaseV1.UPLOAD_ONLY:
        return StagingPolicyStateV1.NO_CONTROLLER_HOST_OBJECT_READ_GRANT
    return StagingPolicyStateV1.EXACTLY_ONE_FUTURE_HOST_EXACT_OBJECT_READ_GRANT


def build_staging_structural_model_v1(
    phase: object,
    /,
) -> dict[str, object]:
    checked_phase = _require_staging_phase(phase)
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Source-free staging topology; intentionally non-deployable.",
        "Metadata": _staging_metadata(checked_phase),
        "Parameters": {
            "StagingAccessPhase": {
                "AllowedValues": [item.value for item in StagingAccessPhaseV1],
                "Type": "String",
            }
        },
        "Resources": {
            "StagingBucketPolicy": {
                "DependsOn": ["StagingBundleBucket"],
                "Metadata": {
                    "DeferredContent": {
                        "PolicyStatements": DeferredResolutionV1.REQUIRES_PRIVILEGED_POLICY_MODULE.value
                    },
                    "StructuralPolicyState": _staging_policy_state(
                        checked_phase
                    ).value,
                },
                "Type": "AWS::S3::BucketPolicy",
            },
            "StagingBundleBucket": {
                "Metadata": {
                    "DeferredContent": {
                        "BucketPhysicalName": DeferredResolutionV1.REQUIRES_PRIVATE_MANIFEST_BINDING.value
                    }
                },
                "Type": "AWS::S3::Bucket",
            },
        },
    }


def canonicalize_structural_model_v1(structural_model: object, /) -> bytes:
    if type(structural_model) is not dict:
        raise ModuleBValidationErrorV1("MODULE_B_CANONICAL_MODEL_REQUIRED")
    try:
        text = json.dumps(
            structural_model,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (RecursionError, TypeError, ValueError):
        raise ModuleBValidationErrorV1("MODULE_B_CANONICAL_MODEL_INVALID") from None
    return (text + "\n").encode("utf-8")


class _DuplicateJsonKeyError(ValueError):
    pass


def _closed_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError
        result[key] = value
    return result


def _decode_canonical_json(
    canonical_utf8: bytes,
) -> tuple[dict[str, object] | None, ModuleBValidationReasonV1]:
    try:
        text = canonical_utf8.decode("utf-8")
        model = json.loads(
            text,
            object_pairs_hook=_closed_json_object,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError()),
        )
    except _DuplicateJsonKeyError:
        return None, ModuleBValidationReasonV1.DUPLICATE_JSON_KEY
    except (RecursionError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None, ModuleBValidationReasonV1.MALFORMED_JSON
    if type(model) is not dict:
        return None, ModuleBValidationReasonV1.INVALID_INPUT
    try:
        canonical_model = canonicalize_structural_model_v1(model)
    except ModuleBValidationErrorV1:
        return None, ModuleBValidationReasonV1.MALFORMED_JSON
    if canonical_model != canonical_utf8:
        return None, ModuleBValidationReasonV1.NON_CANONICAL_JSON
    return model, ModuleBValidationReasonV1.VALID


def _exact_json_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        if frozenset(left) != frozenset(right):
            return False
        return all(_exact_json_equal(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(
            _exact_json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return left == right


def _walk_string_values(
    value: object,
    parent_key: str = "",
) -> tuple[tuple[str, str], ...] | None:
    found: list[tuple[str, str]] = []
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            return None
        for key in sorted(value):
            child = value[key]
            found.append((key, child if type(child) is str else ""))
            nested = _walk_string_values(child, key)
            if nested is None:
                return None
            found.extend(nested)
    elif type(value) is list:
        for child in value:
            if type(child) is str:
                found.append((parent_key, child))
            nested = _walk_string_values(child, parent_key)
            if nested is None:
                return None
            found.extend(nested)
    return tuple(found)


def sensitive_value_scan_v1(structural_model: object, /) -> ModuleBValidationReasonV1:
    if type(structural_model) is not dict:
        return ModuleBValidationReasonV1.INVALID_INPUT
    findings: set[ModuleBValidationReasonV1] = set()
    try:
        string_values = _walk_string_values(structural_model)
    except RecursionError:
        return ModuleBValidationReasonV1.INVALID_INPUT
    if string_values is None:
        return ModuleBValidationReasonV1.INVALID_INPUT
    for key, value in string_values:
        normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
        if normalized_key in {"accesskeyid", "awsaccesskeyid"}:
            findings.add(ModuleBValidationReasonV1.SENSITIVE_ACCESS_KEY)
        if normalized_key in {
            "accesstoken",
            "apikey",
            "authtoken",
            "awssecretaccesskey",
            "awssessiontoken",
            "clientsecret",
            "secretaccesskey",
            "secrettoken",
            "sessiontoken",
            "credential",
            "credentials",
            "password",
            "privatekey",
        }:
            findings.add(ModuleBValidationReasonV1.SENSITIVE_SECRET_OR_SESSION_TOKEN)
        if normalized_key == "username":
            findings.add(ModuleBValidationReasonV1.SENSITIVE_USERNAME)
        if value in _CLOSED_PLACEHOLDER_VALUES:
            continue
        if re.match(r"^https?://", value, flags=re.IGNORECASE) and (
            "waithandle" in normalized_key
            or "waiturl" in normalized_key
            or "signalurl" in normalized_key
            or re.search(
                r"cloudformation-waitcondition",
                value,
                flags=re.IGNORECASE,
            )
        ):
            findings.add(ModuleBValidationReasonV1.SENSITIVE_WAIT_HANDLE_URL)
        if re.search(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", value):
            findings.add(ModuleBValidationReasonV1.SENSITIVE_ACCESS_KEY)
        if re.search(r"\barn:(?:aws|aws-us-gov|aws-cn):", value, re.IGNORECASE):
            findings.add(ModuleBValidationReasonV1.SENSITIVE_ARN)
        if re.search(r"\bami-[0-9a-f]{8,17}\b", value, re.IGNORECASE):
            findings.add(ModuleBValidationReasonV1.SENSITIVE_AMI_PHYSICAL_ID)
        if re.search(
            r"\b(?:subnet|vpc|sg|vol|snap|i)-[0-9a-f]{8,17}\b",
            value,
            re.IGNORECASE,
        ):
            findings.add(ModuleBValidationReasonV1.SENSITIVE_NETWORK_PHYSICAL_ID)
        if normalized_key in {"keyid", "kmskeyid"} and re.fullmatch(
            r"(?:mrk-[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})",
            value,
            re.IGNORECASE,
        ):
            findings.add(ModuleBValidationReasonV1.SENSITIVE_KMS_KEY_ID)
        if re.search(r"(?<!\d)\d{12}(?!\d)", value):
            findings.add(ModuleBValidationReasonV1.SENSITIVE_AWS_ACCOUNT_NUMBER)
        ip_candidates = re.findall(
            r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?(?![\d.])",
            value,
        )
        ip_candidates.extend(
            re.findall(r"\[([0-9A-Fa-f:]+)\](?:/\d{1,3})?", value)
        )
        ip_candidates.extend(re.findall(
            r"(?<![0-9A-Za-z])[0-9A-Fa-f:.]+(?:/\d{1,3})?(?![0-9A-Za-z])",
            value,
        ))
        for candidate in ip_candidates:
            candidate = candidate.strip("[](),;<>")
            if "." not in candidate and ":" not in candidate:
                continue
            try:
                if "/" in candidate:
                    ipaddress.ip_interface(candidate)
                else:
                    ipaddress.ip_address(candidate)
            except ValueError:
                continue
            findings.add(ModuleBValidationReasonV1.SENSITIVE_IP_LITERAL)
            break
        if normalized_key in {
            "bucketname",
            "bucketphysicalname",
            "physicalbucketname",
        } or (normalized_key == "bucket" and bool(value)):
            findings.add(ModuleBValidationReasonV1.SENSITIVE_BUCKET_PHYSICAL_NAME)
        if re.search(
            r"(?:/Users/|/home/|/root/|/private/|[A-Za-z]:\\Users\\)",
            value,
            flags=re.IGNORECASE,
        ):
            findings.add(ModuleBValidationReasonV1.SENSITIVE_PRIVATE_PATH)
    for reason in _SENSITIVE_REASON_PRIORITY:
        if reason in findings:
            return reason
    return ModuleBValidationReasonV1.VALID


def _contains_deployable_claim(value: object) -> bool:
    forbidden_values = frozenset(
        {"deployable", "provisioningready", "changesetready", "livevalidationready"}
    )
    if type(value) is str:
        normalized_value = re.sub(r"[^a-z0-9]", "", value.lower())
        return normalized_value in forbidden_values
    if type(value) is dict:
        for key, child in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized_key in {
                "deployable",
                "provisioningready",
                "changesetready",
                "livevalidationready",
            } and child is True:
                return True
            if _contains_deployable_claim(child):
                return True
    elif type(value) is list:
        return any(_contains_deployable_claim(child) for child in value)
    return False


def _contains_key(value: object, target: str) -> bool:
    if type(value) is dict:
        return target in value or any(_contains_key(child, target) for child in value.values())
    if type(value) is list:
        return any(_contains_key(child, target) for child in value)
    return False


def _evaluate_condition(
    expression: object,
    phase: module_a.ControllerDeploymentPhaseV1,
) -> object:
    if type(expression) is bool or type(expression) is str:
        return expression
    if type(expression) is not dict or len(expression) != 1:
        return _INVALID_CONDITION_VALUE
    if "Ref" in expression:
        if expression["Ref"] == "ControllerDeploymentPhase":
            return phase.value
        return _INVALID_CONDITION_VALUE
    if "Fn::Equals" in expression:
        values = expression["Fn::Equals"]
        if type(values) is not list or len(values) != 2:
            return _INVALID_CONDITION_VALUE
        left = _evaluate_condition(values[0], phase)
        right = _evaluate_condition(values[1], phase)
        if _INVALID_CONDITION_VALUE in (left, right):
            return _INVALID_CONDITION_VALUE
        return left == right
    if "Fn::Or" in expression:
        values = expression["Fn::Or"]
        if type(values) is not list or not values:
            return _INVALID_CONDITION_VALUE
        evaluated = tuple(_evaluate_condition(item, phase) for item in values)
        if any(type(item) is not bool for item in evaluated):
            return _INVALID_CONDITION_VALUE
        return any(evaluated)
    return _INVALID_CONDITION_VALUE


def _forbidden_resource_reason(resources: object) -> ModuleBValidationReasonV1:
    if type(resources) is not dict:
        return ModuleBValidationReasonV1.VALID
    for node in resources.values():
        if type(node) is not dict or type(node.get("Type")) is not str:
            continue
        resource_type = node["Type"]
        if resource_type == "AWS::CloudFormation::Macro":
            return ModuleBValidationReasonV1.FORBIDDEN_MACRO
        if resource_type == "AWS::CloudFormation::Stack":
            return ModuleBValidationReasonV1.FORBIDDEN_NESTED_STACK
        if resource_type == "AWS::CloudFormation::CustomResource" or resource_type.startswith(
            "Custom::"
        ):
            return ModuleBValidationReasonV1.FORBIDDEN_CUSTOM_RESOURCE
    return ModuleBValidationReasonV1.VALID


def _has_free_form_placeholder(value: object) -> bool:
    if type(value) is str:
        if value in _CLOSED_PLACEHOLDER_VALUES:
            return False
        return value.strip().lower() in {"todo", "later", "tbd", "fixme"}
    if type(value) is dict:
        return any(_has_free_form_placeholder(child) for child in value.values())
    if type(value) is list:
        return any(_has_free_form_placeholder(child) for child in value)
    return False


def _dependency_edges(
    resources: dict[str, object],
) -> tuple[tuple[str, str], ...] | None:
    edges: list[tuple[str, str]] = []
    for logical_id in sorted(resources):
        node = resources[logical_id]
        if type(node) is not dict or "DependsOn" not in node:
            continue
        dependencies = node["DependsOn"]
        if (
            type(dependencies) is not list
            or any(type(item) is not str for item in dependencies)
            or len(dependencies) != len(frozenset(dependencies))
            or tuple(dependencies) != tuple(sorted(dependencies))
        ):
            return None
        edges.extend((logical_id, target) for target in dependencies)
    return tuple(edges)


def _dependency_graph_has_cycle(
    resource_ids: tuple[str, ...],
    edges: tuple[tuple[str, str], ...],
) -> bool:
    adjacency = {
        logical_id: tuple(target for source, target in edges if source == logical_id)
        for logical_id in resource_ids
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(logical_id: str) -> bool:
        if logical_id in visiting:
            return True
        if logical_id in visited:
            return False
        visiting.add(logical_id)
        if any(visit(target) for target in adjacency[logical_id]):
            return True
        visiting.remove(logical_id)
        visited.add(logical_id)
        return False

    return any(visit(logical_id) for logical_id in resource_ids)


def _main_active_resource_ids(
    model: dict[str, object],
    phase: module_a.ControllerDeploymentPhaseV1,
) -> tuple[str, ...] | None:
    conditions = model["Conditions"]
    resources = model["Resources"]
    active: list[str] = []
    for logical_id in sorted(resources):
        node = resources[logical_id]
        condition_name = node.get("Condition")
        if condition_name is None:
            active.append(logical_id)
            continue
        evaluated = _evaluate_condition(conditions[condition_name], phase)
        if type(evaluated) is not bool:
            return None
        if evaluated:
            active.append(logical_id)
    return tuple(active)


def _validate_dependencies(
    resources: dict[str, object],
    expected_resources: dict[str, object],
    phases: tuple[module_a.ControllerDeploymentPhaseV1, ...] | None,
    conditions: dict[str, object] | None,
) -> ModuleBValidationReasonV1:
    edges = _dependency_edges(resources)
    if edges is None:
        return ModuleBValidationReasonV1.DEPENDENCY_FORMAT_INVALID
    resource_ids = tuple(sorted(resources))
    if any(target not in resources for _, target in edges):
        return ModuleBValidationReasonV1.DEPENDENCY_TARGET_UNKNOWN
    if any(source == target for source, target in edges):
        return ModuleBValidationReasonV1.DEPENDENCY_SELF_REFERENCE
    if _dependency_graph_has_cycle(resource_ids, edges):
        return ModuleBValidationReasonV1.DEPENDENCY_CYCLE
    if phases is not None and conditions is not None:
        for phase in phases:
            active = frozenset(_main_active_resource_ids(
                {"Conditions": conditions, "Resources": resources},
                phase,
            ) or ())
            if any(source in active and target not in active for source, target in edges):
                return ModuleBValidationReasonV1.DEPENDENCY_PHASE_INCOMPATIBLE
    expected_edges = _dependency_edges(expected_resources)
    if edges != expected_edges:
        return ModuleBValidationReasonV1.DEPENDENCY_EDGE_MISMATCH
    return ModuleBValidationReasonV1.VALID


def _validate_main_model(
    model: dict[str, object],
    phase: module_a.ControllerDeploymentPhaseV1,
) -> ModuleBValidationReasonV1:
    if "Outputs" in model:
        return ModuleBValidationReasonV1.FORBIDDEN_OUTPUT_SECTION
    if "Transform" in model or _contains_key(model, "Fn::Transform"):
        return ModuleBValidationReasonV1.FORBIDDEN_TRANSFORM
    forbidden_resource = _forbidden_resource_reason(model.get("Resources"))
    if forbidden_resource is not ModuleBValidationReasonV1.VALID:
        return forbidden_resource
    keys = frozenset(model)
    if _MAIN_TOP_LEVEL_KEYS - keys:
        return ModuleBValidationReasonV1.MISSING_TOP_LEVEL_KEY
    if keys - _MAIN_TOP_LEVEL_KEYS:
        return ModuleBValidationReasonV1.UNKNOWN_TOP_LEVEL_KEY
    expected = build_main_structural_model_v1(phase)
    metadata = model["Metadata"]
    if type(metadata) is not dict or type(metadata.get("Artifact")) is not dict:
        return ModuleBValidationReasonV1.METADATA_CONTRACT_MISMATCH
    artifact = metadata["Artifact"]
    if (
        artifact.get("ModuleBVersion") != _MODULE_B_VERSION
        or artifact.get("ModuleABinding") != _MODULE_A_VERSION
        or artifact.get("PhaseClarificationBinding") != _CLARIFICATION_VERSION
    ):
        return ModuleBValidationReasonV1.VERSION_BINDING_MISMATCH
    if artifact.get("DeploymentReadiness") != _DEPLOYMENT_READINESS:
        return ModuleBValidationReasonV1.NONDEPLOYABLE_MARKER_MISMATCH
    if artifact.get("RenderProfile") != phase.value:
        return ModuleBValidationReasonV1.METADATA_CONTRACT_MISMATCH
    if not _exact_json_equal(metadata, expected["Metadata"]):
        return ModuleBValidationReasonV1.METADATA_CONTRACT_MISMATCH
    parameters = model["Parameters"]
    if type(parameters) is not dict:
        return ModuleBValidationReasonV1.MISSING_PARAMETER
    expected_parameter_ids = frozenset({"ControllerDeploymentPhase"})
    parameter_ids = frozenset(parameters)
    if expected_parameter_ids - parameter_ids:
        return ModuleBValidationReasonV1.MISSING_PARAMETER
    if parameter_ids - expected_parameter_ids:
        return ModuleBValidationReasonV1.UNKNOWN_PARAMETER
    if not _exact_json_equal(parameters, expected["Parameters"]):
        return ModuleBValidationReasonV1.PARAMETER_CONTRACT_MISMATCH
    conditions = model["Conditions"]
    if type(conditions) is not dict:
        return ModuleBValidationReasonV1.MISSING_CONDITION
    expected_condition_ids = frozenset({"ControllerPresent", "BootstrapSignalActive"})
    condition_ids = frozenset(conditions)
    if expected_condition_ids - condition_ids:
        return ModuleBValidationReasonV1.MISSING_CONDITION
    if condition_ids - expected_condition_ids:
        return ModuleBValidationReasonV1.UNKNOWN_CONDITION
    phases = tuple(module_a.ControllerDeploymentPhaseV1)
    for candidate_phase in phases:
        controller_actual = _evaluate_condition(
            conditions["ControllerPresent"],
            candidate_phase,
        )
        bootstrap_actual = _evaluate_condition(
            conditions["BootstrapSignalActive"],
            candidate_phase,
        )
        if type(controller_actual) is not bool or type(bootstrap_actual) is not bool:
            return ModuleBValidationReasonV1.CONDITION_EXPRESSION_INVALID
        if (
            controller_actual != module_a.controller_present_v1(candidate_phase)
            or bootstrap_actual
            != module_a.bootstrap_signal_active_v1(candidate_phase)
        ):
            return ModuleBValidationReasonV1.CONDITION_TRUTH_TABLE_MISMATCH
    if not _exact_json_equal(conditions, expected["Conditions"]):
        return ModuleBValidationReasonV1.CONDITION_EXPRESSION_NONCANONICAL
    resources = model["Resources"]
    if type(resources) is not dict:
        return ModuleBValidationReasonV1.RESOURCE_NODE_SCHEMA_MISMATCH
    expected_resources = expected["Resources"]
    resource_ids = frozenset(resources)
    expected_resource_ids = frozenset(expected_resources)
    if resource_ids - expected_resource_ids:
        return ModuleBValidationReasonV1.UNEXPECTED_LOGICAL_RESOURCE
    missing = expected_resource_ids - resource_ids
    protected = frozenset(
        item.value for item in module_a.protected_persistent_logical_ids_v1()
    )
    if missing & protected:
        return ModuleBValidationReasonV1.MISSING_PROTECTED_RESOURCE
    if missing:
        return ModuleBValidationReasonV1.MISSING_LOGICAL_RESOURCE
    for logical_id in sorted(expected_resource_ids):
        node = resources[logical_id]
        expected_node = expected_resources[logical_id]
        if type(node) is not dict:
            return ModuleBValidationReasonV1.RESOURCE_NODE_SCHEMA_MISMATCH
        if node.get("Type") != expected_node["Type"]:
            return ModuleBValidationReasonV1.RESOURCE_TYPE_MISMATCH
        actual_condition = node.get("Condition")
        if actual_condition is not None:
            if type(actual_condition) is not str:
                return ModuleBValidationReasonV1.RESOURCE_NODE_SCHEMA_MISMATCH
            if actual_condition not in conditions:
                return ModuleBValidationReasonV1.UNKNOWN_RESOURCE_CONDITION
        if actual_condition != expected_node.get("Condition"):
            return ModuleBValidationReasonV1.RESOURCE_CONDITION_MISMATCH
        if logical_id in _MODULE_A_RETAINED_IDS:
            if node.get("DeletionPolicy") != "Retain":
                return ModuleBValidationReasonV1.DELETION_POLICY_MISMATCH
            if node.get("UpdateReplacePolicy") != "Retain":
                return ModuleBValidationReasonV1.UPDATE_REPLACE_POLICY_MISMATCH
        elif "DeletionPolicy" in node or "UpdateReplacePolicy" in node:
            return ModuleBValidationReasonV1.UNEXPECTED_RETENTION_ATTRIBUTE
        if "Properties" in node:
            return ModuleBValidationReasonV1.PRIVILEGED_CONTENT_PRESENT
    if _has_free_form_placeholder(resources):
        return ModuleBValidationReasonV1.FREE_FORM_PLACEHOLDER_FORBIDDEN
    controller_id = module_a.ControllerLogicalResourceIdV1.CONTROLLER_INSTANCE.value
    if not _exact_json_equal(
        resources[controller_id].get("Metadata"),
        expected_resources[controller_id]["Metadata"],
    ):
        return ModuleBValidationReasonV1.CONTROLLER_METADATA_MISMATCH
    for bootstrap_id in (
        module_a.ControllerLogicalResourceIdV1.BOOTSTRAP_WAIT_HANDLE.value,
        module_a.ControllerLogicalResourceIdV1.BOOTSTRAP_WAIT_CONDITION.value,
    ):
        for field in ("Type", "Condition", "Metadata"):
            if not _exact_json_equal(
                resources[bootstrap_id].get(field),
                expected_resources[bootstrap_id].get(field),
            ):
                return ModuleBValidationReasonV1.BOOTSTRAP_STRUCTURE_MISMATCH
    dependency_reason = _validate_dependencies(
        resources,
        expected_resources,
        phases,
        conditions,
    )
    if dependency_reason is not ModuleBValidationReasonV1.VALID:
        return dependency_reason
    active = _main_active_resource_ids(model, phase)
    if active is None:
        return ModuleBValidationReasonV1.MODULE_A_CONDITION_MISMATCH
    expected_active = tuple(
        item.value for item in module_a.logical_resource_ids_for_phase_v1(phase)
    )
    if len(active) != len(expected_active):
        return ModuleBValidationReasonV1.MODULE_A_RESOURCE_COUNT_MISMATCH
    if active != expected_active:
        return ModuleBValidationReasonV1.MODULE_A_ACTIVE_RESOURCE_SET_MISMATCH
    for logical_id in sorted(expected_resource_ids):
        if not _exact_json_equal(
            resources[logical_id].get("Metadata"),
            expected_resources[logical_id]["Metadata"],
        ):
            return ModuleBValidationReasonV1.STRUCTURAL_PLACEHOLDER_MISMATCH
        if frozenset(resources[logical_id]) != frozenset(expected_resources[logical_id]):
            return ModuleBValidationReasonV1.UNRESTRICTED_EXTENSION_FIELD
    if not _exact_json_equal(model, expected):
        return ModuleBValidationReasonV1.UNRESTRICTED_EXTENSION_FIELD
    return ModuleBValidationReasonV1.VALID


def _validate_staging_model(
    model: dict[str, object],
    phase: StagingAccessPhaseV1,
) -> ModuleBValidationReasonV1:
    if "Outputs" in model:
        return ModuleBValidationReasonV1.FORBIDDEN_OUTPUT_SECTION
    if "Transform" in model or _contains_key(model, "Fn::Transform"):
        return ModuleBValidationReasonV1.FORBIDDEN_TRANSFORM
    forbidden_resource = _forbidden_resource_reason(model.get("Resources"))
    if forbidden_resource is not ModuleBValidationReasonV1.VALID:
        return forbidden_resource
    keys = frozenset(model)
    if _STAGING_TOP_LEVEL_KEYS - keys:
        return ModuleBValidationReasonV1.MISSING_TOP_LEVEL_KEY
    if keys - _STAGING_TOP_LEVEL_KEYS:
        return ModuleBValidationReasonV1.UNKNOWN_TOP_LEVEL_KEY
    expected = build_staging_structural_model_v1(phase)
    metadata = model["Metadata"]
    if type(metadata) is not dict or type(metadata.get("Artifact")) is not dict:
        return ModuleBValidationReasonV1.METADATA_CONTRACT_MISMATCH
    artifact = metadata["Artifact"]
    if (
        artifact.get("ModuleBVersion") != _MODULE_B_VERSION
        or artifact.get("ModuleABinding") != _MODULE_A_VERSION
        or artifact.get("PhaseClarificationBinding") != _CLARIFICATION_VERSION
    ):
        return ModuleBValidationReasonV1.VERSION_BINDING_MISMATCH
    if artifact.get("DeploymentReadiness") != _DEPLOYMENT_READINESS:
        return ModuleBValidationReasonV1.NONDEPLOYABLE_MARKER_MISMATCH
    if not _exact_json_equal(metadata, expected["Metadata"]):
        return ModuleBValidationReasonV1.METADATA_CONTRACT_MISMATCH
    parameters = model["Parameters"]
    if type(parameters) is not dict:
        return ModuleBValidationReasonV1.MISSING_PARAMETER
    expected_parameter_ids = frozenset({"StagingAccessPhase"})
    parameter_ids = frozenset(parameters)
    if expected_parameter_ids - parameter_ids:
        return ModuleBValidationReasonV1.MISSING_PARAMETER
    if parameter_ids - expected_parameter_ids:
        return ModuleBValidationReasonV1.UNKNOWN_PARAMETER
    if not _exact_json_equal(parameters, expected["Parameters"]):
        return ModuleBValidationReasonV1.PARAMETER_CONTRACT_MISMATCH
    resources = model["Resources"]
    if type(resources) is not dict:
        return ModuleBValidationReasonV1.RESOURCE_NODE_SCHEMA_MISMATCH
    resource_ids = frozenset(resources)
    expected_resource_ids = frozenset(_STAGING_RESOURCE_IDS)
    if resource_ids - expected_resource_ids:
        return ModuleBValidationReasonV1.UNEXPECTED_LOGICAL_RESOURCE
    if expected_resource_ids - resource_ids:
        return ModuleBValidationReasonV1.MISSING_LOGICAL_RESOURCE
    for logical_id in sorted(expected_resource_ids):
        node = resources[logical_id]
        expected_node = expected["Resources"][logical_id]
        if type(node) is not dict:
            return ModuleBValidationReasonV1.RESOURCE_NODE_SCHEMA_MISMATCH
        if node.get("Type") != expected_node["Type"]:
            return ModuleBValidationReasonV1.RESOURCE_TYPE_MISMATCH
        if "Properties" in node:
            return ModuleBValidationReasonV1.PRIVILEGED_CONTENT_PRESENT
    policy_metadata = resources["StagingBucketPolicy"].get("Metadata")
    if type(policy_metadata) is not dict:
        return ModuleBValidationReasonV1.RESOURCE_NODE_SCHEMA_MISMATCH
    policy_state = policy_metadata.get("StructuralPolicyState")
    if policy_state != _staging_policy_state(phase).value:
        return ModuleBValidationReasonV1.STAGING_ACCESS_POLICY_STATE_MISMATCH
    dependency_reason = _validate_dependencies(
        resources,
        expected["Resources"],
        None,
        None,
    )
    if dependency_reason is not ModuleBValidationReasonV1.VALID:
        return dependency_reason
    if _has_free_form_placeholder(resources):
        return ModuleBValidationReasonV1.FREE_FORM_PLACEHOLDER_FORBIDDEN
    if not _exact_json_equal(model, expected):
        return ModuleBValidationReasonV1.UNRESTRICTED_EXTENSION_FIELD
    return ModuleBValidationReasonV1.VALID


def validate_structural_artifact_v1(
    template_kind: object,
    profile: object,
    canonical_utf8: object,
    /,
) -> ModuleBValidationResultV1:
    checked_kind = _require_template_kind(template_kind)
    if type(canonical_utf8) is not bytes:
        raise ModuleBValidationErrorV1("MODULE_B_CANONICAL_BYTES_REQUIRED")
    if checked_kind is StructuralTemplateKindV1.MAIN:
        checked_profile: object = _require_main_phase(profile)
    else:
        checked_profile = _require_staging_phase(profile)
    model, decode_reason = _decode_canonical_json(canonical_utf8)
    if decode_reason is not ModuleBValidationReasonV1.VALID:
        return _invalid_result(decode_reason)
    try:
        sensitive_reason = sensitive_value_scan_v1(model)
        if sensitive_reason is not ModuleBValidationReasonV1.VALID:
            return _invalid_result(sensitive_reason)
        if _contains_deployable_claim(model):
            return _invalid_result(
                ModuleBValidationReasonV1.DEPLOYMENT_READINESS_CLAIM_FORBIDDEN
            )
        if checked_kind is StructuralTemplateKindV1.MAIN:
            reason = _validate_main_model(model, checked_profile)
        else:
            reason = _validate_staging_model(model, checked_profile)
    except RecursionError:
        return _invalid_result(ModuleBValidationReasonV1.INVALID_INPUT)
    if reason is ModuleBValidationReasonV1.VALID:
        return _valid_result()
    return _invalid_result(reason)


def render_main_structural_template_v1(phase: object, /) -> bytes:
    checked_phase = _require_main_phase(phase)
    rendered = canonicalize_structural_model_v1(
        build_main_structural_model_v1(checked_phase)
    )
    review = validate_structural_artifact_v1(
        StructuralTemplateKindV1.MAIN,
        checked_phase,
        rendered,
    )
    if not review.is_valid:
        raise ModuleBValidationErrorV1("MODULE_B_INTERNAL_MAIN_RENDER_INVALID")
    return rendered


def render_staging_structural_template_v1(phase: object, /) -> bytes:
    checked_phase = _require_staging_phase(phase)
    rendered = canonicalize_structural_model_v1(
        build_staging_structural_model_v1(checked_phase)
    )
    review = validate_structural_artifact_v1(
        StructuralTemplateKindV1.STAGING,
        checked_phase,
        rendered,
    )
    if not review.is_valid:
        raise ModuleBValidationErrorV1("MODULE_B_INTERNAL_STAGING_RENDER_INVALID")
    return rendered


def staging_structural_delta_v1() -> StagingStructuralDeltaV1:
    upload = build_staging_structural_model_v1(StagingAccessPhaseV1.UPLOAD_ONLY)
    host_read = build_staging_structural_model_v1(
        StagingAccessPhaseV1.HOST_EXACT_OBJECT_READ
    )
    upload_resources = upload["Resources"]
    host_resources = host_read["Resources"]
    upload_ids = frozenset(upload_resources)
    host_ids = frozenset(host_resources)
    common_ids = upload_ids & host_ids
    modified = tuple(
        sorted(
            logical_id
            for logical_id in common_ids
            if upload_resources[logical_id] != host_resources[logical_id]
        )
    )
    replaced = tuple(
        sorted(
            logical_id
            for logical_id in common_ids
            if upload_resources[logical_id]["Type"]
            != host_resources[logical_id]["Type"]
        )
    )
    result = StagingStructuralDeltaV1(
        create_added_logical_ids=tuple(sorted(upload_ids)),
        update_added_logical_ids=tuple(sorted(host_ids - upload_ids)),
        update_removed_logical_ids=tuple(sorted(upload_ids - host_ids)),
        update_modified_logical_ids=modified,
        update_replaced_logical_ids=replaced,
    )
    expected = (
        ("StagingBucketPolicy", "StagingBundleBucket"),
        (),
        (),
        ("StagingBucketPolicy",),
        (),
    )
    if (
        result.create_added_logical_ids,
        result.update_added_logical_ids,
        result.update_removed_logical_ids,
        result.update_modified_logical_ids,
        result.update_replaced_logical_ids,
    ) != expected:
        raise ModuleBValidationErrorV1("MODULE_B_STAGING_DELTA_MISMATCH")
    return result


__all__ = (
    "DeferredResolutionV1",
    "DeploymentReadinessV1",
    "ModuleBValidationErrorV1",
    "ModuleBValidationReasonV1",
    "ModuleBValidationResultV1",
    "StagingAccessPhaseV1",
    "StagingPolicyStateV1",
    "StagingStructuralDeltaV1",
    "StructuralTemplateKindV1",
    "build_main_structural_model_v1",
    "build_staging_structural_model_v1",
    "canonicalize_structural_model_v1",
    "module_b_version_binding_v1",
    "render_main_structural_template_v1",
    "render_staging_structural_template_v1",
    "require_module_b_version_binding_v1",
    "sensitive_value_scan_v1",
    "staging_structural_delta_v1",
    "validate_structural_artifact_v1",
)
