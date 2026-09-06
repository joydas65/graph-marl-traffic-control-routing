"""Frozen-contract pair gates and a bounded synthetic first-qualifying ladder.

No simulator or writer is launched here. Every pair is revalidated from its
observations; durable acceptance is a separate, explicit readback operation.
"""

import copy
from fractions import Fraction
import json
import math
from pathlib import Path

from scripts.b0.od_concentration_v2 import cutoff_measurement, od_input

from . import integration


IDENTITY = "B0_OD_INTEGRATION_LAYER_V1"


def _contract():
    root = Path(od_input.__file__).resolve().parents[3]
    return od_input.load_contract(root / "configs/b0/od-concentration-v1/calibration-contract.json")


def _fraction(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("a required finite numeric observation is unavailable")
    return Fraction(value)


def _integer(value):
    exact = _fraction(value)
    if exact.denominator != 1 or exact < 0:
        raise ValueError("a nonnegative integer observation is required")
    return exact.numerator


def _pair(n0, d0, *, repeat=False):
    contract = _contract()
    result = {
        "evidence_kind": "SYNTHETIC", "ready_to_run": False,
        "pair_status": "INTEGRITY_FAILURE", "stop_status": "FAIL",
        "qualification_evaluated": False, "gates": {}, "reason_codes": [],
    }
    try:
        expected = ("N0-CAL-R", "D0-CAL-R") if repeat else ("N0", "D0")
        if (n0["condition_label"], d0["condition_label"]) != expected:
            raise ValueError("wrong pair roles")
        if n0["run_id"] == d0["run_id"] or n0["binding"] != d0["binding"]:
            raise ValueError("duplicate or substituted pair input")
        fresh = [integration.validate_run(record) for record in (n0, d0)]
        binding = n0["binding"]
        result.update(seed=binding["seed"], level=binding["level"],
                      run_ids=[n0["run_id"], d0["run_id"]])
        statuses = [measurement["measurement_status"] for measurement in fresh]
        if any(status not in ("VALID", "INTEGRITY_FAILURE", "EVIDENCE_DEFICIENCY")
               for status in statuses):
            raise ValueError("unknown measurement status")
        if "INTEGRITY_FAILURE" in statuses:
            result["reason_codes"] = ["MEASUREMENT_INTEGRITY_FAILURE"]
            result["measurement_reasons"] = [m["integrity_errors"] for m in fresh]
            return result
        if "EVIDENCE_DEFICIENCY" in statuses:
            result.update(pair_status="EVIDENCE_DEFICIENCY", stop_status="INCONCLUSIVE",
                          reason_codes=["REQUIRED_MEASUREMENT_EVIDENCE_DEFICIENT"],
                          measurement_reasons=[m["evidence_deficiencies"] for m in fresh])
            return result
        nm, dm = (measurement["metrics"] for measurement in fresh)
        ledger_n, ledger_d = (measurement["ledger"] for measurement in fresh)
        count = contract["scientific_configuration"]["fixed_total_scheduled_trips"]
        if (nm["scheduled_trips"] != count or dm["scheduled_trips"] != count
                or len(ledger_n) != count or set(ledger_n) != set(ledger_d)):
            raise ValueError("all-scheduled pair accounting differs")
        for metrics in (nm, dm):
            for value in metrics.values():
                _fraction(value)
        difference = sum((_fraction(row["restricted_trip_time_seconds"])
                          for row in ledger_d.values()), Fraction()) - sum(
                              (_fraction(row["restricted_trip_time_seconds"])
                               for row in ledger_n.values()), Fraction())
        nq, dq = (_integer(m["cumulative_queue_vehicle_seconds"]) for m in (nm, dm))
        exposed = d0["summary"]["unique_edge_entries"]["during"]
        if (not isinstance(exposed, list) or len(set(exposed)) != len(exposed)
                or d0["summary"]["unique_edge_entry_counts"]["during"] != len(exposed)):
            raise ValueError("observed unique exposure disagrees")
        local = cutoff_measurement.paired_local_response(
            n0["summary"], d0["summary"], ledger_n, ledger_d)
        gates_contract = contract["qualification_contract"]
        ratio = Fraction(str(gates_contract["d0_queue_burden_relative_increase_minimum"]))
        mean_minimum = count * Fraction(str(gates_contract["d0_mean_trip_time_increase_seconds_minimum"]))
        gates = {
            "n0_completion": cutoff_measurement.completion_gate(_integer(nm["arrived_trips"]), count, "N0"),
            "d0_completion": cutoff_measurement.completion_gate(_integer(dm["arrived_trips"]), count, "D0"),
            "actual_event_entry_exposure": len(exposed) >= gates_contract["d0_exposure_count_minimum"],
            "all_scheduled_restricted_time": difference >= mean_minimum,
            "network_queue": None if nq == 0 else ratio.denominator * dq >= (ratio.denominator + ratio.numerator) * nq,
            "local_physical_response": {"PASS": True, "FAIL": False, "NOT_IDENTIFIABLE": None}[local["status"]],
        }
        failed = [name for name, passed in gates.items() if passed is False]
        unknown = [name for name, passed in gates.items() if passed is None]
        state = "DOES_NOT_QUALIFY" if failed else "NOT_IDENTIFIABLE" if unknown else "QUALIFIES"
        result.update(pair_status=state, stop_status=None, qualification_evaluated=True,
                      gates=gates, failed_gates=failed, unknown_gates=unknown,
                      local_response=local, exact_restricted_sum_difference={
                          "numerator": difference.numerator, "denominator": difference.denominator},
                      queue_totals={"N0": nq, "D0": dq})
        return result
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        result["reason_codes"] = ["INVALID_RUN_OR_PAIR_EVIDENCE"]
        return result


def qualify_pair(n0, d0):
    """Recompute measurements, then apply exact gates to one original N0/D0 pair."""
    return _pair(n0, d0)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _without_operational(value, excluded):
    if isinstance(value, dict):
        return {key: _without_operational(item, excluded)
                for key, item in value.items() if key not in excluded}
    if isinstance(value, list):
        return [_without_operational(item, excluded) for item in value]
    return value


class SelectionSession:
    """At most four ordered three-seed levels and one exact two-run repeat."""

    def __init__(self):
        self._rules = _contract()
        self._levels = []
        self._repeats = None
        self._run_ids = set()
        self._accepted = False
        self._decision = self._state("CONTINUE")

    def _state(self, status, reasons=(), provisional=None):
        return {
            "status": status, "reason_codes": list(reasons),
            "provisional_level": provisional, "evidence_kind": "SYNTHETIC",
            "selected_calibrated_od_concentration": None, "ready_to_run": False,
            "scientific_records": len(self._levels) * 6,
            "repeat_records": 0 if self._repeats is None else 2,
        }

    @property
    def decision(self):
        result = copy.deepcopy(self._decision)
        if self._accepted:
            result.update(status="PASS", readback_verified=True,
                          synthetic_selected_level=result["provisional_level"])
        return result

    def add_level(self, level, pairs):
        if self._decision["status"] != "CONTINUE":
            raise ValueError("selection has stopped; no higher level or retry is permitted")
        sequence = self._rules["selection_rule"]["sequence"]
        if len(self._levels) >= len(sequence) or level != sequence[len(self._levels)]:
            raise ValueError("concentration is missing, repeated or out of order")
        seeds = self._rules["calibration_seeds"]
        if not isinstance(pairs, (list, tuple)) or len(pairs) != len(seeds):
            raise ValueError("every evaluated level requires all three seed pairs")
        prepared, run_ids = [], []
        for seed, pair in zip(seeds, pairs):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError("each seed requires one complete N0/D0 pair")
            n0, d0 = pair
            if any(record["binding"]["seed"] != seed or record["binding"]["level"] != level
                   for record in (n0, d0)):
                raise ValueError("seed or concentration evidence is out of order")
            run_ids.extend([n0["run_id"], d0["run_id"]])
            prepared.append({"N0": copy.deepcopy(n0), "D0": copy.deepcopy(d0)})
        if len(set(run_ids)) != len(run_ids) or set(run_ids) & self._run_ids:
            raise ValueError("run evidence was duplicated or reused")
        if (len(self._levels) + 1) * 6 > self._rules["future_execution_budget"]["scientific_simulations_maximum"]:
            raise ValueError("scientific evidence exceeds the frozen bound")
        self._levels.append({"level": level, "pairs": prepared})
        self._run_ids.update(run_ids)
        decisions = [qualify_pair(pair["N0"], pair["D0"]) for pair in prepared]
        states = [item["pair_status"] for item in decisions]
        if "INTEGRITY_FAILURE" in states:
            self._decision = self._state("FAIL", ["SEED_MEASUREMENT_INTEGRITY_FAILURE"])
        elif "EVIDENCE_DEFICIENCY" in states:
            self._decision = self._state("INCONCLUSIVE", ["SEED_MEASUREMENT_EVIDENCE_DEFICIENT"])
        elif "DOES_NOT_QUALIFY" in states:
            status = self._rules["selection_rule"]["no_qualifying_outcome"] if len(self._levels) == len(sequence) else "CONTINUE"
            self._decision = self._state(status, ["LEVEL_DEFINITIVELY_DOES_NOT_QUALIFY"])
        elif "NOT_IDENTIFIABLE" in states:
            self._decision = self._state("INCONCLUSIVE", ["LEVEL_HAS_REQUIRED_UNKNOWN"])
        else:
            self._decision = self._state("PROVISIONAL", provisional=level)
        self._decision["pair_decisions"] = decisions
        return self.decision

    def add_repeats(self, n0, d0):
        if self._decision["status"] != "PROVISIONAL" or self._repeats is not None:
            raise ValueError("exactly one repeat pair is permitted after the first qualifier")
        level = self._decision["provisional_level"]
        self._repeats = {"N0": copy.deepcopy(n0), "D0": copy.deepcopy(d0)}
        repeat_rule = self._rules["selected_deterministic_repeat"]
        try:
            ids = [n0["run_id"], d0["run_id"]]
            if len(set(ids)) != 2 or set(ids) & self._run_ids:
                raise ValueError("repeat IDs must be fresh and distinct")
            if any(record["binding"]["seed"] != repeat_rule["seed"]
                   or record["binding"]["level"] != level for record in (n0, d0)):
                raise ValueError("repeat must use the selected level and first seed")
            result = _pair(n0, d0, repeat=True)
            if result["pair_status"] != "QUALIFIES":
                raise ValueError("repeat measurement or scientific qualification differs")
            original = self._levels[-1]["pairs"][0]
            excluded = set(repeat_rule["operational_fields_excluded"])
            for condition, repeat_record in (("N0", n0), ("D0", d0)):
                previous = original[condition]
                left = integration.normalized_scientific(previous)
                right = integration.normalized_scientific(repeat_record)
                if (set(left) != set(repeat_rule["normalized_fields"])
                        or set(right) != set(repeat_rule["normalized_fields"])
                        or _canonical(left) != _canonical(right)
                        or _canonical(_without_operational(previous, excluded)) != _canonical(_without_operational(repeat_record, excluded))):
                    raise ValueError("normalized scientific repeat differs")
            self._run_ids.update(ids)
            self._decision = self._state("PENDING_READBACK", provisional=level)
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            self._decision = self._state("FAIL", ["SELECTED_REPEAT_FAILED"], provisional=level)
        return self.decision

    def to_record(self):
        """Return replayable synthetic evidence, never a real selected scenario."""
        return copy.deepcopy({
            "schema_version": 1, "integration_identity": IDENTITY,
            "evidence_kind": "SYNTHETIC", "ready_to_run": False,
            "levels": self._levels, "repeats": self._repeats,
            "decision": self._decision,
        })

    def finalize(self, receipt):
        if self._decision["status"] != "PENDING_READBACK" or self._accepted:
            raise ValueError("successful repeat and a new verified readback are required")
        from . import evidence
        try:
            payload = evidence.readback(receipt)
            if (payload["record_kind"] != "SELECTION"
                    or _canonical(payload["record"]) != _canonical(self.to_record())):
                raise ValueError("readback does not describe this exact selection")
        except Exception as error:
            stop = getattr(error, "experiment_status", "FAIL")
            stop = stop if stop in ("FAIL", "BLOCKED") else "FAIL"
            self._decision = self._state(stop, ["SELECTION_READBACK_FAILED"],
                                         provisional=self._decision["provisional_level"])
            raise
        self._accepted = True
        return self.decision


def validate_selection_record(record):
    """Recompute the complete bounded history; no stored status is authoritative."""
    keys = {"schema_version", "integration_identity", "evidence_kind", "ready_to_run",
            "levels", "repeats", "decision"}
    if (not isinstance(record, dict) or set(record) != keys
            or type(record["schema_version"]) is not int or record["schema_version"] != 1
            or record["integration_identity"] != IDENTITY
            or record["evidence_kind"] != "SYNTHETIC" or record["ready_to_run"] is not False
            or not isinstance(record["levels"], list) or not record["levels"]):
        raise ValueError("invalid synthetic selection envelope")
    session = SelectionSession()
    for level in record["levels"]:
        if not isinstance(level, dict) or set(level) != {"level", "pairs"} or not isinstance(level["pairs"], list):
            raise ValueError("invalid level evidence")
        if any(not isinstance(pair, dict) or set(pair) != {"N0", "D0"} for pair in level["pairs"]):
            raise ValueError("invalid seed-pair evidence")
        session.add_level(level["level"], [(pair["N0"], pair["D0"]) for pair in level["pairs"]])
    if record["repeats"] is not None:
        if not isinstance(record["repeats"], dict) or set(record["repeats"]) != {"N0", "D0"}:
            raise ValueError("invalid repeat evidence")
        session.add_repeats(record["repeats"]["N0"], record["repeats"]["D0"])
    if _canonical(session.to_record()) != _canonical(record):
        raise ValueError("stored decision differs from revalidated evidence")
    return session.decision
