#!/usr/bin/env python3
"""Create deterministic, read-only inventories of two code handovers.

The source trees are never modified and directory symlinks are never followed.
Detailed manifests are written only to the caller-provided output directory.
Standard output contains aggregate counts and no source paths or file hashes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import stat
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple


SCHEMA_VERSION = 1
HASH_CHUNK_SIZE = 1024 * 1024
MANIFEST_FIELDS = (
    "relative_path",
    "entry_type",
    "category",
    "size_bytes",
    "modified_utc",
    "sha256",
    "error",
)
COMPARISON_FIELDS = (
    "relative_path",
    "relation",
    "gcqn_entry_type",
    "gcqn_size_bytes",
    "gcqn_sha256",
    "gcac_entry_type",
    "gcac_size_bytes",
    "gcac_sha256",
)


class InventoryConfigurationError(ValueError):
    """Raised when roots or the output directory are unsafe or ambiguous."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory GCQN and GCAC handover trees without modifying them."
    )
    parser.add_argument("gcqn_root", type=Path, help="root of the GCQN handover")
    parser.add_argument("gcac_root", type=Path, help="root of the GCAC handover")
    parser.add_argument("output_dir", type=Path, help="external private output directory")
    return parser.parse_args(argv)


def is_relative_to(path: Path, possible_parent: Path) -> bool:
    try:
        path.relative_to(possible_parent)
    except ValueError:
        return False
    return True


def validate_roots(
    gcqn_root: Path, gcac_root: Path, output_dir: Path
) -> Tuple[Path, Path, Path]:
    source_roots: List[Path] = []
    for label, supplied in (("GCQN", gcqn_root), ("GCAC", gcac_root)):
        expanded = supplied.expanduser()
        if expanded.is_symlink():
            raise InventoryConfigurationError(f"{label} root must not be a symlink")
        if not expanded.exists():
            raise InventoryConfigurationError(f"{label} root does not exist")
        if not expanded.is_dir():
            raise InventoryConfigurationError(f"{label} root is not a directory")
        source_roots.append(expanded.resolve(strict=True))

    resolved_gcqn, resolved_gcac = source_roots
    if os.path.samefile(resolved_gcqn, resolved_gcac):
        raise InventoryConfigurationError("GCQN and GCAC roots resolve to the same directory")
    if is_relative_to(resolved_gcqn, resolved_gcac) or is_relative_to(
        resolved_gcac, resolved_gcqn
    ):
        raise InventoryConfigurationError("GCQN and GCAC roots must not overlap")

    resolved_output = output_dir.expanduser().resolve(strict=False)
    for label, root in (("GCQN", resolved_gcqn), ("GCAC", resolved_gcac)):
        if is_relative_to(resolved_output, root) or is_relative_to(root, resolved_output):
            raise InventoryConfigurationError(
                f"output directory must not overlap the {label} archive"
            )

    return resolved_gcqn, resolved_gcac, resolved_output


def utc_timestamp_from_ns(timestamp_ns: int) -> str:
    seconds, nanoseconds = divmod(timestamp_ns, 1_000_000_000)
    prefix = datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{prefix}.{nanoseconds:09d}Z"


def safe_error(exc: OSError) -> str:
    detail = exc.strerror or "operating-system error"
    return f"{type(exc).__name__}: {detail}"


