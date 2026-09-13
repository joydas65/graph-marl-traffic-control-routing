"""Preserve real evidence-deficient outcomes through the worker handoff.

The production worker, collector, assessment, writer and readback run against
existing synthetic fixtures. Supervisor process/IPC/wait observations are
injected operations only; no native process, socket, wait or signal is used.
"""

import copy
from dataclasses import asdict
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.b0.od_integration_v1 import evidence as io, finalization as final
from scripts.b0.od_integration_v1 import integration as core
from scripts.b0.od_integration_v1 import native_supervisor as supervisor
from scripts.b0.od_integration_v1 import native_worker as worker
import b0_od_integration_fixtures as core_fixtures
import test_b0_od_integration_finalization as final_fixtures
import test_b0_od_integration_live_binding as binding_fixtures
import test_b0_od_integration_terminal_cleanup as cleanup_fixtures


class InconclusiveHandoffTests(unittest.TestCase):
    def execute(self, *, outcome='warning', cleanup_context=True, child_identity=True):
        options = {
            'warning': {'stderr': b'Warning: Unmapped synthetic warning.\n'},
            'missing': {'missing': True},
            'valid': {},
            'fail': {'stderr': b'Error: Synthetic independent contradiction.\n',
                     'missing': True},
        }
        fixture = binding_fixtures.Fixture(**options[outcome])
        self.addCleanup(fixture.close)
        if child_identity:
            fixture.process.pid = cleanup_fixtures.CHILD_PID
        context = (dict(cleanup_token=cleanup_fixtures.TOKEN,
                        worker_pid=cleanup_fixtures.WORKER_PID)
                   if cleanup_context else {})
        events = []
        done = worker.execute_worker(fixture.plan, binding_fixtures.BOUNDS,
            events.append, process_factory=fixture.process_factory,
            transport_factory=fixture.transport_factory, owned_scope_verified=True,
            **context)
        self.assertEqual(len(fixture.process.waits), 1)
        self.assertEqual(len([call for call in fixture.calls if call[0] == 'start']), 1)
        return fixture, done, events

    def read_actual(self, fixture, done):
        references = final.ReferenceContext(final.ReferenceGrant(**grant)
                                             for grant in done['grants'])
        payload = io.readback(done['receipt'], references=references)
        self.assertEqual(worker.validate_worker_result(fixture.plan, done), payload)
        run = payload['record'] if payload['record_kind'] == 'RUN' else payload['record']['run']
        assessment = core.assess_run(run, references=references)
        self.assertEqual(done['assessment'], dict(
            measurement_status=assessment['measurement']['measurement_status'],
            stop_status=assessment['stop_status'], reason_codes=assessment['reason_codes']))
        self.assertFalse(assessment['qualification_evaluated'])
        self.assertFalse(payload['ready_to_run'])
        self.assertEqual(payload['evidence_kind'], 'SYNTHETIC')
        self.assertEqual(done['receipt']['persistence_status'], 'VERIFIED')
        return payload, run, assessment

    def assert_inconclusive(self, fixture, done, events):
        payload, run, assessed = self.read_actual(fixture, done)
        self.assertEqual(run['finalization']['collection_state'], 'COMPLETED')
        self.assertIsNone(run['operational_abort'])
        self.assertEqual(assessed['measurement']['measurement_status'], 'EVIDENCE_DEFICIENCY')
        self.assertEqual(assessed['stop_status'], 'INCONCLUSIVE')
        self.assertEqual(assessed['measurement']['integrity_errors'], [])
        self.assertTrue(assessed['measurement']['evidence_deficiencies'])
        self.assertEqual(payload['record_kind'], 'FAILURE')
        self.assertEqual(payload['record']['experiment_status'], 'INCONCLUSIVE')
        self.assertEqual(payload['record']['measurement_status'], 'EVIDENCE_DEFICIENCY')
        expected = run['failure'] or dict(kind='EVIDENCE', stage='ASSESSMENT',
                                         code='WORKER_RUN_ASSESSMENT_STOP')
        self.assertEqual(done['first_failure'], expected)
        self.assertEqual([event['failure'] for event in events
                          if event['type'] == 'FIRST_FAILURE'], [expected])
        self.assertTrue(done['child_reaped'])
        return payload, run, assessed

    def coordinate(self, fixture, done, events, *, terminal_observation=True):
        def actual_done(message):
            message.clear()
            message.update(type='DONE', **copy.deepcopy(done))
        observations = ([dict(state='NO_STATUS'), cleanup_fixtures.terminal()]
                        if terminal_observation else [dict(state='NO_STATUS')])
        ops = cleanup_fixtures.Operations(fixture.plan, mutate=actual_done,
            prior_failure=done['first_failure'], observations=observations,
            child_reported=any(event['type'] == 'CHILD' for event in events))
        with patch.object(supervisor.os, 'urandom',
                          return_value=bytes.fromhex(cleanup_fixtures.TOKEN)):
            result = supervisor.supervise(fixture.plan, cleanup_fixtures.BOUNDS,
                                           ops=ops, clock=ops.clock)
        self.assertEqual(result['worker_result'], done)
        self.assertTrue(result['normal_finalization'])
        self.assertTrue(result['worker_reap_within_deadline'])
        self.assertTrue(result['scope_signalling_disabled'])
        signals = [entry[1] for entry in ops.log if entry[0] in ('group', 'worker')]
        if done['first_failure'] is not None:
            self.assertEqual(result['status'], 'COMPLETED_WITH_FAILURE')
            self.assertEqual(result['first_failure']['worker_failure'], done['first_failure'])
        return result, signals

    def test_actual_completed_warning_and_missing_output_are_inconclusive(self):
        for outcome in ('warning', 'missing'):
            with self.subTest(outcome=outcome):
                fixture, done, events = self.execute(outcome=outcome)
                _, run, _ = self.assert_inconclusive(fixture, done, events)
                if outcome == 'warning':
                    self.assertIsNone(run['finalization']['diagnostics']['counts']['simulator_errors'])
                else:
                    self.assertEqual(run['finalization']['tripinfo']['availability'], 'MISSING')
                    self.assertEqual(done['first_failure'], dict(kind='EVIDENCE',
                        stage='TRIPINFO_FINALIZATION', code='OUTPUT_IDENTITY_UNVERIFIED'))

    def test_actual_inconclusive_wait_handoff_allows_only_ownership_cleanup(self):
        for outcome in ('warning', 'missing'):
            with self.subTest(outcome=outcome):
                fixture, done, events = self.execute(outcome=outcome)
                original = copy.deepcopy(done)
                worker._handoff_references(fixture.plan, done)
                worker.validate_cleanup_handoff(fixture.plan, done,
                    worker_pid=cleanup_fixtures.WORKER_PID,
                    child_pid=cleanup_fixtures.CHILD_PID, token=cleanup_fixtures.TOKEN)
                self.assertEqual(done['cleanup_handoff']['child_wait'], dict(
                    pid=cleanup_fixtures.CHILD_PID, exit_code=0, wait_returned=True))
                result, signals = self.coordinate(fixture, done, events)
                self.assertTrue(result['terminal_cleanup'])
                self.assertEqual(signals, ['TERM'])
                self.assertEqual(result['child_scope'], 'REPORTED_CHILD_REAPED_AND_WORKER_REAPED')
                self.assert_inconclusive(fixture, result['worker_result'], events)
                self.assertEqual(done, original)

    def test_inconclusive_without_closure_retains_ordinary_readback_not_shortcut(self):
        for cleanup_context, child_identity in ((False, True), (True, False)):
            with self.subTest(cleanup_context=cleanup_context, child_identity=child_identity):
                fixture, done, events = self.execute(cleanup_context=cleanup_context,
                                                      child_identity=child_identity)
                self.assertIsNone(done['cleanup_handoff'])
                worker._handoff_references(fixture.plan, done)
                with self.assertRaisesRegex(ValueError, '^CLEANUP_HANDOFF_SCHEMA$'):
                    worker.validate_cleanup_handoff(fixture.plan, done,
                        worker_pid=cleanup_fixtures.WORKER_PID,
                        child_pid=cleanup_fixtures.CHILD_PID, token=cleanup_fixtures.TOKEN)
                result, signals = self.coordinate(fixture, done, events)
                self.assertFalse(result['terminal_cleanup'])
                self.assertEqual(signals, ['TERM', 'KILL'])
                self.assertEqual(result['child_scope'], 'UNRESOLVED')
                self.assert_inconclusive(fixture, result['worker_result'], events)

    def test_inconclusive_wait_handoff_without_terminal_proof_keeps_escalation(self):
        fixture, done, events = self.execute()
        result, signals = self.coordinate(fixture, done, events, terminal_observation=False)
        self.assertFalse(result['terminal_cleanup'])
        self.assertEqual(signals, ['TERM', 'KILL'])
        self.assert_inconclusive(fixture, result['worker_result'], events)

    def test_actual_valid_and_integrity_failure_remain_supported(self):
        for outcome, status in (('valid', None), ('fail', 'FAIL')):
            with self.subTest(outcome=outcome):
                fixture, done, events = self.execute(outcome=outcome)
                result, signals = self.coordinate(fixture, done, events)
                self.assertTrue(result['terminal_cleanup'])
                self.assertEqual(signals, ['TERM'])
                payload, run, assessed = self.read_actual(fixture, result['worker_result'])
                self.assertEqual(assessed['stop_status'], status)
                if status is None:
                    self.assertEqual(assessed['measurement']['measurement_status'], 'VALID')
                    self.assertEqual(payload['record_kind'], 'RUN')
                    self.assertEqual(result['status'], 'WORKER_COMPLETED')
                else:
                    self.assertEqual(assessed['measurement']['measurement_status'], 'INTEGRITY_FAILURE')
                    self.assertIn('UNEXPLAINED_SIMULATOR_ERROR', assessed['reason_codes'])
                    self.assertEqual(run['finalization']['tripinfo']['availability'], 'MISSING')
                    self.assertEqual(payload['record']['experiment_status'], 'FAIL')

    def test_existing_actual_blocked_assessment_and_writer_pass_handoff_schema(self):
        # Existing generic collector proves a supported unchanged-clock abort.
        # Native diagnostic coverage is deliberately NOT broadened to claim it.
        run, backend = final_fixtures.terminal_run('clean', fail_step=50)
        references = core_fixtures.REFERENCES
        assessed = core.assess_run(run, references=references)
        self.assertEqual(assessed['stop_status'], 'BLOCKED')
        self.assertFalse(assessed['qualification_evaluated'])
        self.assertNotEqual(assessed['measurement']['measurement_status'], 'VALID')
        output = run['finalization']['output_identity']['output_directory']
        plan = SimpleNamespace(run_id=run['run_id'], condition=run['condition_label'],
            binding=run['binding'], output_directory=output, evidence_kind=run['evidence_kind'])
        payload = dict(io.PAYLOAD_BASE, record_kind='FAILURE', record=dict(
            failure_code='WORKER_RUN_ASSESSMENT_STOP', experiment_status='BLOCKED',
            measurement_status=assessed['measurement']['measurement_status'],
            run=run, raw_evidence=None))
        receipt = io.write_once(backend.output_path, worker.RESULT_NAME, payload,
                                references=references)
        grants = [asdict(grant) for grant in references._grants
                  if (grant.run_id, grant.output_directory) == (run['run_id'], output)]
        done = dict(receipt=receipt, grants=grants, child_reaped=True,
            assessment=dict(measurement_status=assessed['measurement']['measurement_status'],
                            stop_status=assessed['stop_status'], reason_codes=assessed['reason_codes']),
            first_failure=run['failure'], cleanup_handoff=None)
        checked = worker._handoff_references(plan, done)
        self.assertEqual(io.readback(receipt, references=checked), payload)

    def test_unknown_and_malformed_assessment_statuses_remain_rejected(self):
        fixture, done, _ = self.execute()
        for field, values in (
            ('stop_status', ('PASS', 'inconclusive', '', True, 0, [], {})),
            ('measurement_status', ('INCONCLUSIVE', 'INVALID', None, True, [], {})),
            ('reason_codes', (None, 'not-a-list', [7], [None])),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    changed = copy.deepcopy(done)
                    changed['assessment'][field] = value
                    for validate in (lambda: worker._handoff_references(fixture.plan, changed),
                                     lambda: worker.validate_cleanup_handoff(fixture.plan, changed,
                                         worker_pid=cleanup_fixtures.WORKER_PID,
                                         child_pid=cleanup_fixtures.CHILD_PID,
                                         token=cleanup_fixtures.TOKEN)):
                        with self.assertRaisesRegex(ValueError, '^WORKER_HANDOFF_ASSESSMENT_SCHEMA$'):
                            validate()

    def test_supported_but_disagreeing_summary_still_fails_independent_readback(self):
        fixture, done, events = self.execute()
        self.assert_inconclusive(fixture, done, events)
        original = copy.deepcopy(done)
        for field, value in (('stop_status', None), ('stop_status', 'FAIL'),
                             ('stop_status', 'BLOCKED'), ('measurement_status', 'VALID'),
                             ('reason_codes', ['SYNTHETIC_UNSUPPORTED_SUMMARY'])):
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(done)
                changed['assessment'][field] = value
                worker._handoff_references(fixture.plan, changed)
                worker.validate_cleanup_handoff(fixture.plan, changed,
                    worker_pid=cleanup_fixtures.WORKER_PID,
                    child_pid=cleanup_fixtures.CHILD_PID, token=cleanup_fixtures.TOKEN)
                with self.assertRaisesRegex(ValueError, '^WORKER_ASSESSMENT_MISMATCH$'):
                    worker.validate_worker_result(fixture.plan, changed)
        self.assertEqual(done, original)
        self.assert_inconclusive(fixture, done, events)


if __name__ == '__main__':
    unittest.main()
