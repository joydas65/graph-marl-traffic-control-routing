from __future__ import annotations

import importlib.util
import json
import os
import resource
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = ROOT / "scripts" / "runtime_probes" / "harness.py"
PROBE_PATH = ROOT / "scripts" / "runtime_probes" / "candidate_n_l1.py"
RUN_PROBE_PATH = ROOT / "scripts" / "runtime_probes" / "run_probe.py"
TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


harness = load_module("candidate_n_probe_harness", HARNESS_PATH)


@unittest.skipUnless(TORCH_AVAILABLE, "synthetic validation requires existing Torch")
class CandidateNL1ProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_source(self, body: str, *, read_only: bool = True) -> Path:
        source = self.base / "synthetic_candidate.py"
        source.write_text(textwrap.dedent(body), encoding="utf-8")
        if read_only:
            source.chmod(0o444)
        return source

    def run_probe(self, source: Path):
        with mock.patch.dict(os.environ, {"SOURCE_MODULE": str(source)}):
            return harness.run_isolated_probe(
                PROBE_PATH,
                "SYNTH-CANDIDATE-N-L1",
                timeout_seconds=60,
                cpu_time_seconds=30,
            )

    def test_linux_resource_limit_configuration(self) -> None:
        infinity = resource.RLIM_INFINITY
        with (
            mock.patch.object(
                harness.resource,
                "getrlimit",
                return_value=(infinity, infinity),
            ),
            mock.patch.object(harness.resource, "setrlimit") as set_limit,
        ):
            harness._apply_resource_limits(30, 4 * 1024**3)

        self.assertEqual(
            set_limit.call_args_list,
            [
                mock.call(harness.resource.RLIMIT_CPU, (30, infinity)),
                mock.call(
                    harness.resource.RLIMIT_AS,
                    (4 * 1024**3, infinity),
                ),
            ],
        )

    def test_existing_stricter_resource_limits_are_preserved(self) -> None:
        infinity = resource.RLIM_INFINITY
        with (
            mock.patch.object(
                harness.resource,
                "getrlimit",
                side_effect=[
                    (10, infinity),
                    (2 * 1024**3, infinity),
                ],
            ),
            mock.patch.object(harness.resource, "setrlimit") as set_limit,
        ):
            harness._apply_resource_limits(30, 4 * 1024**3)

        self.assertEqual(
            set_limit.call_args_list,
            [
                mock.call(harness.resource.RLIMIT_CPU, (10, infinity)),
                mock.call(
                    harness.resource.RLIMIT_AS,
                    (2 * 1024**3, infinity),
                ),
            ],
        )

    def test_synthetic_gcn_interface_passes(self) -> None:
        source = self.make_source(
            """
            from . import RLAgent
            from common.registry import Registry
            import gym
            from generator.lane_vehicle import LaneVehicleGenerator
            from generator.intersection_phase import IntersectionPhaseGenerator
            import torch
            from torch import nn

            @Registry.register_model("synthetic")
            class UnusedFrameworkAgent(RLAgent):
                pass

            class GCN(nn.Module):
                def __init__(self, input_dim, output_dim, edge_index):
                    super().__init__()
                    self.edge_index = edge_index
                    self.layer = nn.Linear(input_dim, output_dim)

                def forward(self, features, train=True):
                    if tuple(self.edge_index.shape) != (2, 4):
                        raise ValueError("unexpected synthetic edge shape")
                    return self.layer(features)
            """
        )

        result = self.run_probe(source)

        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["exit_status"], 0)
        shape_map = {
            item["label"]: item["dimensions"]
            for item in result["evidence"]["shapes"]
        }
        self.assertEqual(
            shape_map,
            {
                "edge_index": [2, 4],
                "greedy_action": [3],
                "input": [3, 3],
                "q_output": [3, 2],
            },
        )
        values = result["evidence"]["values"]
        self.assertTrue(values["source_unchanged"])
        self.assertTrue(values["deterministic_reconstruction"])
        self.assertEqual(values["forbidden_dependencies_loaded"], [])
        self.assertNotIn(str(self.base), str(result))

    def test_cli_runs_synthetic_candidate_with_cpu_limit(self) -> None:
        source = self.make_source(
            """
            import torch
            from torch import nn

            class GCN(nn.Module):
                def __init__(self, input_dim, output_dim, edge_index):
                    super().__init__()
                    self.layer = nn.Linear(input_dim, output_dim)

                def forward(self, features, train=True):
                    return self.layer(features)
            """
        )
        output = self.base / "result.json"
        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "SOURCE_MODULE": str(source),
            }
        )

        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(RUN_PROBE_PATH),
                str(PROBE_PATH),
                "--id",
                "SYNTH-CANDIDATE-N-L1-CLI",
                "--timeout",
                "60",
                "--cpu-time-limit",
                "30",
                "--output",
                str(output),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=65,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "pass")
        self.assertNotIn(str(self.base), output.read_text(encoding="utf-8"))

    def test_model_use_of_inert_stub_fails(self) -> None:
        source = self.make_source(
            """
            import gym
            import torch
            from torch import nn

            class GCN(nn.Module):
                def __init__(self, input_dim, output_dim, edge_index):
                    super().__init__()
                    self.layer = nn.Linear(input_dim, output_dim)

                def forward(self, features, train=True):
                    gym.spaces
                    return self.layer(features)
            """
        )

        result = self.run_probe(source)

        self.assertEqual(result["status"], "fail")
        self.assertEqual(
            result["message"],
            "model computation touched an inert import boundary",
        )
        self.assertEqual(
            result["evidence"]["values"]["phase"], "model_computation"
        )

    def test_forbidden_dependency_import_is_blocked(self) -> None:
        source = self.make_source(
            """
            import pfrl
            """
        )

        result = self.run_probe(source)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["message"], "forbidden dependency import blocked")
        self.assertEqual(result["evidence"]["values"]["error_type"], "pfrl")

    def test_dynamic_forbidden_dependency_import_fails(self) -> None:
        source = self.make_source(
            """
            import torch
            from torch import nn

            class GCN(nn.Module):
                def __init__(self, input_dim, output_dim, edge_index):
                    super().__init__()
                    self.layer = nn.Linear(input_dim, output_dim)

                def forward(self, features, train=True):
                    import cityflow
                    return self.layer(features)
            """
        )

        result = self.run_probe(source)

        self.assertEqual(result["status"], "fail")
        self.assertEqual(
            result["message"],
            "model computation attempted a forbidden dependency import",
        )
        self.assertEqual(
            result["evidence"]["values"]["error_type"], "cityflow"
        )

    def test_writable_source_is_blocked(self) -> None:
        source = self.make_source(
            """
            class GCN:
                pass
            """,
            read_only=False,
        )

        result = self.run_probe(source)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["message"], "source module is not read-only")

    def test_symlinked_source_is_blocked(self) -> None:
        source = self.make_source(
            """
            class GCN:
                pass
            """
        )
        source_link = self.base / "source-link.py"
        source_link.symlink_to(source)

        result = self.run_probe(source_link)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["message"], "source module is not a regular staged file"
        )


if __name__ == "__main__":
    unittest.main()
