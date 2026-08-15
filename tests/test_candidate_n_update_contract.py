from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = ROOT / "scripts" / "runtime_probes" / "harness.py"
PROBE_PATH = ROOT / "scripts" / "runtime_probes" / "candidate_n_update_contract.py"
TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


harness = load_module("candidate_n_update_harness", HARNESS_PATH)
contract = load_module("candidate_n_update_contract", PROBE_PATH)


class CandidateNUpdateContractTest(unittest.TestCase):
    def run_probe(self, **parameters):
        return harness.run_isolated_probe(
            PROBE_PATH,
            "SYNTH-CANDIDATE-N-UPDATE-A-D",
            timeout_seconds=10,
            parameters=parameters,
        )

    def test_two_transition_storage_and_pre_batch_shapes(self) -> None:
        subject = contract.SyntheticReplayFixture()
        transitions = contract._transitions()
        for transition in transitions:
            subject.store(transition)

        records = subject.records()

        self.assertEqual(len(records), 2)
        self.assertEqual(
            contract._shape(tuple(record["state"] for record in records)),
            (2, 3, 3),
        )
        self.assertEqual(
            contract._shape(tuple(record["next_state"] for record in records)),
            (2, 3, 3),
        )
        self.assertEqual(
            contract._shape(tuple(record["action"] for record in records)),
            (2, 3),
        )
        self.assertEqual(
            contract._shape(tuple(record["reward"] for record in records)),
            (2, 3),
        )
        self.assertEqual(
            tuple(record["phase"] for record in records),
            tuple(transition.phase for transition in transitions),
        )

    def test_batch_shapes_and_exact_flattening_order(self) -> None:
        subject = contract.SyntheticReplayFixture()
        transitions = contract._transitions()
        for transition in transitions:
            subject.store(transition)

        batch = subject.build_batch(subject.records())

        self.assertEqual(contract._shape(batch.states), (6, 3))
        self.assertEqual(contract._shape(batch.next_states), (6, 3))
        self.assertEqual(contract._shape(batch.actions), (6,))
        self.assertEqual(contract._shape(batch.rewards), (6,))
        self.assertEqual(
            batch.states,
            contract._flatten_nodes(tuple(item.state for item in transitions)),
        )
        self.assertEqual(
            batch.next_states,
            contract._flatten_nodes(tuple(item.next_state for item in transitions)),
        )
        self.assertEqual(batch.actions, (0, 1, 0, 1, 0, 1))
        self.assertEqual(batch.rewards, (0.0, 1.0, 2.0, 10.0, 11.0, 12.0))

    def test_constructed_and_retained_edge_shapes_are_both_observed(self) -> None:
        subject = contract.SyntheticReplayFixture()
        for transition in contract._transitions():
            subject.store(transition)

        batch = subject.build_batch(subject.records())

        self.assertEqual(contract._shape(batch.constructed_edge_index), (2, 8))
        self.assertEqual(contract._shape(batch.retained_edge_index), (2, 4))
        self.assertEqual(
            batch.constructed_edge_index,
            ((0, 1, 1, 2, 3, 4, 4, 5), (1, 0, 2, 1, 4, 3, 5, 4)),
        )
        self.assertEqual(
            batch.retained_edge_index,
            contract.SINGLE_GRAPH_EDGE_INDEX,
        )

    def test_done_false_and_true_are_observed_without_expected_outcome(self) -> None:
        omitted = contract.observe_contract(contract.SyntheticReplayFixture)
        retained = contract.observe_contract(
            lambda: contract.SyntheticReplayFixture(retain_done=True)
        )

        self.assertEqual(omitted["terminal_retained"], "NO")
        self.assertEqual(retained["terminal_retained"], "YES")
        self.assertTrue(omitted["phase_metadata_observed"])
        self.assertFalse(omitted["phase_used_as_learning_input"])

    @unittest.skipUnless(TORCH_AVAILABLE, "Module D requires existing Torch")
    def test_deterministic_greedy_action_selection(self) -> None:
        evidence = contract._observe_action_selection(
            contract.SyntheticActionSelectionFixture
        )

        self.assertEqual(evidence["action_selection_shapes"]["action_q_output"], (3, 2))
        self.assertEqual(evidence["action_selection_shapes"]["greedy_actions"], (3,))
        self.assertEqual(evidence["greedy_actions"], [0, 0, 0])
        self.assertEqual(evidence["action_selection_method_count"], 1)
        self.assertTrue(evidence["deterministic_exploitation_only"])
        self.assertFalse(evidence["epsilon_random_executed"])

    @unittest.skipUnless(TORCH_AVAILABLE, "Module D requires existing Torch")
    def test_hard_target_sync_is_one_isolated_complete_copy(self) -> None:
        evidence = contract._observe_hard_sync(
            contract.SyntheticHardSyncFixture
        )

        self.assertEqual(
            evidence["hard_sync_checks"],
            {
                "states_differ_before": True,
                "sync_invoked_once": True,
                "complete_equality_after": True,
                "online_state_unchanged": True,
            },
        )
        self.assertEqual(evidence["hard_target_sync_count"], 1)
        self.assertFalse(evidence["target_sync_schedule_characterized"])
        self.assertEqual(
            evidence["target_sync_microcheck_mutation"], "EXPECTED"
        )

    def test_graph_edge_observer_preserves_forward_input(self) -> None:
        evidence = contract._observe_graph_edges(
            contract.SyntheticGraphEdgeFixture
        )

        self.assertEqual(
            evidence["graph_edge_shapes"],
            {
                "constructed_batch_edge_shape": (2, 8),
                "model_retained_edge_shape": (2, 4),
                "forward_observed_edge_shape": (2, 4),
            },
        )
        self.assertFalse(evidence["edge_observer_substituted_input"])
        self.assertTrue(evidence["forward_edge_identity_preserved"])
        self.assertEqual(evidence["graph_forward_count"], 1)
        self.assertFalse(evidence["candidate_n_runtime_edge_behavior_proven"])

    @unittest.skipUnless(TORCH_AVAILABLE, "Module D requires existing Torch")
    def test_unobservable_graph_edge_is_inconclusive(self) -> None:
        result = contract._module_d_result(
            contract.SyntheticActionSelectionFixture,
            contract.SyntheticHardSyncFixture,
            lambda: contract.SyntheticGraphEdgeFixture(mode="unobservable"),
        )

        self.assertEqual(result["status"], "inconclusive")

    @unittest.skipUnless(TORCH_AVAILABLE, "Module B validation requires existing Torch")
    def test_isolated_probe_records_complete_shape_contract(self) -> None:
        result = self.run_probe()

        self.assertEqual(result["status"], "pass", result)
        shape_map = {
            item["label"]: item["dimensions"]
            for item in result["evidence"]["shapes"]
        }
        self.assertEqual(
            shape_map,
            {
                "actions_flattened": [6],
                "actions_pre_batch": [2, 3],
                "action_q_output": [3, 2],
                "bootstrap_maxima": [6],
                "constructed_batch_edge_shape": [2, 8],
                "constructed_batch_edge_index": [2, 8],
                "detached_target_base": [6, 2],
                "forward_observed_edge_shape": [2, 4],
                "greedy_actions": [3],
                "model_retained_edge_shape": [2, 4],
                "mse_prediction_input": [6, 2],
                "mse_target_input": [6, 2],
                "next_states_flattened": [6, 3],
                "next_states_pre_batch": [2, 3, 3],
                "online_prediction": [6, 2],
                "replacement_target": [6, 2],
                "retained_single_graph_edge_index": [2, 4],
                "rewards_flattened": [6],
                "rewards_pre_batch": [2, 3],
                "scalar_loss": [],
                "states_flattened": [6, 3],
                "states_pre_batch": [2, 3, 3],
                "target_next_q": [6, 2],
                "td_rewards": [6],
                "td_targets": [6],
            },
        )
        self.assertEqual(
            result["evidence"]["calls"],
            [
                {"label": "action_selection_method", "count": 1},
                {"label": "build_batch", "count": 1},
                {"label": "graph_forward", "count": 1},
                {"label": "hard_target_sync", "count": 1},
                {"label": "target_network_forward", "count": 1},
                {"label": "zero_grad_guard", "count": 1},
                {"label": "online_network_forward", "count": 2},
                {"label": "store_transition", "count": 2},
            ],
        )
        values = result["evidence"]["values"]
        self.assertEqual(values["terminal_retained"], "NO")
        self.assertTrue(values["td_loss_executed"])
        self.assertAlmostEqual(values["loss_value"], 3.355, places=6)
        self.assertEqual(
            values["controlled_stop"],
            "POST_LOSS_MUTATION_BOUNDARY",
        )
        self.assertEqual(values["greedy_actions"], [0, 0, 0])
        self.assertEqual(values["update_path_parameter_mutation"], "NO")
        self.assertEqual(
            values["target_sync_microcheck_mutation"], "EXPECTED"
        )
        self.assertTrue(
            values["post_loss_guard_checks"]["online_parameters_unchanged"]
        )
        self.assertTrue(
            values["post_loss_guard_checks"]["target_parameters_unchanged"]
        )

    def test_status_semantics_cover_fail_inconclusive_and_blocked(self) -> None:
        failed = self.run_probe(synthetic_mode="mismatch")
        inconclusive = self.run_probe(synthetic_mode="inconclusive")
        blocked = self.run_probe(synthetic_mode="blocked")

        self.assertEqual(failed["status"], "fail")
        self.assertEqual(inconclusive["status"], "inconclusive")
        self.assertEqual(blocked["status"], "blocked")

    def test_unexpected_exception_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            private_marker = str(Path(temporary) / "private-source.py")
            result = self.run_probe(
                synthetic_mode="unexpected",
                private_marker=private_marker,
            )

        serialized = json.dumps(result, sort_keys=True)
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(
            result["evidence"]["values"]["error_type"],
            "RuntimeError",
        )
        self.assertNotIn(private_marker, serialized)
        self.assertNotIn("private-source.py", serialized)

    def test_module_a_remains_independent_of_td_loss_fields(self) -> None:
        result = contract._result(contract.SyntheticReplayFixture)
        serialized = json.dumps(result, sort_keys=True)

        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["evidence"]["td_loss_executed"])
        self.assertNotIn("td_target", serialized)
        self.assertNotIn("loss_value", serialized)
        self.assertNotIn("optimizer", serialized)

    @unittest.skipUnless(TORCH_AVAILABLE, "Module B validation requires existing Torch")
    def test_target_next_q_bootstrap_and_td_targets(self) -> None:
        observation = contract.SyntheticTDLossFixture().observe_td_loss()

        self.assertEqual(contract._shape(observation.target_next_q), (6, 2))
        self.assertEqual(contract._shape(observation.bootstrap_maxima), (6,))
        self.assertEqual(contract._shape(observation.rewards), (6,))
        self.assertEqual(contract._shape(observation.td_targets), (6,))
        self.assertTrue(
            contract._all_close(
                observation.target_next_q,
                ((0.5, 2.0),) * 6,
            )
        )
        self.assertTrue(
            contract._all_close(
                observation.bootstrap_maxima,
                contract.EXPECTED_BOOTSTRAP_MAXIMA,
            )
        )
        self.assertTrue(
            contract._all_close(observation.rewards, contract.TD_REWARDS)
        )
        self.assertTrue(
            contract._all_close(
                observation.td_targets,
                contract.EXPECTED_TD_TARGETS,
            )
        )

    @unittest.skipUnless(TORCH_AVAILABLE, "Module B validation requires existing Torch")
    def test_replacement_matrix_changes_selected_cells_only(self) -> None:
        observation = contract.SyntheticTDLossFixture().observe_td_loss()
        base = contract._plain(observation.detached_target_base)
        replacement = contract._plain(observation.replacement_target)

        self.assertTrue(
            contract._all_close(replacement, contract.EXPECTED_TARGET_MATRIX)
        )
        for row, selected_action in enumerate(contract.TD_ACTIONS):
            for column in range(contract.A):
                if column == selected_action:
                    self.assertFalse(
                        contract._all_close(
                            replacement[row][column],
                            base[row][column],
                        )
                    )
                else:
                    self.assertTrue(
                        contract._all_close(
                            replacement[row][column],
                            base[row][column],
                        )
                    )

    @unittest.skipUnless(TORCH_AVAILABLE, "Module B validation requires existing Torch")
    def test_full_matrix_mse_inputs_and_scalar_loss(self) -> None:
        observation = contract.SyntheticTDLossFixture().observe_td_loss()

        self.assertEqual(contract._shape(observation.mse_prediction_input), (6, 2))
        self.assertEqual(contract._shape(observation.mse_target_input), (6, 2))
        self.assertEqual(contract._shape(observation.loss), ())
        self.assertTrue(contract._finite_numeric(observation.loss))
        self.assertTrue(contract._all_close(observation.loss, 3.355))
        self.assertTrue(observation.prediction.requires_grad)
        self.assertFalse(observation.detached_target_base.requires_grad)

    @unittest.skipUnless(TORCH_AVAILABLE, "Module B validation requires existing Torch")
    def test_forward_counts_and_no_learning_mutation(self) -> None:
        observation = contract.SyntheticTDLossFixture().observe_td_loss()

        self.assertEqual(observation.target_forward_count, 1)
        self.assertEqual(observation.online_forward_count, 2)
        self.assertFalse(observation.backward_executed)
        self.assertFalse(observation.optimizer_mutation_executed)

    @unittest.skipUnless(TORCH_AVAILABLE, "Module B validation requires existing Torch")
    def test_module_b_status_and_privacy_sanitization(self) -> None:
        failed = self.run_probe(td_synthetic_mode="mismatch")
        inconclusive = self.run_probe(td_synthetic_mode="inconclusive")
        blocked = self.run_probe(td_synthetic_mode="blocked")
        with tempfile.TemporaryDirectory() as temporary:
            private_marker = str(Path(temporary) / "private-update-source.py")
            unexpected = self.run_probe(
                td_synthetic_mode="unexpected",
                private_marker=private_marker,
            )

        self.assertEqual(failed["status"], "fail")
        self.assertEqual(inconclusive["status"], "inconclusive")
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(unexpected["status"], "inconclusive")
        self.assertEqual(
            unexpected["evidence"]["values"]["error_type"],
            "RuntimeError",
        )
        serialized = json.dumps(unexpected, sort_keys=True)
        self.assertNotIn(private_marker, serialized)
        self.assertNotIn("private-update-source.py", serialized)

    @unittest.skipUnless(TORCH_AVAILABLE, "Module C validation requires existing Torch")
    def test_controlled_stop_occurs_once_after_loss_capture(self) -> None:
        result = contract._post_loss_result(
            contract.SyntheticPostLossUpdateFixture
        )

        self.assertEqual(result["status"], "pass", result)
        evidence = result["evidence"]
        checks = evidence["post_loss_guard_checks"]
        self.assertEqual(
            evidence["controlled_stop"],
            "POST_LOSS_MUTATION_BOUNDARY",
        )
        self.assertTrue(checks["loss_captured_before_guard"])
        self.assertTrue(checks["module_b_complete_before_guard"])
        self.assertTrue(checks["guard_reached_once"])
        self.assertEqual(evidence["zero_grad_guard_count"], 1)
        self.assertEqual(evidence["real_zero_grad_calls"], 0)

    @unittest.skipUnless(TORCH_AVAILABLE, "Module C validation requires existing Torch")
    def test_forbidden_post_guard_operations_are_not_reached(self) -> None:
        result = contract._post_loss_result(
            contract.SyntheticPostLossUpdateFixture
        )

        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(
            result["evidence"]["forbidden_operation_counts"],
            {
                "backward": 0,
                "gradient_clipping": 0,
                "optimizer_step": 0,
                "exploration_decay": 0,
            },
        )
        self.assertTrue(
            result["evidence"]["post_loss_guard_checks"][
                "real_zero_grad_not_called"
            ]
        )

    @unittest.skipUnless(TORCH_AVAILABLE, "Module C validation requires existing Torch")
    def test_parameter_gradient_and_optimizer_state_integrity(self) -> None:
        result = contract._post_loss_result(
            contract.SyntheticPostLossUpdateFixture
        )

        self.assertEqual(result["status"], "pass", result)
        checks = result["evidence"]["post_loss_guard_checks"]
        self.assertTrue(checks["online_parameters_unchanged"])
        self.assertTrue(checks["target_parameters_unchanged"])
        self.assertTrue(checks["online_gradients_unchanged"])
        self.assertTrue(checks["target_gradients_unchanged"])
        self.assertTrue(checks["optimizer_state_unchanged"])
        self.assertFalse(result["evidence"]["preexisting_gradients_present"])

    @unittest.skipUnless(TORCH_AVAILABLE, "Module C validation requires existing Torch")
    def test_preexisting_gradients_may_be_present_if_unchanged(self) -> None:
        result = contract._post_loss_result(
            lambda: contract.SyntheticPostLossUpdateFixture(
                preexisting_gradients=True
            )
        )

        self.assertEqual(result["status"], "pass", result)
        checks = result["evidence"]["post_loss_guard_checks"]
        self.assertTrue(result["evidence"]["preexisting_gradients_present"])
        self.assertTrue(checks["online_gradients_unchanged"])
        self.assertTrue(checks["target_gradients_unchanged"])

    @unittest.skipUnless(TORCH_AVAILABLE, "Module C validation requires existing Torch")
    def test_premature_missing_and_unavailable_guard_statuses(self) -> None:
        premature = contract._post_loss_result(
            lambda: contract.SyntheticPostLossUpdateFixture(
                guard_mode="premature"
            )
        )
        missing = contract._post_loss_result(
            lambda: contract.SyntheticPostLossUpdateFixture(
                guard_mode="missing"
            )
        )
        blocked = contract._post_loss_result(
            lambda: contract.SyntheticPostLossUpdateFixture(
                guard_mode="installation_blocked"
            )
        )

        self.assertEqual(premature["status"], "fail")
        self.assertEqual(missing["status"], "inconclusive")
        self.assertEqual(blocked["status"], "blocked")

    @unittest.skipUnless(TORCH_AVAILABLE, "Module C validation requires existing Torch")
    def test_each_forbidden_operation_sentinel_fails_if_reached(self) -> None:
        cases = {
            "forbidden_backward": "backward",
            "forbidden_clipping": "gradient_clipping",
            "forbidden_step": "optimizer_step",
            "forbidden_exploration": "exploration_decay",
        }

        for mode, operation in cases.items():
            with self.subTest(operation=operation):
                result = contract._post_loss_result(
                    lambda mode=mode: contract.SyntheticPostLossUpdateFixture(
                        guard_mode=mode
                    )
                )
                self.assertEqual(result["status"], "fail")
                self.assertEqual(
                    result["evidence"]["forbidden_operation_counts"][operation],
                    1,
                )

    @unittest.skipUnless(TORCH_AVAILABLE, "Module C validation requires existing Torch")
    def test_guard_exception_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            private_marker = str(Path(temporary) / "private-guard-source.py")
            result = self.run_probe(
                guard_synthetic_mode="unexpected",
                private_marker=private_marker,
            )

        self.assertEqual(result["status"], "inconclusive")
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(private_marker, serialized)
        self.assertNotIn("private-guard-source.py", serialized)
        self.assertEqual(
            result["evidence"]["values"]["error_type"],
            "RuntimeError",
        )

    @unittest.skipUnless(TORCH_AVAILABLE, "Module D requires existing Torch")
    def test_module_d_status_and_privacy_sanitization(self) -> None:
        failed = self.run_probe(action_synthetic_mode="mismatch")
        inconclusive = self.run_probe(edge_synthetic_mode="unobservable")
        blocked = self.run_probe(sync_synthetic_mode="blocked")
        with tempfile.TemporaryDirectory() as temporary:
            private_marker = str(Path(temporary) / "private-module-d.py")
            unexpected = self.run_probe(
                action_synthetic_mode="unexpected",
                private_marker=private_marker,
            )

        self.assertEqual(failed["status"], "fail")
        self.assertEqual(inconclusive["status"], "inconclusive")
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(unexpected["status"], "inconclusive")
        self.assertEqual(
            unexpected["evidence"]["values"]["error_type"],
            "RuntimeError",
        )
        serialized = json.dumps(unexpected, sort_keys=True)
        self.assertNotIn(private_marker, serialized)
        self.assertNotIn("private-module-d.py", serialized)

    @unittest.skipUnless(TORCH_AVAILABLE, "Module D requires existing Torch")
    def test_required_dependency_unavailable_is_blocked(self) -> None:
        class UnavailableTDLossFixture:
            def observe_td_loss(self):
                raise contract.RequiredDependencyUnavailable(
                    "synthetic required dependency unavailable"
                )

        class UnavailablePostLossFixture:
            def __init__(self):
                self.state = contract.PostLossRunState()

            def execute(self):
                raise contract.RequiredDependencyUnavailable(
                    "synthetic required dependency unavailable"
                )

        class UnavailableActionFixture:
            def observe_action_selection(self):
                raise contract.RequiredDependencyUnavailable(
                    "synthetic required dependency unavailable"
                )

        td_result = contract._td_result(UnavailableTDLossFixture)
        post_loss_result = contract._post_loss_result(
            UnavailablePostLossFixture
        )
        module_d_result = contract._module_d_result(
            UnavailableActionFixture,
            contract.SyntheticHardSyncFixture,
            contract.SyntheticGraphEdgeFixture,
        )

        self.assertEqual(td_result["status"], "blocked")
        self.assertEqual(post_loss_result["status"], "blocked")
        self.assertEqual(module_d_result["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
