"""Isolated model-only probe for the Candidate N graph-Q interface.

The source module is supplied through ``SOURCE_MODULE``.  This payload neither
knows nor reports its private location.  Unrelated framework imports are
replaced only at the import boundary; touching any inert symbol during model
construction or forward computation fails the probe.
"""

from __future__ import annotations

import importlib.abc
import importlib.util
import os
import random
import stat
import sys
import types
from pathlib import Path
from typing import Any


SEED = 1729
N, E, F, A = 3, 4, 3, 2
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"cityflow", "libsumo", "pfrl", "sumo", "sumolib", "traci"}
)


class ProbeBoundaryError(RuntimeError):
    """Base class for a deliberate isolation-boundary result."""


class InertBoundaryTouched(ProbeBoundaryError):
    """Raised if model execution reaches an unrelated framework stub."""

    def __init__(self, label: str) -> None:
        super().__init__("inert import boundary touched")
        self.label = label


class ForbiddenDependencyImported(ProbeBoundaryError):
    """Raised if a prohibited dependency is imported by the source module."""

    def __init__(self, root: str) -> None:
        super().__init__("forbidden dependency import blocked")
        self.root = root


class _ForbiddenImportFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: Any = None,
        target: Any = None,
    ) -> None:
        root = fullname.partition(".")[0]
        if root in FORBIDDEN_IMPORT_ROOTS:
            raise ForbiddenDependencyImported(root)
        return None


class _BoundaryMonitor:
    def __init__(self) -> None:
        self.phase = "source_import"
        self.allowed_import_calls: list[str] = []

    def allow_import_call(self, label: str) -> None:
        if self.phase != "source_import":
            raise InertBoundaryTouched(label)
        self.allowed_import_calls.append(label)

    def reject(self, label: str) -> None:
        raise InertBoundaryTouched(label)


def _guarded_class(label: str, monitor: _BoundaryMonitor) -> type:
    class Guarded:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            monitor.reject(label)

    Guarded.__name__ = label.rpartition(".")[2]
    return Guarded


