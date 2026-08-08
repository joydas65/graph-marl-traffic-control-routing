#!/usr/bin/env python3
"""Run a Python probe in a constrained, sanitised subprocess.

This module uses only the Python standard library.  A probe is a Python file
that exposes ``probe(context)`` and returns an optional mapping containing a
status, message, and additional evidence.  The child process receives no
project-specific imports or paths through its public result.

The write guard covers Python operations that emit audit events.  Native code
requires an operating-system or container read-only boundary in later stages.
"""

from __future__ import annotations

import json
import math
import os
import re
import runpy
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


RESULT_SCHEMA_VERSION = 1
PROBE_STATUSES = ("pass", "fail", "inconclusive", "blocked")
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_CAPTURE_CHARS = 32_768
PROBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
POSIX_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])/(?:[^\s\x00'\"<>|]+)"
)
WINDOWS_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/](?:[^\s\x00'\"<>|]+)"
)

CHILD_LAUNCHER = (
    "import runpy,sys; "
    "namespace=runpy.run_path(sys.argv[1]); "
    "raise SystemExit(namespace['_child_main'](sys.argv[2],sys.argv[3]))"
)


class ProbeConfigurationError(ValueError):
    """Raised when a requested probe execution is unsafe or ambiguous."""


class IsolationViolation(PermissionError):
    """Raised when a child attempts an operation forbidden by the harness."""


class WriteOutsideAllowedRoot(IsolationViolation):
    """Raised in the child when a Python write escapes approved roots."""


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolved_path(value: str | bytes | os.PathLike[str]) -> Path:
    path = Path(os.fsdecode(value)).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve(strict=False)


def _assert_write_allowed(
    value: object, allowed_roots: tuple[Path, ...]
) -> None:
    if isinstance(value, int):
        return
    if not isinstance(value, (str, bytes, os.PathLike)):
        return
    candidate = _resolved_path(value)
    if any(_is_relative_to(candidate, root) for root in allowed_roots):
        return
    raise WriteOutsideAllowedRoot("write outside allowed roots blocked")


def _open_requests_write(mode: object, flags: object) -> bool:
    if isinstance(mode, str) and any(marker in mode for marker in "wax+"):
        return True
    if not isinstance(flags, int):
        return False
    write_flags = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_EXCL"):
        write_flags |= os.O_EXCL
    return bool(flags & write_flags)


def _install_audit_guard(allowed_roots: Sequence[str]) -> None:
    resolved_roots = tuple(
        sorted(
            {_resolved_path(root) for root in allowed_roots},
            key=lambda item: item.as_posix(),
        )
    )

    single_path_events = {
        "os.chmod",
        "os.chown",
        "os.mkdir",
        "os.remove",
        "os.rmdir",
        "os.truncate",
        "os.unlink",
        "os.utime",
    }
    dual_path_events = {"os.link", "os.rename", "os.replace", "os.symlink"}
    blocked_process_events = {"os.system", "subprocess.Popen"}
    blocked_network_events = {"socket.__new__", "socket.bind", "socket.connect"}

    def audit(event: str, args: tuple[object, ...]) -> None:
        if event == "open" and len(args) >= 3:
            if _open_requests_write(args[1], args[2]):
                _assert_write_allowed(args[0], resolved_roots)
            return
        if event in single_path_events and args:
            _assert_write_allowed(args[0], resolved_roots)
            return
        if event in dual_path_events and len(args) >= 2:
            _assert_write_allowed(args[0], resolved_roots)
            _assert_write_allowed(args[1], resolved_roots)
            return
        if event in blocked_process_events:
            raise IsolationViolation("nested process creation blocked")
        if event in blocked_network_events:
            raise IsolationViolation("network access blocked")

    sys.addaudithook(audit)


class ProbeContext:
    """Mutable evidence collector supplied to a probe in the child process."""

    def __init__(
        self,
        probe_id: str,
        work_dir: Path,
        allowed_write_roots: Sequence[Path],
        parameters: Mapping[str, Any],
    ) -> None:
        self.probe_id = probe_id
        self.work_dir = work_dir
        self.allowed_write_roots = tuple(allowed_write_roots)
        self.parameters = dict(parameters)
        self._shapes: list[dict[str, Any]] = []
        self._calls: Counter[str] = Counter()

    def record_shape(
        self, label: str, dimensions: Sequence[int | str | None]
    ) -> None:
        """Record a future model or framework boundary shape."""
        self._shapes.append(
            {
                "label": str(label),
                "dimensions": [dimension for dimension in dimensions],
            }
        )

    def record_call(self, label: str, count: int = 1) -> None:
        """Record a future dispatch or boundary call count."""
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("call count must be a non-negative integer")
        self._calls[str(label)] += count

    def collected_evidence(self) -> dict[str, Any]:
        shapes = sorted(
            self._shapes,
            key=lambda item: (
                item["label"],
                json.dumps(item["dimensions"], sort_keys=True),
            ),
        )
        calls = [
            {"label": label, "count": self._calls[label]}
            for label in sorted(self._calls)
        ]
        return {"shapes": shapes, "calls": calls}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, os.PathLike):
        return os.fspath(value)
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_json_safe(item) for item in value]
        if isinstance(value, (set, frozenset)):
            items.sort(key=lambda item: json.dumps(item, sort_keys=True))
        return items
    return repr(value)


