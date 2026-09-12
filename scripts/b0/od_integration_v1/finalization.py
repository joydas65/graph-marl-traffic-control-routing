"""Bounded schema-2 terminal evidence checks, not a launcher or status engine.

Supports the explicit synthetic diagnostic format and the reviewed native
mapping with origin and evidence checks. Native runtime behavior remains
unvalidated; ownership and coherent fabrication cannot be authenticated here.
"""
import copy
from dataclasses import dataclass
import errno
import hashlib
from pathlib import PurePosixPath
import xml.etree.ElementTree as ET

from . import evidence as io
from scripts.b0.od_concentration_v2 import cutoff_measurement as adapter

COUNTS = ("collisions", "invalid_routes", "simulator_errors")
POSITIVE = dict(zip(COUNTS, ("COLLISION_OBSERVED", "INVALID_ROUTE_OBSERVED",
                           "UNEXPLAINED_SIMULATOR_ERROR")))
CODES = {*POSITIVE.values(), "OUTPUT_OBJECT_MISMATCH", "OUTPUT_BYTES_CHANGED",
         "PROCESS_WAIT_UNAVAILABLE", "PROCESS_NONZERO_EXIT", "DIAGNOSTICS_UNAVAILABLE",
         "TRIPINFO_MISSING", "TRIPINFO_UNREADABLE", "TRIPINFO_UNPARSEABLE",
         "TRIPINFO_ID_CONTRADICTION", "FINALIZER_EXCEPTION"}
ARTIFACTS = {"tripinfo", "diagnostics", "capture"}
SYNTHETIC_MAPPING = "B0_SYNTHETIC_TERMINAL_DIAGNOSTICS_V1"
INTEGRITY_WITNESSES = {*POSITIVE.values(), "OUTPUT_OBJECT_MISMATCH", "OUTPUT_BYTES_CHANGED",
                       "TRIPINFO_ID_CONTRADICTION"}


def new_result(output_directory=None):
    """Integration-owned FinalizationResultV1; collector fills observations only."""
    return dict(version=1, collection_state="NOT_ATTEMPTED",
                process=dict(state="UNOBSERVED", exit_code=None),
                diagnostics=dict(coverage="UNAVAILABLE", counts=dict.fromkeys(COUNTS)),
                tripinfo=dict(availability="UNOBSERVED", parsing="NOT_ATTEMPTED", identity="UNVERIFIED"),
                findings=[], output_identity=dict(output_directory=output_directory,
                    artifacts=dict.fromkeys(sorted(ARTIFACTS)),
                    output_observations=dict(expected=None, observed=None)))


def _require(ok, code="FINALIZATION_SCHEMA"):
    if not ok:
        raise ValueError(code)


def _keys(value, keys):
    _require(type(value) is dict and set(value) == set(keys))


def _integer(value):
    return type(value) is int and value >= 0


def _directory(value):
    _require(type(value) is str and value and not value.startswith("/")
             and all(p not in ("", ".", "..") for p in value.split("/")), "UNSAFE_REFERENCE_DIRECTORY")
    _require(str(PurePosixPath(value)) == value, "UNSAFE_REFERENCE_DIRECTORY")


def _token(value):
    if value is None:
        return
    _keys(value, ("device", "inode", "byte_count", "sha256"))
    _require(_integer(value["device"]) and _integer(value["inode"]))
    _require((value["byte_count"] is None and value["sha256"] is None) or
             (_integer(value["byte_count"]) and value["byte_count"] <= io.MAX_BYTES
              and type(value["sha256"]) is str and io.SHA256.fullmatch(value["sha256"])))


def _process(value):
    _keys(value, ("state", "exit_code"))
    _require(value["state"] in ("UNOBSERVED", "NOT_EXITED", "EXITED"))
    _require(type(value["exit_code"]) is int if value["state"] == "EXITED"
             else value["exit_code"] is None)


def _observations(value):
    _keys(value, ("expected", "observed"))
    for token in value.values():
        _token(token)


@dataclass(frozen=True)
class ReferenceGrant:
    """Exact owner-supplied acquisition context; never inferred from a record.

    expected is the original output anchor, not the retained copy's inode.
    Optional content baseline must be taken after process finalization by the
    future reviewed owner. Synthetic tests supply synthetic anchors explicitly.
    """
    run_id: str
    condition_label: str
    binding_sha256: str
    output_directory: str
    expected: dict | None
    evidence_kind: str = 'SYNTHETIC'