def _module(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__package__ = name.rpartition(".")[0]
    return module


def _install_import_boundaries(
    monitor: _BoundaryMonitor,
) -> tuple[str, tuple[str, ...]]:
    package_name = "_candidate_n_isolated"
    package = _module(package_name)
    package.__path__ = []
    package.RLAgent = _guarded_class("framework.RLAgent", monitor)

    common = _module("common")
    common.__path__ = []
    registry_module = _module("common.registry")

    class GuardedRegistryMeta(type):
        def __getattr__(cls, name: str) -> Any:
            monitor.reject(f"registry.{name}")

    class Registry(metaclass=GuardedRegistryMeta):
        @classmethod
        def register_model(cls, _alias: str):
            monitor.allow_import_call("registry.register_model")

            def decorate(candidate: type) -> type:
                if monitor.phase != "source_import":
                    monitor.reject("registry.register_model")
                return candidate

            return decorate

    registry_module.Registry = Registry
    common.registry = registry_module

    generator = _module("generator")
    generator.__path__ = []
    lane_vehicle = _module("generator.lane_vehicle")
    lane_vehicle.LaneVehicleGenerator = _guarded_class(
        "generator.LaneVehicleGenerator", monitor
    )
    intersection_phase = _module("generator.intersection_phase")
    intersection_phase.IntersectionPhaseGenerator = _guarded_class(
        "generator.IntersectionPhaseGenerator", monitor
    )
    generator.lane_vehicle = lane_vehicle
    generator.intersection_phase = intersection_phase

    gym = _module("gym")

    def missing_gym_attribute(name: str) -> Any:
        monitor.reject(f"gym.{name}")

    gym.__getattr__ = missing_gym_attribute

    stubs = {
        package_name: package,
        "common": common,
        "common.registry": registry_module,
        "generator": generator,
        "generator.lane_vehicle": lane_vehicle,
        "generator.intersection_phase": intersection_phase,
        "gym": gym,
    }
    for name, stub in stubs.items():
        if name in sys.modules:
            raise ProbeBoundaryError("import boundary name already loaded")
        sys.modules[name] = stub
    return package_name, tuple(sorted(stubs))


def _load_source(source: Path, package_name: str) -> types.ModuleType:
    module_name = f"{package_name}.candidate_n_source"
    specification = importlib.util.spec_from_file_location(module_name, source)
    if specification is None or specification.loader is None:
        raise ProbeBoundaryError("source loader unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    return module


def _forbidden_loaded() -> list[str]:
    return sorted(
        root
        for root in FORBIDDEN_IMPORT_ROOTS
        if any(name == root or name.startswith(root + ".") for name in sys.modules)
    )


def _source_signature(path: Path) -> tuple[int, int, int]:
    metadata = path.stat()
    return (
        metadata.st_size,
        metadata.st_mtime_ns,
        stat.S_IMODE(metadata.st_mode),
    )


def _seed_all(np: Any, torch: Any) -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)


def _public_failure(
    status: str,
    message: str,
    phase: str,
    error_type: str | None = None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {"phase": phase}
    if error_type is not None:
        evidence["error_type"] = error_type
    return {"status": status, "message": message, "evidence": evidence}


def probe(context: Any) -> dict[str, Any]:
    source_value = os.environ.get("SOURCE_MODULE")
    if not source_value:
        return _public_failure(
            "blocked", "source module was not supplied", "preflight"
        )

    supplied_source = Path(source_value).expanduser()
    if supplied_source.is_symlink():
        return _public_failure(
            "blocked", "source module is not a regular staged file", "preflight"
        )
    try:
        source = supplied_source.resolve(strict=True)
    except (OSError, RuntimeError):
        return _public_failure(
            "blocked", "source module is unavailable", "preflight"
        )
    if not source.is_file() or source.is_symlink():
        return _public_failure(
            "blocked", "source module is not a regular staged file", "preflight"
        )
    before = _source_signature(source)
    if before[2] & 0o222:
        return _public_failure(
            "blocked", "source module is not read-only", "preflight"
        )
    if _forbidden_loaded():
        return _public_failure(
            "blocked", "forbidden dependency was loaded before probe", "preflight"
        )

    try:
        import numpy as np
        import torch
    except ImportError as exc:
        dependency = getattr(exc, "name", "")
        public_dependency = dependency if dependency in {"numpy", "torch"} else None
        return _public_failure(
            "blocked",
            "required public dependency is unavailable",
            "dependency_import",
            public_dependency,
        )

    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    if torch.cuda.is_available():
        return _public_failure(
            "blocked", "CPU-only boundary was not established", "preflight"
        )

    monitor = _BoundaryMonitor()
    finder = _ForbiddenImportFinder()
    sys.meta_path.insert(0, finder)
    try:
        package_name, stub_names = _install_import_boundaries(monitor)
        module = _load_source(source, package_name)
    except ForbiddenDependencyImported as exc:
        return _public_failure(
            "blocked",
            "forbidden dependency import blocked",
            "source_import",
            exc.root,
        )
    except InertBoundaryTouched as exc:
        return _public_failure(
            "blocked",
            "unexpected framework initialization reached an inert boundary",
            "source_import",
            exc.label,
        )
    except ModuleNotFoundError as exc:
        public_roots = {
            "torch_geometric",
            "torch_scatter",
            "torch_sparse",
        }
        root = (exc.name or "").partition(".")[0]
        return _public_failure(
            "blocked",
            "required public graph dependency is unavailable",
            "source_import",
            root if root in public_roots else None,
        )
    except BaseException as exc:
        return _public_failure(
            "inconclusive",
            "source module could not be isolated",
            "source_import",
            type(exc).__name__,
        )

    model_class = getattr(module, "GCN", None)
    if not isinstance(model_class, type):
        return _public_failure(
            "fail", "expected GCN class was not found", "class_lookup"
        )

    monitor.phase = "model_computation"
    _seed_all(np, torch)
    features = torch.tensor(
        [
            [0.0, 0.5, 1.0],
            [1.5, 2.0, 2.5],
            [3.0, 3.5, 4.0],
        ],
        dtype=torch.float32,
        device="cpu",
    )
    edge_index = torch.tensor(
        [[0, 1, 1, 2], [1, 0, 2, 1]],
        dtype=torch.long,
        device="cpu",
    )

    try:
        model = model_class(F, A, edge_index).to("cpu")
        model.eval()
        with torch.no_grad():
            first = model(features)
            repeated = model(features)
        actions = torch.argmax(first, dim=1)
    except InertBoundaryTouched as exc:
        return _public_failure(
            "fail",
            "model computation touched an inert import boundary",
            "model_computation",
            exc.label,
        )
    except ForbiddenDependencyImported as exc:
        return _public_failure(
            "fail",
            "model computation attempted a forbidden dependency import",
            "model_computation",
            exc.root,
        )
    except BaseException as exc:
        return _public_failure(
            "fail",
            "model construction or forward execution failed",
            "model_computation",
            type(exc).__name__,
        )

    checks = {
        "action_shape": list(actions.shape) == [N],
        "cpu_only": first.device.type == "cpu"
        and all(parameter.device.type == "cpu" for parameter in model.parameters()),
        "finite_output": bool(torch.isfinite(first).all().item()),
        "output_shape": list(first.shape) == [N, A],
        "repeat_equal": bool(torch.equal(first, repeated)),
    }
    if not all(checks.values()):
        return {
            "status": "fail",
            "message": "one or more Candidate N model invariants failed",
            "evidence": {"checks": checks},
        }

    _seed_all(np, torch)
    try:
        reconstructed = model_class(F, A, edge_index).to("cpu")
        reconstructed.eval()
        with torch.no_grad():
            reconstructed_output = reconstructed(features)
    except InertBoundaryTouched as exc:
        return _public_failure(
            "fail",
            "model reconstruction touched an inert import boundary",
            "deterministic_reconstruction",
            exc.label,
        )
    except ForbiddenDependencyImported as exc:
        return _public_failure(
            "fail",
            "model reconstruction attempted a forbidden dependency import",
            "deterministic_reconstruction",
            exc.root,
        )
    except BaseException as exc:
        return _public_failure(
            "fail",
            "deterministic reconstruction failed",
            "deterministic_reconstruction",
            type(exc).__name__,
        )

    deterministic_reconstruction = bool(
        torch.equal(first, reconstructed_output)
    )
    if not deterministic_reconstruction:
        return {
            "status": "fail",
            "message": "fixed-seed model reconstruction was not deterministic",
            "evidence": {"deterministic_reconstruction": False},
        }

    forbidden = _forbidden_loaded()
    if forbidden:
        return {
            "status": "fail",
            "message": "forbidden dependency loaded during model probe",
            "evidence": {"forbidden_dependencies": forbidden},
        }
    after = _source_signature(source)
    if after != before:
        return _public_failure(
            "fail", "source metadata changed during probe", "source_integrity"
        )

    context.record_shape("input", [N, F])
    context.record_shape("edge_index", [2, E])
    context.record_shape("q_output", [N, A])
    context.record_shape("greedy_action", [N])
    context.record_call("forward", 3)

    return {
        "status": "pass",
        "message": "Candidate N model-only invariants passed",
        "evidence": {
            "checks": checks,
            "deterministic_reconstruction": True,
            "forbidden_dependencies_loaded": [],
            "inert_model_boundary_touches": 0,
            "import_boundaries": list(stub_names),
            "permitted_import_boundary_calls": monitor.allowed_import_calls,
            "model_class": "GCN",
            "seed": SEED,
            "source_unchanged": True,
        },
    }
