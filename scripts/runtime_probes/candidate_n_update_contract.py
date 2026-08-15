"""Public synthetic scaffold for the Candidate N update contract.

This payload observes a small, deterministic replay contract through an
adapter.  The built-in adapter is synthetic and contains no inherited
learning logic.  A later, separately reviewed loader can bind the same
observer to the real Candidate N storage and batch-builder methods.

The payload observes replay/batching, TD/loss construction, a guarded
post-loss boundary, deterministic action selection, isolated hard target
synchronization, and graph-edge use.  It does not perform backward
propagation, mutate an optimizer, execute a simulator, or duplicate the
private Candidate N algorithm.
"""

from __future__ import annotations

import copy
import math
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


B, N, E, F, A = 2, 3, 4, 3, 2
GAMMA = 0.8
NUMERICAL_TOLERANCE = 1e-6

TD_ACTIONS = (0, 1, 0, 1, 0, 1)
TD_REWARDS = (0.0, 1.0, -1.0, 2.0, 0.5, -0.5)
EXPECTED_BOOTSTRAP_MAXIMA = (2.0, 2.0, 2.0, 2.0, 2.0, 2.0)
EXPECTED_TD_TARGETS = (1.6, 2.6, 0.6, 3.6, 2.1, 1.1)
EXPECTED_TARGET_MATRIX = (
    (1.6, -1.0),
    (1.0, 2.6),
    (0.6, -1.0),
    (1.0, 3.6),
    (2.1, -1.0),
    (1.0, 1.1),
)
EXPECTED_LOSS = 3.355

REQUIRED_REAL = (
    "candidate_n_agent_storage_method",
    "candidate_n_replay_deque",
    "candidate_n_batch_builder",
    "candidate_n_gcn_online_and_target_forwards",
    "candidate_n_action_selection_method",
    "candidate_n_td_loss_update_method",
    "candidate_n_hard_target_sync_method",
    "pytorch_and_pyg_runtime",
)
SAFE_INERT_BOUNDARY = (
    "registry_and_base_agent_framework",
    "generator_and_world_framework",
    "gym_if_imported_but_unused",
)
NOT_REQUIRED = (
    "pfrl",
    "cityflow",
    "sumo",
    "traci",
    "libsumo",
    "simulator",
    "trainer",
    "checkpoint",
    "dataset",
    "historical_replay",
)

SINGLE_GRAPH_EDGE_INDEX = (
    (0, 1, 1, 2),
    (1, 0, 2, 1),
)


class ContractObservationError(RuntimeError):
    """Base class for a public-safe Module A observation result."""


class ContractViolation(ContractObservationError):
    """Raised when an observed, testable synthetic invariant is false."""


class ContractUnresolved(ContractObservationError):
    """Raised when the replay interface cannot be observed unambiguously."""


class InertBoundaryTouched(ContractObservationError):
    """Raised when replay or batching computation reaches an inert boundary."""


class RequiredDependencyUnavailable(ContractObservationError):
    """Raised when an approved, required runtime dependency is unavailable."""


class PostLossMutationBoundaryReached(RuntimeError):
    """Internal signal for deliberate termination before learning mutation."""

    def __init__(self, *, preconditions_met: bool) -> None:
        super().__init__("controlled post-loss mutation boundary reached")
        self.preconditions_met = preconditions_met


class ForbiddenPostLossOperation(RuntimeError):
    """Raised if execution reaches an operation forbidden by Module C."""


class GuardInstallationBlocked(RuntimeError):
    """Raised when the controlled mutation guard cannot be installed."""


@dataclass(frozen=True)
class TransitionInput:
    """Public synthetic transition supplied to a replay adapter."""

    state: tuple[tuple[float, ...], ...]
    phase: tuple[int, ...]
    action: tuple[int, ...]
    reward: tuple[float, ...]
    next_state: tuple[tuple[float, ...], ...]
    next_phase: tuple[int, ...]
    done: bool


@dataclass(frozen=True)
class BatchObservation:
    """Normalized view of values returned by a replay batch builder."""

    states: Any
    next_states: Any
    actions: Any
    rewards: Any
    constructed_edge_index: Any
    retained_edge_index: Any
    learning_fields: tuple[str, ...]


class ReplayContractAdapter(Protocol):
    """Minimal adapter boundary for synthetic and future real observations."""

    def store(self, transition: TransitionInput) -> None: ...

    def records(self) -> Sequence[Any]: ...

    def build_batch(self, records: Sequence[Any]) -> BatchObservation: ...


@dataclass(frozen=True)
class TDLossObservation:
    """Captured Module B values produced by an update-path adapter."""

    target_next_q: Any
    bootstrap_maxima: Any
    rewards: Any
    td_targets: Any
    detached_target_base: Any
    replacement_target: Any
    prediction: Any
    mse_prediction_input: Any
    mse_target_input: Any
    loss: Any
    actions: Any
    target_forward_count: int
    online_forward_count: int
    backward_executed: bool
    optimizer_mutation_executed: bool
    online_parameters: tuple[Any, ...]
    target_parameters: tuple[Any, ...]


class TDLossContractAdapter(Protocol):
    """Observation boundary for a future real Candidate N update call."""

    def observe_td_loss(self) -> TDLossObservation: ...


@dataclass(frozen=True)
class ActionSelectionObservation:
    """Captured deterministic exploitation-path values."""

    q_output: Any
    actions: Any
    method_invocation_count: int
    deterministic_exploitation_only: bool
    epsilon_random_executed: bool


class ActionSelectionAdapter(Protocol):
    def observe_action_selection(self) -> ActionSelectionObservation: ...


@dataclass(frozen=True)
class HardSyncObservation:
    """Sanitized structural evidence from one isolated hard sync."""

    states_differ_before: bool
    sync_invocation_count: int
    complete_equality_after: bool
    online_state_unchanged: bool


class HardSyncAdapter(Protocol):
    def observe_hard_sync(self) -> HardSyncObservation: ...


@dataclass(frozen=True)
class GraphEdgeObservation:
    """Shapes and identity evidence captured without substituting an edge."""

    constructed_batch_edge: Any
    model_retained_edge: Any
    forward_observed_edge: Any | None
    observer_substituted_edge: bool
    forward_edge_identity_preserved: bool | None
    forward_invocation_count: int


class GraphEdgeAdapter(Protocol):
    def observe_graph_edges(self) -> GraphEdgeObservation: ...


ActionAdapterFactory = Callable[[], ActionSelectionAdapter]
SyncAdapterFactory = Callable[[], HardSyncAdapter]
EdgeAdapterFactory = Callable[[], GraphEdgeAdapter]


def _state(base: int) -> tuple[tuple[float, ...], ...]:
    return tuple(
        tuple(float(base + node * F + feature) for feature in range(F))
        for node in range(N)
    )