class ReferenceContext:
    def __init__(self, grants):
        self._grants = tuple(copy.deepcopy(tuple(grants)))
        for grant in self._grants:
            _require(type(grant) is ReferenceGrant)
            _require(grant.evidence_kind in ('SYNTHETIC', 'LIVE'), 'REFERENCE_ORIGIN')
            _directory(grant.output_directory)
            _token(grant.expected)
            _require(type(grant.run_id) is str and grant.run_id
                     and grant.condition_label in ("N0", "D0", "N0-CAL-R", "D0-CAL-R")
                     and type(grant.binding_sha256) is str
                     and io.SHA256.fullmatch(grant.binding_sha256))
        keys = [(g.run_id, g.condition_label, g.binding_sha256, g.output_directory, g.evidence_kind) for g in self._grants]
        _require(len(keys) == len(set(keys)), "DUPLICATE_REFERENCE_GRANT")

    def authorize(self, grant):
        """Owner explicitly adds one exact scope before collection; no discovery."""
        checked = ReferenceContext((*self._grants, grant))
        self._grants = checked._grants

    def grant(self, run, directory):
        from .integration import digest
        key = run["run_id"], run["condition_label"], digest(run["binding"]), directory, run['evidence_kind']
        matches = [g for g in self._grants if
                   (g.run_id, g.condition_label, g.binding_sha256, g.output_directory, g.evidence_kind) == key]
        _require(len(matches) == 1, "UNAUTHORIZED_REFERENCE_CONTEXT")
        return copy.deepcopy(matches[0])


def _shape(value):
    _keys(value, new_result())
    _require(type(value["version"]) is int and value["version"] == 1)
    _require(value["collection_state"] in ("NOT_ATTEMPTED", "INTERRUPTED", "COMPLETED"))
    _process(value["process"])
    diagnostic = value["diagnostics"]
    _keys(diagnostic, ("coverage", "counts"))
    _require(diagnostic["coverage"] in ("UNAVAILABLE", "INCOMPLETE", "COMPLETE"))
    _keys(diagnostic["counts"], COUNTS)
    _require(all(v is None or _integer(v) for v in diagnostic["counts"].values()))
    _require(diagnostic["coverage"] != "COMPLETE" or None not in diagnostic["counts"].values())
    trip = value["tripinfo"]
    _keys(trip, ("availability", "parsing", "identity"))
    _require(trip["availability"] in ("UNOBSERVED", "MISSING", "UNREADABLE", "AVAILABLE"))
    _require(trip["parsing"] in ("NOT_ATTEMPTED", "PARSED", "UNPARSEABLE"))
    _require(trip["identity"] in ("UNVERIFIED", "MATCH", "CONTRADICTED"))
    output = value["output_identity"]
    _keys(output, ("output_directory", "artifacts", "output_observations"))
    if output["output_directory"] is not None:
        _directory(output["output_directory"])
    _keys(output["artifacts"], ARTIFACTS)
    _observations(output["output_observations"])
    names = []
    for ref in output["artifacts"].values():
        if ref is None:
            continue
        _keys(ref, ("name", "byte_count", "sha256"))
        _require(type(ref["name"]) is str and io.NAME.fullmatch(ref["name"])
                 and ".." not in ref["name"], "UNSAFE_REFERENCE_NAME")
        _require(_integer(ref["byte_count"]) and ref["byte_count"] <= io.MAX_BYTES
                 and type(ref["sha256"]) is str and io.SHA256.fullmatch(ref["sha256"]), "REFERENCE_BOUND_OR_HASH")
        names.append(ref["name"])
    _require(len(set(names)) == len(names), "ALIASED_REFERENCES")
    _require(type(value["findings"]) is list and len(value["findings"]) <= len(CODES))
    codes = []
    for item in value["findings"]:
        _keys(item, ("code", "evidence_keys"))
        _require(type(item["code"]) is str and item["code"] in CODES)
        keys = item["evidence_keys"]
        _require(type(keys) is list and all(type(k) is str and k in ARTIFACTS | {"output_observations"} for k in keys)
                 and len(keys) == len(set(keys)))
        codes.append(item["code"])
    _require(len(codes) == len(set(codes)), "DUPLICATE_FINDING")


