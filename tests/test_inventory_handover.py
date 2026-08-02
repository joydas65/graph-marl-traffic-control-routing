from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "provenance"
    / "inventory_handover.py"
)
SPEC = importlib.util.spec_from_file_location("inventory_handover", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
inventory_handover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory_handover)


class InventoryHandoverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.gcqn = self.base / "gcqn"
        self.gcac = self.base / "gcac"
        self.gcqn.mkdir()
        self.gcac.mkdir()
        self.fixed_ns = 1_700_000_000_123_456_789

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_file(self, root: Path, relative_path: str, content: bytes) -> Path:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        os.utime(path, ns=(self.fixed_ns, self.fixed_ns))
        return path

    def populate(self) -> None:
        self.write_file(self.gcqn, "common/equal.txt", b"equal")
        self.write_file(self.gcac, "common/equal.txt", b"equal")
        self.write_file(self.gcqn, "common/different.txt", b"left")
        self.write_file(self.gcac, "common/different.txt", b"right")
        self.write_file(self.gcqn, "duplicates/one.bin", b"duplicate")
        self.write_file(self.gcqn, "duplicates/two.bin", b"duplicate")
        self.write_file(self.gcac, "elsewhere/copy.bin", b"duplicate")
        self.write_file(self.gcqn, "only-left.txt", b"left only")
        self.write_file(self.gcac, "only-right.txt", b"right only")

    def output_bytes(self, output: Path) -> dict[str, bytes]:
        return {
            path.name: path.read_bytes()
            for path in sorted(output.iterdir(), key=lambda item: item.name)
        }

    def test_deterministic_manifests_and_comparison(self) -> None:
        self.populate()
        first = self.base / "output-one"
        second = self.base / "output-two"

        summary_one = inventory_handover.run_inventory(self.gcqn, self.gcac, first)
        summary_two = inventory_handover.run_inventory(self.gcqn, self.gcac, second)

        self.assertEqual(summary_one, summary_two)
        self.assertEqual(self.output_bytes(first), self.output_bytes(second))
        comparison = json.loads((first / "comparison.json").read_text(encoding="utf-8"))
        self.assertEqual(comparison["summary"]["same_path_equal_content"], 1)
        self.assertEqual(comparison["summary"]["same_path_different_content"], 1)
        self.assertEqual(comparison["summary"]["cross_archive_duplicate_hash_groups"], 2)
        self.assertEqual(summary_one["gcqn"]["duplicate_hash_groups"], 1)

    def test_manifest_paths_are_relative_posix_paths(self) -> None:
        self.write_file(self.gcqn, "nested/example.py", b"print('ok')\n")
        self.write_file(self.gcac, "nested/example.py", b"print('ok')\n")
        output = self.base / "output"

        inventory_handover.run_inventory(self.gcqn, self.gcac, output)
        manifest = json.loads((output / "gcqn-manifest.json").read_text(encoding="utf-8"))

        for entry in manifest["entries"]:
            relative_path = entry["relative_path"]
            self.assertFalse(Path(relative_path).is_absolute())
            self.assertNotIn("\\", relative_path)
            self.assertNotIn(str(self.base), relative_path)

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_symlink_is_recorded_without_following_target(self) -> None:
        external = self.write_file(self.base, "external/private.bin", b"private target")
        os.symlink(external, self.gcqn / "external-link")
        self.write_file(self.gcac, "placeholder.txt", b"placeholder")
        output = self.base / "output"

        inventory_handover.run_inventory(self.gcqn, self.gcac, output)
        manifest = json.loads((output / "gcqn-manifest.json").read_text(encoding="utf-8"))
        link = next(entry for entry in manifest["entries"] if entry["entry_type"] == "symlink")

        self.assertEqual(link["relative_path"], "external-link")
        self.assertNotEqual(
            link["sha256"], inventory_handover.hash_regular_file(external)
        )
        self.assertEqual(manifest["summary"]["files"], 0)

    def test_rejects_output_that_overlaps_an_archive(self) -> None:
        with self.assertRaises(inventory_handover.InventoryConfigurationError):
            inventory_handover.validate_roots(
                self.gcqn, self.gcac, self.gcqn / "audit-output"
            )

    def test_embedded_git_summary_distinguishes_root_and_nested_metadata(self) -> None:
        for child, content in (("HEAD", b"ref: refs/heads/main\n"), ("config", b"")):
            self.write_file(self.gcqn, f".git/{child}", content)
            self.write_file(self.gcac, f"vendor/component/.git/{child}", content)
        (self.gcqn / ".git/refs").mkdir()
        (self.gcqn / ".git/objects").mkdir()
        (self.gcac / "vendor/component/.git/refs").mkdir()
        (self.gcac / "vendor/component/.git/objects").mkdir()

        gcqn_manifest = inventory_handover.build_archive_manifest(self.gcqn, "GCQN")
        gcac_manifest = inventory_handover.build_archive_manifest(self.gcac, "GCAC")
        gcqn_git = gcqn_manifest["summary"]["embedded_git"]
        gcac_git = gcac_manifest["summary"]["embedded_git"]

        self.assertTrue(gcqn_git["root_marker_present"])
        self.assertEqual(gcqn_git["root_marker_type"], "directory")
        self.assertEqual(gcqn_git["structurally_complete_git_directories"], 1)
        self.assertFalse(gcac_git["root_marker_present"])
        self.assertEqual(gcac_git["git_directory_markers"], 1)
        self.assertEqual(gcac_git["structurally_complete_git_directories"], 1)

    def test_unreadable_file_is_reported_without_absolute_path(self) -> None:
        blocked = self.write_file(self.gcqn, "blocked.bin", b"blocked")
        self.write_file(self.gcac, "placeholder.txt", b"placeholder")
        real_hash = inventory_handover.hash_regular_file

        def fail_selected(path: Path) -> str:
            if path == blocked:
                raise PermissionError(13, "Permission denied", str(path))
            return real_hash(path)

        with mock.patch.object(
            inventory_handover, "hash_regular_file", side_effect=fail_selected
        ):
            manifest = inventory_handover.build_archive_manifest(self.gcqn, "GCQN")

        self.assertEqual(manifest["summary"]["unreadable_entries"], 1)
        self.assertEqual(manifest["errors"][0]["relative_path"], "blocked.bin")
        self.assertNotIn(str(self.base), manifest["errors"][0]["error"])
        self.assertEqual(manifest["errors"][0]["error"], "PermissionError: Permission denied")


if __name__ == "__main__":
    unittest.main()