def _transitions() -> tuple[TransitionInput, TransitionInput]:
    return (
        TransitionInput(
            state=_state(0),
            phase=(0, 1, 0),
            action=(0, 1, 0),
            reward=(0.0, 1.0, 2.0),
            next_state=_state(20),
            next_phase=(1, 0, 1),
            done=False,
        ),
        TransitionInput(
            state=_state(100),
            phase=(1, 0, 1),
            action=(1, 0, 1),
            reward=(10.0, 11.0, 12.0),
            next_state=_state(120),
            next_phase=(0, 1, 0),
            done=True,
        ),
    )


def _terminal_transition(done: bool) -> TransitionInput:
    return TransitionInput(
        state=_state(200),
        phase=(0, 0, 1),
        action=(1, 1, 0),
        reward=(2.0, 1.0, 0.0),
        next_state=_state(220),
        next_phase=(1, 1, 0),
        done=done,
    )


def _plain(value: Any) -> Any:
    """Convert public synthetic/tensor-like values without importing a library."""
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _plain(tolist())
    if isinstance(value, Mapping):
        return {
            str(key): _plain(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return tuple(_plain(item) for item in value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise ContractUnresolved("replay value cannot be normalized safely")


def _shape(value: Any) -> tuple[int, ...]:
    explicit = getattr(value, "shape", None)
    if explicit is not None:
        try:
            return tuple(int(dimension) for dimension in explicit)
        except (TypeError, ValueError) as exc:
            raise ContractUnresolved("shape could not be resolved") from exc

    plain = _plain(value)

    def nested_shape(item: Any) -> tuple[int, ...]:
        if not isinstance(item, tuple):
            return ()
        if not item:
            return (0,)
        child_shapes = tuple(nested_shape(child) for child in item)
        if len(set(child_shapes)) != 1:
            raise ContractUnresolved("ragged replay value has no stable shape")
        return (len(item), *child_shapes[0])

    return nested_shape(plain)


def _flatten_nodes(
    samples: Sequence[Sequence[Any]],
) -> tuple[Any, ...]:
    return tuple(node for sample in samples for node in sample)


def _constructed_edges() -> tuple[tuple[int, ...], tuple[int, ...]]:
    return tuple(
        tuple(index + sample * N for sample in range(B) for index in row)
        for row in SINGLE_GRAPH_EDGE_INDEX
    )  # type: ignore[return-value]


class SyntheticReplayFixture:
    """Generic deterministic replay fixture; it contains no TD/update logic."""

    def __init__(
        self,
        *,
        retain_done: bool = False,
        mode: str = "pass",
        private_marker: str = "",
    ) -> None:
        self._records: deque[dict[str, Any]] = deque(maxlen=8)
        self._retain_done = retain_done
        self._mode = mode
        self._private_marker = private_marker

    def store(self, transition: TransitionInput) -> None:
        if self._mode == "blocked":
            raise InertBoundaryTouched("synthetic inert boundary")
        if self._mode == "inconclusive":
            raise ContractUnresolved("synthetic interface unresolved")
        if self._mode == "unexpected":
            raise RuntimeError(self._private_marker)

        record: dict[str, Any] = {
            "state": transition.state,
            "phase": transition.phase,
            "action": transition.action,
            "reward": transition.reward,
            "next_state": transition.next_state,
            "next_phase": transition.next_phase,
        }
        if self._retain_done:
            record["done"] = transition.done
        self._records.append(record)

    def records(self) -> Sequence[Any]:
        return tuple(dict(record) for record in self._records)

    def build_batch(self, records: Sequence[Any]) -> BatchObservation:
        try:
            states = tuple(record["state"] for record in records)
            next_states = tuple(record["next_state"] for record in records)
            actions = tuple(record["action"] for record in records)
            rewards = tuple(record["reward"] for record in records)
        except (KeyError, TypeError) as exc:
            raise ContractUnresolved("replay record layout is unresolved") from exc

        flattened_actions = _flatten_nodes(actions)
        if self._mode == "mismatch":
            flattened_actions = flattened_actions[:-1]

        return BatchObservation(
            states=_flatten_nodes(states),
            next_states=_flatten_nodes(next_states),
            actions=flattened_actions,
            rewards=_flatten_nodes(rewards),
            constructed_edge_index=_constructed_edges(),
            retained_edge_index=SINGLE_GRAPH_EDGE_INDEX,
            learning_fields=("states", "next_states", "actions", "rewards"),
        )


AdapterFactory = Callable[[], ReplayContractAdapter]


def _terminal_retention(factory: AdapterFactory) -> str:
    false_subject = factory()
    true_subject = factory()
    false_subject.store(_terminal_transition(False))
    true_subject.store(_terminal_transition(True))
    false_records = false_subject.records()
    true_records = true_subject.records()
    if len(false_records) != 1 or len(true_records) != 1:
        raise ContractUnresolved("terminal storage could not be observed")
    return "NO" if _plain(false_records[0]) == _plain(true_records[0]) else "YES"


def observe_contract(factory: AdapterFactory) -> dict[str, Any]:
    """Observe Module A through an adapter without implementing learning logic."""
    subject = factory()
    transitions = _transitions()
    for transition in transitions:
        subject.store(transition)

    records = subject.records()
    if len(records) != B:
        raise ContractViolation("two-transition storage invariant failed")

    try:
        stored_states = tuple(record["state"] for record in records)
        stored_next_states = tuple(record["next_state"] for record in records)
        stored_actions = tuple(record["action"] for record in records)
        stored_rewards = tuple(record["reward"] for record in records)
        stored_phases = tuple(record["phase"] for record in records)
        stored_next_phases = tuple(record["next_phase"] for record in records)
    except (KeyError, TypeError) as exc:
        raise ContractUnresolved("stored replay layout is unresolved") from exc

    pre_batch_shapes = {
        "states_pre_batch": _shape(stored_states),
        "next_states_pre_batch": _shape(stored_next_states),
        "actions_pre_batch": _shape(stored_actions),
        "rewards_pre_batch": _shape(stored_rewards),
    }
    expected_pre_batch = {
        "states_pre_batch": (B, N, F),
        "next_states_pre_batch": (B, N, F),
        "actions_pre_batch": (B, N),
        "rewards_pre_batch": (B, N),
    }
    if pre_batch_shapes != expected_pre_batch:
        raise ContractViolation("pre-batch shape invariant failed")

    if _plain(stored_phases) != tuple(transition.phase for transition in transitions):
        raise ContractViolation("phase metadata ordering invariant failed")
    if _plain(stored_next_phases) != tuple(
        transition.next_phase for transition in transitions
    ):
        raise ContractViolation("next-phase metadata ordering invariant failed")

    batch = subject.build_batch(records)
    flattened_shapes = {
        "states_flattened": _shape(batch.states),
        "next_states_flattened": _shape(batch.next_states),
        "actions_flattened": _shape(batch.actions),
        "rewards_flattened": _shape(batch.rewards),
        "constructed_batch_edge_index": _shape(batch.constructed_edge_index),
        "retained_single_graph_edge_index": _shape(batch.retained_edge_index),
    }
    expected_flattened = {
        "states_flattened": (B * N, F),
        "next_states_flattened": (B * N, F),
        "actions_flattened": (B * N,),
        "rewards_flattened": (B * N,),
        "constructed_batch_edge_index": (2, B * E),
        "retained_single_graph_edge_index": (2, E),
    }
    if flattened_shapes != expected_flattened:
        raise ContractViolation("flattened batch shape invariant failed")

    expected_states = _flatten_nodes(tuple(item.state for item in transitions))
    expected_next_states = _flatten_nodes(
        tuple(item.next_state for item in transitions)
    )
    expected_actions = _flatten_nodes(tuple(item.action for item in transitions))
    expected_rewards = _flatten_nodes(tuple(item.reward for item in transitions))
    order_checks = {
        "states": _plain(batch.states) == expected_states,
        "next_states": _plain(batch.next_states) == expected_next_states,
        "actions": _plain(batch.actions) == expected_actions,
        "rewards": _plain(batch.rewards) == expected_rewards,
    }
    if not all(order_checks.values()):
        raise ContractViolation("sample-major node-major ordering invariant failed")

    if _plain(batch.constructed_edge_index) != _constructed_edges():
        raise ContractViolation("constructed edge ordering invariant failed")
    if _plain(batch.retained_edge_index) != SINGLE_GRAPH_EDGE_INDEX:
        raise ContractViolation("retained edge observation invariant failed")

    required_learning_fields = {"states", "next_states", "actions", "rewards"}
    observed_learning_fields = tuple(str(field) for field in batch.learning_fields)
    if not required_learning_fields.issubset(observed_learning_fields):
        raise ContractViolation("Module A learning-field boundary failed")
    phase_fields = {"phase", "phases", "next_phase", "next_phases"}

    return {
        "pre_batch_shapes": pre_batch_shapes,
        "flattened_shapes": flattened_shapes,
        "order_checks": order_checks,
        "replay_count": len(records),
        "phase_metadata_observed": True,
        "phase_used_as_learning_input": bool(
            phase_fields.intersection(observed_learning_fields)
        ),
        "terminal_retained": _terminal_retention(factory),
    }


def _all_close(actual: Any, expected: Any) -> bool:
    actual_plain = _plain(actual)
    expected_plain = _plain(expected)
    if isinstance(actual_plain, tuple) or isinstance(expected_plain, tuple):
        if not isinstance(actual_plain, tuple) or not isinstance(expected_plain, tuple):
            return False
        if len(actual_plain) != len(expected_plain):
            return False
        return all(
            _all_close(actual_item, expected_item)
            for actual_item, expected_item in zip(actual_plain, expected_plain)
        )
    if isinstance(actual_plain, (int, float)) and isinstance(
        expected_plain, (int, float)
    ):
        return math.isclose(
            float(actual_plain),
            float(expected_plain),
            rel_tol=NUMERICAL_TOLERANCE,
            abs_tol=NUMERICAL_TOLERANCE,
        )
    return actual_plain == expected_plain


def _finite_numeric(value: Any) -> bool:
    plain = _plain(value)
    if isinstance(plain, tuple):
        return all(_finite_numeric(item) for item in plain)
    if isinstance(plain, bool) or not isinstance(plain, (int, float)):
        return False
    return math.isfinite(float(plain))


class SyntheticTDLossFixture:
    """Deterministic interface fixture; it is not Candidate N learning code."""

    def __init__(
        self,
        *,
        mode: str = "pass",
        private_marker: str = "",
        preexisting_gradients: bool = False,
    ) -> None:
        self._mode = mode
        self._private_marker = private_marker
        self._preexisting_gradients = preexisting_gradients

    def observe_td_loss(self) -> TDLossObservation:
        if self._mode == "blocked":
            raise InertBoundaryTouched("synthetic TD/loss inert boundary")
        if self._mode == "inconclusive":
            raise ContractUnresolved("synthetic TD/loss interface unresolved")
        if self._mode == "unexpected":
            raise RuntimeError(self._private_marker)

        try:
            import torch
            from torch import nn
        except ImportError as exc:
            raise RequiredDependencyUnavailable(
                "required public tensor dependency unavailable"
            ) from exc

        class ConstantNetwork(nn.Module):
            def __init__(
                self,
                values: tuple[float, float],
                calls: dict[str, int],
                label: str,
                *,
                differentiable: bool,
            ) -> None:
                super().__init__()
                tensor = torch.tensor(values, dtype=torch.float32)
                if differentiable:
                    self.values = nn.Parameter(tensor)
                else:
                    self.values = nn.Parameter(tensor, requires_grad=False)
                self._calls = calls
                self._label = label

            def forward(self, features: Any) -> Any:
                self._calls[self._label] += 1
                return self.values.unsqueeze(0).expand(features.shape[0], -1)

        calls = {"online": 0, "target": 0}
        online = ConstantNetwork(
            (1.0, -1.0), calls, "online", differentiable=True
        )
        target = ConstantNetwork(
            (0.5, 2.0), calls, "target", differentiable=False
        )
        states = torch.zeros((B * N, F), dtype=torch.float32)
        next_states = torch.ones((B * N, F), dtype=torch.float32)
        actions = torch.tensor(TD_ACTIONS, dtype=torch.long)
        rewards = torch.tensor(TD_REWARDS, dtype=torch.float32)

        with torch.no_grad():
            target_next_q = target(next_states)
            bootstrap_maxima = target_next_q.max(dim=1).values
            td_targets = rewards + GAMMA * bootstrap_maxima
            detached_target_base = online(states).detach().clone()
            replacement_target = detached_target_base.clone()
            replacement_target[
                torch.arange(B * N, dtype=torch.long), actions
            ] = td_targets

        if self._mode == "mismatch":
            td_targets = td_targets.clone()
            td_targets[0] += 1.0
            replacement_target = detached_target_base.clone()
            replacement_target[
                torch.arange(B * N, dtype=torch.long), actions
            ] = td_targets

        prediction = online(states)
        mse_prediction_input = prediction
        mse_target_input = replacement_target
        loss = nn.MSELoss(reduction="mean")(
            mse_prediction_input,
            mse_target_input,
        )
        if self._preexisting_gradients:
            for parameter in (*online.parameters(), *target.parameters()):
                parameter.grad = torch.full_like(parameter, 0.25)

        return TDLossObservation(
            target_next_q=target_next_q,
            bootstrap_maxima=bootstrap_maxima,
            rewards=rewards,
            td_targets=td_targets,
            detached_target_base=detached_target_base,
            replacement_target=replacement_target,
            prediction=prediction,
            mse_prediction_input=mse_prediction_input,
            mse_target_input=mse_target_input,
            loss=loss,
            actions=actions,
            target_forward_count=calls["target"],
            online_forward_count=calls["online"],
            backward_executed=False,
            optimizer_mutation_executed=False,
            online_parameters=tuple(online.parameters()),
            target_parameters=tuple(target.parameters()),
        )


TDAdapterFactory = Callable[[], TDLossContractAdapter]


def _validate_td_loss_observation(
    observation: TDLossObservation,
) -> dict[str, Any]:
    """Validate captured values without replacing the adapter's computation."""
    shapes = {
        "target_next_q": _shape(observation.target_next_q),
        "bootstrap_maxima": _shape(observation.bootstrap_maxima),
        "td_rewards": _shape(observation.rewards),
        "td_targets": _shape(observation.td_targets),
        "detached_target_base": _shape(observation.detached_target_base),
        "replacement_target": _shape(observation.replacement_target),
        "online_prediction": _shape(observation.prediction),
        "mse_prediction_input": _shape(observation.mse_prediction_input),
        "mse_target_input": _shape(observation.mse_target_input),
        "scalar_loss": _shape(observation.loss),
    }
    expected_shapes = {
        "target_next_q": (B * N, A),
        "bootstrap_maxima": (B * N,),
        "td_rewards": (B * N,),
        "td_targets": (B * N,),
        "detached_target_base": (B * N, A),
        "replacement_target": (B * N, A),
        "online_prediction": (B * N, A),
        "mse_prediction_input": (B * N, A),
        "mse_target_input": (B * N, A),
        "scalar_loss": (),
    }
    if shapes != expected_shapes:
        raise ContractViolation("TD/loss shape invariant failed")

    value_checks = {
        "bootstrap_maxima": _all_close(
            observation.bootstrap_maxima, EXPECTED_BOOTSTRAP_MAXIMA
        ),
        "td_rewards": _all_close(observation.rewards, TD_REWARDS),
        "td_targets": _all_close(observation.td_targets, EXPECTED_TD_TARGETS),
        "target_matrix": _all_close(
            observation.replacement_target, EXPECTED_TARGET_MATRIX
        ),
        "loss": _all_close(observation.loss, EXPECTED_LOSS),
    }
    if not all(value_checks.values()):
        raise ContractViolation("TD/loss numerical invariant failed")

    base = _plain(observation.detached_target_base)
    replacement = _plain(observation.replacement_target)
    actions = _plain(observation.actions)
    if _shape(actions) != (B * N,):
        raise ContractViolation("selected-action shape invariant failed")

    replacement_checks: list[bool] = []
    unselected_checks: list[bool] = []
    changed_cells = 0
    for row in range(B * N):
        for column in range(A):
            changed = not _all_close(replacement[row][column], base[row][column])
            if changed:
                changed_cells += 1
            if column == actions[row]:
                replacement_checks.append(changed)
                replacement_checks.append(
                    _all_close(replacement[row][column], EXPECTED_TD_TARGETS[row])
                )
            else:
                unselected_checks.append(
                    _all_close(replacement[row][column], base[row][column])
                )
    if changed_cells != B * N or not all(replacement_checks):
        raise ContractViolation("selected-cell replacement invariant failed")
    if not all(unselected_checks):
        raise ContractViolation("unselected-cell preservation invariant failed")

    if getattr(observation.detached_target_base, "requires_grad", None) is not False:
        raise ContractViolation("detached target-base invariant failed")
    if getattr(observation.prediction, "requires_grad", None) is not True:
        raise ContractViolation("differentiable prediction invariant failed")
    if observation.target_forward_count != 1:
        raise ContractViolation("target forward-count invariant failed")
    if observation.online_forward_count != 2:
        raise ContractViolation("online forward-count invariant failed")
    if observation.backward_executed or observation.optimizer_mutation_executed:
        raise ContractViolation("Module B mutation boundary failed")
    if not _finite_numeric(observation.loss):
        raise ContractViolation("finite-loss invariant failed")

    return {
        "td_loss_shapes": shapes,
        "td_loss_value_checks": value_checks,
        "selected_cells_replaced": changed_cells,
        "unselected_cells_preserved": all(unselected_checks),
        "detached_target_base": True,
        "prediction_differentiable": True,
        "finite_loss": True,
        "loss_value": float(_plain(observation.loss)),
        "target_forward_count": observation.target_forward_count,
        "online_forward_count": observation.online_forward_count,
        "backward_executed": False,
        "optimizer_mutation_executed": False,
        "terminal_tensor_observed": False,
    }


def observe_td_loss_contract(factory: TDAdapterFactory) -> dict[str, Any]:
    """Collect and validate one adapter-produced TD/loss observation."""
    return _validate_td_loss_observation(factory().observe_td_loss())


def _td_result(factory: TDAdapterFactory) -> dict[str, Any]:
    try:
        evidence = observe_td_loss_contract(factory)
    except RequiredDependencyUnavailable:
        return {
            "status": "blocked",
            "message": "required TD/loss dependency is unavailable",
            "evidence": {"phase": "td_target_or_loss"},
        }
    except InertBoundaryTouched:
        return {
            "status": "blocked",
            "message": "TD/loss computation touched an inert boundary",
            "evidence": {"phase": "td_target_or_loss"},
        }
    except ContractUnresolved:
        return {
            "status": "inconclusive",
            "message": "TD/loss contract could not be observed unambiguously",
            "evidence": {"phase": "td_target_or_loss"},
        }
    except ContractViolation:
        return {
            "status": "fail",
            "message": "one or more TD/loss contract invariants failed",
            "evidence": {"phase": "td_target_or_loss"},
        }
    except BaseException as exc:
        return {
            "status": "inconclusive",
            "message": "unexpected TD/loss observation boundary",
            "evidence": {
                "phase": "td_target_or_loss",
                "error_type": type(exc).__name__,
            },
        }

    return {
        "status": "pass",
        "message": "synthetic Candidate N TD/loss invariants passed",
        "evidence": evidence,
    }


@dataclass
class PostLossRunState:
    """Private in-process state used to validate the controlled stop."""

    loss_captured: bool = False
    module_b_complete: bool = False
    zero_grad_guard_count: int = 0
    real_zero_grad_calls: int = 0
    forbidden_calls: dict[str, int] = field(
        default_factory=lambda: {
            "backward": 0,
            "gradient_clipping": 0,
            "optimizer_step": 0,
            "exploration_decay": 0,
        }
    )
    observation: TDLossObservation | None = None
    module_b_evidence: dict[str, Any] | None = None
    online_snapshot: tuple[Any, ...] = ()
    target_snapshot: tuple[Any, ...] = ()
    online_gradient_snapshot: tuple[Any, ...] = ()
    target_gradient_snapshot: tuple[Any, ...] = ()
    optimizer_state_before: Any = None
    wrapped_optimizer: Any = None


class PostLossContractAdapter(Protocol):
    """Minimal controlled-update interface for synthetic and real adapters."""

    state: PostLossRunState

    def execute(self) -> None: ...


class ForbiddenOperationSentinels:
    """Explicitly fail if execution proceeds into a forbidden operation."""

    def __init__(self, state: PostLossRunState) -> None:
        self._state = state

    def _reject(self, operation: str) -> None:
        self._state.forbidden_calls[operation] += 1
        raise ForbiddenPostLossOperation("forbidden post-loss operation reached")

    def backward(self) -> None:
        self._reject("backward")

    def gradient_clipping(self) -> None:
        self._reject("gradient_clipping")

    def optimizer_step(self) -> None:
        self._reject("optimizer_step")

    def exploration_decay(self) -> None:
        self._reject("exploration_decay")


class SyntheticWrappedOptimizer:
    """Sentinel optimizer whose real mutation methods must never be delegated to."""

    def __init__(
        self,
        state: PostLossRunState,
        sentinels: ForbiddenOperationSentinels,
    ) -> None:
        self._state = state
        self._sentinels = sentinels
        self._optimizer_state = {"synthetic_state_counter": 0}

    def zero_grad(self, *args: Any, **kwargs: Any) -> None:
        self._state.real_zero_grad_calls += 1
        self._optimizer_state["synthetic_state_counter"] += 1
        raise ForbiddenPostLossOperation("wrapped zero_grad unexpectedly executed")

    def step(self, *args: Any, **kwargs: Any) -> None:
        self._sentinels.optimizer_step()

    def state_dict(self) -> dict[str, int]:
        return copy.deepcopy(self._optimizer_state)


class PostLossOptimizerGuard:
    """Stop at zero_grad without invoking the wrapped optimizer."""

    def __init__(
        self,
        wrapped: SyntheticWrappedOptimizer,
        state: PostLossRunState,
        sentinels: ForbiddenOperationSentinels,
    ) -> None:
        self._wrapped = wrapped
        self._state = state
        self._sentinels = sentinels

    def zero_grad(self, *args: Any, **kwargs: Any) -> None:
        self._state.zero_grad_guard_count += 1
        raise PostLossMutationBoundaryReached(
            preconditions_met=(
                self._state.loss_captured and self._state.module_b_complete
            )
        )

    def step(self, *args: Any, **kwargs: Any) -> None:
        self._sentinels.optimizer_step()


def _parameter_snapshot(parameters: Sequence[Any]) -> tuple[Any, ...]:
    return tuple(parameter.detach().clone() for parameter in parameters)


def _gradient_snapshot(parameters: Sequence[Any]) -> tuple[Any, ...]:
    return tuple(
        None if parameter.grad is None else parameter.grad.detach().clone()
        for parameter in parameters
    )


def _parameters_unchanged(
    parameters: Sequence[Any], snapshots: Sequence[Any]
) -> bool:
    if len(parameters) != len(snapshots):
        return False
    return all(
        bool(parameter.detach().equal(snapshot))
        for parameter, snapshot in zip(parameters, snapshots)
    )


def _gradients_unchanged(
    parameters: Sequence[Any], snapshots: Sequence[Any]
) -> bool:
    if len(parameters) != len(snapshots):
        return False
    for parameter, snapshot in zip(parameters, snapshots):
        current = parameter.grad
        if current is None or snapshot is None:
            if current is not None or snapshot is not None:
                return False
        elif not bool(current.detach().equal(snapshot)):
            return False
    return True


class SyntheticPostLossUpdateFixture:
    """Synthetic update shell that deliberately stops before mutation."""

    def __init__(
        self,
        *,
        td_mode: str = "pass",
        guard_mode: str = "pass",
        private_marker: str = "",
        preexisting_gradients: bool = False,
    ) -> None:
        self.td_mode = td_mode
        self.guard_mode = guard_mode
        self.private_marker = private_marker
        self.preexisting_gradients = preexisting_gradients
        self.state = PostLossRunState()

    def execute(self) -> None:
        if self.guard_mode == "installation_blocked":
            raise GuardInstallationBlocked("post-loss guard unavailable")
        if self.guard_mode == "unexpected":
            raise RuntimeError(self.private_marker)

        sentinels = ForbiddenOperationSentinels(self.state)
        wrapped = SyntheticWrappedOptimizer(self.state, sentinels)
        guard = PostLossOptimizerGuard(wrapped, self.state, sentinels)
        self.state.wrapped_optimizer = wrapped

        if self.guard_mode == "premature":
            guard.zero_grad()

        observation = SyntheticTDLossFixture(
            mode=self.td_mode,
            private_marker=self.private_marker,
            preexisting_gradients=self.preexisting_gradients,
        ).observe_td_loss()
        module_b_evidence = _validate_td_loss_observation(observation)
        self.state.observation = observation
        self.state.module_b_evidence = module_b_evidence
        self.state.loss_captured = (
            _shape(observation.loss) == () and _finite_numeric(observation.loss)
        )
        self.state.module_b_complete = True
        self.state.online_snapshot = _parameter_snapshot(
            observation.online_parameters
        )
        self.state.target_snapshot = _parameter_snapshot(
            observation.target_parameters
        )
        self.state.online_gradient_snapshot = _gradient_snapshot(
            observation.online_parameters
        )
        self.state.target_gradient_snapshot = _gradient_snapshot(
            observation.target_parameters
        )
        self.state.optimizer_state_before = wrapped.state_dict()

        if self.guard_mode == "missing":
            return
        if self.guard_mode == "forbidden_backward":
            sentinels.backward()
        if self.guard_mode == "forbidden_clipping":
            sentinels.gradient_clipping()
        if self.guard_mode == "forbidden_step":
            guard.step()
        if self.guard_mode == "forbidden_exploration":
            sentinels.exploration_decay()

        guard.zero_grad()

        sentinels.backward()
        sentinels.gradient_clipping()
        guard.step()
        sentinels.exploration_decay()


PostLossFixtureFactory = Callable[[], PostLossContractAdapter]


def _controlled_stop_result(state: PostLossRunState) -> dict[str, Any]:
    observation = state.observation
    if observation is None or state.module_b_evidence is None:
        return {
            "status": "fail",
            "message": "controlled stop lacked required pre-mutation evidence",
            "evidence": {"phase": "post_loss_guard"},
        }

    online_parameters_unchanged = _parameters_unchanged(
        observation.online_parameters, state.online_snapshot
    )
    target_parameters_unchanged = _parameters_unchanged(
        observation.target_parameters, state.target_snapshot
    )
    online_gradients_unchanged = _gradients_unchanged(
        observation.online_parameters, state.online_gradient_snapshot
    )
    target_gradients_unchanged = _gradients_unchanged(
        observation.target_parameters, state.target_gradient_snapshot
    )
    preexisting_gradients_present = any(
        snapshot is not None
        for snapshot in (
            *state.online_gradient_snapshot,
            *state.target_gradient_snapshot,
        )
    )
    optimizer_state_unchanged = (
        state.wrapped_optimizer is not None
        and state.wrapped_optimizer.state_dict() == state.optimizer_state_before
    )
    forbidden_operations_absent = all(
        count == 0 for count in state.forbidden_calls.values()
    )
    checks = {
        "loss_captured_before_guard": state.loss_captured,
        "module_b_complete_before_guard": state.module_b_complete,
        "guard_reached_once": state.zero_grad_guard_count == 1,
        "real_zero_grad_not_called": state.real_zero_grad_calls == 0,
        "forbidden_operations_absent": forbidden_operations_absent,
        "online_parameters_unchanged": online_parameters_unchanged,
        "target_parameters_unchanged": target_parameters_unchanged,
        "online_gradients_unchanged": online_gradients_unchanged,
        "target_gradients_unchanged": target_gradients_unchanged,
        "optimizer_state_unchanged": optimizer_state_unchanged,
    }
    if not all(checks.values()):
        return {
            "status": "fail",
            "message": "post-loss mutation-boundary invariant failed",
            "evidence": {"post_loss_guard_checks": checks},
        }

    return {
        "status": "pass",
        "message": "controlled post-loss mutation boundary passed",
        "evidence": {
            **state.module_b_evidence,
            "controlled_stop": "POST_LOSS_MUTATION_BOUNDARY",
            "post_loss_guard_checks": checks,
            "zero_grad_guard_count": state.zero_grad_guard_count,
            "real_zero_grad_calls": state.real_zero_grad_calls,
            "preexisting_gradients_present": preexisting_gradients_present,
            "forbidden_operation_counts": dict(state.forbidden_calls),
        },
    }


def _post_loss_result(factory: PostLossFixtureFactory) -> dict[str, Any]:
    fixture = factory()
    try:
        fixture.execute()
    except PostLossMutationBoundaryReached as signal:
        if not signal.preconditions_met:
            return {
                "status": "fail",
                "message": "mutation guard was reached before loss capture",
                "evidence": {"phase": "post_loss_guard"},
            }
        return _controlled_stop_result(fixture.state)
    except GuardInstallationBlocked:
        return {
            "status": "blocked",
            "message": "post-loss mutation guard could not be installed",
            "evidence": {"phase": "post_loss_guard"},
        }
    except RequiredDependencyUnavailable:
        return {
            "status": "blocked",
            "message": "required post-loss dependency is unavailable",
            "evidence": {"phase": "post_loss_guard"},
        }
    except InertBoundaryTouched:
        return {
            "status": "blocked",
            "message": "post-loss computation touched an inert boundary",
            "evidence": {"phase": "post_loss_guard"},
        }
    except ForbiddenPostLossOperation:
        return {
            "status": "fail",
            "message": "forbidden post-loss operation was reached",
            "evidence": {
                "phase": "post_loss_guard",
                "forbidden_operation_counts": dict(
                    fixture.state.forbidden_calls
                ),
            },
        }
    except ContractUnresolved:
        return {
            "status": "inconclusive",
            "message": "post-loss contract could not be observed unambiguously",
            "evidence": {"phase": "post_loss_guard"},
        }
    except ContractViolation:
        return {
            "status": "fail",
            "message": "pre-mutation TD/loss invariant failed",
            "evidence": {"phase": "post_loss_guard"},
        }
    except BaseException as exc:
        return {
            "status": "inconclusive",
            "message": "unexpected post-loss observation boundary",
            "evidence": {
                "phase": "post_loss_guard",
                "error_type": type(exc).__name__,
            },
        }

    if fixture.state.loss_captured and fixture.state.module_b_complete:
        return {
            "status": "inconclusive",
            "message": (
                "update returned without reaching the expected mutation boundary"
            ),
            "evidence": {"phase": "post_loss_guard"},
        }
    return {
        "status": "inconclusive",
        "message": "post-loss mutation boundary was not observed",
        "evidence": {"phase": "post_loss_guard"},
    }


class SyntheticActionSelectionFixture:
    """Deterministic exploitation fixture for the action observer."""

    def __init__(self, *, mode: str = "pass", private_marker: str = "") -> None:
        self._mode = mode
        self._private_marker = private_marker
        self._calls = 0

    def select_actions(self, features: Any) -> tuple[Any, Any]:
        """Mimic only a deterministic real-method action interface."""
        import torch

        self._calls += 1
        q_output = torch.tensor(
            ((1.0, -1.0),) * int(features.shape[0]),
            dtype=torch.float32,
        )
        actions = q_output.argmax(dim=1)
        if self._mode == "mismatch":
            actions = actions.clone()
            actions[0] = 1
        return q_output, actions

    def observe_action_selection(self) -> ActionSelectionObservation:
        if self._mode == "blocked":
            raise InertBoundaryTouched("synthetic action inert boundary")
        if self._mode == "inconclusive":
            raise ContractUnresolved("synthetic action interface unresolved")
        if self._mode == "unexpected":
            raise RuntimeError(self._private_marker)

        try:
            import torch
        except ImportError as exc:
            raise RequiredDependencyUnavailable(
                "required public tensor dependency unavailable"
            ) from exc

        features = torch.zeros((N, F), dtype=torch.float32)
        q_output, actions = self.select_actions(features)
        return ActionSelectionObservation(
            q_output=q_output,
            actions=actions,
            method_invocation_count=self._calls,
            deterministic_exploitation_only=True,
            epsilon_random_executed=False,
        )


def _observe_action_selection(factory: ActionAdapterFactory) -> dict[str, Any]:
    observation = factory().observe_action_selection()
    shapes = {
        "action_q_output": _shape(observation.q_output),
        "greedy_actions": _shape(observation.actions),
    }
    if shapes != {
        "action_q_output": (N, A),
        "greedy_actions": (N,),
    }:
        raise ContractViolation("action-selection shape invariant failed")
    if not _all_close(observation.q_output, ((1.0, -1.0),) * N):
        raise ContractViolation("action-selection Q-value invariant failed")
    if _plain(observation.actions) != (0, 0, 0):
        raise ContractViolation("greedy-action invariant failed")
    if observation.method_invocation_count != 1:
        raise ContractViolation("action-method invocation invariant failed")
    if not observation.deterministic_exploitation_only:
        raise ContractViolation("deterministic exploitation invariant failed")
    if observation.epsilon_random_executed:
        raise ContractViolation("epsilon-random path was unexpectedly executed")

    return {
        "action_selection_shapes": shapes,
        "greedy_actions": list(_plain(observation.actions)),
        "action_selection_method_count": observation.method_invocation_count,
        "deterministic_exploitation_only": True,
        "epsilon_random_executed": False,
    }


def _state_dict_snapshot(model: Any) -> dict[str, Any]:
    return {
        str(name): value.detach().clone()
        for name, value in model.state_dict().items()
    }


def _state_dicts_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    if tuple(left) != tuple(right):
        return False
    return all(bool(left[name].equal(right[name])) for name in left)


class SyntheticHardSyncFixture:
    """Isolated hard-sync fixture, separate from Module C update execution."""

    def __init__(self, *, mode: str = "pass", private_marker: str = "") -> None:
        self._mode = mode
        self._private_marker = private_marker
        self._calls = 0

    def synchronize_target(self, online: Any, target: Any) -> None:
        """Mimic a real-interface hard online-to-target state copy."""
        self._calls += 1
        target.load_state_dict(online.state_dict())

    def observe_hard_sync(self) -> HardSyncObservation:
        if self._mode == "blocked":
            raise InertBoundaryTouched("synthetic sync inert boundary")
        if self._mode == "inconclusive":
            raise ContractUnresolved("synthetic sync interface unresolved")
        if self._mode == "unexpected":
            raise RuntimeError(self._private_marker)

        try:
            import torch
            from torch import nn
        except ImportError as exc:
            raise RequiredDependencyUnavailable(
                "required public tensor dependency unavailable"
            ) from exc

        online = nn.Linear(2, 2, bias=True)
        target = nn.Linear(2, 2, bias=True)
        with torch.no_grad():
            online.weight.fill_(1.0)
            online.bias.fill_(0.5)
            target.weight.fill_(-1.0)
            target.bias.fill_(-0.5)

        online_before = _state_dict_snapshot(online)
        target_before = _state_dict_snapshot(target)
        states_differ_before = not _state_dicts_equal(
            online_before, target_before
        )
        self.synchronize_target(online, target)
        if self._mode == "mismatch":
            with torch.no_grad():
                target.bias.add_(1.0)

        online_after = _state_dict_snapshot(online)
        target_after = _state_dict_snapshot(target)
        return HardSyncObservation(
            states_differ_before=states_differ_before,
            sync_invocation_count=self._calls,
            complete_equality_after=_state_dicts_equal(
                online_after, target_after
            ),
            online_state_unchanged=_state_dicts_equal(
                online_before, online_after
            ),
        )


def _observe_hard_sync(factory: SyncAdapterFactory) -> dict[str, Any]:
    observation = factory().observe_hard_sync()
    checks = {
        "states_differ_before": observation.states_differ_before,
        "sync_invoked_once": observation.sync_invocation_count == 1,
        "complete_equality_after": observation.complete_equality_after,
        "online_state_unchanged": observation.online_state_unchanged,
    }
    if not all(checks.values()):
        raise ContractViolation("hard target-sync invariant failed")
    return {
        "hard_sync_checks": checks,
        "hard_target_sync_count": observation.sync_invocation_count,
        "target_sync_schedule_characterized": False,
        "target_sync_microcheck_mutation": "EXPECTED",
    }


class PassiveEdgeObserver:
    """Capture an edge reference without returning or substituting a value."""

    def __init__(self) -> None:
        self.observed: Any | None = None

    def observe(self, edge_index: Any) -> None:
        self.observed = edge_index


class SyntheticGraphEdgeFixture:
    """Generic graph fixture that validates passive edge observation."""

    def __init__(self, *, mode: str = "pass", private_marker: str = "") -> None:
        self._mode = mode
        self._private_marker = private_marker

    def observe_graph_edges(self) -> GraphEdgeObservation:
        if self._mode == "blocked":
            raise InertBoundaryTouched("synthetic edge inert boundary")
        if self._mode == "inconclusive":
            raise ContractUnresolved("synthetic edge interface unresolved")
        if self._mode == "unexpected":
            raise RuntimeError(self._private_marker)

        observer = PassiveEdgeObserver()
        model_retained_edge = SINGLE_GRAPH_EDGE_INDEX
        forward_invocation_count = 0

        def forward(features: Any) -> Any:
            nonlocal forward_invocation_count
            forward_invocation_count += 1
            if self._mode != "unobservable":
                edge = model_retained_edge
                if self._mode == "replacement":
                    edge = tuple(tuple(list(row)) for row in edge)
                observer.observe(edge)
            return features

        features = tuple(tuple(0.0 for _ in range(F)) for _ in range(B * N))
        returned_features = forward(features)
        if returned_features is not features:
            raise ContractViolation("graph observer replaced node features")
        observed_edge = observer.observed
        return GraphEdgeObservation(
            constructed_batch_edge=_constructed_edges(),
            model_retained_edge=model_retained_edge,
            forward_observed_edge=observed_edge,
            observer_substituted_edge=False,
            forward_edge_identity_preserved=(
                None
                if observed_edge is None
                else observed_edge is model_retained_edge
            ),
            forward_invocation_count=forward_invocation_count,
        )


def _observe_graph_edges(factory: EdgeAdapterFactory) -> dict[str, Any]:
    observation = factory().observe_graph_edges()
    if observation.forward_observed_edge is None:
        raise ContractUnresolved(
            "forward edge use could not be observed without substitution"
        )
    shapes = {
        "constructed_batch_edge_shape": _shape(
            observation.constructed_batch_edge
        ),
        "model_retained_edge_shape": _shape(observation.model_retained_edge),
        "forward_observed_edge_shape": _shape(
            observation.forward_observed_edge
        ),
    }
    if shapes != {
        "constructed_batch_edge_shape": (2, B * E),
        "model_retained_edge_shape": (2, E),
        "forward_observed_edge_shape": (2, E),
    }:
        raise ContractViolation("graph-edge shape invariant failed")
    if observation.observer_substituted_edge:
        raise ContractViolation("graph observer substituted the edge input")
    if observation.forward_edge_identity_preserved is not True:
        raise ContractViolation("forward edge identity was not preserved")
    if observation.forward_invocation_count != 1:
        raise ContractViolation("graph forward-count invariant failed")
    return {
        "graph_edge_shapes": shapes,
        "edge_observer_substituted_input": False,
        "forward_edge_identity_preserved": True,
        "graph_forward_count": observation.forward_invocation_count,
        "candidate_n_runtime_edge_behavior_proven": False,
    }


def _module_d_result(
    action_factory: ActionAdapterFactory,
    sync_factory: SyncAdapterFactory,
    edge_factory: EdgeAdapterFactory,
) -> dict[str, Any]:
    try:
        action_evidence = _observe_action_selection(action_factory)
        sync_evidence = _observe_hard_sync(sync_factory)
        edge_evidence = _observe_graph_edges(edge_factory)
    except RequiredDependencyUnavailable:
        return {
            "status": "blocked",
            "message": "required Module D dependency is unavailable",
            "evidence": {"phase": "module_d_observation"},
        }
    except InertBoundaryTouched:
        return {
            "status": "blocked",
            "message": "Module D computation touched an inert boundary",
            "evidence": {"phase": "module_d_observation"},
        }
    except ContractUnresolved:
        return {
            "status": "inconclusive",
            "message": "Module D contract could not be observed unambiguously",
            "evidence": {"phase": "module_d_observation"},
        }
    except ContractViolation:
        return {
            "status": "fail",
            "message": "one or more Module D invariants failed",
            "evidence": {"phase": "module_d_observation"},
        }
    except BaseException as exc:
        return {
            "status": "inconclusive",
            "message": "unexpected Module D observation boundary",
            "evidence": {
                "phase": "module_d_observation",
                "error_type": type(exc).__name__,
            },
        }

    return {
        "status": "pass",
        "message": "synthetic Candidate N Module D invariants passed",
        "evidence": {
            **action_evidence,
            **sync_evidence,
            **edge_evidence,
            "update_path_parameter_mutation": "NO",
        },
    }


def _result(factory: AdapterFactory) -> dict[str, Any]:
    try:
        evidence = observe_contract(factory)
    except InertBoundaryTouched:
        return {
            "status": "blocked",
            "message": "replay computation touched an inert boundary",
            "evidence": {"phase": "replay_or_batching"},
        }
    except ContractUnresolved:
        return {
            "status": "inconclusive",
            "message": "replay contract could not be observed unambiguously",
            "evidence": {"phase": "replay_or_batching"},
        }
    except ContractViolation:
        return {
            "status": "fail",
            "message": "one or more replay contract invariants failed",
            "evidence": {"phase": "replay_or_batching"},
        }
    except BaseException as exc:
        return {
            "status": "inconclusive",
            "message": "unexpected replay observation boundary",
            "evidence": {
                "phase": "replay_or_batching",
                "error_type": type(exc).__name__,
            },
        }

    return {
        "status": "pass",
        "message": "synthetic Candidate N replay contract invariants passed",
        "evidence": {
            **evidence,
            "required_real": list(REQUIRED_REAL),
            "safe_inert_boundary": list(SAFE_INERT_BOUNDARY),
            "not_required": list(NOT_REQUIRED),
            "contract_dimensions": {
                "B": B,
                "N": N,
                "E": E,
                "F": F,
                "A": A,
            },
            "td_loss_executed": False,
        },
    }


def run_integrated_contract(
    context: Any,
    *,
    replay_factory: AdapterFactory,
    post_loss_factory: PostLossFixtureFactory,
    action_factory: ActionAdapterFactory,
    sync_factory: SyncAdapterFactory,
    edge_factory: EdgeAdapterFactory,
) -> dict[str, Any]:
    """Compose Modules A-D without duplicating their tested control flow."""
    result = _result(replay_factory)
    if result["status"] != "pass":
        return result

    post_loss_result = _post_loss_result(post_loss_factory)
    if post_loss_result["status"] != "pass":
        return post_loss_result

    module_d_result = _module_d_result(
        action_factory,
        sync_factory,
        edge_factory,
    )
    if module_d_result["status"] != "pass":
        return module_d_result

    result["message"] = "Candidate N Modules A-D contract invariants passed"
    result["evidence"].update(post_loss_result["evidence"])
    result["evidence"].update(module_d_result["evidence"])
    result["evidence"]["td_loss_executed"] = True

    for label, dimensions in result["evidence"]["pre_batch_shapes"].items():
        context.record_shape(label, dimensions)
    for label, dimensions in result["evidence"]["flattened_shapes"].items():
        context.record_shape(label, dimensions)
    for label, dimensions in result["evidence"]["td_loss_shapes"].items():
        context.record_shape(label, dimensions)
    for label, dimensions in result["evidence"][
        "action_selection_shapes"
    ].items():
        context.record_shape(label, dimensions)
    for label, dimensions in result["evidence"]["graph_edge_shapes"].items():
        context.record_shape(label, dimensions)
    context.record_call("store_transition", B)
    context.record_call("build_batch", 1)
    context.record_call(
        "target_network_forward",
        result["evidence"]["target_forward_count"],
    )
    context.record_call(
        "online_network_forward",
        result["evidence"]["online_forward_count"],
    )
    context.record_call(
        "zero_grad_guard",
        result["evidence"]["zero_grad_guard_count"],
    )
    context.record_call(
        "action_selection_method",
        result["evidence"]["action_selection_method_count"],
    )
    context.record_call(
        "hard_target_sync",
        result["evidence"]["hard_target_sync_count"],
    )
    context.record_call(
        "graph_forward",
        result["evidence"]["graph_forward_count"],
    )

    return result


def probe(context: Any) -> dict[str, Any]:
    """Run public synthetic Modules A-D through the shared harness."""
    mode = str(context.parameters.get("synthetic_mode", "pass"))
    td_mode = str(context.parameters.get("td_synthetic_mode", "pass"))
    guard_mode = str(context.parameters.get("guard_synthetic_mode", "pass"))
    action_mode = str(
        context.parameters.get("action_synthetic_mode", "pass")
    )
    sync_mode = str(context.parameters.get("sync_synthetic_mode", "pass"))
    edge_mode = str(context.parameters.get("edge_synthetic_mode", "pass"))
    retain_done = bool(context.parameters.get("retain_done", False))
    private_marker = str(context.parameters.get("private_marker", ""))

    return run_integrated_contract(
        context,
        replay_factory=lambda: SyntheticReplayFixture(
            retain_done=retain_done,
            mode=mode,
            private_marker=private_marker,
        ),
        post_loss_factory=lambda: SyntheticPostLossUpdateFixture(
            td_mode=td_mode,
            guard_mode=guard_mode,
            private_marker=private_marker,
        ),
        action_factory=lambda: SyntheticActionSelectionFixture(
            mode=action_mode,
            private_marker=private_marker,
        ),
        sync_factory=lambda: SyntheticHardSyncFixture(
            mode=sync_mode,
            private_marker=private_marker,
        ),
        edge_factory=lambda: SyntheticGraphEdgeFixture(
            mode=edge_mode,
            private_marker=private_marker,
        ),
    )
