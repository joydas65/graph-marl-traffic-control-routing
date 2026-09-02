"""Exhaustive offline tests for controller-provisioning Module B."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
import importlib
from itertools import product
import json
from pathlib import Path
import sys
import unittest


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

module_a = importlib.import_module(
    "scripts.controller_provisioning.controller_provisioning_module_a_v1"
)
subject = importlib.import_module(
    "scripts.controller_provisioning.controller_provisioning_module_b_v1"
)


MainPhase = module_a.ControllerDeploymentPhaseV1
Kind = subject.StructuralTemplateKindV1
StagingPhase = subject.StagingAccessPhaseV1
Reason = subject.ModuleBValidationReasonV1


MODULE_B_ID = "CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_B_V1"
MODULE_A_ID = "CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_A_V1"
CLARIFICATION_ID = (
    "CANDIDATE_N_V4_CLOUDFORMATION_PHASE_AND_CHANGESET_CLARIFICATION_V1"
)
NON_DEPLOYABLE = "NON_DEPLOYABLE_STRUCTURAL_SKELETON"
SYNTHETIC_ACCESS_KEY_ID = "".join(
    ("A", "K", "I", "A", "ABCD", "EFGH", "IJKL", "MNOP")
)

EXPECTED_MAIN_TYPES = {
    "BootstrapWaitCondition": "AWS::CloudFormation::WaitCondition",
    "BootstrapWaitHandle": "AWS::CloudFormation::WaitConditionHandle",
    "ControllerBudget": "AWS::Budgets::Budget",
    "ControllerCommandDocument": "AWS::SSM::Document",
    "ControllerHostRole": "AWS::IAM::Role",
    "ControllerInstance": "AWS::EC2::Instance",
    "ControllerInstanceProfile": "AWS::IAM::InstanceProfile",
    "ControllerSecurityGroup": "AWS::EC2::SecurityGroup",
    "EvidenceKey": "AWS::KMS::Key",
    "EvidenceVolume": "AWS::EC2::Volume",
    "EvidenceVolumeAttachment": "AWS::EC2::VolumeAttachment",
    "ExperimentRuntimeRole": "AWS::IAM::Role",
}

EXPECTED_UNCONDITIONAL_IDS = frozenset(
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
EXPECTED_CONTROLLER_IDS = frozenset(
    {"ControllerInstance", "EvidenceVolumeAttachment"}
)
EXPECTED_BOOTSTRAP_IDS = frozenset(
    {"BootstrapWaitCondition", "BootstrapWaitHandle"}
)
EXPECTED_MAIN_IDS = (
    EXPECTED_UNCONDITIONAL_IDS
    | EXPECTED_CONTROLLER_IDS
    | EXPECTED_BOOTSTRAP_IDS
)
EXPECTED_DEPENDENCY_EDGES = frozenset(
    {
        ("EvidenceVolumeAttachment", "ControllerInstance"),
        ("EvidenceVolumeAttachment", "EvidenceVolume"),
        ("BootstrapWaitCondition", "EvidenceVolumeAttachment"),
    }
)
EXPECTED_STAGING_TYPES = {
    "StagingBucketPolicy": "AWS::S3::BucketPolicy",
    "StagingBundleBucket": "AWS::S3::Bucket",
}


def decoded(canonical_bytes: bytes) -> dict[str, object]:
    result = json.loads(canonical_bytes.decode("utf-8"))
    if type(result) is not dict:
        raise AssertionError("expected a JSON object")
    return result


def main_model(
    phase: MainPhase = MainPhase.FOUNDATION_ONLY,
) -> dict[str, object]:
    return deepcopy(subject.build_main_structural_model_v1(phase))


def staging_model(
    phase: StagingPhase = StagingPhase.UPLOAD_ONLY,
) -> dict[str, object]:
    return deepcopy(subject.build_staging_structural_model_v1(phase))


def validation_for_model(
    kind: Kind,
    profile: object,
    model: dict[str, object],
) -> subject.ModuleBValidationResultV1:
    return subject.validate_structural_artifact_v1(
        kind,
        profile,
        subject.canonicalize_structural_model_v1(model),
    )


def evaluate_condition(expression: object, phase: MainPhase) -> object:
    if type(expression) is bool or type(expression) is str:
        return expression
    if type(expression) is not dict or len(expression) != 1:
        return None
    if "Ref" in expression:
        if expression["Ref"] == "ControllerDeploymentPhase":
            return phase.value
        return None
    if "Fn::Equals" in expression:
        operands = expression["Fn::Equals"]
        if type(operands) is not list or len(operands) != 2:
            return None
        left = evaluate_condition(operands[0], phase)
        right = evaluate_condition(operands[1], phase)
        if left is None or right is None:
            return None
        return left == right
    if "Fn::Or" in expression:
        operands = expression["Fn::Or"]
        if type(operands) is not list or not operands:
            return None
        values = tuple(evaluate_condition(item, phase) for item in operands)
        if any(type(item) is not bool for item in values):
            return None
        return any(values)
    return None


def active_main_ids(model: dict[str, object], phase: MainPhase) -> tuple[str, ...]:
    conditions = model["Conditions"]
    resources = model["Resources"]
    active: list[str] = []
    for logical_id in sorted(resources):
        condition = resources[logical_id].get("Condition")
        if condition is None or evaluate_condition(conditions[condition], phase) is True:
            active.append(logical_id)
    return tuple(active)


def dependency_edges(model: dict[str, object]) -> frozenset[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for logical_id, node in model["Resources"].items():
        for target in node.get("DependsOn", []):
            edges.add((logical_id, target))
    return frozenset(edges)


def assert_all_keys_canonical(test: unittest.TestCase, value: object) -> None:
    if type(value) is dict:
        test.assertEqual(tuple(value), tuple(sorted(value)))
        for child in value.values():
            assert_all_keys_canonical(test, child)
    elif type(value) is list:
        for child in value:
            assert_all_keys_canonical(test, child)


def _extra_resource(model: dict[str, object]) -> None:
    model["Resources"]["UnexpectedResource"] = {
        "Metadata": {"StructuralClass": "FOUNDATION_PERSISTENT"},
        "Type": "AWS::EC2::Volume",
    }


def _missing_foundation_resource(model: dict[str, object]) -> None:
    del model["Resources"]["ControllerBudget"]


def _missing_evidence_key(model: dict[str, object]) -> None:
    del model["Resources"]["EvidenceKey"]


def _missing_evidence_volume(model: dict[str, object]) -> None:
    del model["Resources"]["EvidenceVolume"]


def _wrong_resource_type(model: dict[str, object]) -> None:
    model["Resources"]["ControllerBudget"]["Type"] = "AWS::EC2::Volume"


def _controller_present_during_foundation(model: dict[str, object]) -> None:
    model["Conditions"]["ControllerPresent"] = True


def _controller_absent_during_compute(model: dict[str, object]) -> None:
    model["Conditions"]["ControllerPresent"] = False


def _bootstrap_present_during_sealed(model: dict[str, object]) -> None:
    model["Conditions"]["BootstrapSignalActive"] = True


def _bootstrap_absent_during_compute(model: dict[str, object]) -> None:
    model["Conditions"]["BootstrapSignalActive"] = False


def _wrong_deletion_policy(model: dict[str, object]) -> None:
    model["Resources"]["EvidenceKey"]["DeletionPolicy"] = "Delete"


def _wrong_update_replace_policy(model: dict[str, object]) -> None:
    model["Resources"]["EvidenceVolume"]["UpdateReplacePolicy"] = "Delete"


def _retention_on_wrong_resource(model: dict[str, object]) -> None:
    model["Resources"]["ControllerBudget"]["DeletionPolicy"] = "Retain"


def _unknown_condition(model: dict[str, object]) -> None:
    model["Conditions"]["UnexpectedCondition"] = False


def _unknown_parameter(model: dict[str, object]) -> None:
    model["Parameters"]["UnexpectedParameter"] = {"Type": "String"}


def _dependency_on_unknown_resource(model: dict[str, object]) -> None:
    model["Resources"]["EvidenceVolumeAttachment"]["DependsOn"] = [
        "ControllerInstance",
        "MissingResource",
    ]


def _dependency_cycle(model: dict[str, object]) -> None:
    model["Resources"]["ControllerInstance"]["DependsOn"] = [
        "BootstrapWaitCondition"
    ]


def _output_present(model: dict[str, object]) -> None:
    model["Outputs"] = {}


def _transform_present(model: dict[str, object]) -> None:
    model["Transform"] = "ExampleTransform"


def _custom_resource_present(model: dict[str, object]) -> None:
    model["Resources"]["UnexpectedCustom"] = {
        "Type": "Custom::Unexpected",
    }


def _nested_stack_present(model: dict[str, object]) -> None:
    model["Resources"]["UnexpectedNestedStack"] = {
        "Type": "AWS::CloudFormation::Stack",
    }


def _physical_cloud_id_leakage(model: dict[str, object]) -> None:
    model["Description"] = "ami-0123456789abcdef0"


def _credential_like_value(model: dict[str, object]) -> None:
    model["Description"] = SYNTHETIC_ACCESS_KEY_ID


def _wait_handle_url_leakage(model: dict[str, object]) -> None:
    model["Metadata"]["PhysicalWaitHandleUrl"] = (
        "https://cloudformation-waitcondition.example/signal"
    )


def _deployable_status_claim(model: dict[str, object]) -> None:
    model["Metadata"]["Artifact"]["DeploymentReadiness"] = "DEPLOYABLE"


def _staging_third_resource(model: dict[str, object]) -> None:
    model["Resources"]["UnexpectedThirdResource"] = {
        "Metadata": {},
        "Type": "AWS::S3::Bucket",
    }


def _host_read_in_upload_only(model: dict[str, object]) -> None:
    model["Resources"]["StagingBucketPolicy"]["Metadata"][
        "StructuralPolicyState"
    ] = subject.StagingPolicyStateV1.EXACTLY_ONE_FUTURE_HOST_EXACT_OBJECT_READ_GRANT.value


NEGATIVE_FIXTURES_V1 = (
    (
        "extra_resource",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _extra_resource,
        Reason.UNEXPECTED_LOGICAL_RESOURCE,
    ),
    (
        "missing_foundation_resource",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _missing_foundation_resource,
        Reason.MISSING_PROTECTED_RESOURCE,
    ),
    (
        "missing_evidence_key",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _missing_evidence_key,
        Reason.MISSING_PROTECTED_RESOURCE,
    ),
    (
        "missing_evidence_volume",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _missing_evidence_volume,
        Reason.MISSING_PROTECTED_RESOURCE,
    ),
    (
        "wrong_resource_type",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _wrong_resource_type,
        Reason.RESOURCE_TYPE_MISMATCH,
    ),
    (
        "controller_present_during_foundation",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _controller_present_during_foundation,
        Reason.CONDITION_TRUTH_TABLE_MISMATCH,
    ),
    (
        "controller_absent_during_compute",
        Kind.MAIN,
        MainPhase.CONTROLLER_COMPUTE,
        _controller_absent_during_compute,
        Reason.CONDITION_TRUTH_TABLE_MISMATCH,
    ),
    (
        "bootstrap_signal_present_in_sealed_phase",
        Kind.MAIN,
        MainPhase.SEALED_STOPPED,
        _bootstrap_present_during_sealed,
        Reason.CONDITION_TRUTH_TABLE_MISMATCH,
    ),
    (
        "bootstrap_signal_absent_in_compute",
        Kind.MAIN,
        MainPhase.CONTROLLER_COMPUTE,
        _bootstrap_absent_during_compute,
        Reason.CONDITION_TRUTH_TABLE_MISMATCH,
    ),
    (
        "wrong_deletion_policy",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _wrong_deletion_policy,
        Reason.DELETION_POLICY_MISMATCH,
    ),
    (
        "wrong_update_replace_policy",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _wrong_update_replace_policy,
        Reason.UPDATE_REPLACE_POLICY_MISMATCH,
    ),
    (
        "retained_policy_added_to_wrong_resource",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _retention_on_wrong_resource,
        Reason.UNEXPECTED_RETENTION_ATTRIBUTE,
    ),
    (
        "unknown_condition",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _unknown_condition,
        Reason.UNKNOWN_CONDITION,
    ),
    (
        "unknown_parameter",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _unknown_parameter,
        Reason.UNKNOWN_PARAMETER,
    ),
    (
        "dependency_on_unknown_resource",
        Kind.MAIN,
        MainPhase.CONTROLLER_COMPUTE,
        _dependency_on_unknown_resource,
        Reason.DEPENDENCY_TARGET_UNKNOWN,
    ),
    (
        "dependency_cycle",
        Kind.MAIN,
        MainPhase.CONTROLLER_COMPUTE,
        _dependency_cycle,
        Reason.DEPENDENCY_CYCLE,
    ),
    (
        "output_present",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _output_present,
        Reason.FORBIDDEN_OUTPUT_SECTION,
    ),
    (
        "transform_present",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _transform_present,
        Reason.FORBIDDEN_TRANSFORM,
    ),
    (
        "custom_resource_present",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _custom_resource_present,
        Reason.FORBIDDEN_CUSTOM_RESOURCE,
    ),
    (
        "nested_stack_present",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _nested_stack_present,
        Reason.FORBIDDEN_NESTED_STACK,
    ),
    (
        "physical_cloud_id_leakage",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _physical_cloud_id_leakage,
        Reason.SENSITIVE_AMI_PHYSICAL_ID,
    ),
    (
        "credential_like_value",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _credential_like_value,
        Reason.SENSITIVE_ACCESS_KEY,
    ),
    (
        "wait_handle_url_leakage",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _wait_handle_url_leakage,
        Reason.SENSITIVE_WAIT_HANDLE_URL,
    ),
    (
        "deployable_status_claim",
        Kind.MAIN,
        MainPhase.FOUNDATION_ONLY,
        _deployable_status_claim,
        Reason.DEPLOYMENT_READINESS_CLAIM_FORBIDDEN,
    ),
    (
        "staging_third_resource",
        Kind.STAGING,
        StagingPhase.UPLOAD_ONLY,
        _staging_third_resource,
        Reason.UNEXPECTED_LOGICAL_RESOURCE,
    ),
    (
        "host_read_staging_grant_in_upload_only_state",
        Kind.STAGING,
        StagingPhase.UPLOAD_ONLY,
        _host_read_in_upload_only,
        Reason.STAGING_ACCESS_POLICY_STATE_MISMATCH,
    ),
)


class ModuleABindingTests(unittest.TestCase):
    def test_module_a_dependency_is_the_exact_frozen_contract(self) -> None:
        self.assertEqual(
            module_a.module_a_version_binding_v1(),
            (MODULE_A_ID, CLARIFICATION_ID),
        )
        self.assertEqual(
            module_a.require_module_a_version_binding_v1(
                MODULE_A_ID,
                CLARIFICATION_ID,
            ),
            (MODULE_A_ID, CLARIFICATION_ID),
        )

    def test_module_b_binding_is_exact(self) -> None:
        expected = (MODULE_B_ID, MODULE_A_ID, CLARIFICATION_ID)
        self.assertEqual(subject.module_b_version_binding_v1(), expected)
        self.assertEqual(subject.require_module_b_version_binding_v1(*expected), expected)

    def test_module_b_binding_rejects_mismatch_range_and_wildcard(self) -> None:
        invalid = (
            (MODULE_B_ID + "_V2", MODULE_A_ID, CLARIFICATION_ID),
            (MODULE_B_ID, MODULE_A_ID + "_V2", CLARIFICATION_ID),
            (MODULE_B_ID, MODULE_A_ID, CLARIFICATION_ID + "_V2"),
            ("*", MODULE_A_ID, CLARIFICATION_ID),
            (MODULE_B_ID, ">=A_V1", CLARIFICATION_ID),
        )
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(subject.ModuleBValidationErrorV1):
                    subject.require_module_b_version_binding_v1(*candidate)

    def test_main_api_consumes_module_a_nominal_phase(self) -> None:
        for phase in MainPhase:
            self.assertIsInstance(subject.build_main_structural_model_v1(phase), dict)
        for invalid in ("FOUNDATION_ONLY", None, False, StagingPhase.UPLOAD_ONLY):
            with self.subTest(invalid=invalid):
                with self.assertRaises(subject.ModuleBValidationErrorV1):
                    subject.build_main_structural_model_v1(invalid)

    def test_module_a_registry_is_the_declared_main_registry(self) -> None:
        from_a = frozenset(
            record.logical_id.value
            for record in module_a.logical_resource_registry_v1()
        )
        self.assertEqual(from_a, EXPECTED_MAIN_IDS)
        for phase in MainPhase:
            self.assertEqual(
                frozenset(main_model(phase)["Resources"]),
                from_a,
            )


class ClosedTypeAndImmutabilityTests(unittest.TestCase):
    def test_public_enums_are_exact_and_have_no_aliases(self) -> None:
        expected = {
            subject.StructuralTemplateKindV1: ("MAIN", "STAGING"),
            subject.DeploymentReadinessV1: (NON_DEPLOYABLE,),
            subject.StagingAccessPhaseV1: (
                "UPLOAD_ONLY",
                "HOST_EXACT_OBJECT_READ",
            ),
            subject.StagingPolicyStateV1: (
                "NO_CONTROLLER_HOST_OBJECT_READ_GRANT",
                "EXACTLY_ONE_FUTURE_HOST_EXACT_OBJECT_READ_GRANT",
            ),
            subject.DeferredResolutionV1: (
                "STRUCTURE_ONLY",
                "REQUIRES_PRIVILEGED_POLICY_MODULE",
                "REQUIRES_BOOTSTRAP_MODULE",
                "REQUIRES_PRIVATE_MANIFEST_BINDING",
                "IMPLEMENTED_IN_LATER_PRIVILEGED_TEMPLATE_MODULE",
                "REQUIRED_LATER_NOT_IMPLEMENTED",
            ),
        }
        for enum_type, values in expected.items():
            with self.subTest(enum_type=enum_type.__name__):
                self.assertEqual(tuple(item.value for item in enum_type), values)
                self.assertEqual(len(enum_type.__members__), len(values))

    def test_enum_aliases_and_free_form_values_are_rejected(self) -> None:
        invalid_rows = (
            (subject.StructuralTemplateKindV1, "main"),
            (subject.DeploymentReadinessV1, "DEPLOYABLE"),
            (subject.StagingAccessPhaseV1, "upload_only"),
            (subject.StagingAccessPhaseV1, "HOST_READ"),
            (subject.DeferredResolutionV1, "TODO"),
            (subject.DeferredResolutionV1, "later"),
        )
        for enum_type, value in invalid_rows:
            with self.subTest(enum_type=enum_type.__name__, value=value):
                with self.assertRaises(ValueError):
                    enum_type(value)

    def test_validation_result_is_frozen_and_internally_consistent(self) -> None:
        result = subject.ModuleBValidationResultV1(True, Reason.VALID)
        with self.assertRaises(FrozenInstanceError):
            result.is_valid = False
        for is_valid, reason in ((True, Reason.INVALID_INPUT), (False, Reason.VALID)):
            with self.subTest(is_valid=is_valid, reason=reason):
                with self.assertRaises(subject.ModuleBValidationErrorV1):
                    subject.ModuleBValidationResultV1(is_valid, reason)

    def test_staging_delta_is_frozen_and_tuple_only(self) -> None:
        result = subject.staging_structural_delta_v1()
        for field_name in (
            "create_added_logical_ids",
            "update_added_logical_ids",
            "update_removed_logical_ids",
            "update_modified_logical_ids",
            "update_replaced_logical_ids",
        ):
            self.assertIsInstance(getattr(result, field_name), tuple)
        with self.assertRaises(FrozenInstanceError):
            result.update_modified_logical_ids = ()


class CanonicalRenderingTests(unittest.TestCase):
    def test_all_five_profiles_render_valid_utf8_bytes(self) -> None:
        rows = tuple((Kind.MAIN, phase) for phase in MainPhase) + tuple(
            (Kind.STAGING, phase) for phase in StagingPhase
        )
        for kind, phase in rows:
            with self.subTest(kind=kind, phase=phase):
                rendered = (
                    subject.render_main_structural_template_v1(phase)
                    if kind is Kind.MAIN
                    else subject.render_staging_structural_template_v1(phase)
                )
                self.assertIs(type(rendered), bytes)
                rendered.decode("utf-8")
                review = subject.validate_structural_artifact_v1(
                    kind,
                    phase,
                    rendered,
                )
                self.assertTrue(review.is_valid)
                self.assertIs(review.reason, Reason.VALID)

    def test_rendering_uses_compact_sorted_json_and_one_lf(self) -> None:
        rendered_rows = tuple(
            subject.render_main_structural_template_v1(phase)
            for phase in MainPhase
        ) + tuple(
            subject.render_staging_structural_template_v1(phase)
            for phase in StagingPhase
        )
        for rendered in rendered_rows:
            with self.subTest(size=len(rendered)):
                self.assertTrue(rendered.endswith(b"\n"))
                self.assertFalse(rendered.endswith(b"\n\n"))
                self.assertNotIn(b"\r", rendered)
                self.assertFalse(rendered.startswith(b"\xef\xbb\xbf"))
                model = json.loads(rendered.decode("utf-8"))
                expected = (
                    json.dumps(
                        model,
                        allow_nan=False,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8")
                self.assertEqual(rendered, expected)
                assert_all_keys_canonical(self, model)

    def test_canonicalizer_preserves_utf8_without_ascii_escaping(self) -> None:
        rendered = subject.canonicalize_structural_model_v1({"clé": "välue"})
        self.assertIn("clé".encode("utf-8"), rendered)
        self.assertIn("välue".encode("utf-8"), rendered)
        self.assertNotIn(b"\\u", rendered)

    def test_noncanonical_json_is_rejected(self) -> None:
        model = main_model()
        noncanonical = json.dumps(model, indent=2).encode("utf-8")
        result = subject.validate_structural_artifact_v1(
            Kind.MAIN,
            MainPhase.FOUNDATION_ONLY,
            noncanonical,
        )
        self.assertFalse(result.is_valid)
        self.assertIs(result.reason, Reason.NON_CANONICAL_JSON)

    def test_duplicate_json_key_is_rejected(self) -> None:
        result = subject.validate_structural_artifact_v1(
            Kind.MAIN,
            MainPhase.FOUNDATION_ONLY,
            b'{"x":1,"x":2}\n',
        )
        self.assertFalse(result.is_valid)
        self.assertIs(result.reason, Reason.DUPLICATE_JSON_KEY)

    def test_malformed_json_and_utf8_are_rejected(self) -> None:
        deeply_nested = (
            b'{"x":' + (b"[" * 600) + b"0" + (b"]" * 600) + b"}\n"
        )
        values = (
            (b"{\n", Reason.MALFORMED_JSON),
            (b"\xff\n", Reason.MALFORMED_JSON),
            (b'{"x":NaN}\n', Reason.MALFORMED_JSON),
            (b'{"x":1e309}\n', Reason.MALFORMED_JSON),
            (deeply_nested, Reason.INVALID_INPUT),
        )
        for value, expected_reason in values:
            with self.subTest(value=value):
                result = subject.validate_structural_artifact_v1(
                    Kind.MAIN,
                    MainPhase.FOUNDATION_ONLY,
                    value,
                )
                self.assertFalse(result.is_valid)
                self.assertIs(result.reason, expected_reason)

    def test_non_object_json_is_rejected(self) -> None:
        result = subject.validate_structural_artifact_v1(
            Kind.MAIN,
            MainPhase.FOUNDATION_ONLY,
            b"[]\n",
        )
        self.assertFalse(result.is_valid)
        self.assertIs(result.reason, Reason.INVALID_INPUT)

    def test_canonicalizer_rejects_non_model_and_non_json_values(self) -> None:
        for value in ([], (), None, "{}"):
            with self.subTest(value=value):
                with self.assertRaises(subject.ModuleBValidationErrorV1):
                    subject.canonicalize_structural_model_v1(value)
        for model in ({"x": object()}, {"x": float("nan")}):
            with self.subTest(model=model):
                with self.assertRaises(subject.ModuleBValidationErrorV1):
                    subject.canonicalize_structural_model_v1(model)

    def test_builders_return_fresh_models(self) -> None:
        first = main_model(MainPhase.FOUNDATION_ONLY)
        second = main_model(MainPhase.FOUNDATION_ONLY)
        first["Description"] = "mutated"
        first["Resources"]["ControllerBudget"]["Type"] = "mutated"
        self.assertNotEqual(first, second)
        self.assertEqual(
            second,
            subject.build_main_structural_model_v1(MainPhase.FOUNDATION_ONLY),
        )


class MainTemplateStructureTests(unittest.TestCase):
    def test_main_top_level_schema_is_exact(self) -> None:
        expected = {
            "AWSTemplateFormatVersion",
            "Description",
            "Metadata",
            "Parameters",
            "Conditions",
            "Resources",
        }
        for phase in MainPhase:
            self.assertEqual(set(main_model(phase)), expected)

    def test_main_metadata_binds_versions_profile_and_readiness(self) -> None:
        for phase in MainPhase:
            artifact = main_model(phase)["Metadata"]["Artifact"]
            self.assertEqual(
                artifact,
                {
                    "DeploymentReadiness": NON_DEPLOYABLE,
                    "ModuleABinding": MODULE_A_ID,
                    "ModuleBVersion": MODULE_B_ID,
                    "PhaseClarificationBinding": CLARIFICATION_ID,
                    "RenderProfile": phase.value,
                    "TemplateKind": "MAIN",
                },
            )

    def test_main_phase_parameter_is_exact_and_derived_from_module_a(self) -> None:
        expected = {
            "ControllerDeploymentPhase": {
                "AllowedValues": [phase.value for phase in MainPhase],
                "Type": "String",
            }
        }
        for phase in MainPhase:
            parameters = main_model(phase)["Parameters"]
            self.assertEqual(parameters, expected)
            self.assertNotIn("Default", parameters["ControllerDeploymentPhase"])

    def test_condition_names_and_truth_are_exact(self) -> None:
        for rendered_phase in MainPhase:
            conditions = main_model(rendered_phase)["Conditions"]
            self.assertEqual(
                set(conditions),
                {"ControllerPresent", "BootstrapSignalActive"},
            )
            for evaluated_phase in MainPhase:
                with self.subTest(
                    rendered_phase=rendered_phase,
                    evaluated_phase=evaluated_phase,
                ):
                    self.assertIs(
                        evaluate_condition(
                            conditions["ControllerPresent"],
                            evaluated_phase,
                        ),
                        module_a.controller_present_v1(evaluated_phase),
                    )
                    self.assertIs(
                        evaluate_condition(
                            conditions["BootstrapSignalActive"],
                            evaluated_phase,
                        ),
                        module_a.bootstrap_signal_active_v1(evaluated_phase),
                    )

    def test_main_logical_ids_and_resource_types_are_exact(self) -> None:
        for phase in MainPhase:
            resources = main_model(phase)["Resources"]
            self.assertEqual(set(resources), EXPECTED_MAIN_IDS)
            self.assertEqual(
                {logical_id: node["Type"] for logical_id, node in resources.items()},
                EXPECTED_MAIN_TYPES,
            )

    def test_resource_condition_assignments_are_exact(self) -> None:
        resources = main_model()["Resources"]
        self.assertEqual(
            frozenset(
                logical_id
                for logical_id, node in resources.items()
                if "Condition" not in node
            ),
            EXPECTED_UNCONDITIONAL_IDS,
        )
        self.assertEqual(
            frozenset(
                logical_id
                for logical_id, node in resources.items()
                if node.get("Condition") == "ControllerPresent"
            ),
            EXPECTED_CONTROLLER_IDS,
        )
        self.assertEqual(
            frozenset(
                logical_id
                for logical_id, node in resources.items()
                if node.get("Condition") == "BootstrapSignalActive"
            ),
            EXPECTED_BOOTSTRAP_IDS,
        )

    def test_retention_attributes_are_exact(self) -> None:
        resources = main_model()["Resources"]
        retained = frozenset(
            logical_id
            for logical_id, node in resources.items()
            if node.get("DeletionPolicy") == "Retain"
            and node.get("UpdateReplacePolicy") == "Retain"
        )
        self.assertEqual(retained, frozenset({"EvidenceKey", "EvidenceVolume"}))
        for logical_id, node in resources.items():
            if logical_id in retained:
                continue
            self.assertNotIn("DeletionPolicy", node)
            self.assertNotIn("UpdateReplacePolicy", node)

    def test_later_retention_controls_are_explicitly_unimplemented(self) -> None:
        expected = {
            "RetainExceptOnCreate": "REQUIRED_LATER_NOT_IMPLEMENTED",
            "StackPolicy": "REQUIRED_LATER_NOT_IMPLEMENTED",
            "TerminationProtection": "REQUIRED_LATER_NOT_IMPLEMENTED",
        }
        for phase in MainPhase:
            self.assertEqual(main_model(phase)["Metadata"]["DeferredControls"], expected)

    def test_dependency_edges_are_exact_and_targets_exist(self) -> None:
        for phase in MainPhase:
            model = main_model(phase)
            edges = dependency_edges(model)
            self.assertEqual(edges, EXPECTED_DEPENDENCY_EDGES)
            ids = frozenset(model["Resources"])
            self.assertTrue(all(source in ids and target in ids for source, target in edges))
            self.assertFalse(any(source == target for source, target in edges))

    def test_dependency_graph_is_acyclic(self) -> None:
        model = main_model()
        edges = dependency_edges(model)
        adjacency = {
            logical_id: frozenset(target for source, target in edges if source == logical_id)
            for logical_id in model["Resources"]
        }

        def reaches(start: str, target: str, seen: frozenset[str]) -> bool:
            if start == target and seen:
                return True
            if start in seen:
                return False
            next_seen = seen | {start}
            return any(reaches(child, target, next_seen) for child in adjacency[start])

        for logical_id in adjacency:
            self.assertFalse(reaches(logical_id, logical_id, frozenset()))

    def test_bootstrap_structure_is_exact(self) -> None:
        resources = main_model()["Resources"]
        handle = resources["BootstrapWaitHandle"]
        wait = resources["BootstrapWaitCondition"]
        self.assertEqual(handle["Type"], "AWS::CloudFormation::WaitConditionHandle")
        self.assertEqual(handle["Condition"], "BootstrapSignalActive")
        self.assertIs(
            handle["Metadata"]["StructuralExpectations"]["PhysicalSignalUrlRendered"],
            False,
        )
        self.assertEqual(wait["Type"], "AWS::CloudFormation::WaitCondition")
        self.assertEqual(wait["Condition"], "BootstrapSignalActive")
        self.assertEqual(wait["DependsOn"], ["EvidenceVolumeAttachment"])
        expectations = wait["Metadata"]["StructuralExpectations"]
        self.assertIs(type(expectations["Count"]), int)
        self.assertEqual(expectations["Count"], 1)
        self.assertIs(type(expectations["TimeoutSeconds"]), int)
        self.assertEqual(expectations["TimeoutSeconds"], 28800)

    def test_controller_bootstrap_indirection_is_exact(self) -> None:
        metadata = main_model()["Resources"]["ControllerInstance"]["Metadata"]
        self.assertEqual(
            metadata["CandidateNBootstrapSignalUrl"],
            {
                "Fn::If": [
                    "BootstrapSignalActive",
                    {"Ref": "BootstrapWaitHandle"},
                    "SEALED_STOPPED",
                ]
            },
        )

    def test_controller_structural_requirements_are_closed(self) -> None:
        requirements = main_model()["Resources"]["ControllerInstance"]["Metadata"][
            "StructuralRequirements"
        ]
        self.assertEqual(
            set(requirements),
            {
                "ExactFrozenAmi",
                "ImdsV2Controls",
                "InstanceClass",
                "InstanceProfileBinding",
                "PublicAddressProfile",
                "RootBlockDeviceMapping",
                "SecurityGroupBinding",
                "StandardCreditMode",
                "SubnetBinding",
            },
        )
        self.assertEqual(requirements["InstanceClass"]["RequiredValue"], "t3.small")
        closed = frozenset(item.value for item in subject.DeferredResolutionV1)
        for key, value in requirements.items():
            if key == "InstanceClass":
                self.assertIn(value["Resolution"], closed)
            else:
                self.assertIn(value, closed)

    def test_privileged_content_is_only_closed_deferral_metadata(self) -> None:
        model = main_model()
        closed = frozenset(item.value for item in subject.DeferredResolutionV1)
        deferred_values: list[str] = []
        for node in model["Resources"].values():
            self.assertNotIn("Properties", node)
            deferred = node["Metadata"].get("DeferredContent", {})
            deferred_values.extend(deferred.values())
        self.assertTrue(deferred_values)
        self.assertTrue(all(value in closed for value in deferred_values))
        rendered_lower = subject.canonicalize_structural_model_v1(model).decode().lower()
        for free_form in ('"todo"', '"later"', '"tbd"', '"fixme"'):
            self.assertNotIn(free_form, rendered_lower)

    def test_prohibited_standalone_resources_are_absent(self) -> None:
        prohibited_fragments = (
            "RootBlock",
            "Eip",
            "NatGateway",
            "Endpoint",
            "KeyPair",
            "LoadBalancer",
            "LogGroup",
            "Snapshot",
            "Backup",
            "Custom",
            "NestedStack",
            "Decommission",
        )
        ids = tuple(main_model()["Resources"])
        for fragment in prohibited_fragments:
            self.assertFalse(any(fragment in logical_id for logical_id in ids))


class StagingTemplateTests(unittest.TestCase):
    def test_staging_top_level_and_resource_model_are_exact(self) -> None:
        for phase in StagingPhase:
            model = staging_model(phase)
            self.assertEqual(
                set(model),
                {
                    "AWSTemplateFormatVersion",
                    "Description",
                    "Metadata",
                    "Parameters",
                    "Resources",
                },
            )
            self.assertEqual(
                {logical_id: node["Type"] for logical_id, node in model["Resources"].items()},
                EXPECTED_STAGING_TYPES,
            )
            self.assertEqual(len(model["Resources"]), 2)

    def test_staging_parameter_is_exact_and_has_no_default(self) -> None:
        expected = {
            "StagingAccessPhase": {
                "AllowedValues": [phase.value for phase in StagingPhase],
                "Type": "String",
            }
        }
        for phase in StagingPhase:
            self.assertEqual(staging_model(phase)["Parameters"], expected)
            self.assertNotIn("Default", expected["StagingAccessPhase"])

    def test_staging_policy_states_are_exact(self) -> None:
        expected = {
            StagingPhase.UPLOAD_ONLY: (
                "NO_CONTROLLER_HOST_OBJECT_READ_GRANT"
            ),
            StagingPhase.HOST_EXACT_OBJECT_READ: (
                "EXACTLY_ONE_FUTURE_HOST_EXACT_OBJECT_READ_GRANT"
            ),
        }
        for phase, state in expected.items():
            actual = staging_model(phase)["Resources"]["StagingBucketPolicy"][
                "Metadata"
            ]["StructuralPolicyState"]
            self.assertEqual(actual, state)

    def test_staging_delta_is_exact(self) -> None:
        delta = subject.staging_structural_delta_v1()
        self.assertEqual(
            delta.create_added_logical_ids,
            ("StagingBucketPolicy", "StagingBundleBucket"),
        )
        self.assertEqual(delta.update_added_logical_ids, ())
        self.assertEqual(delta.update_removed_logical_ids, ())
        self.assertEqual(delta.update_modified_logical_ids, ("StagingBucketPolicy",))
        self.assertEqual(delta.update_replaced_logical_ids, ())
        upload = staging_model(StagingPhase.UPLOAD_ONLY)
        host_read = staging_model(StagingPhase.HOST_EXACT_OBJECT_READ)
        self.assertEqual(
            {key: value for key, value in upload.items() if key != "Resources"},
            {key: value for key, value in host_read.items() if key != "Resources"},
        )
        changed_resources = tuple(
            sorted(
                logical_id
                for logical_id in upload["Resources"]
                if upload["Resources"][logical_id]
                != host_read["Resources"][logical_id]
            )
        )
        self.assertEqual(changed_resources, ("StagingBucketPolicy",))

    def test_staging_contains_no_bundle_object_resource_or_policy_body(self) -> None:
        for phase in StagingPhase:
            model = staging_model(phase)
            self.assertEqual(set(model["Resources"]), set(EXPECTED_STAGING_TYPES))
            for node in model["Resources"].values():
                self.assertNotIn("Properties", node)


class ModuleACrossValidationAndExhaustiveTests(unittest.TestCase):
    def test_all_three_active_sets_equal_module_a_exactly(self) -> None:
        expected_counts = {
            MainPhase.FOUNDATION_ONLY: 8,
            MainPhase.CONTROLLER_COMPUTE: 12,
            MainPhase.SEALED_STOPPED: 10,
        }
        for phase in MainPhase:
            model = main_model(phase)
            from_b = active_main_ids(model, phase)
            from_a = tuple(
                logical_id.value
                for logical_id in module_a.logical_resource_ids_for_phase_v1(phase)
            )
            self.assertEqual(from_b, from_a)
            self.assertEqual(len(from_b), expected_counts[phase])

    def test_all_thirty_six_resource_phase_relations_match_module_a(self) -> None:
        registry = module_a.logical_resource_registry_v1()
        self.assertEqual(len(registry), 12)
        relations = tuple(product(registry, MainPhase))
        self.assertEqual(len(relations), 36)
        for record, phase in relations:
            active = frozenset(active_main_ids(main_model(phase), phase))
            with self.subTest(logical_id=record.logical_id, phase=phase):
                self.assertIs(
                    record.logical_id.value in active,
                    phase in record.phase_presence_mask,
                )

    def test_every_condition_resource_combination_matches_module_a_masks(self) -> None:
        model = main_model()
        for record in module_a.logical_resource_registry_v1():
            node = model["Resources"][record.logical_id.value]
            condition = node.get("Condition")
            for phase in MainPhase:
                actual = (
                    True
                    if condition is None
                    else evaluate_condition(model["Conditions"][condition], phase)
                )
                self.assertIs(actual, phase in record.phase_presence_mask)

    def test_resource_class_phase_cardinality_is_exact(self) -> None:
        occurrence_counts = {
            logical_id: sum(
                logical_id in active_main_ids(main_model(phase), phase)
                for phase in MainPhase
            )
            for logical_id in EXPECTED_MAIN_IDS
        }
        for logical_id in EXPECTED_UNCONDITIONAL_IDS:
            self.assertEqual(occurrence_counts[logical_id], 3)
        for logical_id in EXPECTED_CONTROLLER_IDS:
            self.assertEqual(occurrence_counts[logical_id], 2)
        for logical_id in EXPECTED_BOOTSTRAP_IDS:
            self.assertEqual(occurrence_counts[logical_id], 1)

    def test_all_protected_resources_remain_present(self) -> None:
        protected = frozenset(
            logical_id.value
            for logical_id in module_a.protected_persistent_logical_ids_v1()
        )
        self.assertEqual(protected, EXPECTED_UNCONDITIONAL_IDS)
        for phase in MainPhase:
            self.assertTrue(
                protected.issubset(active_main_ids(main_model(phase), phase))
            )
        self.assertTrue(module_a.persistent_resource_invariants_hold_v1())

    def test_both_staging_profiles_have_exactly_two_resources(self) -> None:
        for phase in StagingPhase:
            model = staging_model(phase)
            self.assertEqual(set(model["Resources"]), set(EXPECTED_STAGING_TYPES))
            self.assertEqual(len(model["Resources"]), 2)


class RequiredNegativeFixtureTests(unittest.TestCase):
    def test_fixture_manifest_is_exact_complete_and_unique(self) -> None:
        required_names = {
            "extra_resource",
            "missing_foundation_resource",
            "missing_evidence_key",
            "missing_evidence_volume",
            "wrong_resource_type",
            "controller_present_during_foundation",
            "controller_absent_during_compute",
            "bootstrap_signal_present_in_sealed_phase",
            "bootstrap_signal_absent_in_compute",
            "wrong_deletion_policy",
            "wrong_update_replace_policy",
            "retained_policy_added_to_wrong_resource",
            "unknown_condition",
            "unknown_parameter",
            "dependency_on_unknown_resource",
            "dependency_cycle",
            "output_present",
            "transform_present",
            "custom_resource_present",
            "nested_stack_present",
            "physical_cloud_id_leakage",
            "credential_like_value",
            "wait_handle_url_leakage",
            "deployable_status_claim",
            "staging_third_resource",
            "host_read_staging_grant_in_upload_only_state",
        }
        actual_names = tuple(row[0] for row in NEGATIVE_FIXTURES_V1)
        self.assertEqual(len(actual_names), 26)
        self.assertEqual(len(actual_names), len(frozenset(actual_names)))
        self.assertEqual(set(actual_names), required_names)

    def test_all_required_negative_fixtures_return_exact_closed_reason(self) -> None:
        for name, kind, profile, mutate, expected_reason in NEGATIVE_FIXTURES_V1:
            with self.subTest(name=name):
                model = (
                    main_model(profile)
                    if kind is Kind.MAIN
                    else staging_model(profile)
                )
                mutate(model)
                result = validation_for_model(kind, profile, model)
                self.assertFalse(result.is_valid)
                self.assertIs(type(result.reason), Reason)
                self.assertIs(result.reason, expected_reason)


class AdditionalValidatorRejectionTests(unittest.TestCase):
    def assertMainReason(
        self,
        model: dict[str, object],
        reason: Reason,
        phase: MainPhase = MainPhase.FOUNDATION_ONLY,
    ) -> None:
        result = validation_for_model(Kind.MAIN, phase, model)
        self.assertFalse(result.is_valid)
        self.assertIs(result.reason, reason)

    def test_unknown_and_missing_top_level_keys(self) -> None:
        unknown = main_model()
        unknown["Mappings"] = {}
        self.assertMainReason(unknown, Reason.UNKNOWN_TOP_LEVEL_KEY)
        missing = main_model()
        del missing["Description"]
        self.assertMainReason(missing, Reason.MISSING_TOP_LEVEL_KEY)

    def test_missing_parameter_and_condition(self) -> None:
        missing_parameter = main_model()
        del missing_parameter["Parameters"]["ControllerDeploymentPhase"]
        self.assertMainReason(missing_parameter, Reason.MISSING_PARAMETER)
        missing_condition = main_model()
        del missing_condition["Conditions"]["ControllerPresent"]
        self.assertMainReason(missing_condition, Reason.MISSING_CONDITION)

    def test_missing_nonprotected_resource(self) -> None:
        model = main_model()
        del model["Resources"]["ControllerInstance"]
        self.assertMainReason(model, Reason.MISSING_LOGICAL_RESOURCE)

    def test_invalid_and_semantically_equivalent_noncanonical_conditions(self) -> None:
        invalid = main_model()
        invalid["Conditions"]["ControllerPresent"] = {"Fn::And": []}
        self.assertMainReason(invalid, Reason.CONDITION_EXPRESSION_INVALID)
        noncanonical = main_model()
        noncanonical["Conditions"]["ControllerPresent"]["Fn::Or"].reverse()
        self.assertMainReason(
            noncanonical,
            Reason.CONDITION_EXPRESSION_NONCANONICAL,
        )

    def test_wrong_and_unknown_resource_conditions(self) -> None:
        wrong = main_model()
        wrong["Resources"]["ControllerInstance"]["Condition"] = (
            "BootstrapSignalActive"
        )
        self.assertMainReason(wrong, Reason.RESOURCE_CONDITION_MISMATCH)
        unknown = main_model()
        unknown["Resources"]["ControllerInstance"]["Condition"] = (
            "NotACondition"
        )
        self.assertMainReason(unknown, Reason.UNKNOWN_RESOURCE_CONDITION)
        malformed = main_model()
        malformed["Resources"]["ControllerInstance"]["Condition"] = []
        self.assertMainReason(malformed, Reason.RESOURCE_NODE_SCHEMA_MISMATCH)

    def test_missing_retention_attributes(self) -> None:
        missing_deletion = main_model()
        del missing_deletion["Resources"]["EvidenceKey"]["DeletionPolicy"]
        self.assertMainReason(missing_deletion, Reason.DELETION_POLICY_MISMATCH)
        missing_update = main_model()
        del missing_update["Resources"]["EvidenceVolume"]["UpdateReplacePolicy"]
        self.assertMainReason(
            missing_update,
            Reason.UPDATE_REPLACE_POLICY_MISMATCH,
        )

    def test_properties_and_free_form_placeholders_are_forbidden(self) -> None:
        properties = main_model()
        properties["Resources"]["ControllerInstance"]["Properties"] = {}
        self.assertMainReason(properties, Reason.PRIVILEGED_CONTENT_PRESENT)
        free_form = main_model()
        free_form["Resources"]["ControllerBudget"]["Metadata"]["DeferredContent"][
            "BudgetNotificationDestinations"
        ] = "TODO"
        self.assertMainReason(free_form, Reason.FREE_FORM_PLACEHOLDER_FORBIDDEN)

    def test_controller_and_bootstrap_metadata_tampering_is_rejected(self) -> None:
        controller = main_model()
        controller["Resources"]["ControllerInstance"]["Metadata"][
            "StructuralRequirements"
        ]["InstanceClass"]["RequiredValue"] = "t3.medium"
        self.assertMainReason(controller, Reason.CONTROLLER_METADATA_MISMATCH)
        bootstrap = main_model()
        bootstrap["Resources"]["BootstrapWaitCondition"]["Metadata"][
            "StructuralExpectations"
        ]["Count"] = 2
        self.assertMainReason(bootstrap, Reason.BOOTSTRAP_STRUCTURE_MISMATCH)
        exact_type_mutations = (
            ("BootstrapWaitHandle", "PhysicalSignalUrlRendered", 0),
            ("BootstrapWaitCondition", "Count", True),
            ("BootstrapWaitCondition", "TimeoutSeconds", 28800.0),
        )
        for logical_id, field, value in exact_type_mutations:
            with self.subTest(logical_id=logical_id, field=field):
                model = main_model()
                model["Resources"][logical_id]["Metadata"][
                    "StructuralExpectations"
                ][field] = value
                self.assertMainReason(
                    model,
                    Reason.BOOTSTRAP_STRUCTURE_MISMATCH,
                )

    def test_dependency_format_self_reference_and_edge_mismatch(self) -> None:
        malformed = main_model()
        malformed["Resources"]["EvidenceVolumeAttachment"]["DependsOn"] = (
            "EvidenceVolume"
        )
        self.assertMainReason(malformed, Reason.DEPENDENCY_FORMAT_INVALID)
        self_reference = main_model()
        self_reference["Resources"]["EvidenceVolumeAttachment"]["DependsOn"] = [
            "EvidenceVolumeAttachment"
        ]
        self.assertMainReason(self_reference, Reason.DEPENDENCY_SELF_REFERENCE)
        mismatch = main_model()
        mismatch["Resources"]["EvidenceVolumeAttachment"]["DependsOn"] = [
            "ControllerInstance"
        ]
        self.assertMainReason(mismatch, Reason.DEPENDENCY_EDGE_MISMATCH)

    def test_macro_and_unrestricted_resource_extension_are_rejected(self) -> None:
        macro = main_model()
        macro["Resources"]["UnexpectedMacro"] = {
            "Type": "AWS::CloudFormation::Macro"
        }
        self.assertMainReason(macro, Reason.FORBIDDEN_MACRO)
        extension = main_model()
        extension["Resources"]["ControllerBudget"]["Extension"] = "closed"
        self.assertMainReason(extension, Reason.UNRESTRICTED_EXTENSION_FIELD)

    def test_all_forbidden_readiness_claim_spellings_are_rejected_as_claims(self) -> None:
        for claim in (
            "deployable",
            "provisioning-ready",
            "change-set-ready",
            "live-validation-ready",
        ):
            with self.subTest(claim=claim):
                model = main_model()
                model["Metadata"]["Artifact"]["DeploymentReadiness"] = claim
                self.assertMainReason(
                    model,
                    Reason.DEPLOYMENT_READINESS_CLAIM_FORBIDDEN,
                )

    def test_staging_malformed_metadata_is_closed_rejection(self) -> None:
        for invalid_metadata in ("invalid", []):
            with self.subTest(type=type(invalid_metadata)):
                model = staging_model()
                model["Resources"]["StagingBucketPolicy"][
                    "Metadata"
                ] = invalid_metadata
                result = validation_for_model(
                    Kind.STAGING,
                    StagingPhase.UPLOAD_ONLY,
                    model,
                )
                self.assertFalse(result.is_valid)
                self.assertIs(type(result.reason), Reason)


class SensitiveValueScannerTests(unittest.TestCase):
    def test_all_required_sensitive_categories_have_closed_findings(self) -> None:
        rows = (
            ("Value", "arn:aws:iam::123456789012:role/example", Reason.SENSITIVE_ARN),
            ("Value", "123456789012", Reason.SENSITIVE_AWS_ACCOUNT_NUMBER),
            ("Value", "192.0.2.10", Reason.SENSITIVE_IP_LITERAL),
            ("Value", "2001:db8::1", Reason.SENSITIVE_IP_LITERAL),
            ("Value", "subnet-0123456789abcdef0", Reason.SENSITIVE_NETWORK_PHYSICAL_ID),
            ("Value", "vpc-0123456789abcdef0", Reason.SENSITIVE_NETWORK_PHYSICAL_ID),
            ("Value", "sg-0123456789abcdef0", Reason.SENSITIVE_NETWORK_PHYSICAL_ID),
            ("Value", "ami-0123456789abcdef0", Reason.SENSITIVE_AMI_PHYSICAL_ID),
            (
                "KmsKeyId",
                "12345678-1234-1234-1234-123456789abc",
                Reason.SENSITIVE_KMS_KEY_ID,
            ),
            (
                "KmsKeyId",
                "mrk-0123456789abcdef0123456789abcdef",
                Reason.SENSITIVE_KMS_KEY_ID,
            ),
            ("BucketName", "example-physical-bucket", Reason.SENSITIVE_BUCKET_PHYSICAL_NAME),
            ("Bucket", "example-physical-bucket", Reason.SENSITIVE_BUCKET_PHYSICAL_NAME),
            ("Value", SYNTHETIC_ACCESS_KEY_ID, Reason.SENSITIVE_ACCESS_KEY),
            (
                "SecretAccessKey",
                "redacted-secret-shape",
                Reason.SENSITIVE_SECRET_OR_SESSION_TOKEN,
            ),
            ("Value", "/Users/example/private/file", Reason.SENSITIVE_PRIVATE_PATH),
            ("Username", "example-user", Reason.SENSITIVE_USERNAME),
            (
                "WaitHandleUrl",
                "https://cloudformation-waitcondition.example/signal",
                Reason.SENSITIVE_WAIT_HANDLE_URL,
            ),
            (
                "AccessKeyId",
                subject.DeferredResolutionV1.REQUIRES_PRIVATE_MANIFEST_BINDING.value,
                Reason.SENSITIVE_ACCESS_KEY,
            ),
            (
                "AWS_SECRET_ACCESS_KEY",
                subject.DeferredResolutionV1.REQUIRES_PRIVATE_MANIFEST_BINDING.value,
                Reason.SENSITIVE_SECRET_OR_SESSION_TOKEN,
            ),
            ("Value", "endpoint 192.0.2.10:443", Reason.SENSITIVE_IP_LITERAL),
            (
                "Value",
                "file:///Users/example/private/file",
                Reason.SENSITIVE_PRIVATE_PATH,
            ),
        )
        for key, value, expected in rows:
            with self.subTest(key=key, expected=expected):
                self.assertIs(
                    subject.sensitive_value_scan_v1({"Probe": {key: value}}),
                    expected,
                )

    def test_sensitive_priority_is_deterministic(self) -> None:
        model = {
            "Arn": "arn:aws:iam::123456789012:role/example",
            "WaitHandleUrl": "https://cloudformation-waitcondition.example/signal",
            "Access": SYNTHETIC_ACCESS_KEY_ID,
        }
        for _ in range(100):
            self.assertIs(
                subject.sensitive_value_scan_v1(model),
                Reason.SENSITIVE_WAIT_HANDLE_URL,
            )

    def test_generic_non_wait_url_is_not_misclassified(self) -> None:
        self.assertIs(
            subject.sensitive_value_scan_v1(
                {"Documentation": "https://example.invalid/docs"}
            ),
            Reason.VALID,
        )

    def test_all_positive_models_and_closed_placeholders_scan_clean(self) -> None:
        for phase in MainPhase:
            self.assertIs(
                subject.sensitive_value_scan_v1(main_model(phase)),
                Reason.VALID,
            )
        for phase in StagingPhase:
            self.assertIs(
                subject.sensitive_value_scan_v1(staging_model(phase)),
                Reason.VALID,
            )
        for placeholder in subject.DeferredResolutionV1:
            self.assertIs(
                subject.sensitive_value_scan_v1(
                    {"BucketPhysicalName": placeholder.value}
                ),
                Reason.VALID,
            )

    def test_scanner_non_mapping_input_is_closed_invalid_input(self) -> None:
        for value in (None, [], (), "value", 1, False):
            with self.subTest(value=value):
                self.assertIs(
                    subject.sensitive_value_scan_v1(value),
                    Reason.INVALID_INPUT,
                )

    def test_scanner_non_string_mapping_key_is_closed_invalid_input(self) -> None:
        self.assertIs(
            subject.sensitive_value_scan_v1({1: "value", "key": "value"}),
            Reason.INVALID_INPUT,
        )

    def test_credential_field_names_are_rejected_for_container_values(self) -> None:
        rows = (
            ({"Credentials": {}}, Reason.SENSITIVE_SECRET_OR_SESSION_TOKEN),
            ({"AccessKeyId": []}, Reason.SENSITIVE_ACCESS_KEY),
            ({"Username": None}, Reason.SENSITIVE_USERNAME),
        )
        for model, expected_reason in rows:
            with self.subTest(model=model):
                self.assertIs(
                    subject.sensitive_value_scan_v1(model),
                    expected_reason,
                )

    def test_scanner_cyclic_mapping_is_closed_invalid_input(self) -> None:
        cyclic: dict[str, object] = {}
        cyclic["self"] = cyclic
        self.assertIs(
            subject.sensitive_value_scan_v1(cyclic),
            Reason.INVALID_INPUT,
        )


class PublicApiMisuseTests(unittest.TestCase):
    def test_validator_requires_nominal_kind_and_profile(self) -> None:
        canonical = subject.render_main_structural_template_v1(
            MainPhase.FOUNDATION_ONLY
        )
        invalid_rows = (
            ("MAIN", MainPhase.FOUNDATION_ONLY),
            (Kind.MAIN, "FOUNDATION_ONLY"),
            (Kind.MAIN, StagingPhase.UPLOAD_ONLY),
            (Kind.STAGING, MainPhase.FOUNDATION_ONLY),
        )
        for kind, profile in invalid_rows:
            with self.subTest(kind=kind, profile=profile):
                with self.assertRaises(subject.ModuleBValidationErrorV1):
                    subject.validate_structural_artifact_v1(kind, profile, canonical)

    def test_validator_requires_bytes(self) -> None:
        for value in ("{}\n", {}, bytearray(b"{}\n"), memoryview(b"{}\n")):
            with self.subTest(value_type=type(value)):
                with self.assertRaises(subject.ModuleBValidationErrorV1):
                    subject.validate_structural_artifact_v1(
                        Kind.MAIN,
                        MainPhase.FOUNDATION_ONLY,
                        value,
                    )

    def test_staging_builder_rejects_aliases_and_other_nominal_types(self) -> None:
        for value in (
            "UPLOAD_ONLY",
            MainPhase.FOUNDATION_ONLY,
            None,
            False,
        ):
            with self.subTest(value=value):
                with self.assertRaises(subject.ModuleBValidationErrorV1):
                    subject.build_staging_structural_model_v1(value)

    def test_programmer_errors_do_not_echo_inputs(self) -> None:
        sensitive_input = "unexpected-sensitive-input"
        with self.assertRaises(subject.ModuleBValidationErrorV1) as caught:
            subject.build_main_structural_model_v1(sensitive_input)
        self.assertNotIn(sensitive_input, str(caught.exception))


class RenderDeterminismTests(unittest.TestCase):
    def test_one_thousand_main_render_validate_cycles_per_profile_are_identical(self) -> None:
        baselines = {
            phase: subject.render_main_structural_template_v1(phase)
            for phase in MainPhase
        }
        self.assertEqual(len(frozenset(baselines.values())), 3)
        phases = tuple(MainPhase)
        for cycle in range(1000):
            ordered = phases if cycle % 2 == 0 else tuple(reversed(phases))
            for phase in ordered:
                rendered = subject.render_main_structural_template_v1(phase)
                self.assertEqual(rendered, baselines[phase])
                self.assertTrue(
                    subject.validate_structural_artifact_v1(
                        Kind.MAIN,
                        phase,
                        rendered,
                    ).is_valid
                )

    def test_one_thousand_staging_render_validate_cycles_per_profile_are_identical(self) -> None:
        baselines = {
            phase: subject.render_staging_structural_template_v1(phase)
            for phase in StagingPhase
        }
        self.assertEqual(len(frozenset(baselines.values())), 2)
        phases = tuple(StagingPhase)
        for cycle in range(1000):
            ordered = phases if cycle % 2 == 0 else tuple(reversed(phases))
            for phase in ordered:
                rendered = subject.render_staging_structural_template_v1(phase)
                self.assertEqual(rendered, baselines[phase])
                self.assertTrue(
                    subject.validate_structural_artifact_v1(
                        Kind.STAGING,
                        phase,
                        rendered,
                    ).is_valid
                )


if __name__ == "__main__":
    unittest.main()
