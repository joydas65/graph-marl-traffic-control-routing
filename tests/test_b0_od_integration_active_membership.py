"""Whole-validator differential checks; all runtime capabilities stay injected."""

import copy
import hashlib
import json
import pickle
import unittest
from unittest.mock import patch

from b0_active_membership_oracle import make_reference_validate_run, reference_active
from b0_od_integration_fixtures import REFERENCES, FakeBackend, good_record, observe
from scripts.b0.od_integration_v1 import evidence as io, finalization as final
from scripts.b0.od_integration_v1 import integration as core, native_worker as worker
from test_b0_od_integration_live_binding import BOUNDS, Fixture


class PlainDict(dict):
    pass


class PlainList(list):
    pass


class IntegralInt(int):
    pass


class IntegralFloat(float):
    pass


def outcome(call):
    try:
        return ("RETURN", call())
    except Exception as error:
        return ("RAISE", type(error).__name__, str(error))


def serialized(value):
    # Nonfinite malformed inputs are compared, never sanitized for production.
    return json.dumps(value, sort_keys=True, allow_nan=True, separators=(",", ":"))


class ActiveMembershipDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = staticmethod(make_reference_validate_run(core))
        cls.records = {label: good_record(condition_label=label,
                          run_id="SYNTHETIC-ACTIVE-" + label)
                       for label in ("N0", "D0", "N0-CAL-R", "D0-CAL-R")}

    def compare(self, run, *, prefix=False):
        before = pickle.dumps(run, protocol=5)
        old = outcome(lambda: self.reference(run, prefix=prefix, references=REFERENCES))
        new = outcome(lambda: core._validate_run(run, prefix=prefix, references=REFERENCES))
        self.assertEqual(serialized(new), serialized(old))
        self.assertEqual(pickle.dumps(run, protocol=5), before, "validation mutated evidence")
        with patch.object(core, "_validate_run", self.reference):
            old_assessment = outcome(lambda: core.assess_run(run, references=REFERENCES))
        new_assessment = outcome(lambda: core.assess_run(run, references=REFERENCES))
        self.assertEqual(serialized(new_assessment), serialized(old_assessment))
        self.assertEqual(pickle.dumps(run, protocol=5), before, "assessment mutated evidence")
        return new, new_assessment

    def test_n0_d0_and_repeats_compare_complete_outputs(self):
        for label, run in self.records.items():
            with self.subTest(label=label):
                result, assessment = self.compare(run)
                self.assertEqual(result[0], "RETURN")
                self.assertEqual(result[1]["measurement_status"], "VALID")
                self.assertEqual(result[1]["ledger"], run["measurement"]["ledger"])
                self.assertEqual(result[1]["metrics"], run["measurement"]["metrics"])
                self.assertIsNone(assessment[1]["stop_status"])
                with patch.object(core, "_validate_run", self.reference):
                    old = core.normalized_scientific(run, references=REFERENCES)
                self.assertEqual(core.normalized_scientific(run, references=REFERENCES), old)

    def test_empty_events_no_departures_and_active_at_cutoff(self):
        for name, options in (("pending", dict(pending_count=540, queue_budget=0)),
                              ("censored", dict(active_count=3)),
                              ("missing-output", dict(missing_output=True))):
            with self.subTest(case=name):
                run = good_record(run_id="SYNTHETIC-ACTIVE-" + name, **options)
                self.compare(run)
                if name == "pending":
                    self.assertEqual(run["observations"]["departed_events"], {})
                    self.assertEqual(run["observations"]["arrival_events"], {})
                if name == "censored":
                    active = run["observations"]["cutoff_active_ids"]
                    self.assertEqual(len(active), 3)
                    self.assertTrue(all(v not in run["observations"]["arrival_events"] for v in active))

    def test_supported_prefix_and_zero_prefix_complete_outputs(self):
        for condition, end in (("N0", 0), ("N0", 50), ("D0", 350), ("D0", 1499)):
            with self.subTest(condition=condition, end=end):
                run = good_record(condition_label=condition, fail_step=end,
                                  run_id=f"SYNTHETIC-ACTIVE-PREFIX-{condition}-{end}")
                result, assessed = self.compare(run, prefix=True)
                self.assertEqual(result[0], "RETURN")
                self.assertEqual(result[1]["integrity_errors"], [])
                self.assertEqual(assessed[1]["stop_status"], "BLOCKED")
                self.assertFalse(assessed[1]["qualification_evaluated"])

    def test_missing_output_stays_inconclusive_and_independent_contradiction_wins(self):
        run = good_record(run_id="SYNTHETIC-ACTIVE-DEFICIENT-PRECEDENCE", missing_output=True)
        result, assessed = self.compare(run)
        self.assertEqual(result[1]["measurement_status"], "EVIDENCE_DEFICIENCY")
        self.assertEqual(assessed[1]["stop_status"], "INCONCLUSIVE")
        self.assertFalse(assessed[1]["qualification_evaluated"])
        self.assertTrue(result[1]["evidence_deficiencies"])
        run["controls"]["steps"][0]["active_ids"] = []
        contradicted, assessment = self.compare(run)
        self.assertEqual(contradicted[1]["measurement_status"], "INTEGRITY_FAILURE")
        self.assertIn("OBSERVATION_OR_CONTROL_EVIDENCE:ACTIVE_OR_HALTING_EVIDENCE",
                      contradicted[1]["integrity_errors"])
        self.assertEqual(assessment[1]["stop_status"], "FAIL")
        self.assertFalse(assessment[1]["qualification_evaluated"])

    def test_plain_container_and_numeric_subclasses_retain_reference_behavior(self):
        for kind in (PlainDict, PlainList, IntegralInt, IntegralFloat):
            with self.subTest(kind=kind.__name__):
                run = copy.deepcopy(self.records["N0"])
                for key in ("departed_events", "arrival_events"):
                    if kind is PlainDict:
                        run["observations"][key] = PlainDict(run["observations"][key])
                    elif kind is PlainList:
                        run["observations"][key] = {
                            v: PlainList(times) for v, times in run["observations"][key].items()}
                    else:
                        run["observations"][key] = {
                            v: [kind(t) for t in times] for v, times in run["observations"][key].items()}
                self.compare(run)

    def test_same_time_multiple_boundaries_use_departure_inclusive_arrival_exclusive(self):
        binding = core.build_binding(core.repository_root(), 20260904, "C1")
        backend = FakeBackend(binding, queue_budget=0)
        vehicles = list(backend.departure)
        # These are explicit synthetic trajectories, not changed scientific inputs.
        for vehicle in vehicles[:3]:
            backend.departure[vehicle] = 11
            backend.arrival[vehicle] = 11
        for vehicle in vehicles[3:6]:
            backend.departure[vehicle] = 11
            backend.arrival[vehicle] = 12
        run = observe(binding, "N0", "SYNTHETIC-ACTIVE-BOUNDARIES", backend, backend)
        self.compare(run)
        departed, arrived = run["observations"]["departed_events"], run["observations"]["arrival_events"]
        self.assertFalse(set(vehicles[:3]) & reference_active(departed, arrived, 11))
        self.assertTrue(set(vehicles[3:6]) <= reference_active(departed, arrived, 11))
        self.assertFalse(set(vehicles[3:6]) & reference_active(departed, arrived, 12))

    def test_integral_float_and_shuffled_map_order(self):
        for conversion in ("float", "reverse", "both"):
            with self.subTest(conversion=conversion):
                run = copy.deepcopy(self.records["D0"])
                for name in ("departed_events", "arrival_events"):
                    items = list(run["observations"][name].items())
                    if conversion in ("reverse", "both"):
                        items.reverse()
                    run["observations"][name] = {
                        key: [float(v) for v in values] if conversion in ("float", "both") else values
                        for key, values in items}
                self.compare(run)

    def test_zero_and_horizon_event_boundaries(self):
        cases = (("zero-int", "departed_events", 0),
                 ("zero-float", "departed_events", 0.0),
                 ("negative-zero", "departed_events", -0.0),
                 ("arrival-first-sample", "arrival_events", 1),
                 ("arrival-horizon", "arrival_events", 1500),
                 ("departure-horizon", "departed_events", 1500))
        for name, key, value in cases:
            with self.subTest(case=name):
                run = copy.deepcopy(self.records["N0"])
                run["observations"][key]["veh_0000"] = [value]
                if name == "departure-horizon":
                    run["observations"]["arrival_events"].pop("veh_0000")
                self.compare(run)

    def test_malformed_events_preserve_full_diagnostics(self):
        cases = (
            ("fraction", lambda o, v: o["departed_events"].__setitem__(v, [1.5])),
            ("boolean", lambda o, v: o["departed_events"].__setitem__(v, [True])),
            ("nan", lambda o, v: o["departed_events"].__setitem__(v, [float("nan")])),
            ("infinity", lambda o, v: o["arrival_events"].__setitem__(v, [float("inf")])),
            ("negative-infinity", lambda o, v: o["departed_events"].__setitem__(v, [-float("inf")])),
            ("missing-departure", lambda o, v: o["departed_events"].pop(v)),
            ("missing-arrival", lambda o, v: o["arrival_events"].pop(v)),
            ("duplicate-departure", lambda o, v: o["departed_events"].__setitem__(v, [1, 1])),
            ("duplicate-arrival", lambda o, v: o["arrival_events"].__setitem__(v, [101, 101])),
            ("empty-departure", lambda o, v: o["departed_events"].__setitem__(v, [])),
            ("empty-arrival", lambda o, v: o["arrival_events"].__setitem__(v, [])),
            ("backwards", lambda o, v: o["arrival_events"].__setitem__(v, [0])),
            ("map-list", lambda o, v: o.__setitem__("departed_events", [])),
            ("arrival-map-none", lambda o, v: o.__setitem__("arrival_events", None)),
            ("scalar-event", lambda o, v: o["departed_events"].__setitem__(v, 1)),
            ("text-event", lambda o, v: o["departed_events"].__setitem__(v, ["1"])),
            ("tuple-event", lambda o, v: o["departed_events"].__setitem__(v, (1,))),
            ("huge-integer", lambda o, v: o["departed_events"].__setitem__(v, [10 ** 1000])),
            ("unused-bad-arrival", lambda o, v: o["arrival_events"].__setitem__("unknown", [])),
            ("duplicate-skips-bad-arrival", lambda o, v: (
                o["departed_events"].__setitem__(v, [1, 1]),
                o["arrival_events"].__setitem__(v, []))),
            ("empty-skips-bad-arrival", lambda o, v: (
                o["departed_events"].__setitem__(v, []),
                o["arrival_events"].__setitem__(v, []))),
        )
        for name, change in cases:
            with self.subTest(case=name):
                run = copy.deepcopy(self.records["N0"])
                change(run["observations"], "veh_0000")
                self.compare(run)

    def test_bad_sample_identity_precedes_later_malformed_event(self):
        for sample_index in (0, 20):
            for field, replacement in (("time", -1), ("controls_sha256", "0" * 64)):
                with self.subTest(field=field, sample_index=sample_index):
                    run = copy.deepcopy(self.records["N0"])
                    run["controls"]["steps"][sample_index][field] = replacement
                    run["observations"]["arrival_events"]["veh_0539"] = []
                    result, assessed = self.compare(run)
                    self.assertEqual(result[0], "RETURN")
                    errors = result[1]["integrity_errors"]
                    self.assertIn("OBSERVATION_OR_CONTROL_EVIDENCE:CONTROL_TIME_OR_BINDING", errors)
                    self.assertEqual(assessed[1]["stop_status"], "FAIL")

    def test_no_shared_validation_state_hides_later_observation_change(self):
        run = copy.deepcopy(self.records["N0"])
        original = core.validate_run(run, references=REFERENCES)
        original["ledger"].clear()
        fresh = core.validate_run(run, references=REFERENCES)
        self.assertEqual(fresh["ledger"], run["measurement"]["ledger"])
        self.assertEqual(len(fresh["ledger"]), 540)
        run["controls"]["steps"][0]["active_ids"] = []
        result, assessed = self.compare(run)
        self.assertIn("OBSERVATION_OR_CONTROL_EVIDENCE:ACTIVE_OR_HALTING_EVIDENCE",
                      result[1]["integrity_errors"])
        self.assertEqual(assessed[1]["stop_status"], "FAIL")


