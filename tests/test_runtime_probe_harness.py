from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = ROOT / "scripts" / "runtime_probes" / "harness.py"
FAKE_WORLD_PATH = ROOT / "scripts" / "runtime_probes" / "fake_world.py"


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


harness = load_module("runtime_probe_harness", HARNESS_PATH)
fake_world = load_module("runtime_probe_fake_world", FAKE_WORLD_PATH)


class RuntimeProbeHarnessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_probe(self, body: str, name: str = "probe.py") -> Path:
        path = self.base / name
        path.write_text(textwrap.dedent(body), encoding="utf-8")
        return path

    def test_successful_isolated_execution_and_evidence_hooks(self) -> None:
        probe = self.make_probe(
            """
            from pathlib import Path

            def probe(context):
                context.record_shape("observation", ["N", "F"])
                context.record_call("reset")
                print("synthetic probe completed")
                return {
                    "status": "pass",
                    "message": "isolated",
                    "evidence": {
                        "cwd_matches": Path.cwd() == context.work_dir,
                        "cpu_only": __import__("os").environ.get("CUDA_VISIBLE_DEVICES") == "-1",
                    },
                }
            """
        )

        result = harness.run_isolated_probe(probe, "SYNTH-SUCCESS")

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["exit_status"], 0)
        self.assertFalse(result["timed_out"])
        self.assertIn("synthetic probe completed", result["stdout"])
        self.assertEqual(
            result["evidence"]["shapes"],
            [{"label": "observation", "dimensions": ["N", "F"]}],
        )
        self.assertEqual(
            result["evidence"]["calls"], [{"label": "reset", "count": 1}]
        )
        self.assertTrue(result["evidence"]["values"]["cwd_matches"])
        self.assertTrue(result["evidence"]["values"]["cpu_only"])

    def test_timeout_is_reported_as_blocked(self) -> None:
        probe = self.make_probe(
            """
            import time

            def probe(context):
                time.sleep(2)
                return {"status": "pass"}
            """
        )

        result = harness.run_isolated_probe(
            probe, "SYNTH-TIMEOUT", timeout_seconds=0.2
        )

        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["timed_out"])
        self.assertIsNone(result["exit_status"])

    def test_write_outside_allowed_roots_is_blocked(self) -> None:
        blocked_target = self.base / "must-not-exist.txt"
        probe = self.make_probe(
            """
            from pathlib import Path

            def probe(context):
                Path(context.parameters["target"]).write_text("blocked", encoding="utf-8")
                return {"status": "pass"}
            """
        )

        result = harness.run_isolated_probe(
            probe,
            "SYNTH-BLOCK-WRITE",
            parameters={"target": str(blocked_target)},
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["exit_status"], 4)
        self.assertFalse(blocked_target.exists())
        self.assertNotIn(str(self.base), json.dumps(result, sort_keys=True))

    def test_write_inside_temporary_work_directory_is_allowed(self) -> None:
        probe = self.make_probe(
            """
            def probe(context):
                target = context.work_dir / "allowed.txt"
                target.write_text("allowed", encoding="utf-8")
                return {
                    "status": "pass",
                    "evidence": {"written": target.read_text(encoding="utf-8")},
                }
            """
        )

        result = harness.run_isolated_probe(probe, "SYNTH-ALLOW-WRITE")

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["evidence"]["values"]["written"], "allowed")

    def test_output_exception_and_structured_paths_are_sanitised(self) -> None:
        private_path = self.base / "private" / "secret.txt"
        probe = self.make_probe(
            """
            def probe(context):
                print(context.parameters["private_path"])
                raise RuntimeError("private path: " + context.parameters["private_path"])
            """
        )

        result = harness.run_isolated_probe(
            probe,
            "SYNTH-SANITISE",
            parameters={"private_path": str(private_path)},
        )
        serialized = json.dumps(result, sort_keys=True)

        self.assertEqual(result["status"], "fail")
        self.assertNotIn(str(self.base), serialized)
        self.assertNotIn("secret.txt", serialized)
        self.assertIn("<redacted-path>", serialized)

    def test_stderr_and_structured_evidence_are_sanitised(self) -> None:
        private_path = self.base / "private" / "structured-secret.txt"
        probe = self.make_probe(
            """
            import sys

            def probe(context):
                value = context.parameters["private_path"]
                print(value, file=sys.stderr)
                return {
                    "status": "pass",
                    "message": "structured path: " + value,
                    "evidence": {"location": value},
                }
            """
        )

        result = harness.run_isolated_probe(
            probe,
            "SYNTH-SANITISE-STRUCTURED",
            parameters={"private_path": str(private_path)},
        )
        serialized = json.dumps(result, sort_keys=True)

        self.assertEqual(result["status"], "pass")
        self.assertNotIn(str(self.base), serialized)
        self.assertNotIn("structured-secret.txt", serialized)
        self.assertIn("<redacted-path>", result["stderr"])
        self.assertIn("<redacted-path>", result["message"])
        self.assertEqual(
            result["evidence"]["values"]["location"], "<redacted-path>"
        )

    def test_network_creation_is_blocked(self) -> None:
        probe = self.make_probe(
            """
            import socket

            def probe(context):
                socket.socket()
                return {"status": "pass"}
            """
        )

        result = harness.run_isolated_probe(probe, "SYNTH-BLOCK-NETWORK")

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["exit_status"], 4)
        self.assertEqual(result["message"], "network access blocked")

    def test_nested_subprocess_creation_is_blocked(self) -> None:
        probe = self.make_probe(
            """
            import subprocess
            import sys

            def probe(context):
                subprocess.run([sys.executable, "-c", "pass"], check=True)
                return {"status": "pass"}
            """
        )

        result = harness.run_isolated_probe(probe, "SYNTH-BLOCK-SUBPROCESS")

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["exit_status"], 4)
        self.assertEqual(result["message"], "nested process creation blocked")

    def test_result_schema_is_stable_and_uses_no_external_modules(self) -> None:
        probe = self.make_probe(
            """
            import sys

            def probe(context):
                forbidden = [
                    name for name in ("torch", "gym", "sumo", "traci", "cityflow")
                    if name in sys.modules
                ]
                return {"status": "pass", "evidence": {"forbidden": forbidden}}
            """
        )

        first = harness.run_isolated_probe(probe, "SYNTH-SCHEMA")
        second = harness.run_isolated_probe(probe, "SYNTH-SCHEMA")
        expected_keys = {
            "schema_version",
            "probe_id",
            "status",
            "elapsed_seconds",
            "exit_status",
            "timed_out",
            "message",
            "evidence",
            "stdout",
            "stderr",
        }

        self.assertEqual(set(first), expected_keys)
        self.assertEqual(set(second), expected_keys)
        self.assertEqual(first["schema_version"], 1)
        self.assertEqual(first["evidence"]["values"]["forbidden"], [])
        first_without_time = {k: v for k, v in first.items() if k != "elapsed_seconds"}
        second_without_time = {k: v for k, v in second.items() if k != "elapsed_seconds"}
        self.assertEqual(first_without_time, second_without_time)

    def test_generic_synthetic_world_is_deterministic(self) -> None:
        world = fake_world.SyntheticWorld(
            node_count=2, feature_width=2, action_count=2
        )

        initial = world.reset()
        observation, rewards, dones, info = world.step([0, 1])

        self.assertEqual(initial, ((0.0, 1.0), (1.0, 2.0)))
        self.assertEqual(observation, ((1.0, 2.0), (2.0, 3.0)))
        self.assertEqual(rewards, (-0.0, -1.0))
        self.assertEqual(dones, (False, False))
        self.assertEqual(info, {"step": 1})


if __name__ == "__main__":
    unittest.main()
