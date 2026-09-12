"""Small origin-bound write-once evidence and independent readback.

Completion requires data plus its verified marker and absence of the pending
latch. The latch is removed only after every write, readback and close passes.
Direct descriptor writes are fsynced; this is not a power-loss durability or
concurrent-adversarial-mutation guarantee. No simulator or launcher is imported.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid


IDENTITY = "B0_OD_INTEGRATION_LAYER_V1"
WORKSPACE = Path(__file__).absolute().parents[3] / ".local-evidence" / "b0-od-integration-public-v1"
# Operational byte bound: the measured full 26-run synthetic fixture is about
# 57 MB. This permits that bounded payload, not arbitrary evidence growth.
MAX_BYTES = 64 * 1024 * 1024
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\Z")
CODE = re.compile(r"[A-Z][A-Z0-9_]{0,79}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
EVIDENCE_KINDS = ("SYNTHETIC", "LIVE")
BASE = {"schema_version": 1, "integration_identity": IDENTITY,
        "evidence_kind": "SYNTHETIC", "ready_to_run": False}
PAYLOAD_BASE = {**BASE, "schema_version": 2}


class EvidenceError(RuntimeError):
    def __init__(self, code, failure_receipt_name=None, experiment_status="FAIL"):
        super().__init__(code)
        self.code = code
        self.failure_receipt_name = failure_receipt_name
        self.experiment_status = experiment_status


def _require(condition, code="EVIDENCE_SCHEMA"):
    if not condition:
        raise EvidenceError(code)


def _keys(value, keys):
    _require(type(value) is dict and set(value) == set(keys))


def _origin(value):
    _require(type(value) is str and value in EVIDENCE_KINDS, "EVIDENCE_ORIGIN")
    return value


def _origin_base(evidence_kind):
    return {**BASE, "evidence_kind": _origin(evidence_kind)}


def _json_types(value, depth=0):
    _require(depth <= 64, "JSON_DEPTH_LIMIT")
    if value is None or type(value) in (str, int, float, bool):
        return
    if type(value) is list:
        for item in value:
            _json_types(item, depth + 1)
        return
    _require(type(value) is dict and all(type(key) is str for key in value))
    for item in value.values():
        _json_types(item, depth + 1)


def _encode(value):
    _json_types(value)
    try:
        raw = (json.dumps(value, allow_nan=False, ensure_ascii=False,
                          sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    except (ValueError, OverflowError, UnicodeError, TypeError) as error:
        raise EvidenceError("SERIALIZATION_FAILURE") from error
    _require(len(raw) <= MAX_BYTES, "PAYLOAD_SIZE_LIMIT")
    return raw


def _no_constant(value):
    raise EvidenceError("NONSTANDARD_JSON")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _decode(raw):
    try:
        value = json.loads(raw.decode("utf-8"), parse_constant=_no_constant,
                           object_pairs_hook=_unique)
    except (ValueError, UnicodeError, TypeError) as error:
        raise EvidenceError("READBACK_JSON") from error
    _require(_encode(value) == raw, "NONCANONICAL_JSON")
    return value


def _base(value, version=1):
    _require(type(value.get("schema_version")) is int and value["schema_version"] == version)
    _require(value.get("integration_identity") == IDENTITY)
    _origin(value.get("evidence_kind"))
    _require(value.get("ready_to_run") is False)


def _validate_payload(payload, *, references=None):
    _keys(payload, (*BASE, "record_kind", "record"))
    _base(payload, version=2)
    kind, record = payload["record_kind"], payload["record"]
    _require(type(record) is dict)
    if kind == "SELECTION":
        from .qualification import validate_selection_record
        _require(record.get("evidence_kind") == payload["evidence_kind"], "EVIDENCE_ORIGIN_MISMATCH")
        _require(type(record.get("schema_version")) is int and record["schema_version"] == payload["schema_version"])
        decision = validate_selection_record(record, references=references)
        _require(record.get("decision") == decision, "DECISION_REVALIDATION")
    elif kind == "RUN":
        from .integration import validate_run
        from .finalization import require_supported_assertions
        _require(record.get("evidence_kind") == payload["evidence_kind"], "EVIDENCE_ORIGIN_MISMATCH")
        _require(type(record.get("schema_version")) is int and record["schema_version"] == payload["schema_version"])
        measurement = validate_run(record, references=references)
        require_supported_assertions(record, references=references)
        _require(record.get("measurement") == measurement, "MEASUREMENT_REVALIDATION")
        _require(measurement.get("measurement_status") == "VALID", "INVALID_RUN_REQUIRES_FAILURE_RECORD")
    elif kind == "FAILURE":
        status_keys = ("experiment_status",) if "experiment_status" in record else ()
        _keys(record, ("failure_code", "measurement_status", "run", "raw_evidence", *status_keys))
        _require(type(record["failure_code"]) is str and CODE.fullmatch(record["failure_code"]))
        if record["run"] is None:
            _require(record["measurement_status"] is None and not status_keys)
        else:
            from .integration import assess_run
            from .finalization import require_supported_assertions
            _require(type(record["run"]) is dict)
            _require(record["run"].get("evidence_kind") == payload["evidence_kind"], "EVIDENCE_ORIGIN_MISMATCH")
            _require(type(record["run"].get("schema_version")) is int
                     and record["run"]["schema_version"] == payload["schema_version"])
            assessment = assess_run(record["run"], references=references)
            require_supported_assertions(record["run"], references=references)
            measurement = assessment["measurement"]
            # Aborted-run failure envelopes must carry the independently
            # revalidated stop. A verified persistence receipt is not PASS.
            # Keep the original Adapter result verbatim. Integration may add
            # failure diagnostics; only its freshly revalidated status governs.
            _require(measurement.get("measurement_status") in
                     ("INTEGRITY_FAILURE", "EVIDENCE_DEFICIENCY"), "FAILURE_STATUS_CONTRADICTION")
            _require(record["measurement_status"] == measurement["measurement_status"],
                     "FAILURE_STATUS_CONTRADICTION")
            _require(record.get("experiment_status") == assessment["stop_status"],
                     "FAILURE_EXPERIMENT_STATUS_CONTRADICTION")
    else:
        raise EvidenceError("RECORD_KIND")


def _name(name, format):
    _require(type(name) is str and NAME.fullmatch(name) and ".." not in name, "UNSAFE_NAME")
    _require(name.endswith(".json" if format == "JSON" else ".xml"), "UNSAFE_NAME")


@contextmanager
def _directory(output_dir):
    raw = os.fspath(output_dir)
    _require(type(raw) is str and raw.startswith("/") and ".." not in raw.split("/"), "UNSAFE_DIRECTORY")
    path = Path(raw)
    try:
        path.relative_to(WORKSPACE)
    except ValueError as error:
        raise EvidenceError("OUTPUT_OUTSIDE_WORKSPACE") from error
    _require(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"), "UNSUPPORTED_FILESYSTEM_API")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    try:
        for component in path.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor, path
    finally:
        os.close(descriptor)


def _exists(directory, name):
    try:
        os.stat(name, dir_fd=directory, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def _create(directory, name, raw):
    descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
    first = None
    try:
        if os.write(descriptor, raw) != len(raw):
            raise EvidenceError("SHORT_WRITE", experiment_status="BLOCKED")
        os.fsync(descriptor)
    except BaseException as error:
        first = error
    try:
        os.close(descriptor)
    except OSError as error:
        if first is None:
            first = error
    if first is not None:
        raise first


def _read(directory, name):
    # A substituted FIFO must not block before the regular-file check.
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        metadata = os.fstat(descriptor)
        _require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1, "UNSAFE_READBACK_OBJECT")
        _require(metadata.st_size <= MAX_BYTES, "READBACK_SIZE_LIMIT")
        chunks, size = [], 0
        while True:
            chunk = os.read(descriptor, min(65536, MAX_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            _require(size <= MAX_BYTES, "READBACK_SIZE_LIMIT")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _checked_data(raw, format, validator=None, *, references=None):
    if format == "JSON":
        value = _decode(raw)
        _validate_payload(value, references=references)
        return value
    _require(format == "XML" and callable(validator), "INPUT_VALIDATOR_REQUIRED")
    _require(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), "INPUT_NEWLINE")
    raw.decode("utf-8", errors="strict")
    _require(validator(raw) is not False, "INPUT_VALIDATION")
    return raw


def _verify(directory, name, *, allow_pending=False, validator=None, references=None):
    _require(allow_pending or not _exists(directory, name + ".pending"), "INCOMPLETE_WRITE")
    marker = _decode(_read(directory, name + ".complete.json"))
    _keys(marker, (*BASE, "name", "format", "byte_count", "sha256", "state"))
    _base(marker)
    _require(marker["name"] == name and marker["format"] in ("JSON", "XML")
             and marker["state"] == "VERIFIED", "COMPLETION_MARKER")
    _require(type(marker["byte_count"]) is int and 0 < marker["byte_count"] <= MAX_BYTES
             and type(marker["sha256"]) is str and SHA256.fullmatch(marker["sha256"]), "COMPLETION_MARKER")
    _name(name, marker["format"])
    if allow_pending:
        pending = _decode(_read(directory, name + ".pending"))
        _keys(pending, (*BASE, "state"))
        _base(pending)
        _require(pending["state"] == "INCOMPLETE"
                 and pending["evidence_kind"] == marker["evidence_kind"], "PENDING_ORIGIN_MISMATCH")
    raw = _read(directory, name)
    _require(len(raw) == marker["byte_count"] and hashlib.sha256(raw).hexdigest() == marker["sha256"],
             "READBACK_MISMATCH")
    checked = _checked_data(raw, marker["format"], validator, references=references)
    if marker["format"] == "JSON":
        _require(checked["evidence_kind"] == marker["evidence_kind"], "EVIDENCE_ORIGIN_MISMATCH")
    return checked, marker


def _failure_receipt(directory, name, code, experiment_status, evidence_kind):
    # This distinct attempt receipt cannot complete or replace the failed data.
    receipt_name = name + ".failure-" + uuid.uuid4().hex + ".json"
    raw = _encode({**_origin_base(evidence_kind), "record_kind": "WRITE_FAILURE", "failure_code": code,
                   "experiment_status": experiment_status, "completed": False,
                   "payload_preserved": False})
    try:
        _create(directory, receipt_name, raw)
        if _read(directory, receipt_name) == raw:
            return receipt_name
    except (Exception, KeyboardInterrupt):
        pass
    return None


def _validated_experiment_failed(payload):
    """Use only AFTER actual payload revalidation; no independent assessment."""
    return ((payload["record_kind"] == "FAILURE" and payload["record"].get("experiment_status") == "FAIL")
            or (payload["record_kind"] == "SELECTION" and payload["record"]["decision"]["status"] == "FAIL"))


def _write(output_dir, name, payload, format, validator=None, *, references=None,
           evidence_kind="SYNTHETIC"):
    directory = None
    experiment_failed = False
    try:
        if format == "JSON":
            _require(type(payload) is dict)
            evidence_kind = _origin(payload.get("evidence_kind"))
        base = _origin_base(evidence_kind)
        _name(name, format)
        with _directory(output_dir) as (directory, path):
            for suffix in ("", ".pending", ".complete.json"):
                _require(not _exists(directory, name + suffix), "DESTINATION_CONFLICT")
            try:
                raw = _encode(payload) if format == "JSON" else payload
                _require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "PAYLOAD_SIZE_LIMIT")
                checked = _checked_data(raw, format, validator, references=references)
                experiment_failed = format == "JSON" and _validated_experiment_failed(checked)
                _create(directory, name + ".pending", _encode({**base, "state": "INCOMPLETE"}))
                _create(directory, name, raw)
                _require(_read(directory, name) == raw, "READBACK_MISMATCH")
                marker = {**base, "name": name, "format": format, "byte_count": len(raw),
                          "sha256": hashlib.sha256(raw).hexdigest(), "state": "VERIFIED"}
                marker_raw = _encode(marker)
                _create(directory, name + ".complete.json", marker_raw)
                _require(_read(directory, name + ".complete.json") == marker_raw, "MARKER_READBACK_MISMATCH")
                _verify(directory, name, allow_pending=True, validator=validator, references=references)
                receipt = {"schema_version": 1, "evidence_kind": evidence_kind, "ready_to_run": False,
                           "persistence_status": "VERIFIED", "output_directory": str(path.relative_to(WORKSPACE)),
                           "name": name, "format": format, "sha256": marker["sha256"], "byte_count": len(raw)}
                pending_path = path / (name + ".pending")
                # Rewalk without following symlinks and compare directory identity
                # before releasing the anchored descriptor. Concurrent adversarial
                # directory replacement after this check is not a claimed guarantee.
                with _directory(path) as (current, _):
                    original, checked = os.fstat(directory), os.fstat(current)
                    _require((original.st_dev, original.st_ino) == (checked.st_dev, checked.st_ino),
                             "OUTPUT_DIRECTORY_CHANGED")
            except (Exception, KeyboardInterrupt) as error:
                code = error.code if isinstance(error, EvidenceError) else (
                    "IO_FAILURE" if isinstance(error, OSError) else "VALIDATION_FAILURE")
                status = error.experiment_status if isinstance(error, EvidenceError) else (
                    "BLOCKED" if isinstance(error, OSError) else "FAIL")
                if experiment_failed:
                    status = "FAIL"
                failure_name = _failure_receipt(directory, name, code, status, evidence_kind)
                raise EvidenceError(code, failure_name, status) from error
        # The directory descriptor has now closed successfully. This exact-path
        # unlink is the final filesystem action; its failure retains the latch.
        os.unlink(pending_path)
        return receipt
    except EvidenceError:
        raise
    except (Exception, KeyboardInterrupt) as error:
        if isinstance(error, OSError):
            raise EvidenceError("IO_FAILURE", experiment_status="FAIL" if experiment_failed else "BLOCKED") from error
        raise EvidenceError("UNSAFE_PATH_OR_VALIDATION_FAILURE") from error


def write_once(output_dir, name, payload, *, references=None):
    """Write one explicit-origin JSON envelope; origin is not authorization."""
    return _write(output_dir, name, payload, "JSON", references=references)


def write_input_once(output_dir, name, raw, validator, *, evidence_kind="SYNTHETIC"):
    """Materialize the generated XML with the same write-once/readback rule."""
    return _write(output_dir, name, raw, "XML", validator, evidence_kind=evidence_kind)


def readback(receipt, *, validator=None, references=None):
    """Independently verify completion, bytes/hash, schema and scientific status."""
    experiment_failed = False
    try:
        _keys(receipt, ("schema_version", "evidence_kind", "ready_to_run", "persistence_status",
                        "output_directory", "name", "format", "sha256", "byte_count"))
        _require(type(receipt["schema_version"]) is int and receipt["schema_version"] == 1
                 and type(receipt["evidence_kind"]) is str and receipt["evidence_kind"] in EVIDENCE_KINDS
                 and receipt["ready_to_run"] is False
                 and receipt["persistence_status"] == "VERIFIED", "RECEIPT_SCHEMA")
        relative = receipt["output_directory"]
        _require(type(relative) is str and not relative.startswith("/") and ".." not in relative.split("/"),
                 "RECEIPT_DIRECTORY")
        _require(receipt["format"] in ("JSON", "XML"), "RECEIPT_SCHEMA")
        _name(receipt["name"], receipt["format"])
        with _directory(WORKSPACE / relative) as (directory, _):
            value, marker = _verify(directory, receipt["name"], validator=validator, references=references)
            _require(all(receipt[key] == marker[key] for key in
                         ("name", "format", "sha256", "byte_count", "evidence_kind")),
                     "RECEIPT_MISMATCH")
            experiment_failed = marker["format"] == "JSON" and _validated_experiment_failed(value)
            return value
    except EvidenceError:
        raise
    except FileNotFoundError as error:
        raise EvidenceError("READBACK_MISSING") from error
    except OSError as error:
        raise EvidenceError("IO_FAILURE", experiment_status="FAIL" if experiment_failed else "BLOCKED") from error
    except (Exception, KeyboardInterrupt) as error:
        raise EvidenceError("READBACK_FAILURE") from error
