"""Pure synthetic native-representation tests; no SUMO or client dependency."""
import base64
import copy
import unittest

from scripts.b0.od_integration_v1 import native_mapping as native


COLLISION = (b"Warning: Vehicle 'test-a'; collision with vehicle 'test-b', "
             b"lane='test_0', gap=-0.10, time=51.00, stage=movements.\n")
ERROR = b"Error: Vehicle 'test-a' has no route.\n"
BENIGN = (b"Warning: The option tripinfo-output.write-undeparted implies "
          b"tripinfo-output.write-unfinished.\n")


class NativeMappingTests(unittest.TestCase):
    def payload(self, raw=b"", stderr=b"", finalized=True):
        return native.diagnostic_payload(raw, stderr=stderr, evidence_kind="SYNTHETIC", finalized=finalized)

    def parse(self, payload):
        return native.parse_diagnostics(payload, evidence_kind="SYNTHETIC")

    def test_empty_finalized_available_streams_establish_genuine_zero(self):
        self.assertEqual(self.parse(self.payload()),
                         (dict.fromkeys(native.COUNTS, 0), "COMPLETE"))

    def test_error_log_without_stderr_does_not_cover_early_output(self):
        payload = native.diagnostic_payload(b"", evidence_kind="SYNTHETIC", finalized=True)
        self.assertEqual(self.parse(payload), (dict.fromkeys(native.COUNTS), "INCOMPLETE"))

    def test_missing_or_unfinalized_streams_do_not_invent_zero(self):
        for raw, stderr, finalized, coverage in (
            (None, None, True, "UNAVAILABLE"), (None, b"", True, "INCOMPLETE"),
            (b"", b"", False, "INCOMPLETE"),
        ):
            with self.subTest(raw=raw, stderr=stderr, finalized=finalized):
                self.assertEqual(self.parse(self.payload(raw, stderr, finalized)),
                                 (dict.fromkeys(native.COUNTS), coverage))

    def test_benign_warning_is_not_a_simulator_error(self):
        self.assertEqual(self.parse(self.payload(BENIGN, BENIGN)),
                         (dict.fromkeys(native.COUNTS, 0), "COMPLETE"))

    def test_unknown_warning_is_not_error_and_prevents_clean_coverage(self):
        counts, coverage = self.parse(self.payload(b"Warning: unreviewed native warning.\n"))
        self.assertIsNone(counts["simulator_errors"])
        self.assertEqual(coverage, "INCOMPLETE")

    def test_explicit_collision_and_route_error_are_supported(self):
        counts, coverage = self.parse(self.payload(COLLISION + ERROR, COLLISION + ERROR))
        self.assertEqual(counts, {"collisions": 1, "invalid_routes": 1, "simulator_errors": 1})
        self.assertEqual(coverage, "COMPLETE")

    def test_stream_duplicates_are_not_added_as_unique_event_counts(self):
        counts, _ = self.parse(self.payload(ERROR + ERROR, ERROR))
        self.assertEqual(counts["simulator_errors"], 2)

    def test_positive_survives_missing_other_stream_and_unknown_line(self):
        counts, coverage = self.parse(self.payload(COLLISION + b"unknown\n", None))
        self.assertEqual(counts, {"collisions": 1, "invalid_routes": None, "simulator_errors": None})
        self.assertEqual(coverage, "INCOMPLETE")

    def test_unterminated_error_is_positive_but_not_complete(self):
        counts, coverage = self.parse(self.payload(ERROR.rstrip(b"\n")))
        self.assertEqual(counts["simulator_errors"], 1)
        self.assertEqual(coverage, "INCOMPLETE")

    def test_invalid_utf8_is_preserved_and_cannot_erase_prior_positive(self):
        raw = ERROR + b"\xff\n"
        payload = self.payload(raw)
        self.assertEqual(base64.b64decode(payload["streams"]["error_log"]["data"]), raw)
        counts, coverage = self.parse(payload)
        self.assertEqual(counts["simulator_errors"], 1)
        self.assertEqual(coverage, "INCOMPLETE")

    def test_positive_in_other_stream_survives_undecodable_first_stream(self):
        counts, coverage = self.parse(self.payload(b"\xff\n", COLLISION))
        self.assertEqual(counts["collisions"], 1)
        self.assertEqual(coverage, "INCOMPLETE")

    def test_collision_word_without_actual_event_pattern_does_not_invent_positive(self):
        counts, coverage = self.parse(self.payload(b"Warning: collision option configuration.\n"))
        self.assertIsNone(counts["collisions"])
        self.assertEqual(coverage, "INCOMPLETE")

    def test_known_collision_kinds_and_teleport_prefix(self):
        for kind in (b"frontal collision", b"side collision", b"junction collision"):
            with self.subTest(kind=kind):
                raw = COLLISION.replace(b"collision with", kind + b" with").replace(b"Vehicle", b"Teleporting vehicle", 1)
                self.assertEqual(self.parse(self.payload(raw))[0]["collisions"], 1)

    def test_live_origin_remains_live_and_cannot_be_read_as_synthetic(self):
        payload = native.diagnostic_payload(b"", stderr=b"", evidence_kind="LIVE", finalized=True)
        self.assertEqual(native.parse_diagnostics(payload, evidence_kind="LIVE")[1], "COMPLETE")
        with self.assertRaisesRegex(ValueError, "NATIVE_DIAGNOSTIC_ORIGIN"):
            self.parse(payload)

    def test_schema_mapping_version_and_unknown_fields_are_closed(self):
        for key, value in (("mapping", "other"), ("version", 2), ("version", True),
                           ("finalized", 1), ("extra", "field"), ("streams", {})):
            with self.subTest(key=key, value=value):
                payload = self.payload(); payload[key] = value
                with self.assertRaises(ValueError):
                    self.parse(payload)

    def test_malformed_stream_encoding_is_rejected(self):
        for value in ({"encoding": "utf8", "data": "text"},
                      {"encoding": "base64", "data": "%%%"},
                      {"encoding": "base64", "data": "YQ==\n"},
                      {"encoding": "base64", "data": "YQ==", "extra": True}):
            with self.subTest(value=value):
                payload = self.payload(); payload["streams"]["error_log"] = value
                with self.assertRaises(ValueError):
                    self.parse(payload)

    def test_payload_argument_types_are_exact(self):
        for options in ({"raw": "text"}, {"evidence_kind": "OTHER"},
                        {"finalized": 1}, {"stderr": bytearray()}):
            with self.subTest(options=options):
                arguments = dict(raw=b"", evidence_kind="SYNTHETIC", finalized=True)
                arguments.update(options)
                with self.assertRaises(ValueError):
                    native.diagnostic_payload(**arguments)

    def test_raw_permissions_are_not_mutated(self):
        allowed = sorted(native.VEHICLE_CLASSES - {"passenger"}); disallowed = ["passenger"]
        before = copy.deepcopy((allowed, disallowed))
        self.assertEqual(native.normalize_permissions(allowed, disallowed),
                         {"allowed": [], "disallowed": ["passenger"]})
        self.assertEqual((allowed, disallowed), before)

    def test_unrestricted_and_all_denied_are_distinct(self):
        self.assertEqual(native.normalize_permissions((), ()), {"allowed": [], "disallowed": []})
        self.assertEqual(native.normalize_permissions([], sorted(native.VEHICLE_CLASSES)),
                         {"allowed": [], "disallowed": sorted(native.VEHICLE_CLASSES)})

    def test_full_explicit_native_allow_list_has_unrestricted_canonical_form(self):
        self.assertEqual(native.normalize_permissions(sorted(native.VEHICLE_CLASSES), []),
                         {"allowed": [], "disallowed": []})

    def test_incomplete_or_unknown_permission_views_fail_closed(self):
        for allowed, disallowed in (([], ["passenger"]), (["passenger"], []),
                                    (None, []), (["ignoring"], []), (["all"], []),
                                    (["bus", "bus"], []), (["public_transport"], [])):
            with self.subTest(allowed=allowed, disallowed=disallowed):
                with self.assertRaises(ValueError):
                    native.normalize_permissions(allowed, disallowed)


if __name__ == "__main__":
    unittest.main()
