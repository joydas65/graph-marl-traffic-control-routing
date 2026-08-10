#!/usr/bin/env python3
"""Command-line entry point for the generic runtime-probe harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

try:
    from .harness import ProbeConfigurationError, result_json, run_isolated_probe
except ImportError:  # direct execution from the repository checkout
    from harness import ProbeConfigurationError, result_json, run_isolated_probe


def parse_parameter(value: str) -> tuple[str, object]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("parameter must use KEY=JSON_VALUE")
    key, raw_value = value.split("=", 1)
    if not key:
        raise argparse.ArgumentTypeError("parameter key must not be empty")
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed = raw_value
    return key, parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one synthetic or approved future probe in isolation."
    )
    parser.add_argument("probe", type=Path, help="Python file defining probe(context)")
    parser.add_argument("--id", required=True, dest="probe_id", help="public-safe probe ID")
    parser.add_argument("--timeout", type=float, default=30.0, help="timeout in seconds")
    parser.add_argument(
        "--cpu-time-limit",
        type=int,
        help="optional POSIX CPU-time limit in seconds",
    )
    parser.add_argument(
        "--memory-limit-bytes",
        type=int,
        help="optional POSIX address-space limit in bytes",
    )
    parser.add_argument(
        "--allow-write-root",
        action="append",
        default=[],
        type=Path,
        help="additional existing directory in which Python writes are allowed",
    )
    parser.add_argument(
        "--parameter",
        action="append",
        default=[],
        type=parse_parameter,
        help="probe parameter in KEY=JSON_VALUE form",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional parent-written JSON result; omitted results go to stdout",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    parameters = dict(args.parameter)
    try:
        result = run_isolated_probe(
            args.probe,
            args.probe_id,
            timeout_seconds=args.timeout,
            cpu_time_seconds=args.cpu_time_limit,
            memory_limit_bytes=args.memory_limit_bytes,
            allowed_write_roots=args.allow_write_root,
            parameters=parameters,
        )
    except (OSError, ProbeConfigurationError) as exc:
        print(f"probe configuration rejected: {type(exc).__name__}", file=sys.stderr)
        return 2

    serialized = result_json(result)
    if args.output is None:
        sys.stdout.write(serialized)
    else:
        try:
            args.output.write_text(serialized, encoding="utf-8")
        except OSError as exc:
            print(f"result output failed: {type(exc).__name__}", file=sys.stderr)
            return 2
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
