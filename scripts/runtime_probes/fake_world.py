"""Generic standard-library fixtures for future framework probes.

These fixtures model only small deterministic state/action transitions.  They
do not reproduce any private framework, simulator, traffic network, or agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SyntheticIntersection:
    identifier: str
    action_count: int


class SyntheticWorld:
    """A deterministic node collection with reset and one-step observations."""

    def __init__(
        self,
        node_count: int = 2,
        feature_width: int = 3,
        action_count: int = 2,
    ) -> None:
        if min(node_count, feature_width, action_count) <= 0:
            raise ValueError("synthetic dimensions must be positive")
        self.node_count = node_count
        self.feature_width = feature_width
        self.action_count = action_count
        self.intersections = tuple(
            SyntheticIntersection(f"node-{index}", action_count)
            for index in range(node_count)
        )
        self.step_count = 0
        self.last_actions: tuple[int, ...] | None = None

    def observation(self) -> tuple[tuple[float, ...], ...]:
        return tuple(
            tuple(
                float(node + feature + self.step_count)
                for feature in range(self.feature_width)
            )
            for node in range(self.node_count)
        )

    def reset(self) -> tuple[tuple[float, ...], ...]:
        self.step_count = 0
        self.last_actions = None
        return self.observation()

    def step(
        self, actions: Sequence[int]
    ) -> tuple[
        tuple[tuple[float, ...], ...],
        tuple[float, ...],
        tuple[bool, ...],
        dict[str, int],
    ]:
        action_tuple = tuple(actions)
        if len(action_tuple) != self.node_count:
            raise ValueError("one synthetic action is required per node")
        if any(action < 0 or action >= self.action_count for action in action_tuple):
            raise ValueError("synthetic action is outside the declared range")
        self.last_actions = action_tuple
        self.step_count += 1
        rewards = tuple(-float(action) for action in action_tuple)
        dones = tuple(False for _ in range(self.node_count))
        return self.observation(), rewards, dones, {"step": self.step_count}