def _merge_evidence(
    collected: Mapping[str, Any], returned: Mapping[str, Any]
) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "shapes": list(collected.get("shapes", [])),
        "calls": list(collected.get("calls", [])),
        "values": {},
    }
    for key, value in returned.items():
        if key in {"shapes", "calls"}:
            merged[key].extend(value if isinstance(value, list) else [value])
        else:
            merged["values"][str(key)] = value
    merged["shapes"] = sorted(
        merged["shapes"], key=lambda item: json.dumps(_json_safe(item), sort_keys=True)
    )
    merged["calls"] = sorted(
        merged["calls"], key=lambda item: json.dumps(_json_safe(item), sort_keys=True)
    )
    return _json_safe(merged)


def _child_result(
    status: str,
    message: str,
    context: ProbeContext,
    returned_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = _merge_evidence(
        context.collected_evidence(), returned_evidence or {}
    )
    return {
        "status": status,
        "message": message,
        "evidence": evidence,
    }


def _child_main(payload_path: str, result_path: str) -> int:
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    allowed_roots = tuple(Path(path) for path in payload["allowed_write_roots"])
    context = ProbeContext(
        probe_id=payload["probe_id"],
        work_dir=Path(payload["work_dir"]),
        allowed_write_roots=allowed_roots,
        parameters=payload.get("parameters", {}),
    )
    _install_audit_guard(payload["allowed_write_roots"])

    try:
        namespace = runpy.run_path(payload["probe_path"], run_name="__runtime_probe__")
        probe = namespace.get("probe")
        if not callable(probe):
            raise TypeError("probe file must define callable probe(context)")
        returned = probe(context)
        if returned is None:
            returned = {}
        if not isinstance(returned, Mapping):
            raise TypeError("probe(context) must return a mapping or None")
        status = str(returned.get("status", "pass"))
        if status not in PROBE_STATUSES:
            raise ValueError("probe returned an unsupported status")
        message = str(returned.get("message", ""))
        raw_evidence = returned.get("evidence", {})
        if not isinstance(raw_evidence, Mapping):
            raise TypeError("probe evidence must be a mapping")
        result = _child_result(status, message, context, raw_evidence)
    except IsolationViolation as exc:
        result = _child_result("blocked", str(exc), context)
    except BaseException as exc:  # child boundary converts failures to evidence
        result = _child_result(
            "fail", f"{type(exc).__name__}: {exc}", context
        )

    Path(result_path).write_text(
        json.dumps(_json_safe(result), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return {"pass": 0, "fail": 1, "inconclusive": 3, "blocked": 4}[result["status"]]


def _truncate(text: str, limit: int = MAX_CAPTURE_CHARS) -> str:
    if len(text) <= limit:
        return text
    marker = "\n<output-truncated>"
    return text[: max(0, limit - len(marker))] + marker


def _sanitise_text(text: str, redactions: Sequence[str]) -> str:
    sanitised = text
    for sensitive in sorted(
        {item for item in redactions if item}, key=len, reverse=True
    ):
        sanitised = sanitised.replace(sensitive, "<redacted-path>")
    sanitised = WINDOWS_ABSOLUTE_PATH_PATTERN.sub(
        "<redacted-path>", sanitised
    )
    sanitised = POSIX_ABSOLUTE_PATH_PATTERN.sub("<redacted-path>", sanitised)
    return _truncate(sanitised)


def _sanitise_value(value: Any, redactions: Sequence[str]) -> Any:
    safe = _json_safe(value)
    if isinstance(safe, str):
        return _sanitise_text(safe, redactions)
    if isinstance(safe, list):
        return [_sanitise_value(item, redactions) for item in safe]
    if isinstance(safe, dict):
        return {
            _sanitise_text(str(key), redactions): _sanitise_value(item, redactions)
            for key, item in sorted(safe.items(), key=lambda pair: str(pair[0]))
        }
    return safe


def _decode_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _child_environment(work_dir: Path) -> dict[str, str]:
    environment: dict[str, str] = {
        "CUDA_VISIBLE_DEVICES": "-1",
        "HOME": str(work_dir),
        "NVIDIA_VISIBLE_DEVICES": "none",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "TEMP": str(work_dir),
        "TMP": str(work_dir),
        "TMPDIR": str(work_dir),
    }
    for key in ("LANG", "LC_ALL", "PATH", "SYSTEMROOT", "WINDIR"):
        if key in os.environ:
            environment[key] = os.environ[key]
    return environment


def _empty_result(
    probe_id: str,
    status: str,
    message: str,
    elapsed_seconds: float,
    exit_status: int | None,
    timed_out: bool,
    stdout: str,
    stderr: str,
) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "probe_id": probe_id,
        "status": status,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "exit_status": exit_status,
        "timed_out": timed_out,
        "message": message,
        "evidence": {"shapes": [], "calls": [], "values": {}},
        "stdout": stdout,
        "stderr": stderr,
    }


def run_isolated_probe(
    probe_path: Path,
    probe_id: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    allowed_write_roots: Sequence[Path] = (),
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one probe and return a deterministic public-safe schema."""
    if not PROBE_ID_PATTERN.fullmatch(probe_id):
        raise ProbeConfigurationError("probe ID contains unsupported characters")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ProbeConfigurationError("timeout must be a positive finite number")

    probe = probe_path.expanduser().resolve(strict=True)
    if not probe.is_file():
        raise ProbeConfigurationError("probe path must identify a file")

    supplied_roots: list[Path] = []
    for supplied in allowed_write_roots:
        root = supplied.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ProbeConfigurationError("allowed write roots must be directories")
        supplied_roots.append(root)

    with tempfile.TemporaryDirectory(prefix="runtime-probe-") as temporary:
        work_dir = Path(temporary).resolve()
        roots = tuple(
            sorted(
                {work_dir, *supplied_roots}, key=lambda item: item.as_posix()
            )
        )
        payload_path = work_dir / "payload.json"
        result_path = work_dir / "child-result.json"
        payload = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "probe_id": probe_id,
            "probe_path": str(probe),
            "work_dir": str(work_dir),
            "allowed_write_roots": [str(root) for root in roots],
            "parameters": _json_safe(parameters or {}),
        }
        payload_path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

        command = [
            sys.executable,
            "-I",
            "-B",
            "-c",
            CHILD_LAUNCHER,
            str(Path(__file__).resolve()),
            str(payload_path),
            str(result_path),
        ]
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=work_dir,
                env=_child_environment(work_dir),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            elapsed = time.monotonic() - started
            stdout = completed.stdout
            stderr = completed.stderr
            exit_status: int | None = completed.returncode
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - started
            stdout = _decode_output(exc.stdout)
            stderr = _decode_output(exc.stderr)
            exit_status = None
            timed_out = True

        redactions = [
            str(work_dir),
            str(probe),
            str(Path(__file__).resolve()),
            str(Path.cwd().resolve()),
            str(Path.home().resolve()),
            *(str(root) for root in roots),
        ]
        safe_stdout = _sanitise_text(stdout, redactions)
        safe_stderr = _sanitise_text(stderr, redactions)

        if timed_out:
            return _empty_result(
                probe_id,
                "blocked",
                "probe exceeded configured timeout",
                elapsed,
                exit_status,
                True,
                safe_stdout,
                safe_stderr,
            )

        if result_path.is_file():
            try:
                child_result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                child_result = None
        else:
            child_result = None

        if not isinstance(child_result, Mapping):
            return _empty_result(
                probe_id,
                "fail",
                "child returned no valid structured result",
                elapsed,
                exit_status,
                False,
                safe_stdout,
                safe_stderr,
            )

        status = str(child_result.get("status", "fail"))
        if status not in PROBE_STATUSES:
            status = "fail"
        result = _empty_result(
            probe_id,
            status,
            str(child_result.get("message", "")),
            elapsed,
            exit_status,
            False,
            safe_stdout,
            safe_stderr,
        )
        evidence = child_result.get("evidence", {})
        result["evidence"] = evidence if isinstance(evidence, Mapping) else {}
        return _sanitise_value(result, redactions)


def result_json(result: Mapping[str, Any]) -> str:
    """Serialize a result deterministically for private evidence storage."""
    return json.dumps(_json_safe(result), indent=2, sort_keys=True) + "\n"
