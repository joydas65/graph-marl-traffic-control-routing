"""Independent offline tests for controller-provisioning Module C."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, dataclass, fields
from itertools import permutations
from pathlib import Path
from typing import Callable

import pytest

from scripts.controller_provisioning import controller_provisioning_module_a_v1 as module_a
from scripts.controller_provisioning import controller_provisioning_module_b_v1 as module_b

from scripts.controller_provisioning import controller_provisioning_module_c_v1 as subject


MODULE_C_VERSION = (
    "CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_C_CHANGESET_REVIEWER_V1"
)
MODULE_A_VERSION = "CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_A_V1"
MODULE_B_VERSION = "CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_B_V1"
CLARIFICATION_VERSION = (
    "CANDIDATE_N_V4_CLOUDFORMATION_PHASE_AND_CHANGESET_CLARIFICATION_V1"
)


@dataclass(frozen=True)
class IndependentIntent:
    operation: subject.ProvisioningChangeSetOperationV1
    stack_kind: subject.ReviewedStackKindV1
    change_set_type: subject.NormalizedChangeSetTypeV1
    from_state: object
    to_state: object


def _intent(
    operation: subject.ProvisioningChangeSetOperationV1,
) -> IndependentIntent:
    operation_type = subject.ProvisioningChangeSetOperationV1
    stack = subject.ReviewedStackKindV1
    change_set_type = subject.NormalizedChangeSetTypeV1
    main_state = module_a.MainStackPhaseStateV1
    staging_state = subject.StagingReviewStateV1
    if operation is operation_type.S0:
        return IndependentIntent(
            operation,
            stack.STAGING,
            change_set_type.CREATE,
            staging_state.NONEXISTENT,
            staging_state.UPLOAD_ONLY,
        )
    if operation is operation_type.M0:
        return IndependentIntent(
            operation,
            stack.MAIN,
            change_set_type.CREATE,
            main_state.NONEXISTENT,
            main_state.FOUNDATION_ONLY,
        )
    if operation is operation_type.S1:
        return IndependentIntent(
            operation,
            stack.STAGING,
            change_set_type.UPDATE,
            staging_state.UPLOAD_ONLY,
            staging_state.HOST_EXACT_OBJECT_READ,
        )
    if operation is operation_type.M1:
        return IndependentIntent(
            operation,
            stack.MAIN,
            change_set_type.UPDATE,
            main_state.FOUNDATION_ONLY,
            main_state.CONTROLLER_COMPUTE,
        )
    return IndependentIntent(
        operation,
        stack.MAIN,
        change_set_type.UPDATE,
        main_state.CONTROLLER_COMPUTE,
        main_state.SEALED_STOPPED,
    )


def _resource_type(model: dict[str, object], logical_id: str) -> str:
    resources = model["Resources"]
    assert isinstance(resources, dict)
    node = resources[logical_id]
    assert isinstance(node, dict)
    resource_type = node["Type"]
    assert isinstance(resource_type, str)
    return resource_type


def _contains_ref(value: object, logical_ids: frozenset[str]) -> bool:
    if isinstance(value, dict):
        if value.get("Ref") in logical_ids:
            return True
        return any(_contains_ref(child, logical_ids) for child in value.values())
    if isinstance(value, list):
        return any(_contains_ref(child, logical_ids) for child in value)
    return False


def _change(
    logical_id: str,
    resource_type: str,
    action: subject.NormalizedResourceChangeActionV1,
    replacement: subject.NormalizedReplacementV1,
    scope: subject.NormalizedChangeScopeV1,
    role: subject.NormalizedModificationRoleV1,
) -> subject.NormalizedResourceChangeV1:
    return subject.create_normalized_resource_change_v1(
        logical_id,
        resource_type,
        action,
        replacement,
        scope,
        role,
    )


def _add(logical_id: str, resource_type: str) -> subject.NormalizedResourceChangeV1:
    return _change(
        logical_id,
        resource_type,
        subject.NormalizedResourceChangeActionV1.ADD,
        subject.NormalizedReplacementV1.NOT_APPLICABLE,
        subject.NormalizedChangeScopeV1.NONE,
        subject.NormalizedModificationRoleV1.NONE,
    )


def _remove(
    logical_id: str,
    resource_type: str,
) -> subject.NormalizedResourceChangeV1:
    return _change(
        logical_id,
        resource_type,
        subject.NormalizedResourceChangeActionV1.REMOVE,
        subject.NormalizedReplacementV1.NOT_APPLICABLE,
        subject.NormalizedChangeScopeV1.NONE,
        subject.NormalizedModificationRoleV1.NONE,
    )


def _modify(
    logical_id: str,
    resource_type: str,
    *,
    replacement: subject.NormalizedReplacementV1 = subject.NormalizedReplacementV1.FALSE,
    scope: subject.NormalizedChangeScopeV1 = subject.NormalizedChangeScopeV1.PROPERTIES,
    role: subject.NormalizedModificationRoleV1 = (
        subject.NormalizedModificationRoleV1.STAGING_EXACT_OBJECT_READ_POLICY_STATE
    ),
) -> subject.NormalizedResourceChangeV1:
    return _change(logical_id, resource_type, subject.NormalizedResourceChangeActionV1.MODIFY, replacement, scope, role)


def _main_changes(
    intent: IndependentIntent,
) -> tuple[subject.NormalizedResourceChangeV1, ...]:
    assert isinstance(intent.from_state, module_a.MainStackPhaseStateV1)
    assert isinstance(intent.to_state, module_a.MainStackPhaseStateV1)
    transition = module_a.review_controller_phase_transition_v1(
        intent.from_state,
        intent.to_state,
    )
    assert (
        transition.transition_classification
        is module_a.TransitionClassificationV1.LEGAL_FORWARD
    )
    requested_phase = module_a.ControllerDeploymentPhaseV1(intent.to_state.value)
    requested_model = module_b.build_main_structural_model_v1(requested_phase)
    if intent.from_state is module_a.MainStackPhaseStateV1.NONEXISTENT:
        previous_model = requested_model
    else:
        previous_model = module_b.build_main_structural_model_v1(
            module_a.ControllerDeploymentPhaseV1(intent.from_state.value)
        )
    changes = [
        _add(logical_id.value, _resource_type(requested_model, logical_id.value))
        for logical_id in transition.added_logical_ids
    ]
    changes.extend(
        _remove(logical_id.value, _resource_type(previous_model, logical_id.value))
        for logical_id in transition.removed_logical_ids
    )
    if (
        transition.metadata_expectation
        is not module_a.TransitionMetadataExpectationV1.NONE
    ):
        removed_ids = frozenset(
            logical_id.value for logical_id in transition.removed_logical_ids
        )
        resources = previous_model["Resources"]
        assert isinstance(resources, dict)
        owners = tuple(
            sorted(
                logical_id
                for logical_id, node in resources.items()
                if isinstance(logical_id, str)
                and isinstance(node, dict)
                and _contains_ref(node.get("Metadata"), removed_ids)
            )
        )
        assert len(owners) == 1
        changes.append(
            _modify(
                owners[0],
                _resource_type(previous_model, owners[0]),
                scope=subject.NormalizedChangeScopeV1.METADATA,
                role=subject.NormalizedModificationRoleV1(
                    transition.metadata_expectation.value
                ),
            )
        )
    return tuple(sorted(changes, key=lambda item: item.logical_resource_id))


def _staging_changes(
    intent: IndependentIntent,
) -> tuple[subject.NormalizedResourceChangeV1, ...]:
    upload = module_b.build_staging_structural_model_v1(
        module_b.StagingAccessPhaseV1.UPLOAD_ONLY
    )
    host_read = module_b.build_staging_structural_model_v1(
        module_b.StagingAccessPhaseV1.HOST_EXACT_OBJECT_READ
    )
    delta = module_b.staging_structural_delta_v1()
    if intent.operation is subject.ProvisioningChangeSetOperationV1.S0:
        return tuple(
            sorted(
                (
                    _add(logical_id, _resource_type(upload, logical_id))
                    for logical_id in delta.create_added_logical_ids
                ),
                key=lambda item: item.logical_resource_id,
            )
        )
    assert not delta.update_added_logical_ids
    assert not delta.update_removed_logical_ids
    assert not delta.update_replaced_logical_ids
    assert len(delta.update_modified_logical_ids) == 1
    logical_id = delta.update_modified_logical_ids[0]
    upload_resources = upload["Resources"]
    host_resources = host_read["Resources"]
    assert isinstance(upload_resources, dict)
    assert isinstance(host_resources, dict)
    assert upload_resources[logical_id] != host_resources[logical_id]
    return (
        _modify(logical_id, _resource_type(host_read, logical_id)),
    )


def independent_fixture(
    operation: subject.ProvisioningChangeSetOperationV1,
) -> subject.SyntheticChangeSetViewV1:
    intent = _intent(operation)
    if intent.stack_kind is subject.ReviewedStackKindV1.MAIN:
        changes = _main_changes(intent)
    else:
        changes = _staging_changes(intent)
    return subject.create_synthetic_change_set_view_v1(
        MODULE_C_VERSION,
        MODULE_A_VERSION,
        MODULE_B_VERSION,
        CLARIFICATION_VERSION,
        operation,
        intent.stack_kind,
        intent.change_set_type,
        intent.from_state,
        intent.to_state,
        subject.ChangeSetCreationStatusV1.CREATE_COMPLETE,
        subject.ChangeSetExecutionStatusV1.AVAILABLE,
        True,
        changes,
    )


VIEW_FIELDS = tuple(field.name for field in fields(subject.SyntheticChangeSetViewV1))
CHANGE_FIELDS = tuple(field.name for field in fields(subject.NormalizedResourceChangeV1))
REVIEW_FIELDS = tuple(field.name for field in fields(subject.ChangeSetSemanticReviewV1))


def _replace_view(
    view: subject.SyntheticChangeSetViewV1,
    **updates: object,
) -> subject.SyntheticChangeSetViewV1:
    values = {field: getattr(view, field) for field in VIEW_FIELDS}
    values.update(updates)
    return subject.create_synthetic_change_set_view_v1(
        *(values[field] for field in VIEW_FIELDS)
    )


def _replace_change(
    change: subject.NormalizedResourceChangeV1,
    **updates: object,
) -> subject.NormalizedResourceChangeV1:
    values = {field: getattr(change, field) for field in CHANGE_FIELDS}
    values.update(updates)
    return subject.create_normalized_resource_change_v1(
        *(values[field] for field in CHANGE_FIELDS)
    )


def _change_with_action(
    change: subject.NormalizedResourceChangeV1,
    action: subject.NormalizedResourceChangeActionV1,
) -> subject.NormalizedResourceChangeV1:
    if action is subject.NormalizedResourceChangeActionV1.MODIFY:
        return _modify(
            change.logical_resource_id,
            change.structural_resource_type,
        )
    factory = (
        _add
        if action is subject.NormalizedResourceChangeActionV1.ADD
        else _remove
    )
    return factory(change.logical_resource_id, change.structural_resource_type)


def _replace_change_at(
    view: subject.SyntheticChangeSetViewV1,
    index: int,
    change: subject.NormalizedResourceChangeV1,
) -> subject.SyntheticChangeSetViewV1:
    changes = list(view.resource_changes)
    changes[index] = change
    return _replace_view(view, resource_changes=tuple(changes))


def _replace_change_by_id(
    view: subject.SyntheticChangeSetViewV1,
    logical_id: str,
    **updates: object,
) -> subject.SyntheticChangeSetViewV1:
    index = next(
        index
        for index, change in enumerate(view.resource_changes)
        if change.logical_resource_id == logical_id
    )
    return _replace_change_at(
        view,
        index,
        _replace_change(view.resource_changes[index], **updates),
    )


def _replace_change_action_by_id(
    view: subject.SyntheticChangeSetViewV1,
    logical_id: str,
    action: subject.NormalizedResourceChangeActionV1,
) -> subject.SyntheticChangeSetViewV1:
    index = next(
        index
        for index, change in enumerate(view.resource_changes)
        if change.logical_resource_id == logical_id
    )
    return _replace_change_at(
        view,
        index,
        _change_with_action(view.resource_changes[index], action),
    )


def _drop_change(
    view: subject.SyntheticChangeSetViewV1,
    logical_id: str,
) -> subject.SyntheticChangeSetViewV1:
    return _replace_view(
        view,
        resource_changes=tuple(
            change
            for change in view.resource_changes
            if change.logical_resource_id != logical_id
        ),
    )


def _append_change(
    view: subject.SyntheticChangeSetViewV1,
    change: subject.NormalizedResourceChangeV1,
) -> subject.SyntheticChangeSetViewV1:
    return _replace_view(view, resource_changes=(*view.resource_changes, change))


def _main_type(logical_id: str) -> str:
    model = module_b.build_main_structural_model_v1(
        module_a.ControllerDeploymentPhaseV1.CONTROLLER_COMPUTE
    )
    return _resource_type(model, logical_id)


def _staging_type(logical_id: str) -> str:
    model = module_b.build_staging_structural_model_v1(
        module_b.StagingAccessPhaseV1.UPLOAD_ONLY
    )
    return _resource_type(model, logical_id)


def _alternate_state(value: object) -> object:
    enum_type = type(value)
    return next(candidate for candidate in enum_type if candidate is not value)


def _opposite_stack(
    stack: subject.ReviewedStackKindV1,
) -> subject.ReviewedStackKindV1:
    if stack is subject.ReviewedStackKindV1.MAIN:
        return subject.ReviewedStackKindV1.STAGING
    return subject.ReviewedStackKindV1.MAIN


def _opposite_change_set_type(
    value: subject.NormalizedChangeSetTypeV1,
) -> subject.NormalizedChangeSetTypeV1:
    if value is subject.NormalizedChangeSetTypeV1.CREATE:
        return subject.NormalizedChangeSetTypeV1.UPDATE
    return subject.NormalizedChangeSetTypeV1.CREATE


@pytest.mark.parametrize(
    "operation",
    tuple(subject.ProvisioningChangeSetOperationV1),
    ids=lambda operation: operation.value,
)
def test_independently_derived_positive_fixture_is_accepted(operation: object) -> None:
    view = independent_fixture(operation)
    result = subject.review_synthetic_change_set_v1(view)
    assert result.disposition is subject.ChangeSetReviewDispositionV1.ACCEPTED
    assert result.primary_reason is subject.ChangeSetReviewReasonV1.MATCHED_EXPECTATION
    assert result.expected_change_count == result.observed_change_count
    assert result.protected_resource_untouched
    assert result.order_independent_comparison
    assert result.exact_dependency_version_binding
    assert result.added_logical_ids == tuple(sorted(result.added_logical_ids))
    assert result.modified_logical_ids == tuple(sorted(result.modified_logical_ids))
    assert result.removed_logical_ids == tuple(sorted(result.removed_logical_ids))


@pytest.mark.parametrize(
    "operation",
    tuple(subject.ProvisioningChangeSetOperationV1),
    ids=lambda operation: operation.value,
)
def test_canonical_fixture_matches_independent_public_dependency_derivation(
    operation: object,
) -> None:
    assert subject.canonical_synthetic_change_set_fixture_v1(operation) == independent_fixture(
        operation
    )


def test_all_canonical_fixture_collection_matches_independent_derivation() -> None:
    assert subject.canonical_synthetic_change_set_fixtures_v1() == tuple(
        independent_fixture(operation)
        for operation in subject.ProvisioningChangeSetOperationV1
    )


def test_positive_operation_shapes_are_exact() -> None:
    operation = subject.ProvisioningChangeSetOperationV1
    fixtures = {candidate: independent_fixture(candidate) for candidate in operation}
    expected_counts = {
        operation.S0: (2, 0, 0),
        operation.M0: (8, 0, 0),
        operation.S1: (0, 1, 0),
        operation.M1: (4, 0, 0),
        operation.M2: (0, 1, 2),
    }
    action = subject.NormalizedResourceChangeActionV1
    for candidate, view in fixtures.items():
        actual = tuple(
            sum(change.action is selected for change in view.resource_changes)
            for selected in (action.ADD, action.MODIFY, action.REMOVE)
        )
        assert actual == expected_counts[candidate]
    s1_change = fixtures[operation.S1].resource_changes[0]
    assert s1_change.logical_resource_id == "StagingBucketPolicy"
    assert s1_change.replacement is subject.NormalizedReplacementV1.FALSE
    assert s1_change.scope is subject.NormalizedChangeScopeV1.PROPERTIES
    assert (
        s1_change.modification_role
        is subject.NormalizedModificationRoleV1.STAGING_EXACT_OBJECT_READ_POLICY_STATE
    )
    m2_changes = {change.logical_resource_id: change for change in fixtures[operation.M2].resource_changes}
    controller = m2_changes[module_a.ControllerLogicalResourceIdV1.CONTROLLER_INSTANCE.value]
    assert controller.action is action.MODIFY
    assert controller.replacement is subject.NormalizedReplacementV1.FALSE
    assert controller.scope is subject.NormalizedChangeScopeV1.METADATA
    assert controller.modification_role is (
        subject.NormalizedModificationRoleV1.CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL
    )


def test_public_dependency_interfaces_supply_all_expected_semantics() -> None:
    assert module_a.module_a_version_binding_v1() == (
        MODULE_A_VERSION,
        CLARIFICATION_VERSION,
    )
    assert module_b.module_b_version_binding_v1() == (
        MODULE_B_VERSION,
        MODULE_A_VERSION,
        CLARIFICATION_VERSION,
    )
    assert subject.module_c_version_binding_v1() == (
        MODULE_C_VERSION,
        MODULE_A_VERSION,
        MODULE_B_VERSION,
        CLARIFICATION_VERSION,
    )
    assert module_a.persistent_resource_invariants_hold_v1()
    for operation in subject.ProvisioningChangeSetOperationV1:
        assert independent_fixture(operation).operation is operation


def test_normalized_enums_are_exact_and_closed() -> None:
    expected = {
        subject.ProvisioningChangeSetOperationV1: ("S0", "M0", "S1", "M1", "M2"),
        subject.ReviewedStackKindV1: ("MAIN", "STAGING"),
        subject.NormalizedChangeSetTypeV1: ("CREATE", "UPDATE"),
        subject.NormalizedResourceChangeActionV1: ("ADD", "MODIFY", "REMOVE"),
        subject.NormalizedReplacementV1: (
            "NOT_APPLICABLE",
            "FALSE",
            "TRUE",
            "CONDITIONAL",
            "UNKNOWN",
        ),
        subject.NormalizedChangeScopeV1: ("NONE", "PROPERTIES", "METADATA"),
        subject.NormalizedModificationRoleV1: (
            "NONE",
            "STAGING_EXACT_OBJECT_READ_POLICY_STATE",
            "CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL",
        ),
        subject.ChangeSetCreationStatusV1: ("CREATE_COMPLETE", "OTHER"),
        subject.ChangeSetExecutionStatusV1: ("AVAILABLE", "OTHER"),
        subject.StagingReviewStateV1: (
            "NONEXISTENT",
            "UPLOAD_ONLY",
            "HOST_EXACT_OBJECT_READ",
        ),
        subject.ChangeSetReviewDispositionV1: ("ACCEPTED", "BLOCKED"),
    }
    for enum_type, values in expected.items():
        assert tuple(member.value for member in enum_type) == values
    assert "S2" not in subject.ProvisioningChangeSetOperationV1.__members__
    assert "D0" not in subject.ProvisioningChangeSetOperationV1.__members__
    assert "IMPORT" not in subject.NormalizedChangeSetTypeV1.__members__
    assert "DELETE" not in subject.NormalizedChangeSetTypeV1.__members__


def test_staging_review_states_bind_to_module_b_values() -> None:
    assert subject.StagingReviewStateV1.UPLOAD_ONLY.value == (
        module_b.StagingAccessPhaseV1.UPLOAD_ONLY.value
    )
    assert subject.StagingReviewStateV1.HOST_EXACT_OBJECT_READ.value == (
        module_b.StagingAccessPhaseV1.HOST_EXACT_OBJECT_READ.value
    )


def test_dto_fields_are_exact() -> None:
    assert CHANGE_FIELDS == (
        "logical_resource_id",
        "structural_resource_type",
        "action",
        "replacement",
        "scope",
        "modification_role",
    )
    assert VIEW_FIELDS == (
        "module_c_schema_version",
        "module_a_binding",
        "module_b_binding",
        "clarification_binding",
        "operation",
        "stack_kind",
        "change_set_type",
        "from_state",
        "to_state",
        "terminal_creation_status",
        "execution_availability_status",
        "complete_page_set",
        "resource_changes",
    )
    assert REVIEW_FIELDS == (
        "reviewer_version",
        "operation",
        "disposition",
        "primary_reason",
        "expected_change_count",
        "observed_change_count",
        "added_logical_ids",
        "modified_logical_ids",
        "removed_logical_ids",
        "protected_resource_untouched",
        "order_independent_comparison",
        "exact_dependency_version_binding",
    )


def test_dtos_are_deeply_immutable_and_direct_construction_is_closed() -> None:
    view = independent_fixture(subject.ProvisioningChangeSetOperationV1.M2)
    result = subject.review_synthetic_change_set_v1(view)
    assert isinstance(view.resource_changes, tuple)
    assert not hasattr(view, "__dict__")
    assert not hasattr(view.resource_changes[0], "__dict__")
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        view.complete_page_set = False
    with pytest.raises(FrozenInstanceError):
        view.resource_changes[0].logical_resource_id = "Changed"
    with pytest.raises(FrozenInstanceError):
        result.disposition = subject.ChangeSetReviewDispositionV1.BLOCKED
    for dto_type in (
        subject.NormalizedResourceChangeV1,
        subject.SyntheticChangeSetViewV1,
        subject.ChangeSetSemanticReviewV1,
    ):
        with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
            dto_type()
        assert caught.value.reason is subject.ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION


def test_result_and_validation_exception_types_are_final() -> None:
    with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
        class InvalidChange(subject.NormalizedResourceChangeV1):
            pass
    assert caught.value.reason is subject.ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
    with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
        class InvalidView(subject.SyntheticChangeSetViewV1):
            pass
    assert caught.value.reason is subject.ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
    with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
        class InvalidReview(subject.ChangeSetSemanticReviewV1):
            pass
    assert caught.value.reason is subject.ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION
    with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
        class InvalidError(subject.ModuleCValidationErrorV1):
            pass
    assert caught.value.reason is subject.ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION


def test_completeness_requires_an_exact_boolean() -> None:
    view = independent_fixture(subject.ProvisioningChangeSetOperationV1.S0)
    for invalid in (None, "true", 1):
        with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
            _replace_view(view, complete_page_set=invalid)
        assert caught.value.reason is subject.ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION


@pytest.mark.parametrize("raw_type", ("IMPORT", "DELETE"))
def test_raw_import_and_delete_change_set_types_are_rejected(raw_type: str) -> None:
    view = independent_fixture(subject.ProvisioningChangeSetOperationV1.S0)
    with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
        _replace_view(view, change_set_type=raw_type)
    assert caught.value.reason is subject.ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION


@pytest.mark.parametrize("raw_action", ("Add", "Modify", "Remove", "ADD"))
def test_raw_provider_action_spellings_are_rejected(raw_action: str) -> None:
    change = independent_fixture(subject.ProvisioningChangeSetOperationV1.S0).resource_changes[0]
    with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
        _replace_change(change, action=raw_action)
    assert caught.value.reason is subject.ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION


def test_non_dto_review_input_is_rejected_with_closed_reason() -> None:
    with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
        subject.review_synthetic_change_set_v1({})
    assert caught.value.reason is subject.ChangeSetReviewReasonV1.INVALID_DTO_COMBINATION


def _first_change(view: subject.SyntheticChangeSetViewV1) -> subject.NormalizedResourceChangeV1:
    return view.resource_changes[0]


def _first_modify(view: subject.SyntheticChangeSetViewV1) -> subject.NormalizedResourceChangeV1:
    return next(
        change
        for change in view.resource_changes
        if change.action is subject.NormalizedResourceChangeActionV1.MODIFY
    )


def _duplicate_first(view: subject.SyntheticChangeSetViewV1) -> subject.SyntheticChangeSetViewV1:
    return _append_change(view, _first_change(view))


def _append_synthetic_extra(
    view: subject.SyntheticChangeSetViewV1,
) -> subject.SyntheticChangeSetViewV1:
    return _append_change(view, _add("UnexpectedSyntheticResource", "AWS::Synthetic::Resource"))


def _append_main_modify(
    view: subject.SyntheticChangeSetViewV1,
    logical_id: str,
) -> subject.SyntheticChangeSetViewV1:
    return _append_change(view, _modify(logical_id, _main_type(logical_id)))


def _append_main_remove(
    view: subject.SyntheticChangeSetViewV1,
    logical_id: str,
) -> subject.SyntheticChangeSetViewV1:
    return _append_change(view, _remove(logical_id, _main_type(logical_id)))


def _view_with_extra_field(
    view: subject.SyntheticChangeSetViewV1,
    key: str,
    value: object,
) -> subject.SyntheticChangeSetViewV1:
    values = tuple(getattr(view, field) for field in VIEW_FIELDS)
    return subject.create_synthetic_change_set_view_v1(*values, **{key: value})


def _change_with_extra_field(
    change: subject.NormalizedResourceChangeV1,
    key: str,
    value: object,
) -> subject.NormalizedResourceChangeV1:
    values = tuple(getattr(change, field) for field in CHANGE_FIELDS)
    return subject.create_normalized_resource_change_v1(*values, **{key: value})


@dataclass(frozen=True)
class NamedNegative:
    name: str
    operation: subject.ProvisioningChangeSetOperationV1
    mutate: Callable[[subject.SyntheticChangeSetViewV1], object]
    reason: subject.ChangeSetReviewReasonV1
    validation_error: bool = False


operation = subject.ProvisioningChangeSetOperationV1
reason = subject.ChangeSetReviewReasonV1
action = subject.NormalizedResourceChangeActionV1
replacement = subject.NormalizedReplacementV1
scope = subject.NormalizedChangeScopeV1
role = subject.NormalizedModificationRoleV1
logical_id = module_a.ControllerLogicalResourceIdV1


NAMED_NEGATIVES = (
    NamedNegative(
        "wrong-module-a-version",
        operation.S0,
        lambda view: _replace_view(view, module_a_binding="WRONG_MODULE_A_VERSION"),
        reason.VERSION_MISMATCH,
    ),
    NamedNegative(
        "wrong-module-b-version",
        operation.S0,
        lambda view: _replace_view(view, module_b_binding="WRONG_MODULE_B_VERSION"),
        reason.VERSION_MISMATCH,
    ),
    NamedNegative(
        "wrong-module-c-version",
        operation.S0,
        lambda view: _replace_view(view, module_c_schema_version="WRONG_MODULE_C_VERSION"),
        reason.VERSION_MISMATCH,
    ),
    NamedNegative(
        "wrong-clarification-version",
        operation.S0,
        lambda view: _replace_view(view, clarification_binding="WRONG_CLARIFICATION_VERSION"),
        reason.VERSION_MISMATCH,
    ),
    NamedNegative(
        "wrong-operation-stack",
        operation.S0,
        lambda view: _replace_view(view, stack_kind=_opposite_stack(view.stack_kind)),
        reason.WRONG_OPERATION_STACK_BINDING,
    ),
    NamedNegative(
        "wrong-change-set-type",
        operation.S0,
        lambda view: _replace_view(
            view,
            change_set_type=_opposite_change_set_type(view.change_set_type),
        ),
        reason.WRONG_CHANGE_SET_TYPE,
    ),
    NamedNegative(
        "wrong-from-state",
        operation.S0,
        lambda view: _replace_view(view, from_state=_alternate_state(view.from_state)),
        reason.WRONG_FROM_STATE,
    ),
    NamedNegative(
        "wrong-to-state",
        operation.S0,
        lambda view: _replace_view(view, to_state=_alternate_state(view.to_state)),
        reason.WRONG_TO_STATE,
    ),
    NamedNegative(
        "illegal-module-a-transition",
        operation.M1,
        lambda view: _replace_view(
            view,
            from_state=module_a.MainStackPhaseStateV1.SEALED_STOPPED,
            to_state=module_a.MainStackPhaseStateV1.FOUNDATION_ONLY,
        ),
        reason.ILLEGAL_MODULE_A_TRANSITION,
    ),
    NamedNegative(
        "wrong-creation-status",
        operation.S0,
        lambda view: _replace_view(
            view,
            terminal_creation_status=subject.ChangeSetCreationStatusV1.OTHER,
        ),
        reason.WRONG_CREATION_STATUS,
    ),
    NamedNegative(
        "incomplete-page-set",
        operation.S0,
        lambda view: _replace_view(view, complete_page_set=False),
        reason.INCOMPLETE_CHANGE_LIST,
    ),
    NamedNegative(
        "non-available-execution-status",
        operation.S0,
        lambda view: _replace_view(
            view,
            execution_availability_status=subject.ChangeSetExecutionStatusV1.OTHER,
        ),
        reason.EXECUTION_UNAVAILABLE,
    ),
    NamedNegative("duplicate-change", operation.S0, _duplicate_first, reason.DUPLICATE_LOGICAL_RESOURCE_CHANGE),
    NamedNegative("unexpected-extra-resource", operation.S0, _append_synthetic_extra, reason.UNEXPECTED_EXTRA_CHANGE),
    NamedNegative(
        "missing-resource",
        operation.S0,
        lambda view: _drop_change(view, _first_change(view).logical_resource_id),
        reason.MISSING_EXPECTED_CHANGE,
    ),
    NamedNegative(
        "wrong-resource-type",
        operation.S0,
        lambda view: _replace_change_at(
            view,
            0,
            _replace_change(
                _first_change(view),
                structural_resource_type="AWS::Synthetic::Different",
            ),
        ),
        reason.WRONG_LOGICAL_RESOURCE_TYPE,
    ),
    NamedNegative(
        "wrong-action",
        operation.S0,
        lambda view: _replace_change_at(
            view,
            0,
            _change_with_action(_first_change(view), action.REMOVE),
        ),
        reason.WRONG_ACTION,
    ),
    NamedNegative(
        "modify-replacement-true",
        operation.S1,
        lambda view: _replace_change_by_id(
            view,
            "StagingBucketPolicy",
            replacement=replacement.TRUE,
        ),
        reason.REPLACEMENT_TRUE,
    ),
    NamedNegative(
        "modify-replacement-conditional",
        operation.S1,
        lambda view: _replace_change_by_id(
            view,
            "StagingBucketPolicy",
            replacement=replacement.CONDITIONAL,
        ),
        reason.REPLACEMENT_CONDITIONAL,
    ),
    NamedNegative(
        "modify-replacement-unknown",
        operation.S1,
        lambda view: _replace_change_by_id(
            view,
            "StagingBucketPolicy",
            replacement=replacement.UNKNOWN,
        ),
        reason.REPLACEMENT_UNKNOWN,
    ),
    NamedNegative(
        "add-marked-replacement-false",
        operation.S0,
        lambda view: _replace_change_at(
            view,
            0,
            _replace_change(_first_change(view), replacement=replacement.FALSE),
        ),
        reason.WRONG_REPLACEMENT,
    ),
    NamedNegative(
        "remove-marked-replacement-false",
        operation.M2,
        lambda view: _replace_change_by_id(
            view,
            logical_id.BOOTSTRAP_WAIT_HANDLE.value,
            replacement=replacement.FALSE,
        ),
        reason.WRONG_REPLACEMENT,
    ),
    NamedNegative(
        "s1-bucket-added-instead-of-modified",
        operation.S1,
        lambda view: _replace_change_action_by_id(
            view,
            "StagingBucketPolicy",
            action.ADD,
        ),
        reason.WRONG_ACTION,
    ),
    NamedNegative(
        "s1-bucket-policy-removed",
        operation.S1,
        lambda view: _replace_change_action_by_id(
            view,
            "StagingBucketPolicy",
            action.REMOVE,
        ),
        reason.WRONG_ACTION,
    ),
    NamedNegative(
        "s1-bucket-replacement",
        operation.S1,
        lambda view: _replace_change_by_id(
            view,
            "StagingBucketPolicy",
            replacement=replacement.TRUE,
        ),
        reason.REPLACEMENT_TRUE,
    ),
    NamedNegative(
        "s1-wrong-scope",
        operation.S1,
        lambda view: _replace_change_by_id(
            view,
            "StagingBucketPolicy",
            scope=scope.METADATA,
        ),
        reason.WRONG_SCOPE,
    ),
    NamedNegative(
        "s1-wrong-modification-role",
        operation.S1,
        lambda view: _replace_change_by_id(
            view,
            "StagingBucketPolicy",
            modification_role=role.CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL,
        ),
        reason.WRONG_MODIFICATION_ROLE,
    ),
    NamedNegative(
        "s1-third-staging-change",
        operation.S1,
        lambda view: _append_change(
            view,
            _add("StagingBundleBucket", _staging_type("StagingBundleBucket")),
        ),
        reason.UNEXPECTED_STAGING_RESOURCE_MUTATION,
    ),
    NamedNegative(
        "m1-missing-controller-instance",
        operation.M1,
        lambda view: _drop_change(view, logical_id.CONTROLLER_INSTANCE.value),
        reason.MISSING_EXPECTED_CHANGE,
    ),
    NamedNegative(
        "m1-missing-attachment",
        operation.M1,
        lambda view: _drop_change(view, logical_id.EVIDENCE_VOLUME_ATTACHMENT.value),
        reason.MISSING_EXPECTED_CHANGE,
    ),
    NamedNegative(
        "m1-missing-wait-handle",
        operation.M1,
        lambda view: _drop_change(view, logical_id.BOOTSTRAP_WAIT_HANDLE.value),
        reason.MISSING_EXPECTED_CHANGE,
    ),
    NamedNegative(
        "m1-missing-wait-condition",
        operation.M1,
        lambda view: _drop_change(view, logical_id.BOOTSTRAP_WAIT_CONDITION.value),
        reason.MISSING_EXPECTED_CHANGE,
    ),
    NamedNegative(
        "m1-modify-foundation-resource",
        operation.M1,
        lambda view: _append_main_modify(view, logical_id.CONTROLLER_BUDGET.value),
        reason.UNEXPECTED_FOUNDATION_MODIFICATION,
    ),
    NamedNegative(
        "m1-remove-foundation-resource",
        operation.M1,
        lambda view: _append_main_remove(view, logical_id.CONTROLLER_SECURITY_GROUP.value),
        reason.PROTECTED_PERSISTENT_RESOURCE_TOUCHED,
    ),
    NamedNegative(
        "m1-modify-evidence-key",
        operation.M1,
        lambda view: _append_main_modify(view, logical_id.EVIDENCE_KEY.value),
        reason.RETAINED_EVIDENCE_RESOURCE_TOUCHED,
    ),
    NamedNegative(
        "m1-modify-evidence-volume",
        operation.M1,
        lambda view: _append_main_modify(view, logical_id.EVIDENCE_VOLUME.value),
        reason.RETAINED_EVIDENCE_RESOURCE_TOUCHED,
    ),
    NamedNegative("m1-extra-resource-add", operation.M1, _append_synthetic_extra, reason.UNEXPECTED_EXTRA_CHANGE),
    NamedNegative(
        "m1-instance-replacement",
        operation.M1,
        lambda view: _replace_change_by_id(
            view,
            logical_id.CONTROLLER_INSTANCE.value,
            replacement=replacement.TRUE,
        ),
        reason.REPLACEMENT_TRUE,
    ),
    NamedNegative(
        "m1-iam-role-modification",
        operation.M1,
        lambda view: _append_main_modify(view, logical_id.CONTROLLER_HOST_ROLE.value),
        reason.UNEXPECTED_FOUNDATION_MODIFICATION,
    ),
    NamedNegative(
        "m1-security-group-modification",
        operation.M1,
        lambda view: _append_main_modify(view, logical_id.CONTROLLER_SECURITY_GROUP.value),
        reason.UNEXPECTED_FOUNDATION_MODIFICATION,
    ),
    NamedNegative(
        "m1-ssm-document-modification",
        operation.M1,
        lambda view: _append_main_modify(view, logical_id.CONTROLLER_COMMAND_DOCUMENT.value),
        reason.UNEXPECTED_FOUNDATION_MODIFICATION,
    ),
    NamedNegative(
        "m1-budget-modification",
        operation.M1,
        lambda view: _append_main_modify(view, logical_id.CONTROLLER_BUDGET.value),
        reason.UNEXPECTED_FOUNDATION_MODIFICATION,
    ),
    NamedNegative(
        "m1-remove-action-on-expected-resource",
        operation.M1,
        lambda view: _replace_change_action_by_id(
            view,
            logical_id.CONTROLLER_INSTANCE.value,
            action.REMOVE,
        ),
        reason.WRONG_ACTION,
    ),
    NamedNegative(
        "m1-modify-action-on-expected-resource",
        operation.M1,
        lambda view: _replace_change_action_by_id(
            view,
            logical_id.CONTROLLER_INSTANCE.value,
            action.MODIFY,
        ),
        reason.WRONG_ACTION,
    ),
    NamedNegative(
        "m2-missing-wait-handle-removal",
        operation.M2,
        lambda view: _drop_change(view, logical_id.BOOTSTRAP_WAIT_HANDLE.value),
        reason.MISSING_EXPECTED_CHANGE,
    ),
    NamedNegative(
        "m2-missing-wait-condition-removal",
        operation.M2,
        lambda view: _drop_change(view, logical_id.BOOTSTRAP_WAIT_CONDITION.value),
        reason.MISSING_EXPECTED_CHANGE,
    ),
    NamedNegative(
        "m2-controller-replacement",
        operation.M2,
        lambda view: _replace_change_by_id(
            view,
            logical_id.CONTROLLER_INSTANCE.value,
            replacement=replacement.TRUE,
        ),
        reason.REPLACEMENT_TRUE,
    ),
    NamedNegative(
        "m2-controller-properties-scope",
        operation.M2,
        lambda view: _replace_change_by_id(
            view,
            logical_id.CONTROLLER_INSTANCE.value,
            scope=scope.PROPERTIES,
        ),
        reason.WRONG_SCOPE,
    ),
    NamedNegative(
        "m2-wrong-metadata-role",
        operation.M2,
        lambda view: _replace_change_by_id(
            view,
            logical_id.CONTROLLER_INSTANCE.value,
            modification_role=role.STAGING_EXACT_OBJECT_READ_POLICY_STATE,
        ),
        reason.WRONG_MODIFICATION_ROLE,
    ),
    NamedNegative(
        "m2-attachment-removal",
        operation.M2,
        lambda view: _append_main_remove(view, logical_id.EVIDENCE_VOLUME_ATTACHMENT.value),
        reason.UNEXPECTED_M2_RESOURCE_MODIFICATION,
    ),
    NamedNegative(
        "m2-evidence-modification",
        operation.M2,
        lambda view: _append_main_modify(view, logical_id.EVIDENCE_VOLUME.value),
        reason.RETAINED_EVIDENCE_RESOURCE_TOUCHED,
    ),
    NamedNegative("m2-extra-add", operation.M2, _append_synthetic_extra, reason.UNEXPECTED_EXTRA_CHANGE),
    NamedNegative(
        "m2-persistent-resource-change",
        operation.M2,
        lambda view: _append_main_remove(view, logical_id.CONTROLLER_HOST_ROLE.value),
        reason.PROTECTED_PERSISTENT_RESOURCE_TOUCHED,
    ),
    NamedNegative(
        "m2-user-data-modification-role",
        operation.M2,
        lambda view: _replace_change_by_id(
            view,
            logical_id.CONTROLLER_INSTANCE.value,
            modification_role=role.STAGING_EXACT_OBJECT_READ_POLICY_STATE,
        ),
        reason.WRONG_MODIFICATION_ROLE,
    ),
    NamedNegative(
        "m2-compute-resource-removal",
        operation.M2,
        lambda view: _replace_change_action_by_id(
            view,
            logical_id.CONTROLLER_INSTANCE.value,
            action.REMOVE,
        ),
        reason.WRONG_ACTION,
    ),
    NamedNegative(
        "m2-iam-role-modification",
        operation.M2,
        lambda view: _append_main_modify(view, logical_id.CONTROLLER_HOST_ROLE.value),
        reason.UNEXPECTED_FOUNDATION_MODIFICATION,
    ),
    NamedNegative(
        "m2-network-resource-modification",
        operation.M2,
        lambda view: _append_main_modify(view, logical_id.CONTROLLER_SECURITY_GROUP.value),
        reason.UNEXPECTED_FOUNDATION_MODIFICATION,
    ),
    NamedNegative(
        "m2-kms-resource-modification",
        operation.M2,
        lambda view: _append_main_modify(view, logical_id.EVIDENCE_KEY.value),
        reason.RETAINED_EVIDENCE_RESOURCE_TOUCHED,
    ),
    NamedNegative(
        "m2-budget-modification",
        operation.M2,
        lambda view: _append_main_modify(view, logical_id.CONTROLLER_BUDGET.value),
        reason.UNEXPECTED_FOUNDATION_MODIFICATION,
    ),
    NamedNegative("m2-resource-addition", operation.M2, _append_synthetic_extra, reason.UNEXPECTED_EXTRA_CHANGE),
    NamedNegative(
        "m2-bootstrap-retained-as-add",
        operation.M2,
        lambda view: _replace_change_action_by_id(
            view,
            logical_id.BOOTSTRAP_WAIT_HANDLE.value,
            action.ADD,
        ),
        reason.WRONG_ACTION,
    ),
    NamedNegative(
        "sensitive-view-extra-field",
        operation.S0,
        lambda view: _view_with_extra_field(
            view,
            "".join(("stack", "_id")),
            "".join(("synthetic", "-", "identifier")),
        ),
        reason.SENSITIVE_PRIVATE_FIELD_ATTEMPTED,
        True,
    ),
    NamedNegative(
        "sensitive-change-extra-field",
        operation.S0,
        lambda view: _change_with_extra_field(
            _first_change(view),
            "".join(("physical", "_resource", "_id")),
            "".join(("synthetic", "-", "physical", "-", "identifier")),
        ),
        reason.SENSITIVE_PRIVATE_FIELD_ATTEMPTED,
        True,
    ),
    NamedNegative(
        "unknown-safe-extra-field",
        operation.S0,
        lambda view: _view_with_extra_field(view, "unknown_safe_field", "benign"),
        reason.INVALID_DTO_COMBINATION,
        True,
    ),
)

NEGATIVE_FIXTURE_MANIFEST = tuple(
    (case.name, case.operation.value, case.reason.value, case.validation_error)
    for case in NAMED_NEGATIVES
)

ORDER_INDEPENDENCE_CONTROL_MANIFEST = (
    ("reordered-valid-changes", operation.M1.value, "ACCEPTED", "MATCHED_EXPECTATION"),
)


def named_negative_fixture_manifest_v1() -> tuple[tuple[str, str, str, bool], ...]:
    """Return deterministic public-safe evidence rows without executable callables."""
    return NEGATIVE_FIXTURE_MANIFEST


@pytest.mark.parametrize("case", NAMED_NEGATIVES, ids=lambda case: case.name)
def test_named_negative_fixture_has_one_exact_closed_reason(case: NamedNegative) -> None:
    view = independent_fixture(case.operation)
    if case.validation_error:
        with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
            case.mutate(view)
        assert caught.value.reason is case.reason
        assert str(caught.value) == case.reason.value
        return
    mutated = case.mutate(view)
    assert type(mutated) is subject.SyntheticChangeSetViewV1
    result = subject.review_synthetic_change_set_v1(mutated)
    assert result.disposition is subject.ChangeSetReviewDispositionV1.BLOCKED
    assert result.primary_reason is case.reason


def test_named_reordered_valid_change_list_remains_accepted() -> None:
    assert ORDER_INDEPENDENCE_CONTROL_MANIFEST == (
        ("reordered-valid-changes", "M1", "ACCEPTED", "MATCHED_EXPECTATION"),
    )
    view = independent_fixture(operation.M1)
    reordered = _replace_view(view, resource_changes=tuple(reversed(view.resource_changes)))
    assert subject.review_synthetic_change_set_v1(reordered) == subject.review_synthetic_change_set_v1(view)


def test_closed_reason_enum_covers_the_complete_contract() -> None:
    required = {
        "MATCHED_EXPECTATION",
        "VERSION_MISMATCH",
        "WRONG_OPERATION_STACK_BINDING",
        "WRONG_CHANGE_SET_TYPE",
        "WRONG_FROM_STATE",
        "WRONG_TO_STATE",
        "ILLEGAL_MODULE_A_TRANSITION",
        "WRONG_CREATION_STATUS",
        "EXECUTION_UNAVAILABLE",
        "INCOMPLETE_CHANGE_LIST",
        "DUPLICATE_LOGICAL_RESOURCE_CHANGE",
        "MISSING_EXPECTED_CHANGE",
        "UNEXPECTED_EXTRA_CHANGE",
        "WRONG_LOGICAL_RESOURCE_TYPE",
        "WRONG_ACTION",
        "WRONG_REPLACEMENT",
        "REPLACEMENT_TRUE",
        "REPLACEMENT_CONDITIONAL",
        "REPLACEMENT_UNKNOWN",
        "WRONG_SCOPE",
        "WRONG_MODIFICATION_ROLE",
        "PROTECTED_PERSISTENT_RESOURCE_TOUCHED",
        "RETAINED_EVIDENCE_RESOURCE_TOUCHED",
        "UNEXPECTED_FOUNDATION_MODIFICATION",
        "UNEXPECTED_STAGING_RESOURCE_MUTATION",
        "UNEXPECTED_M2_RESOURCE_MODIFICATION",
        "SENSITIVE_PRIVATE_FIELD_ATTEMPTED",
        "INVALID_DTO_COMBINATION",
    }
    assert required.issubset(subject.ChangeSetReviewReasonV1.__members__)
    exercised = {case.reason.name for case in NAMED_NEGATIVES}
    exercised.add("MATCHED_EXPECTATION")
    assert required.issubset(exercised)


def test_dependency_interface_mismatch_is_a_controlled_closed_reason(monkeypatch: object) -> None:
    invalid_delta = module_b.StagingStructuralDeltaV1(
        create_added_logical_ids=(),
        update_added_logical_ids=(),
        update_removed_logical_ids=(),
        update_modified_logical_ids=(),
        update_replaced_logical_ids=(),
    )
    monkeypatch.setattr(module_b, "staging_structural_delta_v1", lambda: invalid_delta)
    with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
        subject.canonical_synthetic_change_set_fixture_v1(operation.S1)
    assert caught.value.reason is reason.DEPENDENCY_INTERFACE_MISMATCH


@pytest.mark.parametrize(
    ("review_operation", "record"),
    tuple(
        (review_operation, record)
        for review_operation in (operation.M1, operation.M2)
        for record in module_a.logical_resource_registry_v1()
        if record.replacement_protected
    ),
    ids=lambda value: value.value if hasattr(value, "value") else value.logical_id.value,
)
def test_every_protected_resource_is_a_hard_gate(
    review_operation: subject.ProvisioningChangeSetOperationV1,
    record: module_a.LogicalResourceRecordV1,
) -> None:
    view = independent_fixture(review_operation)
    mutated = _append_main_modify(view, record.logical_id.value)
    result = subject.review_synthetic_change_set_v1(mutated)
    assert result.disposition is subject.ChangeSetReviewDispositionV1.BLOCKED
    expected_reason = (
        reason.RETAINED_EVIDENCE_RESOURCE_TOUCHED
        if record.retained_evidence_protected
        else reason.UNEXPECTED_FOUNDATION_MODIFICATION
    )
    assert result.primary_reason is expected_reason
    assert not result.protected_resource_untouched


@pytest.mark.parametrize("review_operation", (operation.M1, operation.M2))
def test_accepted_updates_touch_no_protected_resource(
    review_operation: subject.ProvisioningChangeSetOperationV1,
) -> None:
    protected = frozenset(
        item.value for item in module_a.protected_persistent_logical_ids_v1()
    )
    view = independent_fixture(review_operation)
    assert not protected.intersection(
        change.logical_resource_id for change in view.resource_changes
    )
    assert subject.review_synthetic_change_set_v1(view).protected_resource_untouched


def _sensitive_values_built_at_runtime() -> tuple[str, ...]:
    account_number = "".join(("123", "456", "789", "012"))
    arn_value = "".join(("a", "rn", ":", "aws", ":iam::", account_number, ":role/", "example"))
    ami_value = "".join(("a", "mi", "-", "1234", "abcd"))
    network_value = "".join(("s", "ubnet", "-", "1234", "abcd"))
    private_path = "/".join(("", "Users", "example", "private", "artifact"))
    ip_value = ".".join(("192", "0", "2", "17"))
    wait_url = "".join(
        (
            "https",
            "://",
            "cloudformation",
            "-waitcondition.",
            "example",
            ".invalid/",
            "signal",
        )
    )
    return (
        account_number,
        arn_value,
        ami_value,
        network_value,
        private_path,
        ip_value,
        wait_url,
    )


def test_sensitive_shaped_values_are_rejected_without_persisting_samples() -> None:
    baseline = _first_change(independent_fixture(operation.S0))
    for sensitive_value in _sensitive_values_built_at_runtime():
        assert (
            module_b.sensitive_value_scan_v1({"Value": sensitive_value})
            is not module_b.ModuleBValidationReasonV1.VALID
        )
        with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
            _replace_change(baseline, logical_resource_id=sensitive_value)
        assert caught.value.reason is reason.SENSITIVE_PRIVATE_FIELD_ATTEMPTED


def test_sensitive_field_names_are_rejected_before_nominal_construction() -> None:
    view = independent_fixture(operation.S1)
    sensitive_names = (
        "".join(("account", "_id")),
        "".join(("bucket", "_name")),
        "".join(("policy", "_body")),
        "".join(("wait", "_handle", "_url")),
        "".join(("credential", "s")),
        "".join(("pa", "th")),
    )
    for field_name in sensitive_names:
        with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
            _view_with_extra_field(view, field_name, "synthetic")
        assert caught.value.reason is reason.SENSITIVE_PRIVATE_FIELD_ATTEMPTED


def test_no_mapping_or_raw_provider_payload_can_enter_a_dto() -> None:
    view = independent_fixture(operation.S0)
    with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
        _replace_view(view, resource_changes={})
    assert caught.value.reason is reason.INVALID_DTO_COMBINATION
    with pytest.raises(subject.ModuleCValidationErrorV1) as caught:
        _view_with_extra_field(view, "".join(("raw", "_response")), {})
    assert caught.value.reason is reason.SENSITIVE_PRIVATE_FIELD_ATTEMPTED


@dataclass(frozen=True)
class MutationCase:
    name: str
    operation: subject.ProvisioningChangeSetOperationV1
    dimension: str
    mutate: Callable[[subject.SyntheticChangeSetViewV1], object]


def _mutate_action(view: subject.SyntheticChangeSetViewV1) -> subject.SyntheticChangeSetViewV1:
    original = _first_change(view)
    changed_action = (
        action.REMOVE
        if original.action is action.ADD
        else action.ADD
    )
    return _replace_change_at(
        view,
        0,
        _replace_change(original, action=changed_action),
    )


def _mutate_resource_type(view: subject.SyntheticChangeSetViewV1) -> subject.SyntheticChangeSetViewV1:
    return _replace_change_at(
        view,
        0,
        _replace_change(
            _first_change(view),
            structural_resource_type="AWS::Synthetic::Mutated",
        ),
    )


def _mutate_logical_id(view: subject.SyntheticChangeSetViewV1) -> subject.SyntheticChangeSetViewV1:
    original = _first_change(view)
    return _replace_change_at(
        view,
        0,
        _replace_change(
            original,
            logical_resource_id=f"{original.logical_resource_id}Mutated",
        ),
    )


def _mutation_target(view: subject.SyntheticChangeSetViewV1) -> subject.NormalizedResourceChangeV1:
    return next(
        (
            change
            for change in view.resource_changes
            if change.action is action.MODIFY
        ),
        _first_change(view),
    )


def _replace_mutation_target(
    view: subject.SyntheticChangeSetViewV1,
    **updates: object,
) -> subject.SyntheticChangeSetViewV1:
    target = _mutation_target(view)
    return _replace_change_by_id(view, target.logical_resource_id, **updates)


def _mutate_replacement(view: subject.SyntheticChangeSetViewV1) -> subject.SyntheticChangeSetViewV1:
    target = _mutation_target(view)
    mutated_replacement = (
        replacement.TRUE
        if target.replacement is replacement.FALSE
        else replacement.FALSE
    )
    return _replace_mutation_target(view, replacement=mutated_replacement)


def _mutate_scope(view: subject.SyntheticChangeSetViewV1) -> subject.SyntheticChangeSetViewV1:
    target = _mutation_target(view)
    mutated_scope = (
        scope.METADATA
        if target.scope is scope.PROPERTIES
        else scope.PROPERTIES
    )
    return _replace_mutation_target(view, scope=mutated_scope)


def _mutate_role(view: subject.SyntheticChangeSetViewV1) -> subject.SyntheticChangeSetViewV1:
    target = _mutation_target(view)
    mutated_role = (
        role.CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL
        if target.modification_role
        is not role.CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL
        else role.STAGING_EXACT_OBJECT_READ_POLICY_STATE
    )
    return _replace_mutation_target(view, modification_role=mutated_role)


def _mutate_operation(view: subject.SyntheticChangeSetViewV1) -> subject.SyntheticChangeSetViewV1:
    operations = tuple(subject.ProvisioningChangeSetOperationV1)
    index = operations.index(view.operation)
    return _replace_view(view, operation=operations[(index + 1) % len(operations)])


def _mutation_definitions() -> tuple[
    tuple[str, Callable[[subject.SyntheticChangeSetViewV1], object]], ...
]:
    return (
        ("action", _mutate_action),
        ("type", _mutate_resource_type),
        ("logical_id", _mutate_logical_id),
        ("replacement", _mutate_replacement),
        ("scope", _mutate_scope),
        ("role", _mutate_role),
        ("from_state", lambda view: _replace_view(view, from_state=_alternate_state(view.from_state))),
        ("to_state", lambda view: _replace_view(view, to_state=_alternate_state(view.to_state))),
        ("operation", _mutate_operation),
        ("stack_kind", lambda view: _replace_view(view, stack_kind=_opposite_stack(view.stack_kind))),
        ("change_set_type", lambda view: _replace_view(view, change_set_type=_opposite_change_set_type(view.change_set_type))),
        ("module_c_version", lambda view: _replace_view(view, module_c_schema_version="MUTATED_MODULE_C_VERSION")),
        ("module_a_version", lambda view: _replace_view(view, module_a_binding="MUTATED_MODULE_A_VERSION")),
        ("module_b_version", lambda view: _replace_view(view, module_b_binding="MUTATED_MODULE_B_VERSION")),
        ("clarification_version", lambda view: _replace_view(view, clarification_binding="MUTATED_CLARIFICATION_VERSION")),
        ("completeness", lambda view: _replace_view(view, complete_page_set=False)),
        ("creation_status", lambda view: _replace_view(view, terminal_creation_status=subject.ChangeSetCreationStatusV1.OTHER)),
        ("execution_status", lambda view: _replace_view(view, execution_availability_status=subject.ChangeSetExecutionStatusV1.OTHER)),
        ("presence_missing", lambda view: _drop_change(view, _first_change(view).logical_resource_id)),
        ("presence_extra", _append_synthetic_extra),
        ("duplicate", _duplicate_first),
    )


MUTATION_CASES = tuple(
    MutationCase(
        f"{review_operation.value}-{dimension}",
        review_operation,
        dimension,
        mutator,
    )
    for review_operation in subject.ProvisioningChangeSetOperationV1
    for dimension, mutator in _mutation_definitions()
)
MUTATION_AUDIT_CASE_COUNT = len(MUTATION_CASES)
MUTATION_AUDIT_MANIFEST = tuple(
    (case.name, case.operation.value, case.dimension) for case in MUTATION_CASES
)


def mutation_audit_manifest_v1() -> tuple[tuple[str, str, str], ...]:
    """Return stable mutation evidence rows without serializing callables."""
    return MUTATION_AUDIT_MANIFEST


@pytest.mark.parametrize("case", MUTATION_CASES, ids=lambda case: case.name)
def test_mutation_audit_rejects_every_single_dimension_mutation(case: MutationCase) -> None:
    view = independent_fixture(case.operation)
    try:
        mutated = case.mutate(view)
    except subject.ModuleCValidationErrorV1 as caught:
        assert caught.reason is reason.INVALID_DTO_COMBINATION
        return
    assert type(mutated) is subject.SyntheticChangeSetViewV1
    result = subject.review_synthetic_change_set_v1(mutated)
    assert result.disposition is subject.ChangeSetReviewDispositionV1.BLOCKED
    assert result.primary_reason is not reason.MATCHED_EXPECTATION


def test_mutation_manifest_is_dynamic_complete_unique_and_stable() -> None:
    required_dimensions = {
        "action",
        "type",
        "logical_id",
        "replacement",
        "scope",
        "role",
        "from_state",
        "to_state",
        "operation",
        "stack_kind",
        "change_set_type",
        "module_c_version",
        "module_a_version",
        "module_b_version",
        "clarification_version",
        "completeness",
        "creation_status",
        "execution_status",
        "presence_missing",
        "presence_extra",
        "duplicate",
    }
    assert MUTATION_AUDIT_CASE_COUNT == len(MUTATION_AUDIT_MANIFEST)
    assert len(MUTATION_AUDIT_MANIFEST) == len(set(MUTATION_AUDIT_MANIFEST))
    for review_operation in subject.ProvisioningChangeSetOperationV1:
        assert {
            case.dimension
            for case in MUTATION_CASES
            if case.operation is review_operation
        } == required_dimensions
    assert mutation_audit_manifest_v1() is MUTATION_AUDIT_MANIFEST


@pytest.mark.parametrize(
    "review_operation",
    tuple(subject.ProvisioningChangeSetOperationV1),
    ids=lambda candidate: candidate.value,
)
def test_every_operation_blocks_the_wrong_stack_kind(
    review_operation: subject.ProvisioningChangeSetOperationV1,
) -> None:
    view = independent_fixture(review_operation)
    result = subject.review_synthetic_change_set_v1(
        _replace_view(view, stack_kind=_opposite_stack(view.stack_kind))
    )
    assert result.primary_reason is reason.WRONG_OPERATION_STACK_BINDING


@pytest.mark.parametrize(
    "review_operation",
    tuple(subject.ProvisioningChangeSetOperationV1),
    ids=lambda candidate: candidate.value,
)
def test_every_operation_blocks_the_other_closed_change_set_type(
    review_operation: subject.ProvisioningChangeSetOperationV1,
) -> None:
    view = independent_fixture(review_operation)
    result = subject.review_synthetic_change_set_v1(
        _replace_view(
            view,
            change_set_type=_opposite_change_set_type(view.change_set_type),
        )
    )
    assert result.primary_reason is reason.WRONG_CHANGE_SET_TYPE


def _valid_permutations(
    view: subject.SyntheticChangeSetViewV1,
) -> tuple[tuple[subject.NormalizedResourceChangeV1, ...], ...]:
    changes = view.resource_changes
    if len(changes) <= 4:
        return tuple(permutations(changes))
    candidates = []
    for offset in range(len(changes)):
        candidates.append(changes[offset:] + changes[:offset])
    reversed_changes = tuple(reversed(changes))
    for offset in range(len(changes)):
        candidates.append(reversed_changes[offset:] + reversed_changes[:offset])
    return tuple(dict.fromkeys(candidates))


@pytest.mark.parametrize(
    "review_operation",
    tuple(subject.ProvisioningChangeSetOperationV1),
    ids=lambda candidate: candidate.value,
)
def test_all_tractable_and_representative_valid_permutations_are_accepted(
    review_operation: subject.ProvisioningChangeSetOperationV1,
) -> None:
    view = independent_fixture(review_operation)
    baseline = subject.review_synthetic_change_set_v1(view)
    permutations_to_review = _valid_permutations(view)
    if review_operation is operation.M0:
        assert len(permutations_to_review) >= len(view.resource_changes)
    else:
        expected_factorials = {operation.S0: 2, operation.S1: 1, operation.M1: 24, operation.M2: 6}
        assert len(permutations_to_review) == expected_factorials[review_operation]
    for permuted_changes in permutations_to_review:
        result = subject.review_synthetic_change_set_v1(
            _replace_view(view, resource_changes=permuted_changes)
        )
        assert result == baseline
        assert result.disposition is subject.ChangeSetReviewDispositionV1.ACCEPTED


def _rotate_changes(
    changes: tuple[subject.NormalizedResourceChangeV1, ...],
    offset: int,
) -> tuple[subject.NormalizedResourceChangeV1, ...]:
    if not changes:
        return changes
    normalized_offset = offset % len(changes)
    return changes[normalized_offset:] + changes[:normalized_offset]


def test_one_thousand_mixed_cycles_are_deterministic_without_state_leakage() -> None:
    operations = tuple(subject.ProvisioningChangeSetOperationV1)
    fixtures = {candidate: independent_fixture(candidate) for candidate in operations}
    accepted_reference = {
        candidate: subject.review_synthetic_change_set_v1(view)
        for candidate, view in fixtures.items()
    }
    blocked_reference = {
        candidate: subject.review_synthetic_change_set_v1(
            _replace_view(view, complete_page_set=False)
        )
        for candidate, view in fixtures.items()
    }
    for cycle in range(1_000):
        ordered = operations[cycle % len(operations):] + operations[: cycle % len(operations)]
        if cycle % 2:
            ordered = tuple(reversed(ordered))
        for candidate in ordered:
            view = fixtures[candidate]
            changes = _rotate_changes(view.resource_changes, cycle)
            if cycle % 3 == 0:
                changes = tuple(reversed(changes))
            permuted = _replace_view(view, resource_changes=changes)
            accepted = subject.review_synthetic_change_set_v1(permuted)
            blocked = subject.review_synthetic_change_set_v1(
                _replace_view(permuted, complete_page_set=False)
            )
            assert accepted == accepted_reference[candidate]
            assert blocked == blocked_reference[candidate]


def test_production_dependency_boundary_and_side_effect_absence() -> None:
    source_path = Path(subject.__file__)
    source_text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    allowed_import_roots = {
        "__future__",
        "dataclasses",
        "enum",
        "re",
        "typing",
        "scripts",
    }
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_roots.add((node.module or "").split(".")[0])
    assert imported_roots.issubset(allowed_import_roots)
    forbidden_imports = {
        "boto3",
        "botocore",
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "numpy",
        "torch",
        "torch_geometric",
    }
    assert imported_roots.isdisjoint(forbidden_imports)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_names.isdisjoint({"open", "eval", "exec", "compile", "__import__"})
    lowered = source_text.lower()
    for forbidden in (
        "create_change_set",
        "execute_change_set",
        "describe_change_set",
        "delete_stack",
        "send_command",
        "aws_access_key",
        "os.environ",
    ):
        assert forbidden not in lowered


def test_production_does_not_duplicate_module_a_or_b_authoritative_tables() -> None:
    source_text = Path(subject.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    string_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    module_a_ids = {
        record.logical_id.value for record in module_a.logical_resource_registry_v1()
    }
    staging_ids = set(
        module_b.build_staging_structural_model_v1(
            module_b.StagingAccessPhaseV1.UPLOAD_ONLY
        )["Resources"]
    )
    assert not module_a_ids.issubset(string_literals)
    assert not staging_ids.issubset(string_literals)
    assert "_MAIN_RESOURCE_TYPE_ROWS" not in source_text
    assert "_LEGAL_FORWARD_TRANSITIONS" not in source_text
    dependency_calls = {
        "logical_resource_registry_v1",
        "protected_persistent_logical_ids_v1",
        "review_controller_phase_transition_v1",
        "build_main_structural_model_v1",
        "build_staging_structural_model_v1",
        "staging_structural_delta_v1",
        "sensitive_value_scan_v1",
    }
    assert all(name in source_text for name in dependency_calls)


def test_manifest_helpers_are_stable_public_safe_and_non_executable() -> None:
    assert named_negative_fixture_manifest_v1() is NEGATIVE_FIXTURE_MANIFEST
    assert len(NEGATIVE_FIXTURE_MANIFEST) == len(NAMED_NEGATIVES)
    assert len(NEGATIVE_FIXTURE_MANIFEST) == len(set(NEGATIVE_FIXTURE_MANIFEST))
    assert all(
        isinstance(value, (str, bool))
        for row in NEGATIVE_FIXTURE_MANIFEST
        for value in row
    )
    assert all(
        isinstance(value, str)
        for row in MUTATION_AUDIT_MANIFEST
        for value in row
    )