def _synthetic_diagnostics(raw):
    """Closed synthetic event vocabulary; never a native SUMO log mapping."""
    data = io._decode(raw)
    _keys(data, ("mapping", "evidence_kind", "complete", "events"))
    _require(data["mapping"] == SYNTHETIC_MAPPING and data["evidence_kind"] == "SYNTHETIC",
             "UNSUPPORTED_DIAGNOSTIC_MAPPING")
    _require(type(data["complete"]) is bool and type(data["events"]) is list)
    _require(all(type(v) is str for v in data["events"]))
    counts = {k: data["events"].count(k) for k in COUNTS}
    complete = data["complete"] and all(v in (*COUNTS, "warning") for v in data["events"])
    return counts, "COMPLETE" if complete else "INCOMPLETE"


def validate(run, *, references=None, acquiring=False):
    """Return compositional facts; integration alone derives experiment status.

    acquiring derives parsing without trusting collector's parsing field. At
    later readback compare it and the stored rows against retained original bytes.
    Missing authorized files/context are deficiencies. Malformed, unsafe or
    hash-inconsistent accessible evidence is record-integrity failure.
    """
    value = run["finalization"]
    errors, deficient, witnesses = [], [], {}
    result = dict(errors=errors, deficiencies=deficient, witnesses=witnesses,
                  parsing="NOT_ATTEMPTED", rows=None, output_finalized=False)
    try:
        _shape(value)
    except (ValueError, TypeError, KeyError):
        errors.append("FINALIZATION_SCHEMA")
        return result
    def witness(code, keys):
        witnesses[code] = keys
    output = value["output_identity"]; refs = output["artifacts"]
    raw = dict.fromkeys(ARTIFACTS); unavailable = set()
    grant = None
    if references is not None:
        try:
            _require(type(references) is ReferenceContext, "REFERENCE_CONTEXT_TYPE")
            if output["output_directory"] is not None:
                grant = references.grant(run, output["output_directory"])
        except ValueError as error:
            errors.append(str(error))
    for key in sorted(ARTIFACTS):
        ref = refs[key]
        if ref is None:
            continue
        if output["output_directory"] is None:
            errors.append("REFERENCE_WITHOUT_DIRECTORY")
        if grant is None:
            deficient.append("REFERENCE_CONTEXT_UNAVAILABLE:"+key); unavailable.add(key)
            continue
        try:
            with io._directory(io.WORKSPACE / grant.output_directory) as (fd, _):
                data = io._read(fd, ref["name"])
            _require(len(data) == ref["byte_count"] and hashlib.sha256(data).hexdigest() == ref["sha256"],
                     "REFERENCE_BYTES_CHANGED:"+key)
            raw[key] = data
        except (ValueError, io.EvidenceError) as error:
            errors.append(str(error))
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                errors.append("UNSAFE_REFERENCE_OBJECT:"+key)
            else:
                deficient.append("REFERENCE_UNAVAILABLE:"+key); unavailable.add(key)

    process = value["process"]; observations = output["output_observations"]
    capture_ok = False
    if raw["capture"] is not None:
        try:
            from .integration import digest
            capture = io._decode(raw["capture"])
            origin_fields = {'evidence_kind':run['evidence_kind']} if 'evidence_kind' in capture else {}
            _require(bool(origin_fields) or run['evidence_kind'] == 'SYNTHETIC', 'CAPTURE_ORIGIN_REQUIRED')
            _keys(capture, ("run_id", "condition_label", "binding_sha256", "process", "output_observations", *origin_fields))
            _process(capture["process"]); _observations(capture["output_observations"])
            _require(capture == dict(run_id=run["run_id"], condition_label=run["condition_label"],
                binding_sha256=digest(run["binding"]), process=process, output_observations=observations, **origin_fields),
                "CAPTURE_CONTEXT_OR_OBSERVATION_MISMATCH")
            _require(observations["expected"] == grant.expected, "EXPECTED_OUTPUT_NOT_ANCHORED")
            capture_ok = True
        except (ValueError, io.EvidenceError) as error:
            errors.append(str(error))
    if process["state"] != "EXITED":
        witness("PROCESS_WAIT_UNAVAILABLE", ["capture"] if capture_ok else [])
        deficient.append("PROCESS_WAIT_UNAVAILABLE")
    elif refs["capture"] is None:
        errors.append("EXIT_WITHOUT_CAPTURE")
    elif capture_ok and process["exit_code"] != 0:
        witness("PROCESS_NONZERO_EXIT", ["capture"]); deficient.append("PROCESS_NONZERO_EXIT")
    if not capture_ok:
        deficient.append("CAPTURE_UNAVAILABLE")

    counts = value["diagnostics"]["counts"]; coverage = value["diagnostics"]["coverage"]
    if raw["diagnostics"] is not None:
        try:
            diagnostic_data = io._decode(raw['diagnostics'])
            _require(type(diagnostic_data) is dict, 'UNSUPPORTED_DIAGNOSTIC_MAPPING')
            if diagnostic_data.get('mapping') == SYNTHETIC_MAPPING:
                _require(run['evidence_kind'] == 'SYNTHETIC', 'DIAGNOSTIC_ORIGIN_MISMATCH')
                actual, actual_coverage = _synthetic_diagnostics(raw["diagnostics"])
            else:
                from .native_mapping import MAPPING, parse_diagnostics
                _require(diagnostic_data.get('mapping') == MAPPING, 'UNSUPPORTED_DIAGNOSTIC_MAPPING')
                actual, actual_coverage = parse_diagnostics(diagnostic_data, evidence_kind=run['evidence_kind'])
                _require(diagnostic_data['finalized'] == (process['state'] == 'EXITED'), 'NATIVE_DIAGNOSTIC_FINALIZATION_MISMATCH')
            # Derive positives before rejecting an inconsistent coverage/count claim.
            for key, count in actual.items():
                if count:
                    witness(POSITIVE[key], ["diagnostics"]); errors.append(POSITIVE[key])
            _require(counts == actual and coverage == actual_coverage, "DIAGNOSTIC_CLAIM_MISMATCH")
        except (ValueError, io.EvidenceError) as error:
            errors.append(str(error))
    elif refs["diagnostics"] is None and (coverage != "UNAVAILABLE" or any(v is not None for v in counts.values())):
        errors.append("DIAGNOSTICS_WITHOUT_SUPPORT")
    if raw["diagnostics"] is None or coverage != "COMPLETE":
        deficient.append("DIAGNOSTICS_UNAVAILABLE")
        witness("DIAGNOSTICS_UNAVAILABLE", ["diagnostics"] if refs["diagnostics"] else [])

    expected, observed = observations["expected"], observations["observed"]
    identity = "UNVERIFIED"
    if capture_ok and expected is not None and observed is not None:
        identity = "MATCH"
        if (expected["device"], expected["inode"]) != (observed["device"], observed["inode"]):
            witness("OUTPUT_OBJECT_MISMATCH", ["capture", "output_observations"])
            errors.append("OUTPUT_OBJECT_MISMATCH"); identity = "CONTRADICTED"
        if expected["sha256"] is not None and observed["sha256"] is not None:
            if (expected["byte_count"], expected["sha256"]) != (observed["byte_count"], observed["sha256"]):
                if process["state"] == "EXITED":
                    witness("OUTPUT_BYTES_CHANGED", ["capture", "output_observations"])
                    errors.append("OUTPUT_BYTES_CHANGED"); identity = "CONTRADICTED"
                else:
                    errors.append("CONTENT_BASELINE_WITHOUT_EXIT")
    trip = value["tripinfo"]
    if trip["identity"] != identity:
        if "capture" in unavailable:
            deficient.append("OUTPUT_IDENTITY_SUPPORT_UNAVAILABLE")
        else:
            errors.append("OUTPUT_IDENTITY_CLAIM_MISMATCH")
    if identity == "UNVERIFIED":
        deficient.append("OUTPUT_IDENTITY_UNVERIFIED")
    if raw["tripinfo"] is not None:
        if trip["availability"] != "AVAILABLE":
            errors.append("TRIPINFO_AVAILABILITY_MISMATCH")
        if capture_ok and observed is not None:
            if observed["sha256"] is None:
                deficient.append("OUTPUT_CONTENT_UNVERIFIED")
            elif (observed["byte_count"], observed["sha256"]) != (len(raw["tripinfo"]), hashlib.sha256(raw["tripinfo"]).hexdigest()):
                errors.append("CAPTURE_RETAINED_BYTES_MISMATCH")
        try:
            result["rows"] = adapter.parse_tripinfo_xml(raw["tripinfo"])
            result["parsing"] = "PARSED"
        except (ValueError, ET.ParseError):
            result["parsing"] = "UNPARSEABLE"
            deficient.append("TRIPINFO_UNPARSEABLE"); witness("TRIPINFO_UNPARSEABLE", ["tripinfo"])
            try:
                root = ET.fromstring(raw["tripinfo"])
                ids = [node.get("id") for node in root.findall("tripinfo")]
                if (root.tag == "tripinfos" and all(n.tag == "tripinfo" for n in root)
                        and (any(not v for v in ids) or len(ids) != len(set(ids)))):
                    errors.append("TRIPINFO_ID_CONTRADICTION")
                    witness("TRIPINFO_ID_CONTRADICTION", ["tripinfo"])
            except ET.ParseError:
                pass
        if not acquiring and (trip["parsing"] != result["parsing"] or
                (result["rows"] is not None and run["observations"]["tripinfo_records"] != result["rows"])):
            errors.append("TRIPINFO_PARSE_OR_ROWS_MISMATCH")
    else:
        deficient.append("TRIPINFO_UNAVAILABLE")
        if refs["tripinfo"] is None and (trip["availability"] == "AVAILABLE" or trip["parsing"] != "NOT_ATTEMPTED"):
            errors.append("TRIPINFO_CLAIM_WITHOUT_REFERENCE")
        if trip["availability"] in ("MISSING", "UNREADABLE"):
            witness("TRIPINFO_"+trip["availability"], ["tripinfo"] if refs["tripinfo"] else [])
    if value["collection_state"] != "COMPLETED":
        deficient.append("FINALIZATION_COLLECTION_INCOMPLETE")
        if value["collection_state"] == "INTERRUPTED":
            witness("FINALIZER_EXCEPTION", [])
    for item in value["findings"]:
        code = item["code"]
        required = (["diagnostics"] if code in POSITIVE.values() else
                    ["capture", "output_observations"] if code in ("OUTPUT_OBJECT_MISMATCH", "OUTPUT_BYTES_CHANGED") else
                    ["tripinfo"] if code in ("TRIPINFO_UNPARSEABLE", "TRIPINFO_ID_CONTRADICTION") else
                    ["capture"] if code == "PROCESS_NONZERO_EXIT" else
                    [] if code == "FINALIZER_EXCEPTION" else None)
        if required is not None and item["evidence_keys"] != required:
            errors.append("FINDING_SUPPORT_MISMATCH:"+code)
            continue
        if code in witnesses:
            if item["evidence_keys"] != witnesses[code]:
                errors.append("FINDING_SUPPORT_MISMATCH:"+code)
        elif (set(item["evidence_keys"]) & unavailable
              and all(refs[k] is not None for k in item["evidence_keys"] if k in ARTIFACTS)):
            deficient.append("FINDING_SUPPORT_UNAVAILABLE:"+code)
        else:
            errors.append("UNSUPPORTED_FINDING:"+code)
    result["output_finalized"] = (value["collection_state"] == "COMPLETED"
                                   and process["state"] == "EXITED" and capture_ok
                                   and result["parsing"] == "PARSED")
    if not acquiring and run["output_finalized"] != result["output_finalized"]:
        if unavailable:
            deficient.append("FINALIZATION_SUPPORT_UNAVAILABLE")
        else:
            errors.append("OUTPUT_FINALIZED_CLAIM_MISMATCH")
    return result


def require_supported_assertions(run, *, references=None):
    """Strict envelopes may retain witnessed failures, not fabricated assertions.

    Rejected material can still be kept as uninterpreted raw FAILURE evidence
    with run=None. This is the same validator, not a second severity policy.
    """
    facts = validate(run, references=references)
    _require(not (set(facts['errors']) - INTEGRITY_WITNESSES), 'INVALID_FINALIZATION_ASSERTIONS')
