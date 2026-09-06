"""Public synthetic fixtures and frozen numeric/input regression identities.

Golden payload hashes record verified frozen V2 outputs, whose representative
valid cases matched V1 during the historical correction audit. They are not
traffic results. V1 source is neither shipped nor imported by these fixtures.
"""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.b0.od_concentration_v2 import od_input


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "configs/b0/od-concentration-v1/calibration-contract.json"
WAITING_METRIC = "sumo_tripinfo_waiting_time_seconds_total"
GOLDEN_PAYLOAD_SHA256 = {
    "valid_mixed": "8c0170b23348db848ff8747371ae886072b3641447d2b7f36a128af30c12a592",
    "valid_large_finite": "1c4feea0a459084964efb8f193a9e75679b8095f7527b180fa8fced410a11ec0",
    "valid_c1_normal_waits": "1a3101787ce118ecb968ed27aecb008be60e2725ef45fdd1bb86a2dca385d70e",
    "overflow_c1_ledger": "6cec72cf4b2249bdc221fbd39c01aa6ea5cf46056351f22c74e247750fa99a7b",
    "overflow_c1_other_metrics": "ddad7625c7100fb55d8d4c583e41a9156d2ef19f03c819796c9e30a4a835afee"
}
FROZEN_INPUT_SHA256 = {
    "20260904-C1": "9d9bf9c509a00fff4c3f1f4b7e6073866d44bc65414d2ef56de7de896df97957",
    "20260904-C2": "42664a362d96c67ced5eb987930512c3c1a7bcce56e4e9296d800f7cb42f6078",
    "20260904-C3": "d8cb065797126a38d048510949a0653d8426ad240bc8ec667d1aae849205556a",
    "20260904-C4": "c01b805ee59b7f7db23dd457263d587e1f4386ff3ee7e664b38b462b502742fa",
    "20260905-C1": "24d6cce52d990c42b341a6a3693ba65cf768c6bdc1777aa8b95bc783a0fd16ff",
    "20260905-C2": "4f29e7480b60f93abf00d2073eef1357f14950b9643e09f37c849a0738590a5c",
    "20260905-C3": "e6200fa967f179f1c73b39144437879700ab4c523cebe32670a7be0d485e77f3",
    "20260905-C4": "c17d48e96553fe047a87d19adf76168e6adfac6ada0e17d0e413632dc085b35c",
    "20260906-C1": "91d30452e7177a890db0f7bf028ee32aaa82b83564544030e8598ad4ef71b9dc",
    "20260906-C2": "ab0c8d5b01c37e1a3d7ba58792ec0f27e1c2a0e41f59421ba81d91355a5dd7bd",
    "20260906-C3": "ae64cc4e832b05231a879fd71d9f608de1a37c2b387cc0b0a631c0514aeb8277",
    "20260906-C4": "6873077d1df22599a03b6a42a14b2ae6031d4f98bcd10dd497b32991eb3d1166"
}


def payload_sha256(value):
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def exact_c1_fixture():
    """Reconstruct the original 540-trip numerical counterexample, without files."""
    contract = od_input.load_contract(CONTRACT_PATH)
    trips = od_input.build_seed_allocations(contract, 20260904)["C1"]
    source = od_input.serialize_routes(contract, 20260904, "C1", trips) + b"\n"
    if hashlib.sha256(source).hexdigest() != FROZEN_INPUT_SHA256["20260904-C1"]:
        raise ValueError("C1 counterexample input identity differs")
    vehicles = ET.fromstring(source).findall("vehicle")
    if len(vehicles) != 540 or sum(v.attrib["route"] == "row1_east" for v in vehicles) != 90:
        raise ValueError("counterexample is not the exact 540-trip C1 population")
    scheduled, records, departures, arrivals = [], [], {}, {}
    for index, vehicle in enumerate(vehicles):
        vehicle_id = vehicle.attrib["id"]
        departure = float(vehicle.attrib["depart"])
        scheduled.append({"vehicle_id": vehicle_id, "route_id": vehicle.attrib["route"],
                          "scheduled_departure_seconds": departure})
        records.append({"id": vehicle_id, "depart": departure + 1,
                        "arrival": departure + 101,
                        "waitingTime": 1e308 if index < 2 else 0})
        departures[vehicle_id] = [departure + 1]
        arrivals[vehicle_id] = [departure + 101]
    return scheduled, {
        "tripinfo_records": records, "departed_events": departures,
        "arrival_events": arrivals, "cutoff_active_ids": [], "cutoff_pending_ids": [],
        "per_trip_halting_seconds": {row["vehicle_id"]: 0 for row in scheduled},
        "queue_trace": [[t, 0] for t in range(1, 1501)],
    }
