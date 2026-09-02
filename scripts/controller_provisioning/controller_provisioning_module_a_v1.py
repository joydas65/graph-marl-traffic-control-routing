"""Pure finite-state contract for controller-provisioning Module A."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from typing import Final, final


_MODULE_A_VERSION: Final[str] = (
    "CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_A_V1"
)
_BOUND_CLARIFICATION_VERSION: Final[str] = (
    "CANDIDATE_N_V4_CLOUDFORMATION_PHASE_AND_CHANGESET_CLARIFICATION_V1"
)
_VERSION_BINDING: Final[tuple[str, str]] = (
    _MODULE_A_VERSION,
    _BOUND_CLARIFICATION_VERSION,
)
_MISSING: Final[object] = object()
_DTO_FACTORY_TOKEN: Final[object] = object()


@final
class ModuleAValidationErrorV1(ValueError):
    """Fixed public exception for invalid calls into this module."""


@unique
class ControllerDeploymentPhaseV1(Enum):
    FOUNDATION_ONLY = "FOUNDATION_ONLY"
    CONTROLLER_COMPUTE = "CONTROLLER_COMPUTE"
    SEALED_STOPPED = "SEALED_STOPPED"


@unique
class MainStackPhaseStateV1(Enum):
    NONEXISTENT = "NONEXISTENT"
    FOUNDATION_ONLY = "FOUNDATION_ONLY"
    CONTROLLER_COMPUTE = "CONTROLLER_COMPUTE"
    SEALED_STOPPED = "SEALED_STOPPED"


@unique
class LogicalResourceClassV1(Enum):
    FOUNDATION_PERSISTENT = "FOUNDATION_PERSISTENT"
    RETAINED_EVIDENCE = "RETAINED_EVIDENCE"
    COMPUTE_PHASE = "COMPUTE_PHASE"
    BOOTSTRAP_ONLY = "BOOTSTRAP_ONLY"


@unique
class ControllerLogicalResourceIdV1(Enum):
    CONTROLLER_BUDGET = "ControllerBudget"
    CONTROLLER_SECURITY_GROUP = "ControllerSecurityGroup"
    CONTROLLER_HOST_ROLE = "ControllerHostRole"
    EXPERIMENT_RUNTIME_ROLE = "ExperimentRuntimeRole"
    CONTROLLER_INSTANCE_PROFILE = "ControllerInstanceProfile"
    CONTROLLER_COMMAND_DOCUMENT = "ControllerCommandDocument"
    EVIDENCE_KEY = "EvidenceKey"
    EVIDENCE_VOLUME = "EvidenceVolume"
    CONTROLLER_INSTANCE = "ControllerInstance"
    EVIDENCE_VOLUME_ATTACHMENT = "EvidenceVolumeAttachment"
    BOOTSTRAP_WAIT_HANDLE = "BootstrapWaitHandle"
    BOOTSTRAP_WAIT_CONDITION = "BootstrapWaitCondition"


@unique
class TransitionClassificationV1(Enum):
    LEGAL_FORWARD = "LEGAL_FORWARD"
    ILLEGAL_SKIP = "ILLEGAL_SKIP"
    ILLEGAL_REPEAT = "ILLEGAL_REPEAT"
    ILLEGAL_REGRESSION = "ILLEGAL_REGRESSION"
    ILLEGAL_OTHER = "ILLEGAL_OTHER"


@unique
class TransitionMetadataExpectationV1(Enum):
    NONE = "NONE"
    CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL = (
        "CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL"
    )


_DEPLOYED_PHASES: Final[tuple[ControllerDeploymentPhaseV1, ...]] = tuple(
    ControllerDeploymentPhaseV1
)


def _require_deployment_phase(value: object) -> ControllerDeploymentPhaseV1:
    if type(value) is not ControllerDeploymentPhaseV1:
        raise ModuleAValidationErrorV1("MODULE_A_INVALID_DEPLOYMENT_PHASE")
    return value


def _require_stack_state(value: object) -> MainStackPhaseStateV1:
    if type(value) is not MainStackPhaseStateV1:
        raise ModuleAValidationErrorV1("MODULE_A_INVALID_STACK_PHASE_STATE")
    return value


def controller_present_v1(
    phase: object = _MISSING,
    /,
    *caller_overrides: object,
    **caller_named_overrides: object,
) -> bool:
    if caller_overrides or caller_named_overrides:
        raise ModuleAValidationErrorV1("MODULE_A_CONDITION_OVERRIDE_FORBIDDEN")
    checked_phase = _require_deployment_phase(phase)
    return checked_phase in (
        ControllerDeploymentPhaseV1.CONTROLLER_COMPUTE,
        ControllerDeploymentPhaseV1.SEALED_STOPPED,
    )


def bootstrap_signal_active_v1(
    phase: object = _MISSING,
    /,
    *caller_overrides: object,
    **caller_named_overrides: object,
) -> bool:
    if caller_overrides or caller_named_overrides:
        raise ModuleAValidationErrorV1("MODULE_A_CONDITION_OVERRIDE_FORBIDDEN")
    checked_phase = _require_deployment_phase(phase)
    return checked_phase is ControllerDeploymentPhaseV1.CONTROLLER_COMPUTE


@final
@dataclass(frozen=True, slots=True, init=False)
class LogicalResourceRecordV1:
    logical_id: ControllerLogicalResourceIdV1
    resource_class: LogicalResourceClassV1
    phase_presence_mask: frozenset[ControllerDeploymentPhaseV1]
    replacement_protected: bool
    retained_evidence_protected: bool

    def __init__(
        self,
        factory_token: object = _MISSING,
        payload: object = _MISSING,
        **caller_fields: object,
    ) -> None:
        valid_payload = (
            factory_token is _DTO_FACTORY_TOKEN
            and not caller_fields
            and type(payload) is tuple
            and len(payload) == 5
        )
        if not valid_payload:
            raise ModuleAValidationErrorV1("MODULE_A_RESOURCE_RECORD_FACTORY_REQUIRED")
        (
            logical_id,
            resource_class,
            phase_presence_mask,
            replacement_protected,
            retained_evidence_protected,
        ) = payload
        valid_fields = (
            type(logical_id) is ControllerLogicalResourceIdV1
            and type(resource_class) is LogicalResourceClassV1
            and type(phase_presence_mask) is frozenset
            and bool(phase_presence_mask)
            and all(
                type(phase) is ControllerDeploymentPhaseV1
                for phase in phase_presence_mask
            )
            and type(replacement_protected) is bool
            and type(retained_evidence_protected) is bool
        )
        if not valid_fields:
            raise ModuleAValidationErrorV1("MODULE_A_INVALID_RESOURCE_RECORD_PAYLOAD")
        expected_class = _resource_class_for_logical_id(logical_id)
        expected_presence = _phase_presence_for_resource_class(expected_class)
        expected_replacement_protection = expected_class in (
            LogicalResourceClassV1.FOUNDATION_PERSISTENT,
            LogicalResourceClassV1.RETAINED_EVIDENCE,
        )
        expected_retained_evidence_protection = (
            expected_class is LogicalResourceClassV1.RETAINED_EVIDENCE
        )
        valid_derivation = (
            resource_class is expected_class
            and phase_presence_mask == expected_presence
            and replacement_protected is expected_replacement_protection
            and retained_evidence_protected is expected_retained_evidence_protection
        )
        if not valid_derivation:
            raise ModuleAValidationErrorV1("MODULE_A_INVALID_RESOURCE_RECORD_DERIVATION")
        object.__setattr__(self, "logical_id", logical_id)
        object.__setattr__(self, "resource_class", resource_class)
        object.__setattr__(self, "phase_presence_mask", phase_presence_mask)
        object.__setattr__(self, "replacement_protected", replacement_protected)
        object.__setattr__(
            self,
            "retained_evidence_protected",
            retained_evidence_protected,
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise ModuleAValidationErrorV1("MODULE_A_RESOURCE_RECORD_IS_FINAL")


def _resource_class_for_logical_id(
    logical_id: ControllerLogicalResourceIdV1,
) -> LogicalResourceClassV1:
    if logical_id in (
        ControllerLogicalResourceIdV1.CONTROLLER_BUDGET,
        ControllerLogicalResourceIdV1.CONTROLLER_SECURITY_GROUP,
        ControllerLogicalResourceIdV1.CONTROLLER_HOST_ROLE,
        ControllerLogicalResourceIdV1.EXPERIMENT_RUNTIME_ROLE,
        ControllerLogicalResourceIdV1.CONTROLLER_INSTANCE_PROFILE,
        ControllerLogicalResourceIdV1.CONTROLLER_COMMAND_DOCUMENT,
    ):
        return LogicalResourceClassV1.FOUNDATION_PERSISTENT
    if logical_id in (
        ControllerLogicalResourceIdV1.EVIDENCE_KEY,
        ControllerLogicalResourceIdV1.EVIDENCE_VOLUME,
    ):
        return LogicalResourceClassV1.RETAINED_EVIDENCE
    if logical_id in (
        ControllerLogicalResourceIdV1.CONTROLLER_INSTANCE,
        ControllerLogicalResourceIdV1.EVIDENCE_VOLUME_ATTACHMENT,
    ):
        return LogicalResourceClassV1.COMPUTE_PHASE
    return LogicalResourceClassV1.BOOTSTRAP_ONLY


def _phase_presence_for_resource_class(
    resource_class: LogicalResourceClassV1,
) -> frozenset[ControllerDeploymentPhaseV1]:
    if resource_class in (
        LogicalResourceClassV1.FOUNDATION_PERSISTENT,
        LogicalResourceClassV1.RETAINED_EVIDENCE,
    ):
        return frozenset(_DEPLOYED_PHASES)
    if resource_class is LogicalResourceClassV1.COMPUTE_PHASE:
        return frozenset(
            phase for phase in _DEPLOYED_PHASES if controller_present_v1(phase)
        )
    return frozenset(
        phase for phase in _DEPLOYED_PHASES if bootstrap_signal_active_v1(phase)
    )


def _resource_record(
    logical_id: ControllerLogicalResourceIdV1,
) -> LogicalResourceRecordV1:
    resource_class = _resource_class_for_logical_id(logical_id)
    presence = _phase_presence_for_resource_class(resource_class)
    replacement_protected = resource_class in (
        LogicalResourceClassV1.FOUNDATION_PERSISTENT,
        LogicalResourceClassV1.RETAINED_EVIDENCE,
    )
    retained_evidence_protected = (
        resource_class is LogicalResourceClassV1.RETAINED_EVIDENCE
    )
    return LogicalResourceRecordV1(
        _DTO_FACTORY_TOKEN,
        (
            logical_id,
            resource_class,
            presence,
            replacement_protected,
            retained_evidence_protected,
        ),
    )


_LOGICAL_RESOURCE_REGISTRY: Final[tuple[LogicalResourceRecordV1, ...]] = tuple(
    sorted(
        (
            _resource_record(ControllerLogicalResourceIdV1.CONTROLLER_BUDGET),
            _resource_record(
                ControllerLogicalResourceIdV1.CONTROLLER_SECURITY_GROUP
            ),
            _resource_record(ControllerLogicalResourceIdV1.CONTROLLER_HOST_ROLE),
            _resource_record(ControllerLogicalResourceIdV1.EXPERIMENT_RUNTIME_ROLE),
            _resource_record(
                ControllerLogicalResourceIdV1.CONTROLLER_INSTANCE_PROFILE
            ),
            _resource_record(
                ControllerLogicalResourceIdV1.CONTROLLER_COMMAND_DOCUMENT
            ),
            _resource_record(ControllerLogicalResourceIdV1.EVIDENCE_KEY),
            _resource_record(ControllerLogicalResourceIdV1.EVIDENCE_VOLUME),
            _resource_record(ControllerLogicalResourceIdV1.CONTROLLER_INSTANCE),
            _resource_record(
                ControllerLogicalResourceIdV1.EVIDENCE_VOLUME_ATTACHMENT
            ),
            _resource_record(ControllerLogicalResourceIdV1.BOOTSTRAP_WAIT_HANDLE),
            _resource_record(
                ControllerLogicalResourceIdV1.BOOTSTRAP_WAIT_CONDITION
            ),
        ),
        key=lambda record: record.logical_id.value,
    )
)


def logical_resource_registry_v1() -> tuple[LogicalResourceRecordV1, ...]:
    return _LOGICAL_RESOURCE_REGISTRY


def logical_resource_ids_for_phase_v1(
    phase: object = _MISSING,
    /,
    *caller_overrides: object,
    **caller_named_overrides: object,
) -> tuple[ControllerLogicalResourceIdV1, ...]:
    if caller_overrides or caller_named_overrides:
        raise ModuleAValidationErrorV1("MODULE_A_RESOURCE_OVERRIDE_FORBIDDEN")
    checked_phase = _require_deployment_phase(phase)
    return tuple(
        record.logical_id
        for record in _LOGICAL_RESOURCE_REGISTRY
        if checked_phase in record.phase_presence_mask
    )


def protected_persistent_logical_ids_v1() -> tuple[ControllerLogicalResourceIdV1, ...]:
    return tuple(
        record.logical_id
        for record in _LOGICAL_RESOURCE_REGISTRY
        if record.resource_class
        in (
            LogicalResourceClassV1.FOUNDATION_PERSISTENT,
            LogicalResourceClassV1.RETAINED_EVIDENCE,
        )
    )


def phase_contains_all_protected_persistent_resources_v1(
    phase: object = _MISSING,
    /,
    *caller_overrides: object,
    **caller_named_overrides: object,
) -> bool:
    if caller_overrides or caller_named_overrides:
        raise ModuleAValidationErrorV1("MODULE_A_RESOURCE_OVERRIDE_FORBIDDEN")
    phase_ids = frozenset(logical_resource_ids_for_phase_v1(phase))
    return frozenset(protected_persistent_logical_ids_v1()).issubset(phase_ids)


@final
@dataclass(frozen=True, slots=True, init=False)
class ControllerPhaseProfileV1:
    artifact_module_version: str
    phase: ControllerDeploymentPhaseV1
    controller_present: bool
    bootstrap_signal_active: bool
    logical_resource_ids: tuple[ControllerLogicalResourceIdV1, ...]
    logical_resource_count: int

    def __init__(
        self,
        factory_token: object = _MISSING,
        payload: object = _MISSING,
        **caller_fields: object,
    ) -> None:
        valid_payload = (
            factory_token is _DTO_FACTORY_TOKEN
            and not caller_fields
            and type(payload) is tuple
            and len(payload) == 6
        )
        if not valid_payload:
            raise ModuleAValidationErrorV1("MODULE_A_PHASE_PROFILE_FACTORY_REQUIRED")
        (
            artifact_module_version,
            phase,
            controller_present,
            bootstrap_signal_active,
            logical_resource_ids,
            logical_resource_count,
        ) = payload
        valid_types = (
            artifact_module_version == _MODULE_A_VERSION
            and type(phase) is ControllerDeploymentPhaseV1
            and type(controller_present) is bool
            and type(bootstrap_signal_active) is bool
            and type(logical_resource_ids) is tuple
            and all(
                type(logical_id) is ControllerLogicalResourceIdV1
                for logical_id in logical_resource_ids
            )
            and type(logical_resource_count) is int
            and logical_resource_count == len(logical_resource_ids)
        )
        if not valid_types:
            raise ModuleAValidationErrorV1("MODULE_A_INVALID_PHASE_PROFILE_PAYLOAD")
        expected_logical_resource_ids = logical_resource_ids_for_phase_v1(phase)
        valid_derivation = (
            controller_present is controller_present_v1(phase)
            and bootstrap_signal_active is bootstrap_signal_active_v1(phase)
            and logical_resource_ids == expected_logical_resource_ids
            and logical_resource_count == len(expected_logical_resource_ids)
        )
        if not valid_derivation:
            raise ModuleAValidationErrorV1("MODULE_A_INVALID_PHASE_PROFILE_DERIVATION")
        object.__setattr__(self, "artifact_module_version", artifact_module_version)
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "controller_present", controller_present)
        object.__setattr__(self, "bootstrap_signal_active", bootstrap_signal_active)
        object.__setattr__(self, "logical_resource_ids", logical_resource_ids)
        object.__setattr__(self, "logical_resource_count", logical_resource_count)

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise ModuleAValidationErrorV1("MODULE_A_PHASE_PROFILE_IS_FINAL")


def create_controller_phase_profile_v1(
    phase: object = _MISSING,
    /,
    *caller_fields: object,
    **caller_named_fields: object,
) -> ControllerPhaseProfileV1:
    if caller_fields or caller_named_fields:
        raise ModuleAValidationErrorV1("MODULE_A_PHASE_PROFILE_DERIVATION_REQUIRED")
    checked_phase = _require_deployment_phase(phase)
    logical_resource_ids = logical_resource_ids_for_phase_v1(checked_phase)
    payload = (
        _MODULE_A_VERSION,
        checked_phase,
        controller_present_v1(checked_phase),
        bootstrap_signal_active_v1(checked_phase),
        logical_resource_ids,
        len(logical_resource_ids),
    )
    return ControllerPhaseProfileV1(_DTO_FACTORY_TOKEN, payload)


_LEGAL_FORWARD_TRANSITIONS: Final[
    tuple[tuple[MainStackPhaseStateV1, MainStackPhaseStateV1], ...]
] = (
    (
        MainStackPhaseStateV1.NONEXISTENT,
        MainStackPhaseStateV1.FOUNDATION_ONLY,
    ),
    (
        MainStackPhaseStateV1.FOUNDATION_ONLY,
        MainStackPhaseStateV1.CONTROLLER_COMPUTE,
    ),
    (
        MainStackPhaseStateV1.CONTROLLER_COMPUTE,
        MainStackPhaseStateV1.SEALED_STOPPED,
    ),
)


def legal_forward_transitions_v1() -> tuple[
    tuple[MainStackPhaseStateV1, MainStackPhaseStateV1], ...
]:
    return _LEGAL_FORWARD_TRANSITIONS


def _state_rank(state: MainStackPhaseStateV1) -> int:
    if state is MainStackPhaseStateV1.NONEXISTENT:
        return 0
    if state is MainStackPhaseStateV1.FOUNDATION_ONLY:
        return 1
    if state is MainStackPhaseStateV1.CONTROLLER_COMPUTE:
        return 2
    return 3


def _transition_classification(
    previous: MainStackPhaseStateV1,
    requested: MainStackPhaseStateV1,
) -> TransitionClassificationV1:
    if previous is requested:
        return TransitionClassificationV1.ILLEGAL_REPEAT
    if (previous, requested) in _LEGAL_FORWARD_TRANSITIONS:
        return TransitionClassificationV1.LEGAL_FORWARD
    if requested is MainStackPhaseStateV1.NONEXISTENT:
        return TransitionClassificationV1.ILLEGAL_OTHER
    if _state_rank(requested) < _state_rank(previous):
        return TransitionClassificationV1.ILLEGAL_REGRESSION
    if _state_rank(requested) > _state_rank(previous) + 1:
        return TransitionClassificationV1.ILLEGAL_SKIP
    return TransitionClassificationV1.ILLEGAL_OTHER


def _logical_resource_ids_for_state(
    state: MainStackPhaseStateV1,
) -> tuple[ControllerLogicalResourceIdV1, ...]:
    if state is MainStackPhaseStateV1.NONEXISTENT:
        return ()
    return logical_resource_ids_for_phase_v1(ControllerDeploymentPhaseV1(state.value))


def _derived_transition_fields(
    previous: MainStackPhaseStateV1,
    requested: MainStackPhaseStateV1,
) -> tuple[
    TransitionClassificationV1,
    tuple[ControllerLogicalResourceIdV1, ...],
    tuple[ControllerLogicalResourceIdV1, ...],
    tuple[ControllerLogicalResourceIdV1, ...],
    TransitionMetadataExpectationV1,
]:
    classification = _transition_classification(previous, requested)
    added: tuple[ControllerLogicalResourceIdV1, ...] = ()
    removed: tuple[ControllerLogicalResourceIdV1, ...] = ()
    unchanged: tuple[ControllerLogicalResourceIdV1, ...] = ()
    metadata_expectation = TransitionMetadataExpectationV1.NONE
    if classification is TransitionClassificationV1.LEGAL_FORWARD:
        previous_ids = frozenset(_logical_resource_ids_for_state(previous))
        requested_ids = frozenset(_logical_resource_ids_for_state(requested))
        added = tuple(sorted(requested_ids - previous_ids, key=lambda item: item.value))
        removed = tuple(sorted(previous_ids - requested_ids, key=lambda item: item.value))
        unchanged = tuple(sorted(previous_ids & requested_ids, key=lambda item: item.value))
        if (
            previous is MainStackPhaseStateV1.CONTROLLER_COMPUTE
            and requested is MainStackPhaseStateV1.SEALED_STOPPED
        ):
            metadata_expectation = (
                TransitionMetadataExpectationV1.CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL
            )
    return classification, added, removed, unchanged, metadata_expectation


@final
@dataclass(frozen=True, slots=True, init=False)
class ControllerPhaseTransitionReviewV1:
    artifact_module_version: str
    previous_stack_phase: MainStackPhaseStateV1
    requested_stack_phase: MainStackPhaseStateV1
    transition_classification: TransitionClassificationV1
    added_logical_ids: tuple[ControllerLogicalResourceIdV1, ...]
    removed_logical_ids: tuple[ControllerLogicalResourceIdV1, ...]
    unchanged_logical_ids: tuple[ControllerLogicalResourceIdV1, ...]
    metadata_expectation: TransitionMetadataExpectationV1

    def __init__(
        self,
        factory_token: object = _MISSING,
        payload: object = _MISSING,
        **caller_fields: object,
    ) -> None:
        valid_payload = (
            factory_token is _DTO_FACTORY_TOKEN
            and not caller_fields
            and type(payload) is tuple
            and len(payload) == 8
        )
        if not valid_payload:
            raise ModuleAValidationErrorV1(
                "MODULE_A_TRANSITION_REVIEW_FACTORY_REQUIRED"
            )
        (
            artifact_module_version,
            previous_stack_phase,
            requested_stack_phase,
            transition_classification,
            added_logical_ids,
            removed_logical_ids,
            unchanged_logical_ids,
            metadata_expectation,
        ) = payload
        logical_id_groups = (
            added_logical_ids,
            removed_logical_ids,
            unchanged_logical_ids,
        )
        valid_types = (
            artifact_module_version == _MODULE_A_VERSION
            and type(previous_stack_phase) is MainStackPhaseStateV1
            and type(requested_stack_phase) is MainStackPhaseStateV1
            and type(transition_classification) is TransitionClassificationV1
            and all(type(group) is tuple for group in logical_id_groups)
            and all(
                type(logical_id) is ControllerLogicalResourceIdV1
                for group in logical_id_groups
                for logical_id in group
            )
            and type(metadata_expectation) is TransitionMetadataExpectationV1
        )
        if not valid_types:
            raise ModuleAValidationErrorV1("MODULE_A_INVALID_TRANSITION_REVIEW_PAYLOAD")
        expected_fields = _derived_transition_fields(
            previous_stack_phase,
            requested_stack_phase,
        )
        actual_fields = (
            transition_classification,
            added_logical_ids,
            removed_logical_ids,
            unchanged_logical_ids,
            metadata_expectation,
        )
        if actual_fields != expected_fields:
            raise ModuleAValidationErrorV1(
                "MODULE_A_INVALID_TRANSITION_REVIEW_DERIVATION"
            )
        object.__setattr__(self, "artifact_module_version", artifact_module_version)
        object.__setattr__(self, "previous_stack_phase", previous_stack_phase)
        object.__setattr__(self, "requested_stack_phase", requested_stack_phase)
        object.__setattr__(self, "transition_classification", transition_classification)
        object.__setattr__(self, "added_logical_ids", added_logical_ids)
        object.__setattr__(self, "removed_logical_ids", removed_logical_ids)
        object.__setattr__(self, "unchanged_logical_ids", unchanged_logical_ids)
        object.__setattr__(self, "metadata_expectation", metadata_expectation)

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise ModuleAValidationErrorV1("MODULE_A_TRANSITION_REVIEW_IS_FINAL")


def review_controller_phase_transition_v1(
    previous: object = _MISSING,
    requested: object = _MISSING,
    /,
    *caller_fields: object,
    **caller_named_fields: object,
) -> ControllerPhaseTransitionReviewV1:
    if caller_fields or caller_named_fields:
        raise ModuleAValidationErrorV1("MODULE_A_TRANSITION_OVERRIDE_FORBIDDEN")
    checked_previous = _require_stack_state(previous)
    checked_requested = _require_stack_state(requested)
    (
        classification,
        added,
        removed,
        unchanged,
        metadata_expectation,
    ) = _derived_transition_fields(checked_previous, checked_requested)
    payload = (
        _MODULE_A_VERSION,
        checked_previous,
        checked_requested,
        classification,
        added,
        removed,
        unchanged,
        metadata_expectation,
    )
    return ControllerPhaseTransitionReviewV1(_DTO_FACTORY_TOKEN, payload)


def persistent_resource_invariants_hold_v1() -> bool:
    persistent_ids = frozenset(protected_persistent_logical_ids_v1())
    present_in_every_phase = all(
        persistent_ids.issubset(
            frozenset(logical_resource_ids_for_phase_v1(phase))
        )
        for phase in _DEPLOYED_PHASES
    )
    preserved_by_every_legal_transition = all(
        not persistent_ids.intersection(
            review_controller_phase_transition_v1(previous, requested).removed_logical_ids
        )
        for previous, requested in _LEGAL_FORWARD_TRANSITIONS
    )
    return present_in_every_phase and preserved_by_every_legal_transition


def module_a_version_binding_v1() -> tuple[str, str]:
    return _VERSION_BINDING


def require_module_a_version_binding_v1(
    module_version: object = _MISSING,
    clarification_version: object = _MISSING,
    /,
    *caller_fields: object,
    **caller_named_fields: object,
) -> tuple[str, str]:
    if caller_fields or caller_named_fields:
        raise ModuleAValidationErrorV1("MODULE_A_VERSION_OVERRIDE_FORBIDDEN")
    if type(module_version) is not str or type(clarification_version) is not str:
        raise ModuleAValidationErrorV1("MODULE_A_VERSION_BINDING_MISMATCH")
    if (module_version, clarification_version) != _VERSION_BINDING:
        raise ModuleAValidationErrorV1("MODULE_A_VERSION_BINDING_MISMATCH")
    return _VERSION_BINDING


__all__ = (
    "ControllerDeploymentPhaseV1",
    "ControllerLogicalResourceIdV1",
    "ControllerPhaseProfileV1",
    "ControllerPhaseTransitionReviewV1",
    "LogicalResourceClassV1",
    "MainStackPhaseStateV1",
    "ModuleAValidationErrorV1",
    "TransitionClassificationV1",
    "TransitionMetadataExpectationV1",
    "bootstrap_signal_active_v1",
    "controller_present_v1",
    "create_controller_phase_profile_v1",
    "legal_forward_transitions_v1",
    "logical_resource_ids_for_phase_v1",
    "logical_resource_registry_v1",
    "module_a_version_binding_v1",
    "persistent_resource_invariants_hold_v1",
    "phase_contains_all_protected_persistent_resources_v1",
    "protected_persistent_logical_ids_v1",
    "require_module_a_version_binding_v1",
    "review_controller_phase_transition_v1",
)