class ActiveMembershipVerificationBoundaryTests(unittest.TestCase):
    def fixture(self):
        fixture = Fixture()
        self.addCleanup(fixture.close)
        return fixture

    def execute(self, fixture):
        return worker.execute_worker(fixture.plan, BOUNDS, lambda event: None,
            process_factory=fixture.process_factory, transport_factory=fixture.transport_factory,
            owned_scope_verified=True)

    def test_actual_worker_assessment_writer_and_readback_each_validate_freshly(self):
        fixture = self.fixture()
        validate, write, read = core._validate_run, io.write_once, io.readback
        phase, validations = ["ASSESSMENT"], []
        def checked(run, **kwargs):
            result = validate(run, **kwargs)
            validations.append((phase[0], result, len(run["controls"]["steps"])))
            return result
        def writer(*args, **kwargs):
            phase[0] = "WRITE_ONCE"
            try:
                return write(*args, **kwargs)
            finally:
                phase[0] = "AFTER_WRITE"
        def reader(*args, **kwargs):
            phase[0] = "EXPLICIT_WORKER_READBACK"
            return read(*args, **kwargs)
        with patch.object(core, "_validate_run", checked), patch.object(io, "write_once", writer), patch.object(io, "readback", reader):
            done = self.execute(fixture)
        self.assertEqual([p for p, _, _ in validations],
                         ["ASSESSMENT", "WRITE_ONCE", "WRITE_ONCE", "EXPLICIT_WORKER_READBACK"])
        self.assertEqual([n for _, _, n in validations], [1500] * 4)
        self.assertEqual(len({id(m) for _, m, _ in validations}), 4)
        self.assertTrue(all(m == validations[0][1] for _, m, _ in validations))
        self.assertEqual(done["assessment"]["measurement_status"], "VALID")
        references = final.ReferenceContext(final.ReferenceGrant(**g) for g in done["grants"])
        payload = read(done["receipt"], references=references)
        self.assertEqual(payload["record"]["measurement"], validations[0][1])

    def test_changed_observation_at_writer_and_explicit_worker_readback_is_rejected(self):
        for boundary in ("writer", "explicit-worker-readback"):
            with self.subTest(boundary=boundary):
                fixture = self.fixture()
                write, read = io.write_once, io.readback
                entered = []
                def writer(directory, name, payload, **kwargs):
                    entered.append("writer")
                    if boundary == "writer":
                        payload["record"]["controls"]["steps"][0]["active_ids"] = []
                    return write(directory, name, payload, **kwargs)
                def reader(receipt, **kwargs):
                    entered.append("explicit-worker-readback")
                    # Forge only this freshly generated synthetic envelope and its
                    # integrity metadata. Source grants and finalization artifacts
                    # stay unchanged; real readback must reject scientific data.
                    path = fixture.output / receipt["name"]
                    payload = json.loads(path.read_text())
                    payload["record"]["controls"]["steps"][0]["active_ids"] = []
                    raw = io._encode(payload)
                    path.write_bytes(raw)
                    marker_path = fixture.output / (receipt["name"] + ".complete.json")
                    marker = json.loads(marker_path.read_text())
                    marker.update(sha256=hashlib.sha256(raw).hexdigest(), byte_count=len(raw))
                    marker_path.write_bytes(io._encode(marker))
                    receipt = {**receipt, "sha256": marker["sha256"], "byte_count": len(raw)}
                    return read(receipt, **kwargs)
                with patch.object(io, "write_once", writer), patch.object(io, "readback", reader):
                    with self.assertRaises(io.EvidenceError) as caught:
                        self.execute(fixture)
                self.assertEqual(caught.exception.code, "MEASUREMENT_REVALIDATION")
                self.assertEqual(caught.exception.experiment_status, "FAIL")
                self.assertEqual(caught.exception.worker_failure["assessment"]["measurement_status"], "VALID")
                self.assertEqual(entered, ["writer"] if boundary == "writer" else
                                 ["writer", "explicit-worker-readback"])


if __name__ == "__main__":
    unittest.main()