def entry_type(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "character_device"
    if stat.S_ISBLK(mode):
        return "block_device"
    return "other"


def classify(relative_path: str, kind: str) -> str:
    if kind == "directory":
        return "directory"
    if kind == "symlink":
        return "symlink"

    path = PurePosixPath(relative_path)
    parts = {part.casefold() for part in path.parts}
    suffix = path.suffix.casefold()
    if ".git" in parts:
        return "git_metadata"
    if parts.intersection({"checkpoint", "checkpoints", "model", "models"}) or suffix in {
        ".ckpt",
        ".pt",
        ".pth",
    }:
        return "checkpoint_or_model"
    if parts.intersection({"log", "logs", "logger"}) or suffix == ".log":
        return "log"
    if parts.intersection({"data", "dataset", "datasets", "raw_data", "output_data"}):
        return "data"
    if suffix in {".py", ".pyi", ".ipynb", ".c", ".cc", ".cpp", ".h", ".hpp"}:
        return "source"
    if suffix in {".cfg", ".conf", ".ini", ".json", ".toml", ".xml", ".yaml", ".yml"}:
        return "configuration"
    if suffix in {".md", ".pdf", ".rst", ".tex", ".txt"}:
        return "documentation"
    return "other"


def hash_regular_file(path: Path) -> str:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    digest = hashlib.sha256()
    with os.fdopen(descriptor, "rb", closefd=True) as stream:
        while True:
            chunk = stream.read(HASH_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def hash_symlink(path: Path) -> str:
    target = os.readlink(path)
    return hashlib.sha256(os.fsencode(target)).hexdigest()


def _record_error(
    errors: List[Dict[str, str]], relative_path: str, operation: str, exc: OSError
) -> str:
    message = safe_error(exc)
    errors.append(
        {
            "relative_path": relative_path,
            "operation": operation,
            "error": message,
        }
    )
    return message


def scan_archive(root: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    records: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    def visit(directory: Path, relative_directory: PurePosixPath) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            relative = relative_directory.as_posix() if relative_directory.parts else "."
            _record_error(errors, relative, "scandir", exc)
            return

        for child in children:
            relative_path = relative_directory / child.name
            relative_text = relative_path.as_posix()
            child_path = directory / child.name
            try:
                metadata = child.stat(follow_symlinks=False)
            except OSError as exc:
                error = _record_error(errors, relative_text, "lstat", exc)
                records.append(
                    {
                        "relative_path": relative_text,
                        "entry_type": "unreadable",
                        "category": "other",
                        "size_bytes": None,
                        "modified_utc": "",
                        "sha256": "",
                        "error": error,
                    }
                )
                continue

            kind = entry_type(metadata.st_mode)
            record: Dict[str, Any] = {
                "relative_path": relative_text,
                "entry_type": kind,
                "category": classify(relative_text, kind),
                "size_bytes": metadata.st_size,
                "modified_utc": utc_timestamp_from_ns(metadata.st_mtime_ns),
                "sha256": "",
                "error": "",
            }

            if kind == "file":
                try:
                    record["sha256"] = hash_regular_file(child_path)
                except OSError as exc:
                    record["error"] = _record_error(errors, relative_text, "sha256", exc)
            elif kind == "symlink":
                try:
                    record["sha256"] = hash_symlink(child_path)
                except OSError as exc:
                    record["error"] = _record_error(errors, relative_text, "readlink", exc)

            records.append(record)
            if kind == "directory":
                visit(child_path, relative_path)

    visit(root, PurePosixPath())
    records.sort(key=lambda item: item["relative_path"])
    errors.sort(key=lambda item: (item["relative_path"], item["operation"], item["error"]))
    return records, errors


def duplicate_groups(records: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: MutableMapping[str, List[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        if record["entry_type"] == "file" and record["sha256"]:
            grouped[str(record["sha256"])].append(record)

    duplicates: List[Dict[str, Any]] = []
    for digest in sorted(grouped):
        members = grouped[digest]
        if len(members) < 2:
            continue
        duplicates.append(
            {
                "sha256": digest,
                "size_bytes": sorted({int(member["size_bytes"]) for member in members}),
                "relative_paths": sorted(str(member["relative_path"]) for member in members),
            }
        )
    return duplicates


def embedded_git_summary(records: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    materialized = list(records)
    indexed = {str(record["relative_path"]): record for record in materialized}
    directory_markers = sorted(
        str(record["relative_path"])
        for record in materialized
        if record["entry_type"] == "directory"
        and PurePosixPath(str(record["relative_path"])).name == ".git"
    )
    file_markers = sorted(
        str(record["relative_path"])
        for record in materialized
        if record["entry_type"] == "file"
        and PurePosixPath(str(record["relative_path"])).name == ".git"
    )

    def has_child(marker: str, child: str, kind: str) -> bool:
        record = indexed.get((PurePosixPath(marker) / child).as_posix())
        return bool(record and record["entry_type"] == kind)

    structurally_complete_directories = sum(
        has_child(marker, "HEAD", "file")
        and has_child(marker, "config", "file")
        and has_child(marker, "refs", "directory")
        and has_child(marker, "objects", "directory")
        for marker in directory_markers
    )
    root_marker = indexed.get(".git")
    root_is_directory = bool(
        root_marker and root_marker["entry_type"] == "directory"
    )
    return {
        "root_marker_present": root_marker is not None,
        "root_marker_type": str(root_marker["entry_type"]) if root_marker else "",
        "root_head_present": has_child(".git", "HEAD", "file")
        if root_is_directory
        else False,
        "root_config_present": has_child(".git", "config", "file")
        if root_is_directory
        else False,
        "root_refs_present": has_child(".git", "refs", "directory")
        if root_is_directory
        else False,
        "root_objects_present": has_child(".git", "objects", "directory")
        if root_is_directory
        else False,
        "git_directory_markers": len(directory_markers),
        "structurally_complete_git_directories": structurally_complete_directories,
        "git_file_markers": len(file_markers),
        "metadata_entries": sum(
            1
            for record in materialized
            if ".git" in PurePosixPath(str(record["relative_path"])).parts
        ),
    }


def archive_summary(
    records: Sequence[Mapping[str, Any]],
    errors: Sequence[Mapping[str, str]],
    duplicates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    entry_counts: MutableMapping[str, int] = defaultdict(int)
    category_counts: MutableMapping[str, int] = defaultdict(int)
    total_file_bytes = 0
    readable_files = 0
    for record in records:
        entry_counts[str(record["entry_type"])] += 1
        category_counts[str(record["category"])] += 1
        if record["entry_type"] == "file":
            total_file_bytes += int(record["size_bytes"])
            if record["sha256"]:
                readable_files += 1
    return {
        "entries": len(records),
        "files": entry_counts.get("file", 0),
        "directories": entry_counts.get("directory", 0),
        "symlinks": entry_counts.get("symlink", 0),
        "other_entries": len(records)
        - entry_counts.get("file", 0)
        - entry_counts.get("directory", 0)
        - entry_counts.get("symlink", 0),
        "readable_files": readable_files,
        "total_file_bytes": total_file_bytes,
        "entry_type_counts": dict(sorted(entry_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "duplicate_hash_groups": len(duplicates),
        "duplicate_file_members": sum(len(group["relative_paths"]) for group in duplicates),
        "unreadable_entries": len(errors),
        "embedded_git": embedded_git_summary(records),
    }


def build_archive_manifest(root: Path, label: str) -> Dict[str, Any]:
    records, errors = scan_archive(root)
    duplicates = duplicate_groups(records)
    return {
        "schema_version": SCHEMA_VERSION,
        "archive_label": label,
        "summary": archive_summary(records, errors, duplicates),
        "entries": records,
        "duplicate_hash_groups": duplicates,
        "errors": errors,
    }


def compare_manifests(
    gcqn_manifest: Mapping[str, Any], gcac_manifest: Mapping[str, Any]
) -> Dict[str, Any]:
    gcqn = {entry["relative_path"]: entry for entry in gcqn_manifest["entries"]}
    gcac = {entry["relative_path"]: entry for entry in gcac_manifest["entries"]}
    rows: List[Dict[str, Any]] = []
    counts: MutableMapping[str, int] = defaultdict(int)

    for relative_path in sorted(set(gcqn) | set(gcac)):
        left = gcqn.get(relative_path)
        right = gcac.get(relative_path)
        if left is None:
            relation = "only_gcac"
        elif right is None:
            relation = "only_gcqn"
        elif left["entry_type"] != right["entry_type"]:
            relation = "same_path_type_different"
        elif left["entry_type"] in {"file", "symlink"}:
            if not left["sha256"] or not right["sha256"]:
                relation = "same_path_unreadable"
            elif left["sha256"] == right["sha256"]:
                relation = "same_path_equal_content"
            else:
                relation = "same_path_different_content"
        else:
            relation = "same_path_equal_type"

        counts[relation] += 1
        rows.append(
            {
                "relative_path": relative_path,
                "relation": relation,
                "gcqn_entry_type": left["entry_type"] if left else "",
                "gcqn_size_bytes": left["size_bytes"] if left else "",
                "gcqn_sha256": left["sha256"] if left else "",
                "gcac_entry_type": right["entry_type"] if right else "",
                "gcac_size_bytes": right["size_bytes"] if right else "",
                "gcac_sha256": right["sha256"] if right else "",
            }
        )

    gcqn_hashes: MutableMapping[str, List[str]] = defaultdict(list)
    gcac_hashes: MutableMapping[str, List[str]] = defaultdict(list)
    for record in gcqn_manifest["entries"]:
        if record["entry_type"] == "file" and record["sha256"]:
            gcqn_hashes[record["sha256"]].append(record["relative_path"])
    for record in gcac_manifest["entries"]:
        if record["entry_type"] == "file" and record["sha256"]:
            gcac_hashes[record["sha256"]].append(record["relative_path"])

    cross_duplicates = [
        {
            "sha256": digest,
            "gcqn_relative_paths": sorted(gcqn_hashes[digest]),
            "gcac_relative_paths": sorted(gcac_hashes[digest]),
        }
        for digest in sorted(set(gcqn_hashes) & set(gcac_hashes))
    ]

    summary = dict(sorted(counts.items()))
    summary.update(
        {
            "union_paths": len(rows),
            "common_paths": len(set(gcqn) & set(gcac)),
            "cross_archive_duplicate_hash_groups": len(cross_duplicates),
            "cross_archive_gcqn_file_members": sum(
                len(group["gcqn_relative_paths"]) for group in cross_duplicates
            ),
            "cross_archive_gcac_file_members": sum(
                len(group["gcac_relative_paths"]) for group in cross_duplicates
            ),
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "path_comparisons": rows,
        "cross_archive_duplicate_hash_groups": cross_duplicates,
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")
    os.replace(temporary, path)


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    os.replace(temporary, path)


def public_summary(
    gcqn_manifest: Mapping[str, Any],
    gcac_manifest: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "gcqn": gcqn_manifest["summary"],
        "gcac": gcac_manifest["summary"],
        "comparison": comparison["summary"],
    }


def run_inventory(gcqn_root: Path, gcac_root: Path, output_dir: Path) -> Dict[str, Any]:
    resolved_gcqn, resolved_gcac, resolved_output = validate_roots(
        gcqn_root, gcac_root, output_dir
    )
    resolved_output.mkdir(parents=True, exist_ok=True)

    gcqn_manifest = build_archive_manifest(resolved_gcqn, "GCQN")
    gcac_manifest = build_archive_manifest(resolved_gcac, "GCAC")
    comparison = compare_manifests(gcqn_manifest, gcac_manifest)
    summary = public_summary(gcqn_manifest, gcac_manifest, comparison)

    write_json(resolved_output / "gcqn-manifest.json", gcqn_manifest)
    write_csv(
        resolved_output / "gcqn-manifest.csv", gcqn_manifest["entries"], MANIFEST_FIELDS
    )
    write_json(resolved_output / "gcac-manifest.json", gcac_manifest)
    write_csv(
        resolved_output / "gcac-manifest.csv", gcac_manifest["entries"], MANIFEST_FIELDS
    )
    write_json(resolved_output / "comparison.json", comparison)
    write_csv(
        resolved_output / "comparison.csv", comparison["path_comparisons"], COMPARISON_FIELDS
    )
    write_json(resolved_output / "summary.json", summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = run_inventory(args.gcqn_root, args.gcac_root, args.output_dir)
    except InventoryConfigurationError as exc:
        print(f"inventory configuration error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"inventory output error: {safe_error(exc)}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2, sort_keys=True))
    unreadable = summary["gcqn"]["unreadable_entries"] + summary["gcac"][
        "unreadable_entries"
    ]
    return 2 if unreadable else 0


if __name__ == "__main__":
    raise SystemExit(main())
