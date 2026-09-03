"""Offline semantic reviewer for normalized synthetic change-set descriptions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
import re
from typing import Final, TypeAlias, final

from scripts.controller_provisioning import controller_provisioning_module_a_v1 as module_a
from scripts.controller_provisioning import controller_provisioning_module_b_v1 as module_b


_MODULE_C_VERSION: Final[str] = (
    "CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_C_CHANGESET_REVIEWER_V1"
)
_MODULE_A_VERSION: Final[str] = (
    "CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_A_V1"
)
_MODULE_B_VERSION: Final[str] = (
    "CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_B_V1"
)
_CLARIFICATION_VERSION: Final[str] = (
    "CANDIDATE_N_V4_CLOUDFORMATION_PHASE_AND_CHANGESET_CLARIFICATION_V1"
)
_VERSION_BINDING: Final[tuple[str, str, str, str]] = (
    _MODULE_C_VERSION,
    _MODULE_A_VERSION,
    _MODULE_B_VERSION,
    _CLARIFICATION_VERSION,
)
_DTO_FACTORY_TOKEN: Final[object] = object()
_MISSING: Final[object] = object()


@unique
class ProvisioningChangeSetOperationV1(Enum):
    S0 = "S0"
    M0 = "M0"
    S1 = "S1"
    M1 = "M1"
    M2 = "M2"


@unique
class ReviewedStackKindV1(Enum):
    MAIN = "MAIN"
    STAGING = "STAGING"


@unique
class NormalizedChangeSetTypeV1(Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"


@unique
class NormalizedResourceChangeActionV1(Enum):
    ADD = "ADD"
    MODIFY = "MODIFY"
    REMOVE = "REMOVE"


@unique
class NormalizedReplacementV1(Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    FALSE = "FALSE"
    TRUE = "TRUE"
    CONDITIONAL = "CONDITIONAL"
    UNKNOWN = "UNKNOWN"


@unique
class NormalizedChangeScopeV1(Enum):
    NONE = "NONE"
    PROPERTIES = "PROPERTIES"
    METADATA = "METADATA"


@unique
class NormalizedModificationRoleV1(Enum):
    NONE = "NONE"
    STAGING_EXACT_OBJECT_READ_POLICY_STATE = (
        "STAGING_EXACT_OBJECT_READ_POLICY_STATE"
    )
    CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL = (
        "CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL"
    )


@unique
class ChangeSetCreationStatusV1(Enum):
    CREATE_COMPLETE = "CREATE_COMPLETE"
    OTHER = "OTHER"


@unique
class ChangeSetExecutionStatusV1(Enum):
    AVAILABLE = "AVAILABLE"
    OTHER = "OTHER"


@unique
class StagingReviewStateV1(Enum):
    NONEXISTENT = "NONEXISTENT"
    UPLOAD_ONLY = module_b.StagingAccessPhaseV1.UPLOAD_ONLY.value
    HOST_EXACT_OBJECT_READ = (
        module_b.StagingAccessPhaseV1.HOST_EXACT_OBJECT_READ.value
    )


@unique
class ChangeSetReviewDispositionV1(Enum):
    ACCEPTED = "ACCEPTED"
    BLOCKED = "BLOCKED"


@unique
class ChangeSetReviewReasonV1(Enum):
    MATCHED_EXPECTATION = "MATCHED_EXPECTATION"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    WRONG_OPERATION_STACK_BINDING = "WRONG_OPERATION_STACK_BINDING"
    WRONG_CHANGE_SET_TYPE = "WRONG_CHANGE_SET_TYPE"
    WRONG_FROM_STATE = "WRONG_FROM_STATE"
    WRONG_TO_STATE = "WRONG_TO_STATE"
    ILLEGAL_MODULE_A_TRANSITION = "ILLEGAL_MODULE_A_TRANSITION"
    WRONG_CREATION_STATUS = "WRONG_CREATION_STATUS"
    EXECUTION_UNAVAILABLE = "EXECUTION_UNAVAILABLE"
    INCOMPLETE_CHANGE_LIST = "INCOMPLETE_CHANGE_LIST"
    DUPLICATE_LOGICAL_RESOURCE_CHANGE = "DUPLICATE_LOGICAL_RESOURCE_CHANGE"
    MISSING_EXPECTED_CHANGE = "MISSING_EXPECTED_CHANGE"
    UNEXPECTED_EXTRA_CHANGE = "UNEXPECTED_EXTRA_CHANGE"
    WRONG_LOGICAL_RESOURCE_TYPE = "WRONG_LOGICAL_RESOURCE_TYPE"
    WRONG_ACTION = "WRONG_ACTION"
    WRONG_REPLACEMENT = "WRONG_REPLACEMENT"
    REPLACEMENT_TRUE = "REPLACEMENT_TRUE"
    REPLACEMENT_CONDITIONAL = "REPLACEMENT_CONDITIONAL"
    REPLACEMENT_UNKNOWN = "REPLACEMENT_UNKNOWN"
    WRONG_SCOPE = "WRONG_SCOPE"
    WRONG_MODIFICATION_ROLE = "WRONG_MODIFICATION_ROLE"
    PROTECTED_PERSISTENT_RESOURCE_TOUCHED = (
        "PROTECTED_PERSISTENT_RESOURCE_TOUCHED"
    )
    RETAINED_EVIDENCE_RESOURCE_TOUCHED = "RETAINED_EVIDENCE_RESOURCE_TOUCHED"
    UNEXPECTED_FOUNDATION_MODIFICATION = "UNEXPECTED_FOUNDATION_MODIFICATION"
    UNEXPECTED_STAGING_RESOURCE_MUTATION = "UNEXPECTED_STAGING_RESOURCE_MUTATION"
    UNEXPECTED_M2_RESOURCE_MODIFICATION = "UNEXPECTED_M2_RESOURCE_MODIFICATION"
    SENSITIVE_PRIVATE_FIELD_ATTEMPTED = "SENSITIVE_PRIVATE_FIELD_ATTEMPTED"
    INVALID_DTO_COMBINATION = "INVALID_DTO_COMBINATION"
    DEPENDENCY_INTERFACE_MISMATCH = "DEPENDENCY_INTERFACE_MISMATCH"


@final
class ModuleCValidationErrorV1(ValueError):
    """Controlled programmer/integration error carrying one closed reason."""

    reason: ChangeSetReviewReasonV1

    def __init__(self, reason: object) -> None:
        if type(reason) is not ChangeSetReviewReasonV1:
            reason = ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
        self.reason = reason
        super().__init__(reason.value)

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
        )


_EXPECTED_MODULE_A_BINDING: Final[tuple[str, str]] = (
    _MODULE_A_VERSION,
    _CLARIFICATION_VERSION,
)
_EXPECTED_MODULE_B_BINDING: Final[tuple[str, str, str]] = (
    _MODULE_B_VERSION,
    _MODULE_A_VERSION,
    _CLARIFICATION_VERSION,
)
if module_a.module_a_version_binding_v1() != _EXPECTED_MODULE_A_BINDING:
    raise ModuleCValidationErrorV1(
        ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
    )
if module_b.module_b_version_binding_v1() != _EXPECTED_MODULE_B_BINDING:
    raise ModuleCValidationErrorV1(
        ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
    )
module_a.require_module_a_version_binding_v1(*_EXPECTED_MODULE_A_BINDING)
module_b.require_module_b_version_binding_v1(*_EXPECTED_MODULE_B_BINDING)


ReviewStateV1: TypeAlias = (
    module_a.MainStackPhaseStateV1 | StagingReviewStateV1
)


_SENSITIVE_EXTRA_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "account",
        "accountid",
        "ami",
        "amiid",
        "arn",
        "bucketname",
        "changesetid",
        "changesetname",
        "credential",
        "credentials",
        "path",
        "physicalresourceid",
        "policy",
        "policybody",
        "rawresponse",
        "region",
        "rolearn",
        "securitygroupid",
        "stackid",
        "subnetid",
        "username",
        "vpcid",
        "waithandleurl",
    }
)


def _normalized_field_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _extra_field_reason(fields: dict[str, object]) -> ChangeSetReviewReasonV1:
    if any(
        _normalized_field_name(name) in _SENSITIVE_EXTRA_FIELD_NAMES
        for name in fields
    ):
        return ChangeSetReviewReasonV1.SENSITIVE_PRIVATE_FIELD_ATTEMPTED
    sensitive_reason = module_b.sensitive_value_scan_v1(fields)
    if sensitive_reason is not module_b.ModuleBValidationReasonV1.VALID:
        return ChangeSetReviewReasonV1.SENSITIVE_PRIVATE_FIELD_ATTEMPTED
    return ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION


def _strings_are_public_safe(*values: str) -> bool:
    model = {f"Value{index}": value for index, value in enumerate(values)}
    return (
        module_b.sensitive_value_scan_v1(model)
        is module_b.ModuleBValidationReasonV1.VALID
    )


@final
@dataclass(frozen=True, slots=True, init=False)
class NormalizedResourceChangeV1:
    logical_resource_id: str
    structural_resource_type: str
    action: NormalizedResourceChangeActionV1
    replacement: NormalizedReplacementV1
    scope: NormalizedChangeScopeV1
    modification_role: NormalizedModificationRoleV1

    def __init__(
        self,
        factory_token: object = _MISSING,
        payload: object = _MISSING,
        **caller_fields: object,
    ) -> None:
        if caller_fields:
            raise ModuleCValidationErrorV1(_extra_field_reason(caller_fields))
        valid_payload = (
            factory_token is _DTO_FACTORY_TOKEN
            and type(payload) is tuple
            and len(payload) == 6
        )
        if not valid_payload:
            raise ModuleCValidationErrorV1(
                ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
            )
        (
            logical_resource_id,
            structural_resource_type,
            action,
            replacement,
            scope,
            modification_role,
        ) = payload
        valid_types = (
            type(logical_resource_id) is str
            and bool(logical_resource_id)
            and type(structural_resource_type) is str
            and bool(structural_resource_type)
            and type(action) is NormalizedResourceChangeActionV1
            and type(replacement) is NormalizedReplacementV1
            and type(scope) is NormalizedChangeScopeV1
            and type(modification_role) is NormalizedModificationRoleV1
        )
        if not valid_types:
            raise ModuleCValidationErrorV1(
                ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
            )
        if not _strings_are_public_safe(
            logical_resource_id,
            structural_resource_type,
        ):
            raise ModuleCValidationErrorV1(
                ChangeSetReviewReasonV1.SENSITIVE_PRIVATE_FIELD_ATTEMPTED
            )
        additive = action in (
            NormalizedResourceChangeActionV1.ADD,
            NormalizedResourceChangeActionV1.REMOVE,
        )
        if additive:
            compatible = (
                scope is NormalizedChangeScopeV1.NONE
                and modification_role is NormalizedModificationRoleV1.NONE
            )
        else:
            compatible = (
                replacement is not NormalizedReplacementV1.NOT_APPLICABLE
                and scope
                in (
                    NormalizedChangeScopeV1.PROPERTIES,
                    NormalizedChangeScopeV1.METADATA,
                )
                and modification_role is not NormalizedModificationRoleV1.NONE
            )
        if not compatible:
            raise ModuleCValidationErrorV1(
                ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
            )
        object.__setattr__(self, "logical_resource_id", logical_resource_id)
        object.__setattr__(self, "structural_resource_type", structural_resource_type)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "replacement", replacement)
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "modification_role", modification_role)

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
        )


def create_normalized_resource_change_v1(
    logical_resource_id: object,
    structural_resource_type: object,
    action: object,
    replacement: object,
    scope: object,
    modification_role: object,
    /,
    **caller_fields: object,
) -> NormalizedResourceChangeV1:
    if caller_fields:
        raise ModuleCValidationErrorV1(_extra_field_reason(caller_fields))
    payload = (
        logical_resource_id,
        structural_resource_type,
        action,
        replacement,
        scope,
        modification_role,
    )
    return NormalizedResourceChangeV1(_DTO_FACTORY_TOKEN, payload)


@final
@dataclass(frozen=True, slots=True, init=False)
class SyntheticChangeSetViewV1:
    module_c_schema_version: str
    module_a_binding: str
    module_b_binding: str
    clarification_binding: str
    operation: ProvisioningChangeSetOperationV1
    stack_kind: ReviewedStackKindV1
    change_set_type: NormalizedChangeSetTypeV1
    from_state: ReviewStateV1
    to_state: ReviewStateV1
    terminal_creation_status: ChangeSetCreationStatusV1
    execution_availability_status: ChangeSetExecutionStatusV1
    complete_page_set: bool
    resource_changes: tuple[NormalizedResourceChangeV1, ...]

    def __init__(
        self,
        factory_token: object = _MISSING,
        payload: object = _MISSING,
        **caller_fields: object,
    ) -> None:
        if caller_fields:
            raise ModuleCValidationErrorV1(_extra_field_reason(caller_fields))
        valid_payload = (
            factory_token is _DTO_FACTORY_TOKEN
            and type(payload) is tuple
            and len(payload) == 13
        )
        if not valid_payload:
            raise ModuleCValidationErrorV1(
                ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
            )
        (
            module_c_schema_version,
            module_a_binding,
            module_b_binding,
            clarification_binding,
            operation,
            stack_kind,
            change_set_type,
            from_state,
            to_state,
            terminal_creation_status,
            execution_availability_status,
            complete_page_set,
            resource_changes,
        ) = payload
        valid_types = (
            type(module_c_schema_version) is str
            and type(module_a_binding) is str
            and type(module_b_binding) is str
            and type(clarification_binding) is str
            and type(operation) is ProvisioningChangeSetOperationV1
            and type(stack_kind) is ReviewedStackKindV1
            and type(change_set_type) is NormalizedChangeSetTypeV1
            and type(from_state)
            in (module_a.MainStackPhaseStateV1, StagingReviewStateV1)
            and type(to_state)
            in (module_a.MainStackPhaseStateV1, StagingReviewStateV1)
            and type(terminal_creation_status) is ChangeSetCreationStatusV1
            and type(execution_availability_status) is ChangeSetExecutionStatusV1
            and type(complete_page_set) is bool
            and type(resource_changes) is tuple
            and all(
                type(change) is NormalizedResourceChangeV1
                for change in resource_changes
            )
        )
        if not valid_types:
            raise ModuleCValidationErrorV1(
                ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
            )
        if not _strings_are_public_safe(
            module_c_schema_version,
            module_a_binding,
            module_b_binding,
            clarification_binding,
        ):
            raise ModuleCValidationErrorV1(
                ChangeSetReviewReasonV1.SENSITIVE_PRIVATE_FIELD_ATTEMPTED
            )
        object.__setattr__(self, "module_c_schema_version", module_c_schema_version)
        object.__setattr__(self, "module_a_binding", module_a_binding)
        object.__setattr__(self, "module_b_binding", module_b_binding)
        object.__setattr__(self, "clarification_binding", clarification_binding)
        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "stack_kind", stack_kind)
        object.__setattr__(self, "change_set_type", change_set_type)
        object.__setattr__(self, "from_state", from_state)
        object.__setattr__(self, "to_state", to_state)
        object.__setattr__(self, "terminal_creation_status", terminal_creation_status)
        object.__setattr__(
            self,
            "execution_availability_status",
            execution_availability_status,
        )
        object.__setattr__(self, "complete_page_set", complete_page_set)
        object.__setattr__(self, "resource_changes", resource_changes)

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
        )


def create_synthetic_change_set_view_v1(
    module_c_schema_version: object,
    module_a_binding: object,
    module_b_binding: object,
    clarification_binding: object,
    operation: object,
    stack_kind: object,
    change_set_type: object,
    from_state: object,
    to_state: object,
    terminal_creation_status: object,
    execution_availability_status: object,
    complete_page_set: object,
    resource_changes: object,
    /,
    **caller_fields: object,
) -> SyntheticChangeSetViewV1:
    if caller_fields:
        raise ModuleCValidationErrorV1(_extra_field_reason(caller_fields))
    payload = (
        module_c_schema_version,
        module_a_binding,
        module_b_binding,
        clarification_binding,
        operation,
        stack_kind,
        change_set_type,
        from_state,
        to_state,
        terminal_creation_status,
        execution_availability_status,
        complete_page_set,
        resource_changes,
    )
    return SyntheticChangeSetViewV1(_DTO_FACTORY_TOKEN, payload)


@final
@dataclass(frozen=True, slots=True, init=False)
class ChangeSetSemanticReviewV1:
    reviewer_version: str
    operation: ProvisioningChangeSetOperationV1
    disposition: ChangeSetReviewDispositionV1
    primary_reason: ChangeSetReviewReasonV1
    expected_change_count: int
    observed_change_count: int
    added_logical_ids: tuple[str, ...]
    modified_logical_ids: tuple[str, ...]
    removed_logical_ids: tuple[str, ...]
    protected_resource_untouched: bool
    order_independent_comparison: bool
    exact_dependency_version_binding: bool

    def __init__(
        self,
        factory_token: object = _MISSING,
        payload: object = _MISSING,
        **caller_fields: object,
    ) -> None:
        if caller_fields:
            raise ModuleCValidationErrorV1(_extra_field_reason(caller_fields))
        valid_payload = (
            factory_token is _DTO_FACTORY_TOKEN
            and type(payload) is tuple
            and len(payload) == 12
        )
        if not valid_payload:
            raise ModuleCValidationErrorV1(
                ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
            )
        (
            reviewer_version,
            operation,
            disposition,
            primary_reason,
            expected_change_count,
            observed_change_count,
            added_logical_ids,
            modified_logical_ids,
            removed_logical_ids,
            protected_resource_untouched,
            order_independent_comparison,
            exact_dependency_version_binding,
        ) = payload
        id_groups = (
            added_logical_ids,
            modified_logical_ids,
            removed_logical_ids,
        )
        valid_types = (
            reviewer_version == _MODULE_C_VERSION
            and type(operation) is ProvisioningChangeSetOperationV1
            and type(disposition) is ChangeSetReviewDispositionV1
            and type(primary_reason) is ChangeSetReviewReasonV1
            and type(expected_change_count) is int
            and expected_change_count >= 0
            and type(observed_change_count) is int
            and observed_change_count >= 0
            and all(type(group) is tuple for group in id_groups)
            and all(type(item) is str for group in id_groups for item in group)
            and all(group == tuple(sorted(group)) for group in id_groups)
            and type(protected_resource_untouched) is bool
            and type(order_independent_comparison) is bool
            and type(exact_dependency_version_binding) is bool
        )
        accepted = disposition is ChangeSetReviewDispositionV1.ACCEPTED
        coherent = accepted is (
            primary_reason is ChangeSetReviewReasonV1.MATCHED_EXPECTATION
        )
        if accepted:
            coherent = coherent and (
                expected_change_count == observed_change_count
                and protected_resource_untouched
                and order_independent_comparison
                and exact_dependency_version_binding
            )
        if not valid_types or not coherent:
            raise ModuleCValidationErrorV1(
                ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
            )
        object.__setattr__(self, "reviewer_version", reviewer_version)
        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(self, "primary_reason", primary_reason)
        object.__setattr__(self, "expected_change_count", expected_change_count)
        object.__setattr__(self, "observed_change_count", observed_change_count)
        object.__setattr__(self, "added_logical_ids", added_logical_ids)
        object.__setattr__(self, "modified_logical_ids", modified_logical_ids)
        object.__setattr__(self, "removed_logical_ids", removed_logical_ids)
        object.__setattr__(
            self,
            "protected_resource_untouched",
            protected_resource_untouched,
        )
        object.__setattr__(
            self,
            "order_independent_comparison",
            order_independent_comparison,
        )
        object.__setattr__(
            self,
            "exact_dependency_version_binding",
            exact_dependency_version_binding,
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
        )


@dataclass(frozen=True, slots=True)
class _ExpectedReviewSpecificationV1:
    operation: ProvisioningChangeSetOperationV1
    stack_kind: ReviewedStackKindV1
    change_set_type: NormalizedChangeSetTypeV1
    from_state: ReviewStateV1
    to_state: ReviewStateV1
    resource_changes: tuple[NormalizedResourceChangeV1, ...]


def module_c_version_binding_v1() -> tuple[str, str, str, str]:
    return _VERSION_BINDING


def require_module_c_version_binding_v1(
    module_c_version: object,
    module_a_version: object,
    module_b_version: object,
    clarification_version: object,
    /,
) -> tuple[str, str, str, str]:
    if (
        type(module_c_version) is not str
        or type(module_a_version) is not str
        or type(module_b_version) is not str
        or type(clarification_version) is not str
        or (
            module_c_version,
            module_a_version,
            module_b_version,
            clarification_version,
        )
        != _VERSION_BINDING
    ):
        raise ModuleCValidationErrorV1(ChangeSetReviewReasonV1.VERSION_MISMATCH)
    module_a.require_module_a_version_binding_v1(
        module_a_version,
        clarification_version,
    )
    module_b.require_module_b_version_binding_v1(
        module_b_version,
        module_a_version,
        clarification_version,
    )
    return _VERSION_BINDING


def _make_change(
    logical_resource_id: str,
    structural_resource_type: str,
    action: NormalizedResourceChangeActionV1,
    replacement: NormalizedReplacementV1,
    scope: NormalizedChangeScopeV1,
    modification_role: NormalizedModificationRoleV1,
) -> NormalizedResourceChangeV1:
    return create_normalized_resource_change_v1(
        logical_resource_id,
        structural_resource_type,
        action,
        replacement,
        scope,
        modification_role,
    )


def _main_intent(
    operation: ProvisioningChangeSetOperationV1,
) -> tuple[
    NormalizedChangeSetTypeV1,
    module_a.MainStackPhaseStateV1,
    module_a.MainStackPhaseStateV1,
]:
    state = module_a.MainStackPhaseStateV1
    if operation is ProvisioningChangeSetOperationV1.M0:
        return (
            NormalizedChangeSetTypeV1.CREATE,
            state.NONEXISTENT,
            state.FOUNDATION_ONLY,
        )
    if operation is ProvisioningChangeSetOperationV1.M1:
        return (
            NormalizedChangeSetTypeV1.UPDATE,
            state.FOUNDATION_ONLY,
            state.CONTROLLER_COMPUTE,
        )
    if operation is ProvisioningChangeSetOperationV1.M2:
        return (
            NormalizedChangeSetTypeV1.UPDATE,
            state.CONTROLLER_COMPUTE,
            state.SEALED_STOPPED,
        )
    raise ModuleCValidationErrorV1(
        ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
    )


def _staging_intent(
    operation: ProvisioningChangeSetOperationV1,
) -> tuple[
    NormalizedChangeSetTypeV1,
    StagingReviewStateV1,
    StagingReviewStateV1,
]:
    if operation is ProvisioningChangeSetOperationV1.S0:
        return (
            NormalizedChangeSetTypeV1.CREATE,
            StagingReviewStateV1.NONEXISTENT,
            StagingReviewStateV1.UPLOAD_ONLY,
        )
    if operation is ProvisioningChangeSetOperationV1.S1:
        return (
            NormalizedChangeSetTypeV1.UPDATE,
            StagingReviewStateV1.UPLOAD_ONLY,
            StagingReviewStateV1.HOST_EXACT_OBJECT_READ,
        )
    raise ModuleCValidationErrorV1(
        ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
    )


def _main_model_for_state(
    state: module_a.MainStackPhaseStateV1,
) -> dict[str, object]:
    if state is module_a.MainStackPhaseStateV1.NONEXISTENT:
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
        )
    phase = module_a.ControllerDeploymentPhaseV1(state.value)
    return module_b.build_main_structural_model_v1(phase)


def _resource_type_from_model(model: dict[str, object], logical_id: str) -> str:
    try:
        resources = model["Resources"]
        node = resources[logical_id]
        resource_type = node["Type"]
    except (KeyError, TypeError):
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
        ) from None
    if type(resource_type) is not str:
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
        )
    return resource_type


def _metadata_references_any(value: object, targets: frozenset[str]) -> bool:
    if type(value) is dict:
        if type(value.get("Ref")) is str and value["Ref"] in targets:
            return True
        return any(_metadata_references_any(child, targets) for child in value.values())
    if type(value) is list:
        return any(_metadata_references_any(child, targets) for child in value)
    return False


def _main_expected_changes(
    previous: module_a.MainStackPhaseStateV1,
    requested: module_a.MainStackPhaseStateV1,
) -> tuple[NormalizedResourceChangeV1, ...]:
    transition = module_a.review_controller_phase_transition_v1(
        previous,
        requested,
    )
    if (
        transition.transition_classification
        is not module_a.TransitionClassificationV1.LEGAL_FORWARD
    ):
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
        )
    requested_model = _main_model_for_state(requested)
    previous_model = (
        requested_model
        if previous is module_a.MainStackPhaseStateV1.NONEXISTENT
        else _main_model_for_state(previous)
    )
    changes: list[NormalizedResourceChangeV1] = []
    for logical_id in transition.added_logical_ids:
        changes.append(
            _make_change(
                logical_id.value,
                _resource_type_from_model(requested_model, logical_id.value),
                NormalizedResourceChangeActionV1.ADD,
                NormalizedReplacementV1.NOT_APPLICABLE,
                NormalizedChangeScopeV1.NONE,
                NormalizedModificationRoleV1.NONE,
            )
        )
    for logical_id in transition.removed_logical_ids:
        changes.append(
            _make_change(
                logical_id.value,
                _resource_type_from_model(previous_model, logical_id.value),
                NormalizedResourceChangeActionV1.REMOVE,
                NormalizedReplacementV1.NOT_APPLICABLE,
                NormalizedChangeScopeV1.NONE,
                NormalizedModificationRoleV1.NONE,
            )
        )
    if (
        transition.metadata_expectation
        is not module_a.TransitionMetadataExpectationV1.NONE
    ):
        removed_names = frozenset(
            logical_id.value for logical_id in transition.removed_logical_ids
        )
        resources = previous_model.get("Resources")
        if type(resources) is not dict:
            raise ModuleCValidationErrorV1(
                ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
            )
        owners = tuple(
            sorted(
                logical_id
                for logical_id, node in resources.items()
                if type(logical_id) is str
                and type(node) is dict
                and _metadata_references_any(node.get("Metadata"), removed_names)
            )
        )
        unchanged_names = frozenset(
            logical_id.value for logical_id in transition.unchanged_logical_ids
        )
        if len(owners) != 1 or owners[0] not in unchanged_names:
            raise ModuleCValidationErrorV1(
                ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
            )
        try:
            role = NormalizedModificationRoleV1(
                transition.metadata_expectation.value
            )
        except ValueError:
            raise ModuleCValidationErrorV1(
                ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
            ) from None
        changes.append(
            _make_change(
                owners[0],
                _resource_type_from_model(previous_model, owners[0]),
                NormalizedResourceChangeActionV1.MODIFY,
                NormalizedReplacementV1.FALSE,
                NormalizedChangeScopeV1.METADATA,
                role,
            )
        )
    return tuple(sorted(changes, key=lambda item: item.logical_resource_id))


def _staging_policy_state(model: dict[str, object], logical_id: str) -> str:
    try:
        return model["Resources"][logical_id]["Metadata"]["StructuralPolicyState"]
    except (KeyError, TypeError):
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
        ) from None


def _staging_expected_changes(
    operation: ProvisioningChangeSetOperationV1,
) -> tuple[NormalizedResourceChangeV1, ...]:
    upload_model = module_b.build_staging_structural_model_v1(
        module_b.StagingAccessPhaseV1.UPLOAD_ONLY
    )
    host_model = module_b.build_staging_structural_model_v1(
        module_b.StagingAccessPhaseV1.HOST_EXACT_OBJECT_READ
    )
    delta = module_b.staging_structural_delta_v1()
    if operation is ProvisioningChangeSetOperationV1.S0:
        return tuple(
            sorted(
                (
                    _make_change(
                        logical_id,
                        _resource_type_from_model(upload_model, logical_id),
                        NormalizedResourceChangeActionV1.ADD,
                        NormalizedReplacementV1.NOT_APPLICABLE,
                        NormalizedChangeScopeV1.NONE,
                        NormalizedModificationRoleV1.NONE,
                    )
                    for logical_id in delta.create_added_logical_ids
                ),
                key=lambda item: item.logical_resource_id,
            )
        )
    valid_delta = (
        not delta.update_added_logical_ids
        and not delta.update_removed_logical_ids
        and len(delta.update_modified_logical_ids) == 1
        and not delta.update_replaced_logical_ids
    )
    if not valid_delta:
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
        )
    logical_id = delta.update_modified_logical_ids[0]
    upload_state = _staging_policy_state(upload_model, logical_id)
    host_state = _staging_policy_state(host_model, logical_id)
    expected_states = (
        module_b.StagingPolicyStateV1.NO_CONTROLLER_HOST_OBJECT_READ_GRANT.value,
        module_b.StagingPolicyStateV1.EXACTLY_ONE_FUTURE_HOST_EXACT_OBJECT_READ_GRANT.value,
    )
    if (upload_state, host_state) != expected_states:
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
        )
    return (
        _make_change(
            logical_id,
            _resource_type_from_model(host_model, logical_id),
            NormalizedResourceChangeActionV1.MODIFY,
            NormalizedReplacementV1.FALSE,
            NormalizedChangeScopeV1.PROPERTIES,
            NormalizedModificationRoleV1.STAGING_EXACT_OBJECT_READ_POLICY_STATE,
        ),
    )


def _expected_review_specification(
    operation: ProvisioningChangeSetOperationV1,
) -> _ExpectedReviewSpecificationV1:
    if operation in (
        ProvisioningChangeSetOperationV1.S0,
        ProvisioningChangeSetOperationV1.S1,
    ):
        change_set_type, previous, requested = _staging_intent(operation)
        changes = _staging_expected_changes(operation)
        stack_kind = ReviewedStackKindV1.STAGING
    else:
        change_set_type, previous, requested = _main_intent(operation)
        changes = _main_expected_changes(previous, requested)
        stack_kind = ReviewedStackKindV1.MAIN
    return _ExpectedReviewSpecificationV1(
        operation=operation,
        stack_kind=stack_kind,
        change_set_type=change_set_type,
        from_state=previous,
        to_state=requested,
        resource_changes=changes,
    )


def canonical_synthetic_change_set_fixture_v1(
    operation: object,
    /,
) -> SyntheticChangeSetViewV1:
    if type(operation) is not ProvisioningChangeSetOperationV1:
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
        )
    expected = _expected_review_specification(operation)
    return create_synthetic_change_set_view_v1(
        _MODULE_C_VERSION,
        _MODULE_A_VERSION,
        _MODULE_B_VERSION,
        _CLARIFICATION_VERSION,
        operation,
        expected.stack_kind,
        expected.change_set_type,
        expected.from_state,
        expected.to_state,
        ChangeSetCreationStatusV1.CREATE_COMPLETE,
        ChangeSetExecutionStatusV1.AVAILABLE,
        True,
        expected.resource_changes,
    )


def canonical_synthetic_change_set_fixtures_v1() -> tuple[
    SyntheticChangeSetViewV1, ...
]:
    return tuple(
        canonical_synthetic_change_set_fixture_v1(operation)
        for operation in ProvisioningChangeSetOperationV1
    )


def _binding_is_exact(view: SyntheticChangeSetViewV1) -> bool:
    return (
        view.module_c_schema_version,
        view.module_a_binding,
        view.module_b_binding,
        view.clarification_binding,
    ) == _VERSION_BINDING


def _observed_id_groups(
    changes: tuple[NormalizedResourceChangeV1, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    action = NormalizedResourceChangeActionV1
    return tuple(
        tuple(
            sorted(
                change.logical_resource_id
                for change in changes
                if change.action is selected_action
            )
        )
        for selected_action in (action.ADD, action.MODIFY, action.REMOVE)
    )


def _protected_sets() -> tuple[frozenset[str], frozenset[str]]:
    protected = frozenset(
        logical_id.value
        for logical_id in module_a.protected_persistent_logical_ids_v1()
    )
    retained = frozenset(
        record.logical_id.value
        for record in module_a.logical_resource_registry_v1()
        if record.retained_evidence_protected
    )
    if not retained.issubset(protected):
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.DEPENDENCY_INTERFACE_MISMATCH
        )
    return protected, retained


def _protected_resource_untouched(view: SyntheticChangeSetViewV1) -> bool:
    if view.operation not in (
        ProvisioningChangeSetOperationV1.M1,
        ProvisioningChangeSetOperationV1.M2,
    ):
        return True
    protected, _ = _protected_sets()
    return not any(
        change.logical_resource_id in protected
        for change in view.resource_changes
    )


def _make_review(
    view: SyntheticChangeSetViewV1,
    expected: _ExpectedReviewSpecificationV1,
    disposition: ChangeSetReviewDispositionV1,
    reason: ChangeSetReviewReasonV1,
    order_independent: bool,
) -> ChangeSetSemanticReviewV1:
    added, modified, removed = _observed_id_groups(view.resource_changes)
    payload = (
        _MODULE_C_VERSION,
        view.operation,
        disposition,
        reason,
        len(expected.resource_changes),
        len(view.resource_changes),
        added,
        modified,
        removed,
        _protected_resource_untouched(view),
        order_independent,
        _binding_is_exact(view),
    )
    return ChangeSetSemanticReviewV1(_DTO_FACTORY_TOKEN, payload)


def _blocked_review(
    view: SyntheticChangeSetViewV1,
    expected: _ExpectedReviewSpecificationV1,
    reason: ChangeSetReviewReasonV1,
    *,
    order_independent: bool = True,
) -> ChangeSetSemanticReviewV1:
    return _make_review(
        view,
        expected,
        ChangeSetReviewDispositionV1.BLOCKED,
        reason,
        order_independent,
    )


def _main_transition_is_illegal_with_both_states_wrong(
    view: SyntheticChangeSetViewV1,
    expected: _ExpectedReviewSpecificationV1,
) -> bool:
    if (
        expected.stack_kind is not ReviewedStackKindV1.MAIN
        or type(view.from_state) is not module_a.MainStackPhaseStateV1
        or type(view.to_state) is not module_a.MainStackPhaseStateV1
        or view.from_state is expected.from_state
        or view.to_state is expected.to_state
    ):
        return False
    transition = module_a.review_controller_phase_transition_v1(
        view.from_state,
        view.to_state,
    )
    return (
        transition.transition_classification
        is not module_a.TransitionClassificationV1.LEGAL_FORWARD
    )


def _special_unexpected_reason(
    view: SyntheticChangeSetViewV1,
    expected_ids: frozenset[str],
) -> ChangeSetReviewReasonV1 | None:
    protected, retained = _protected_sets()
    if view.change_set_type is NormalizedChangeSetTypeV1.UPDATE:
        touched_retained = tuple(
            change
            for change in view.resource_changes
            if change.logical_resource_id in retained
        )
        touched_protected = tuple(
            change
            for change in view.resource_changes
            if change.logical_resource_id in protected
        )
        if touched_retained:
            return ChangeSetReviewReasonV1.RETAINED_EVIDENCE_RESOURCE_TOUCHED
        if any(
            change.action is NormalizedResourceChangeActionV1.MODIFY
            for change in touched_protected
        ):
            return ChangeSetReviewReasonV1.UNEXPECTED_FOUNDATION_MODIFICATION
        if touched_protected:
            return ChangeSetReviewReasonV1.PROTECTED_PERSISTENT_RESOURCE_TOUCHED
    observed_ids = frozenset(
        change.logical_resource_id for change in view.resource_changes
    )
    extras = observed_ids - expected_ids
    if not extras:
        return None
    if view.operation is ProvisioningChangeSetOperationV1.S1:
        staging_model = module_b.build_staging_structural_model_v1(
            module_b.StagingAccessPhaseV1.UPLOAD_ONLY
        )
        staging_ids = frozenset(staging_model["Resources"])
        if extras.intersection(staging_ids):
            return ChangeSetReviewReasonV1.UNEXPECTED_STAGING_RESOURCE_MUTATION
    if view.operation is ProvisioningChangeSetOperationV1.M2:
        main_model = module_b.build_main_structural_model_v1(
            module_a.ControllerDeploymentPhaseV1.CONTROLLER_COMPUTE
        )
        main_ids = frozenset(main_model["Resources"])
        if extras.intersection(main_ids):
            return ChangeSetReviewReasonV1.UNEXPECTED_M2_RESOURCE_MODIFICATION
    return ChangeSetReviewReasonV1.UNEXPECTED_EXTRA_CHANGE


def review_synthetic_change_set_v1(
    view: object,
    /,
) -> ChangeSetSemanticReviewV1:
    if type(view) is not SyntheticChangeSetViewV1:
        raise ModuleCValidationErrorV1(
            ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
        )
    expected = _expected_review_specification(view.operation)
    if not _binding_is_exact(view):
        return _blocked_review(
            view,
            expected,
            ChangeSetReviewReasonV1.VERSION_MISMATCH,
        )
    if view.stack_kind is not expected.stack_kind:
        return _blocked_review(
            view,
            expected,
            ChangeSetReviewReasonV1.WRONG_OPERATION_STACK_BINDING,
        )
    if view.change_set_type is not expected.change_set_type:
        return _blocked_review(
            view,
            expected,
            ChangeSetReviewReasonV1.WRONG_CHANGE_SET_TYPE,
        )
    if _main_transition_is_illegal_with_both_states_wrong(view, expected):
        return _blocked_review(
            view,
            expected,
            ChangeSetReviewReasonV1.ILLEGAL_MODULE_A_TRANSITION,
        )
    if view.from_state is not expected.from_state:
        return _blocked_review(
            view,
            expected,
            ChangeSetReviewReasonV1.WRONG_FROM_STATE,
        )
    if view.to_state is not expected.to_state:
        return _blocked_review(
            view,
            expected,
            ChangeSetReviewReasonV1.WRONG_TO_STATE,
        )
    if view.terminal_creation_status is not ChangeSetCreationStatusV1.CREATE_COMPLETE:
        return _blocked_review(
            view,
            expected,
            ChangeSetReviewReasonV1.WRONG_CREATION_STATUS,
        )
    if view.execution_availability_status is not ChangeSetExecutionStatusV1.AVAILABLE:
        return _blocked_review(
            view,
            expected,
            ChangeSetReviewReasonV1.EXECUTION_UNAVAILABLE,
        )
    if not view.complete_page_set:
        return _blocked_review(
            view,
            expected,
            ChangeSetReviewReasonV1.INCOMPLETE_CHANGE_LIST,
        )
    observed_ids = tuple(
        change.logical_resource_id for change in view.resource_changes
    )
    if len(observed_ids) != len(frozenset(observed_ids)):
        return _blocked_review(
            view,
            expected,
            ChangeSetReviewReasonV1.DUPLICATE_LOGICAL_RESOURCE_CHANGE,
            order_independent=False,
        )
    expected_by_id = {
        change.logical_resource_id: change
        for change in expected.resource_changes
    }
    observed_by_id = {
        change.logical_resource_id: change
        for change in view.resource_changes
    }
    expected_ids = frozenset(expected_by_id)
    observed_id_set = frozenset(observed_by_id)
    special_reason = _special_unexpected_reason(view, expected_ids)
    if special_reason is not None:
        return _blocked_review(view, expected, special_reason)
    if expected_ids - observed_id_set:
        return _blocked_review(
            view,
            expected,
            ChangeSetReviewReasonV1.MISSING_EXPECTED_CHANGE,
        )
    if observed_id_set - expected_ids:
        return _blocked_review(
            view,
            expected,
            ChangeSetReviewReasonV1.UNEXPECTED_EXTRA_CHANGE,
        )
    for logical_id in sorted(expected_ids):
        required = expected_by_id[logical_id]
        observed = observed_by_id[logical_id]
        if observed.structural_resource_type != required.structural_resource_type:
            return _blocked_review(
                view,
                expected,
                ChangeSetReviewReasonV1.WRONG_LOGICAL_RESOURCE_TYPE,
            )
        if observed.action is not required.action:
            return _blocked_review(
                view,
                expected,
                ChangeSetReviewReasonV1.WRONG_ACTION,
            )
        if observed.replacement is NormalizedReplacementV1.TRUE:
            return _blocked_review(
                view,
                expected,
                ChangeSetReviewReasonV1.REPLACEMENT_TRUE,
            )
        if observed.replacement is NormalizedReplacementV1.CONDITIONAL:
            return _blocked_review(
                view,
                expected,
                ChangeSetReviewReasonV1.REPLACEMENT_CONDITIONAL,
            )
        if observed.replacement is NormalizedReplacementV1.UNKNOWN:
            return _blocked_review(
                view,
                expected,
                ChangeSetReviewReasonV1.REPLACEMENT_UNKNOWN,
            )
        if observed.replacement is not required.replacement:
            return _blocked_review(
                view,
                expected,
                ChangeSetReviewReasonV1.WRONG_REPLACEMENT,
            )
        if observed.scope is not required.scope:
            return _blocked_review(
                view,
                expected,
                ChangeSetReviewReasonV1.WRONG_SCOPE,
            )
        if observed.modification_role is not required.modification_role:
            return _blocked_review(
                view,
                expected,
                ChangeSetReviewReasonV1.WRONG_MODIFICATION_ROLE,
            )
    return _make_review(
        view,
        expected,
        ChangeSetReviewDispositionV1.ACCEPTED,
        ChangeSetReviewReasonV1.MATCHED_EXPECTATION,
        True,
    )


__all__ = (
    "ChangeSetCreationStatusV1",
    "ChangeSetExecutionStatusV1",
    "ChangeSetReviewDispositionV1",
    "ChangeSetReviewReasonV1",
    "ChangeSetSemanticReviewV1",
    "ModuleCValidationErrorV1",
    "NormalizedChangeScopeV1",
    "NormalizedChangeSetTypeV1",
    "NormalizedModificationRoleV1",
    "NormalizedReplacementV1",
    "NormalizedResourceChangeActionV1",
    "NormalizedResourceChangeV1",
    "ProvisioningChangeSetOperationV1",
    "ReviewedStackKindV1",
    "StagingReviewStateV1",
    "SyntheticChangeSetViewV1",
    "canonical_synthetic_change_set_fixture_v1",
    "canonical_synthetic_change_set_fixtures_v1",
    "create_normalized_resource_change_v1",
    "create_synthetic_change_set_view_v1",
    "module_c_version_binding_v1",
    "require_module_c_version_binding_v1",
    "review_synthetic_change_set_v1",
)
