"""Read-only SUMO 1.27.1 representations; no client import or runtime authority.

Versioned primary sources are src/libsumo/Lane.cpp, src/utils/common/
SUMOVehicleClass.cpp, StringBijection.h, MsgHandler.{cpp,h}, SystemFrame.cpp,
and src/microsim/{MSLane,MSRouteHandler,MSBaseVehicle}.cpp in eclipse-sumo/sumo
tag v1_27_1. No SUMO source is executed here.

Diagnostic counts are the maximum supported message-occurrence count in either
retained stream, NOT unique collision/vehicle cardinalities. This avoids adding
the usual stderr/error-log duplication; only the frozen zero-tolerance use is
supported. Unknown messages cannot prove zeros. Capture ownership and observed
options are collector obligations, not authenticated by this data wrapper.
"""
import base64
import binascii
import re


MAPPING = "SUMO_1_27_1_ERROR_LOG_V1"
COUNTS = ("collisions", "invalid_routes", "simulator_errors")
REQUIRED_DIAGNOSTIC_OPTIONS = {
    "no-warnings": "false", "aggregate-warnings": "-1", "verbose": "false",
    "language": "en", "log.timestamps": "false", "log.processid": "false",
}
# getStrings() traverses the numeric-to-name map: deprecated aliases have been
# replaced by their final canonical names; 'ignoring' is explicitly excluded.
VEHICLE_CLASSES = frozenset((
    "private", "emergency", "authority", "army", "vip", "pedestrian",
    "passenger", "hov", "taxi", "bus", "coach", "delivery", "truck",
    "trailer", "motorcycle", "moped", "bicycle", "evehicle", "tram",
    "rail_urban", "rail", "rail_electric", "rail_fast", "ship", "container",
    "cable_car", "subway", "aircraft", "wheelchair", "scooter", "drone",
    "custom1", "custom2",
))
_IDENTIFIER = r"[^'\r\n]+"
_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_COLLISION_KIND = r"(?:frontal |side |junction )?collision"
_COLLISION = re.compile(
    rf"Warning: (?:Vehicle|Teleporting vehicle) '{_IDENTIFIER}'; "
    rf"{_COLLISION_KIND} with vehicle '{_IDENTIFIER}', lane='{_IDENTIFIER}', "
    rf"gap={_NUMBER}(?:, latGap={_NUMBER})?, time={_NUMBER}, stage=[A-Za-z0-9_-]+\."
)
_REMOVAL_COLLISION = re.compile(
    rf"Warning: Removing {_COLLISION_KIND} participants: "
    rf"vehicle '{_IDENTIFIER}', vehicle '{_IDENTIFIER}', lane='{_IDENTIFIER}', "
    rf"gap={_NUMBER}(?:, latGap={_NUMBER})?, time={_NUMBER}, stage=[A-Za-z0-9_-]+\."
)
_ROUTE = re.compile(
    rf"(?:Vehicle '{_IDENTIFIER}' has no route\."
    rf"|The route '{_IDENTIFIER}' for vehicle '{_IDENTIFIER}' is not known\."
    rf"|Vehicle '{_IDENTIFIER}' is not allowed to depart on any lane of edge '{_IDENTIFIER}'\."
    rf"|No connection between edge '{_IDENTIFIER}' and edge '{_IDENTIFIER}'\."
    rf"|Edge '{_IDENTIFIER}' prohibits\.)"
)
_BENIGN_WARNINGS = frozenset((
    "Warning: The option tripinfo-output.write-undeparted implies tripinfo-output.write-unfinished.",
))


def _require(ok, code):
    if not ok:
        raise ValueError(code)


def normalize_permissions(allowed, disallowed):
    """Map verified complementary native views to disallow-based canonical data.

    Both [] means unrestricted; allowed=[] plus disallowed=all means no class
    is permitted. Never infer unrestricted permission from allowed=[] alone.
    The caller retains both original native sequences alongside this result.
    """
    groups = []
    for values in (allowed, disallowed):
        _require(type(values) in (list, tuple), "NATIVE_PERMISSIONS_UNAVAILABLE")
        _require(all(type(value) is str and value in VEHICLE_CLASSES for value in values),
                 "NATIVE_PERMISSION_CLASS")
        _require(len(values) == len(set(values)), "NATIVE_PERMISSION_DUPLICATE")
        groups.append(set(values))
    allow, deny = groups
    if not allow and not deny:
        return {"allowed": [], "disallowed": []}
    _require(allow == VEHICLE_CLASSES - deny, "NATIVE_PERMISSION_COMPLEMENT")
    return {"allowed": [], "disallowed": sorted(deny)}


