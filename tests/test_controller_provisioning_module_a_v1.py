"""Exhaustive source-free tests for controller-provisioning Module A."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import importlib.util
from itertools import product
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_A_PATH = (
    ROOT
    / "scripts"
    / "controller_provisioning"
    / "controller_provisioning_module_a_v1.py"
)


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


subject = load_module("controller_provisioning_module_a_v1", MODULE_A_PATH)


Phase = subject.ControllerDeploymentPhaseV1
State = subject.MainStackPhaseStateV1
ResourceId = subject.ControllerLogicalResourceIdV1
ResourceClass = subject.LogicalResourceClassV1
Classification = subject.TransitionClassificationV1
Metadata = subject.TransitionMetadataExpectationV1


FOUNDATION_IDS = frozenset(
    {
        "ControllerBudget",
        "ControllerCommandDocument",
        "ControllerHostRole",
        "ControllerInstanceProfile",
        "ControllerSecurityGroup",
        "EvidenceKey",
        "EvidenceVolume",
        "ExperimentRuntimeRole",
    }
)
COMPUTE_ADDITIONS = frozenset(
    {
        "BootstrapWaitCondition",
        "BootstrapWaitHandle",
        "ControllerInstance",
        "EvidenceVolumeAttachment",
    }
)
SEALED_ADDITIONS = frozenset(
    {
        "ControllerInstance",
        "EvidenceVolumeAttachment",
    }
)
EXPECTED_RESOURCE_IDS = FOUNDATION_IDS | COMPUTE_ADDITIONS


INVALID_TRANSITION_FIXTURES_V1 = (
    (
        "skip_foundation",
        State.NONEXISTENT,
        State.CONTROLLER_COMPUTE,
        Classification.ILLEGAL_SKIP,
    ),
    (
        "skip_compute",
        State.FOUNDATION_ONLY,
        State.SEALED_STOPPED,
        Classification.ILLEGAL_SKIP,
    ),
    (
        "repeat_foundation",
        State.FOUNDATION_ONLY,
        State.FOUNDATION_ONLY,
        Classification.ILLEGAL_REPEAT,
    ),
    (
        "repeat_compute",
        State.CONTROLLER_COMPUTE,
        State.CONTROLLER_COMPUTE,
        Classification.ILLEGAL_REPEAT,
    ),
    (
        "repeat_sealed",
        State.SEALED_STOPPED,
        State.SEALED_STOPPED,
        Classification.ILLEGAL_REPEAT,
    ),
    (
        "regress_compute_to_foundation",
        State.CONTROLLER_COMPUTE,
        State.FOUNDATION_ONLY,
        Classification.ILLEGAL_REGRESSION,
    ),
    (
        "regress_sealed_to_compute",
        State.SEALED_STOPPED,
        State.CONTROLLER_COMPUTE,
        Classification.ILLEGAL_REGRESSION,
    ),
    (
        "regress_sealed_to_foundation",
        State.SEALED_STOPPED,
        State.FOUNDATION_ONLY,
        Classification.ILLEGAL_REGRESSION,
    ),
)


def id_values(logical_ids: tuple[ResourceId, ...]) -> tuple[str, ...]:
    return tuple(logical_id.value for logical_id in logical_ids)


def review(previous: State, requested: State) -> subject.ControllerPhaseTransitionReviewV1:
    return subject.review_controller_phase_transition_v1(previous, requested)


class PhaseTypeTests(unittest.TestCase):
    def test_deployment_phase_enum_is_exact_and_closed(self) -> None:
        self.assertEqual(
            tuple(member.name for member in Phase),
            ("FOUNDATION_ONLY", "CONTROLLER_COMPUTE", "SEALED_STOPPED"),
        )
        self.assertEqual(tuple(member.value for member in Phase), tuple(member.name for member in Phase))
        self.assertEqual(len(Phase.__members__), 3)

    def test_unknown_deployment_phase_values_are_rejected(self) -> None:
        invalid_values = (
            "NONEXISTENT",
            "foundation_only",
            "FOUNDATION",
            "CONTROLLER_COMPUTE ",
            "SEALED",
            "RETAINED_EVIDENCE_ONLY",
            "",
        )
        for invalid_value in invalid_values:
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(ValueError):
                    Phase(invalid_value)

    def test_deployment_phase_accepts_no_aliases(self) -> None:
        self.assertEqual(tuple(Phase.__members__), tuple(member.name for member in Phase))
        for member in Phase:
            self.assertIs(Phase(member.value), member)

    def test_stack_state_is_exact_and_separate(self) -> None:
        self.assertEqual(
            tuple(member.name for member in State),
            (
                "NONEXISTENT",
                "FOUNDATION_ONLY",
                "CONTROLLER_COMPUTE",
                "SEALED_STOPPED",
            ),
        )
        self.assertNotIn("NONEXISTENT", tuple(member.value for member in Phase))
        self.assertIsNot(State.FOUNDATION_ONLY, Phase.FOUNDATION_ONLY)


class ConditionTruthTableTests(unittest.TestCase):
    def test_exact_truth_table(self) -> None:
        expected = (
            (Phase.FOUNDATION_ONLY, False, False),
            (Phase.CONTROLLER_COMPUTE, True, True),
            (Phase.SEALED_STOPPED, True, False),
        )
        actual = tuple(
            (
                phase,
                subject.controller_present_v1(phase),
                subject.bootstrap_signal_active_v1(phase),
            )
            for phase in Phase
        )
        self.assertEqual(actual, expected)

    def test_condition_evaluation_is_total_and_repeatable(self) -> None:
        for phase in Phase:
            controller_results = tuple(subject.controller_present_v1(phase) for _ in range(50))
            bootstrap_results = tuple(
                subject.bootstrap_signal_active_v1(phase) for _ in range(50)
            )
            self.assertEqual(len(frozenset(controller_results)), 1)
            self.assertEqual(len(frozenset(bootstrap_results)), 1)

    def test_condition_outcomes_cannot_be_overridden(self) -> None:
        for condition in (
            subject.controller_present_v1,
            subject.bootstrap_signal_active_v1,
        ):
            with self.subTest(condition=condition.__name__):
                with self.assertRaises(subject.ModuleAValidationErrorV1):
                    condition(Phase.FOUNDATION_ONLY, True)
                with self.assertRaises(subject.ModuleAValidationErrorV1):
                    condition(Phase.FOUNDATION_ONLY, override=False)

    def test_conditions_reject_non_nominal_phases(self) -> None:
        for value in ("FOUNDATION_ONLY", State.FOUNDATION_ONLY, None, 1, False):
            for condition in (
                subject.controller_present_v1,
                subject.bootstrap_signal_active_v1,
            ):
                with self.subTest(value=value, condition=condition.__name__):
                    with self.assertRaises(subject.ModuleAValidationErrorV1):
                        condition(value)


class RegistryTests(unittest.TestCase):
    def test_registry_has_exactly_twelve_ids(self) -> None:
        registry = subject.logical_resource_registry_v1()
        self.assertIsInstance(registry, tuple)
        self.assertEqual(len(registry), 12)
        self.assertEqual(
            frozenset(record.logical_id.value for record in registry),
            EXPECTED_RESOURCE_IDS,
        )

    def test_registry_category_counts_are_exact(self) -> None:
        registry = subject.logical_resource_registry_v1()
        counts = tuple(
            sum(record.resource_class is resource_class for record in registry)
            for resource_class in ResourceClass
        )
        self.assertEqual(counts, (6, 2, 2, 2))

    def test_registry_has_no_duplicate_logical_id(self) -> None:
        logical_ids = tuple(
            record.logical_id for record in subject.logical_resource_registry_v1()
        )
        self.assertEqual(len(logical_ids), len(frozenset(logical_ids)))

    def test_root_mapping_and_decommission_helper_are_absent(self) -> None:
        logical_id_values = tuple(
            record.logical_id.value for record in subject.logical_resource_registry_v1()
        )
        self.assertFalse(any("RootBlock" in value for value in logical_id_values))
        self.assertFalse(any("Decommission" in value for value in logical_id_values))

    def test_registry_order_is_canonical(self) -> None:
        values = tuple(
            record.logical_id.value for record in subject.logical_resource_registry_v1()
        )
        self.assertEqual(values, tuple(sorted(values)))

    def test_registry_masks_are_derived_from_condition_semantics(self) -> None:
        for record, phase in product(subject.logical_resource_registry_v1(), Phase):
            if record.resource_class in (
                ResourceClass.FOUNDATION_PERSISTENT,
                ResourceClass.RETAINED_EVIDENCE,
            ):
                expected = True
            elif record.resource_class is ResourceClass.COMPUTE_PHASE:
                expected = subject.controller_present_v1(phase)
            else:
                expected = subject.bootstrap_signal_active_v1(phase)
            self.assertEqual(phase in record.phase_presence_mask, expected)

    def test_protection_flags_are_exact(self) -> None:
        registry = subject.logical_resource_registry_v1()
        replacement_protected = frozenset(
            record.logical_id.value for record in registry if record.replacement_protected
        )
        retained_evidence = frozenset(
            record.logical_id.value
            for record in registry
            if record.retained_evidence_protected
        )
        self.assertEqual(replacement_protected, FOUNDATION_IDS)
        self.assertEqual(retained_evidence, frozenset({"EvidenceKey", "EvidenceVolume"}))

    def test_registry_is_deeply_immutable(self) -> None:
        registry = subject.logical_resource_registry_v1()
        with self.assertRaises(TypeError):
            registry[0] = registry[1]
        with self.assertRaises(FrozenInstanceError):
            registry[0].replacement_protected = False
        self.assertIsInstance(registry[0].phase_presence_mask, frozenset)

    def test_resource_record_construction_is_not_a_public_extension_surface(self) -> None:
        self.assertNotIn("LogicalResourceRecordV1", subject.__all__)
        with self.assertRaises(subject.ModuleAValidationErrorV1):
            subject.LogicalResourceRecordV1(
                logical_id=ResourceId.EVIDENCE_KEY,
                resource_class=ResourceClass.BOOTSTRAP_ONLY,
                phase_presence_mask=frozenset({Phase.SEALED_STOPPED}),
                replacement_protected=False,
                retained_evidence_protected=False,
            )
        tampered_payload = (
            ResourceId.EVIDENCE_KEY,
            ResourceClass.BOOTSTRAP_ONLY,
            frozenset({Phase.CONTROLLER_COMPUTE}),
            False,
            False,
        )
        with self.assertRaises(subject.ModuleAValidationErrorV1):
            subject.LogicalResourceRecordV1(
                subject._DTO_FACTORY_TOKEN,
                tampered_payload,
            )


class PhaseResourceSetTests(unittest.TestCase):
    def test_exact_phase_resource_sets_and_counts(self) -> None:
        expected = (
            (Phase.FOUNDATION_ONLY, FOUNDATION_IDS),
            (Phase.CONTROLLER_COMPUTE, FOUNDATION_IDS | COMPUTE_ADDITIONS),
            (Phase.SEALED_STOPPED, FOUNDATION_IDS | SEALED_ADDITIONS),
        )
        for phase, expected_ids in expected:
            with self.subTest(phase=phase):
                actual = id_values(subject.logical_resource_ids_for_phase_v1(phase))
                self.assertEqual(frozenset(actual), expected_ids)
                self.assertEqual(len(actual), len(expected_ids))
        self.assertEqual(
            tuple(len(subject.logical_resource_ids_for_phase_v1(phase)) for phase in Phase),
            (8, 12, 10),
        )

    def test_phase_resource_output_is_sorted_and_repeatable(self) -> None:
        for phase in Phase:
            expected = id_values(subject.logical_resource_ids_for_phase_v1(phase))
            self.assertEqual(expected, tuple(sorted(expected)))
            for _ in range(50):
                self.assertEqual(
                    id_values(subject.logical_resource_ids_for_phase_v1(phase)),
                    expected,
                )

    def test_persistent_intersection_is_exact(self) -> None:
        phase_sets = tuple(
            frozenset(id_values(subject.logical_resource_ids_for_phase_v1(phase)))
            for phase in Phase
        )
        intersection = phase_sets[0].intersection(*phase_sets[1:])
        self.assertEqual(intersection, FOUNDATION_IDS)
        self.assertEqual(
            frozenset(id_values(subject.protected_persistent_logical_ids_v1())),
            FOUNDATION_IDS,
        )

    def test_resource_set_api_rejects_override_and_non_nominal_phase(self) -> None:
        with self.assertRaises(subject.ModuleAValidationErrorV1):
            subject.logical_resource_ids_for_phase_v1("FOUNDATION_ONLY")
        with self.assertRaises(subject.ModuleAValidationErrorV1):
            subject.logical_resource_ids_for_phase_v1(Phase.FOUNDATION_ONLY, ())


class TransitionValidatorTests(unittest.TestCase):
    def test_legal_forward_transitions_are_exact(self) -> None:
        expected = (
            (State.NONEXISTENT, State.FOUNDATION_ONLY),
            (State.FOUNDATION_ONLY, State.CONTROLLER_COMPUTE),
            (State.CONTROLLER_COMPUTE, State.SEALED_STOPPED),
        )
        self.assertEqual(subject.legal_forward_transitions_v1(), expected)
        for previous, requested in expected:
            self.assertIs(
                review(previous, requested).transition_classification,
                Classification.LEGAL_FORWARD,
            )

    def test_all_sixteen_pairs_have_exact_classification(self) -> None:
        expected_rows = (
            (
                Classification.ILLEGAL_REPEAT,
                Classification.LEGAL_FORWARD,
                Classification.ILLEGAL_SKIP,
                Classification.ILLEGAL_SKIP,
            ),
            (
                Classification.ILLEGAL_OTHER,
                Classification.ILLEGAL_REPEAT,
                Classification.LEGAL_FORWARD,
                Classification.ILLEGAL_SKIP,
            ),
            (
                Classification.ILLEGAL_OTHER,
                Classification.ILLEGAL_REGRESSION,
                Classification.ILLEGAL_REPEAT,
                Classification.LEGAL_FORWARD,
            ),
            (
                Classification.ILLEGAL_OTHER,
                Classification.ILLEGAL_REGRESSION,
                Classification.ILLEGAL_REGRESSION,
                Classification.ILLEGAL_REPEAT,
            ),
        )
        states = tuple(State)
        pairs = tuple(product(states, repeat=2))
        self.assertEqual(len(pairs), 16)
        for previous, requested in pairs:
            with self.subTest(previous=previous, requested=requested):
                self.assertIs(
                    review(previous, requested).transition_classification,
                    expected_rows[states.index(previous)][states.index(requested)],
                )

    def test_exactly_three_of_sixteen_pairs_are_legal(self) -> None:
        classifications = tuple(
            review(previous, requested).transition_classification
            for previous, requested in product(State, repeat=2)
        )
        self.assertEqual(
            sum(item is Classification.LEGAL_FORWARD for item in classifications),
            3,
        )

    def test_repeat_skip_regression_and_other_counts_are_exact(self) -> None:
        classifications = tuple(
            review(previous, requested).transition_classification
            for previous, requested in product(State, repeat=2)
        )
        self.assertEqual(
            tuple(classifications.count(classification) for classification in Classification),
            (3, 3, 4, 3, 3),
        )

    def test_legal_graph_has_no_cycle_or_skip(self) -> None:
        states = tuple(State)
        for previous, requested in subject.legal_forward_transitions_v1():
            self.assertEqual(states.index(requested), states.index(previous) + 1)
        self.assertEqual(
            len(frozenset(subject.legal_forward_transitions_v1())),
            len(subject.legal_forward_transitions_v1()),
        )

    def test_illegal_reviews_are_non_actionable(self) -> None:
        for previous, requested in product(State, repeat=2):
            result = review(previous, requested)
            if result.transition_classification is Classification.LEGAL_FORWARD:
                continue
            with self.subTest(previous=previous, requested=requested):
                self.assertEqual(result.added_logical_ids, ())
                self.assertEqual(result.removed_logical_ids, ())
                self.assertEqual(result.unchanged_logical_ids, ())
                self.assertIs(result.metadata_expectation, Metadata.NONE)

    def test_unknown_transition_inputs_raise_fixed_public_error(self) -> None:
        invalid_pairs = (
            ("NONEXISTENT", State.FOUNDATION_ONLY),
            (State.NONEXISTENT, "FOUNDATION_ONLY"),
            (None, State.FOUNDATION_ONLY),
            (State.NONEXISTENT, Phase.FOUNDATION_ONLY),
        )
        for previous, requested in invalid_pairs:
            with self.subTest(previous=previous, requested=requested):
                with self.assertRaises(subject.ModuleAValidationErrorV1) as caught:
                    subject.review_controller_phase_transition_v1(previous, requested)
                self.assertNotIn(str(previous), str(caught.exception))
                self.assertNotIn(str(requested), str(caught.exception))


class TransitionDeltaTests(unittest.TestCase):
    def test_foundation_delta_is_exact(self) -> None:
        result = review(State.NONEXISTENT, State.FOUNDATION_ONLY)
        self.assertEqual(frozenset(id_values(result.added_logical_ids)), FOUNDATION_IDS)
        self.assertEqual(len(result.added_logical_ids), 8)
        self.assertEqual(result.removed_logical_ids, ())
        self.assertEqual(result.unchanged_logical_ids, ())
        self.assertIs(result.metadata_expectation, Metadata.NONE)

    def test_compute_delta_is_exact(self) -> None:
        result = review(State.FOUNDATION_ONLY, State.CONTROLLER_COMPUTE)
        self.assertEqual(frozenset(id_values(result.added_logical_ids)), COMPUTE_ADDITIONS)
        self.assertEqual(len(result.added_logical_ids), 4)
        self.assertEqual(result.removed_logical_ids, ())
        self.assertEqual(frozenset(id_values(result.unchanged_logical_ids)), FOUNDATION_IDS)
        self.assertIs(result.metadata_expectation, Metadata.NONE)

    def test_seal_delta_and_metadata_expectation_are_exact(self) -> None:
        result = review(State.CONTROLLER_COMPUTE, State.SEALED_STOPPED)
        self.assertEqual(result.added_logical_ids, ())
        self.assertEqual(
            frozenset(id_values(result.removed_logical_ids)),
            frozenset({"BootstrapWaitCondition", "BootstrapWaitHandle"}),
        )
        self.assertEqual(len(result.removed_logical_ids), 2)
        self.assertEqual(
            frozenset(id_values(result.unchanged_logical_ids)),
            FOUNDATION_IDS | SEALED_ADDITIONS,
        )
        self.assertIs(
            result.metadata_expectation,
            Metadata.CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL,
        )

    def test_metadata_expectation_occurs_on_one_transition_only(self) -> None:
        marked = tuple(
            (previous, requested)
            for previous, requested in product(State, repeat=2)
            if review(previous, requested).metadata_expectation
            is Metadata.CONTROLLER_METADATA_SIGNAL_REFERENCE_REMOVAL
        )
        self.assertEqual(marked, ((State.CONTROLLER_COMPUTE, State.SEALED_STOPPED),))

    def test_all_legal_delta_tuples_are_sorted(self) -> None:
        for previous, requested in subject.legal_forward_transitions_v1():
            result = review(previous, requested)
            for logical_ids in (
                result.added_logical_ids,
                result.removed_logical_ids,
                result.unchanged_logical_ids,
            ):
                self.assertEqual(id_values(logical_ids), tuple(sorted(id_values(logical_ids))))


class PersistentInvariantTests(unittest.TestCase):
    def test_all_three_phases_contain_the_persistent_eight(self) -> None:
        for phase in Phase:
            self.assertTrue(
                subject.phase_contains_all_protected_persistent_resources_v1(phase)
            )

    def test_no_legal_transition_removes_a_persistent_id(self) -> None:
        persistent = frozenset(subject.protected_persistent_logical_ids_v1())
        for previous, requested in subject.legal_forward_transitions_v1():
            self.assertFalse(
                persistent.intersection(review(previous, requested).removed_logical_ids)
            )

    def test_closed_persistent_invariant_helper_passes(self) -> None:
        self.assertTrue(subject.persistent_resource_invariants_hold_v1())


class PhaseProfileTests(unittest.TestCase):
    def test_profiles_are_exact_for_all_phases(self) -> None:
        for phase in Phase:
            profile = subject.create_controller_phase_profile_v1(phase)
            self.assertEqual(profile.artifact_module_version, subject.module_a_version_binding_v1()[0])
            self.assertIs(profile.phase, phase)
            self.assertEqual(profile.controller_present, subject.controller_present_v1(phase))
            self.assertEqual(
                profile.bootstrap_signal_active,
                subject.bootstrap_signal_active_v1(phase),
            )
            self.assertEqual(
                profile.logical_resource_ids,
                subject.logical_resource_ids_for_phase_v1(phase),
            )
            self.assertEqual(profile.logical_resource_count, len(profile.logical_resource_ids))

    def test_profile_is_deeply_immutable_and_hashable(self) -> None:
        profile = subject.create_controller_phase_profile_v1(Phase.CONTROLLER_COMPUTE)
        self.assertIsInstance(profile.logical_resource_ids, tuple)
        self.assertEqual(hash(profile), hash(profile))
        with self.assertRaises(FrozenInstanceError):
            profile.logical_resource_count = 0
        with self.assertRaises(TypeError):
            profile.logical_resource_ids[0] = ResourceId.EVIDENCE_KEY

    def test_profile_direct_construction_and_mapping_are_rejected(self) -> None:
        invalid_calls = (
            lambda: subject.ControllerPhaseProfileV1(),
            lambda: subject.ControllerPhaseProfileV1({"phase": Phase.FOUNDATION_ONLY}),
            lambda: subject.ControllerPhaseProfileV1(
                phase=Phase.FOUNDATION_ONLY,
                controller_present=False,
            ),
            lambda: subject.create_controller_phase_profile_v1(
                {"phase": "FOUNDATION_ONLY"}
            ),
        )
        for invalid_call in invalid_calls:
            with self.subTest(invalid_call=invalid_call):
                with self.assertRaises(subject.ModuleAValidationErrorV1):
                    invalid_call()

    def test_profile_rejects_caller_supplied_derived_values(self) -> None:
        invalid_calls = (
            lambda: subject.create_controller_phase_profile_v1(
                Phase.FOUNDATION_ONLY,
                False,
            ),
            lambda: subject.create_controller_phase_profile_v1(
                Phase.FOUNDATION_ONLY,
                controller_present=False,
            ),
            lambda: subject.create_controller_phase_profile_v1(
                Phase.FOUNDATION_ONLY,
                bootstrap_signal_active=False,
            ),
            lambda: subject.create_controller_phase_profile_v1(
                Phase.FOUNDATION_ONLY,
                logical_resource_ids=(),
            ),
            lambda: subject.create_controller_phase_profile_v1(
                Phase.FOUNDATION_ONLY,
                logical_resource_count=8,
            ),
        )
        for invalid_call in invalid_calls:
            with self.subTest(invalid_call=invalid_call):
                with self.assertRaises(subject.ModuleAValidationErrorV1):
                    invalid_call()

    def test_profile_constructor_revalidates_private_factory_payload(self) -> None:
        logical_ids = subject.logical_resource_ids_for_phase_v1(Phase.FOUNDATION_ONLY)
        tampered_payload = (
            subject.module_a_version_binding_v1()[0],
            Phase.FOUNDATION_ONLY,
            True,
            False,
            logical_ids,
            len(logical_ids),
        )
        with self.assertRaises(subject.ModuleAValidationErrorV1):
            subject.ControllerPhaseProfileV1(subject._DTO_FACTORY_TOKEN, tampered_payload)


class TransitionReviewDtoTests(unittest.TestCase):
    def test_transition_review_is_exact_deeply_immutable_and_hashable(self) -> None:
        result = review(State.FOUNDATION_ONLY, State.CONTROLLER_COMPUTE)
        self.assertEqual(result.artifact_module_version, subject.module_a_version_binding_v1()[0])
        self.assertIs(result.previous_stack_phase, State.FOUNDATION_ONLY)
        self.assertIs(result.requested_stack_phase, State.CONTROLLER_COMPUTE)
        self.assertIs(result.transition_classification, Classification.LEGAL_FORWARD)
        self.assertEqual(hash(result), hash(result))
        with self.assertRaises(FrozenInstanceError):
            result.transition_classification = Classification.ILLEGAL_OTHER
        for attribute_name in (
            "added_logical_ids",
            "removed_logical_ids",
            "unchanged_logical_ids",
        ):
            logical_ids = getattr(result, attribute_name)
            if logical_ids:
                with self.assertRaises(TypeError):
                    logical_ids[0] = ResourceId.EVIDENCE_KEY

    def test_transition_review_direct_construction_is_rejected(self) -> None:
        invalid_calls = (
            lambda: subject.ControllerPhaseTransitionReviewV1(),
            lambda: subject.ControllerPhaseTransitionReviewV1(
                {"previous": State.NONEXISTENT, "requested": State.FOUNDATION_ONLY}
            ),
            lambda: subject.ControllerPhaseTransitionReviewV1(
                previous_stack_phase=State.NONEXISTENT,
                requested_stack_phase=State.FOUNDATION_ONLY,
            ),
        )
        for invalid_call in invalid_calls:
            with self.subTest(invalid_call=invalid_call):
                with self.assertRaises(subject.ModuleAValidationErrorV1):
                    invalid_call()

    def test_transition_constructor_revalidates_private_factory_payload(self) -> None:
        tampered_payload = (
            subject.module_a_version_binding_v1()[0],
            State.NONEXISTENT,
            State.FOUNDATION_ONLY,
            Classification.ILLEGAL_OTHER,
            (),
            (),
            (),
            Metadata.NONE,
        )
        with self.assertRaises(subject.ModuleAValidationErrorV1):
            subject.ControllerPhaseTransitionReviewV1(
                subject._DTO_FACTORY_TOKEN,
                tampered_payload,
            )

    def test_profile_and_review_types_reject_subclassing(self) -> None:
        with self.assertRaises(subject.ModuleAValidationErrorV1):
            class ProfileExtension(subject.ControllerPhaseProfileV1):
                pass

        with self.assertRaises(subject.ModuleAValidationErrorV1):
            class ReviewExtension(subject.ControllerPhaseTransitionReviewV1):
                pass

        with self.assertRaises(subject.ModuleAValidationErrorV1):
            class ResourceExtension(subject.LogicalResourceRecordV1):
                pass


class VersionBindingTests(unittest.TestCase):
    def test_exact_read_only_version_binding(self) -> None:
        expected = (
            "CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_A_V1",
            "CANDIDATE_N_V4_CLOUDFORMATION_PHASE_AND_CHANGESET_CLARIFICATION_V1",
        )
        binding = subject.module_a_version_binding_v1()
        self.assertEqual(binding, expected)
        self.assertIs(binding, subject.module_a_version_binding_v1())
        self.assertEqual(subject.require_module_a_version_binding_v1(*binding), binding)
        with self.assertRaises(TypeError):
            binding[0] = "replacement"

    def test_version_mismatches_are_rejected_without_ranges(self) -> None:
        module_version, clarification_version = subject.module_a_version_binding_v1()
        invalid_bindings = (
            (module_version + "_V2", clarification_version),
            (module_version, clarification_version + "_V2"),
            ("*", clarification_version),
            (module_version, "*"),
            (None, clarification_version),
        )
        for invalid_binding in invalid_bindings:
            with self.subTest(invalid_binding=invalid_binding):
                with self.assertRaises(subject.ModuleAValidationErrorV1):
                    subject.require_module_a_version_binding_v1(*invalid_binding)


class ExhaustiveFiniteStateTests(unittest.TestCase):
    def test_all_four_states_and_sixteen_pairs_are_enumerated(self) -> None:
        states = tuple(State)
        pairs = tuple(product(states, repeat=2))
        self.assertEqual(len(states), 4)
        self.assertEqual(len(pairs), 16)
        self.assertTrue(all(type(review(*pair)) is subject.ControllerPhaseTransitionReviewV1 for pair in pairs))

    def test_all_three_deployed_profiles_are_enumerated(self) -> None:
        profiles = tuple(subject.create_controller_phase_profile_v1(phase) for phase in Phase)
        self.assertEqual(len(profiles), 3)
        self.assertEqual(tuple(profile.logical_resource_count for profile in profiles), (8, 12, 10))

    def test_all_thirty_six_registry_presence_cases_are_enumerated(self) -> None:
        cases = tuple(product(subject.logical_resource_registry_v1(), Phase))
        self.assertEqual(len(cases), 36)
        for record, phase in cases:
            membership = record.logical_id in subject.logical_resource_ids_for_phase_v1(phase)
            self.assertEqual(membership, phase in record.phase_presence_mask)

    def test_phase_presence_frequencies_are_exact(self) -> None:
        registry = subject.logical_resource_registry_v1()
        bootstrap_records = tuple(
            record for record in registry if record.resource_class is ResourceClass.BOOTSTRAP_ONLY
        )
        compute_records = tuple(
            record for record in registry if record.resource_class is ResourceClass.COMPUTE_PHASE
        )
        evidence_records = tuple(
            record for record in registry if record.resource_class is ResourceClass.RETAINED_EVIDENCE
        )
        self.assertTrue(all(len(record.phase_presence_mask) == 1 for record in bootstrap_records))
        self.assertTrue(all(len(record.phase_presence_mask) == 2 for record in compute_records))
        self.assertTrue(all(len(record.phase_presence_mask) == 3 for record in evidence_records))
        self.assertEqual(sum(subject.bootstrap_signal_active_v1(phase) for phase in Phase), 1)
        self.assertEqual(sum(subject.controller_present_v1(phase) for phase in Phase), 2)

    def test_repeated_in_process_results_have_no_state_leakage(self) -> None:
        baseline_registry = subject.logical_resource_registry_v1()
        baseline_profiles = tuple(subject.create_controller_phase_profile_v1(phase) for phase in Phase)
        baseline_reviews = tuple(review(*pair) for pair in product(State, repeat=2))
        for _ in range(100):
            self.assertIs(subject.logical_resource_registry_v1(), baseline_registry)
            self.assertEqual(
                tuple(subject.create_controller_phase_profile_v1(phase) for phase in Phase),
                baseline_profiles,
            )
            self.assertEqual(
                tuple(review(*pair) for pair in product(State, repeat=2)),
                baseline_reviews,
            )


class NegativeFixtureTests(unittest.TestCase):
    def test_named_negative_fixtures_are_exact_and_preserved(self) -> None:
        expected_names = (
            "skip_foundation",
            "skip_compute",
            "repeat_foundation",
            "repeat_compute",
            "repeat_sealed",
            "regress_compute_to_foundation",
            "regress_sealed_to_compute",
            "regress_sealed_to_foundation",
        )
        self.assertEqual(tuple(item[0] for item in INVALID_TRANSITION_FIXTURES_V1), expected_names)
        for name, previous, requested, expected_classification in INVALID_TRANSITION_FIXTURES_V1:
            with self.subTest(name=name):
                result = review(previous, requested)
                self.assertIs(result.transition_classification, expected_classification)
                self.assertIsNot(result.transition_classification, Classification.LEGAL_FORWARD)


if __name__ == "__main__":
    unittest.main()