def _kind(evidence_kind):
    _require(type(evidence_kind) is str and evidence_kind in ("SYNTHETIC", "LIVE"),
             "NATIVE_DIAGNOSTIC_ORIGIN")


def _stream(raw):
    _require(raw is None or type(raw) is bytes, "NATIVE_DIAGNOSTIC_BYTES")
    if raw is None:
        return None
    return {"encoding": "base64", "data": base64.b64encode(raw).decode("ascii")}


def diagnostic_payload(raw, *, evidence_kind, finalized, stderr=None):
    """Retain byte-exact streams; default missing stderr cannot certify coverage.

    Set finalized only after owned-process exit and completed stream acquisition.
    An origin label or finalized flag alone proves no provenance or permission.
    """
    _kind(evidence_kind)
    _require(type(finalized) is bool, "NATIVE_DIAGNOSTIC_FINALIZED")
    return {"mapping": MAPPING, "version": 1, "evidence_kind": evidence_kind,
            "finalized": finalized,
            "streams": {"error_log": _stream(raw), "stderr": _stream(stderr)}}


def _decode_stream(value):
    if value is None:
        return None
    _require(type(value) is dict and set(value) == {"encoding", "data"},
             "NATIVE_DIAGNOSTIC_STREAM")
    _require(value["encoding"] == "base64" and type(value["data"]) is str,
             "NATIVE_DIAGNOSTIC_STREAM")
    try:
        raw = base64.b64decode(value["data"], validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("NATIVE_DIAGNOSTIC_ENCODING") from None
    _require(base64.b64encode(raw).decode("ascii") == value["data"],
             "NATIVE_DIAGNOSTIC_ENCODING")
    return raw


def _parse_stream(raw):
    counts = dict.fromkeys(COUNTS, 0)
    if raw is None:
        return counts, False
    # Decode each original LF-delimited record independently: a later bad byte
    # cannot erase an already accessible positive observation. Unterminated or
    # unknown lines leave coverage incomplete even when a prefix is recognizable.
    complete = not raw or raw.endswith(b"\n")
    for encoded in raw.split(b"\n"):
        if encoded == b"":
            continue
        try:
            line = encoded.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            complete = False
            continue
        if line.startswith("Error: ") and len(line) > len("Error: "):
            counts["simulator_errors"] += 1
            if _ROUTE.fullmatch(line[len("Error: "):]):
                counts["invalid_routes"] += 1
        elif _COLLISION.fullmatch(line) or _REMOVAL_COLLISION.fullmatch(line):
            counts["collisions"] += 1
        elif line in _BENIGN_WARNINGS:
            pass
        else:
            complete = False
    return counts, complete


def parse_diagnostics(payload, *, evidence_kind):
    """Recompute supported observations from bytes, never from supplied counts.

    Missing/unfinalized/partly recognized coverage retains known positives but
    returns None, not zero, for every unsupported zero. All-absent is UNAVAILABLE.
    """
    _kind(evidence_kind)
    _require(type(payload) is dict and set(payload) == {
        "mapping", "version", "evidence_kind", "finalized", "streams"},
        "NATIVE_DIAGNOSTIC_SCHEMA")
    _require(payload["mapping"] == MAPPING and type(payload["version"]) is int
             and payload["version"] == 1, "NATIVE_DIAGNOSTIC_MAPPING")
    _require(payload["evidence_kind"] == evidence_kind, "NATIVE_DIAGNOSTIC_ORIGIN")
    _require(type(payload["finalized"]) is bool, "NATIVE_DIAGNOSTIC_FINALIZED")
    streams = payload["streams"]
    _require(type(streams) is dict and set(streams) == {"error_log", "stderr"},
             "NATIVE_DIAGNOSTIC_STREAM")
    decoded = [_decode_stream(streams[key]) for key in ("error_log", "stderr")]
    parsed = [_parse_stream(raw) for raw in decoded]
    complete = payload["finalized"] and all(item[1] for item in parsed)
    counts = {key: max(item[0][key] for item in parsed) for key in COUNTS}
    if not complete:
        counts = {key: count if count else None for key, count in counts.items()}
    coverage = ("COMPLETE" if complete else "UNAVAILABLE" if all(raw is None for raw in decoded)
                else "INCOMPLETE")
    return counts, coverage
