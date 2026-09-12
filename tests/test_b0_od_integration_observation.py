"""Actual observer/accounting orchestration with hand-computable fake inputs."""
import copy
from b0_od_integration_fixtures import REFERENCES, observe
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.b0.od_integration_v1 import integration as core, qualification as q, evidence
from b0_od_integration_fixtures import FakeBackend, good_record

WORKSPACE=evidence.WORKSPACE
OUTPUTS=WORKSPACE/'synthetic-test-outputs'


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        cls.binding=core.build_binding(core.repository_root(),20260904,'C1')
        cls.n0=good_record(condition_label='N0')
        cls.d0=good_record(condition_label='D0')

    def test_all_twelve_inputs_exact_generated_readback_and_pair_identity(self):
        from b0_od_v2_fixtures import FROZEN_INPUT_SHA256
        with tempfile.TemporaryDirectory(dir=OUTPUTS) as directory:
            for seed in core.contract()['calibration_seeds']:
                for level in core.contract()['selection_rule']['sequence']:
                    with self.subTest(seed=seed,level=level):
                        b=core.build_binding(core.repository_root(),seed,level)
                        self.assertEqual(b['route_file_sha256'],FROZEN_INPUT_SHA256[f'{seed}-{level}'])
                        self.assertEqual(len(core.scheduled(b)),540)
                        receipt=core.materialize_input(b,Path(directory))
                        self.assertEqual(receipt['sha256'],b['route_file_sha256'])
                        self.assertNotEqual(b['implementation_repository_commit'],b['source_repository_historical_commit'])

    def test_invalid_input_seed_level_and_mutated_binding(self):
        for seed,level in [(True,'C1'),(20260907,'C1'),(20260904,'C5')]:
            with self.subTest(seed=seed,level=level),self.assertRaises((ValueError,KeyError)):
                core.build_binding(core.repository_root(),seed,level)
        b=copy.deepcopy(self.binding); b['scientific_configuration']['h_pilot_seconds']=1
        with self.assertRaises(ValueError): core.checked_binding(b)

    def test_backend_loaded_input_mismatch_stops_before_first_advance(self):
        backend=FakeBackend(self.binding,wrong_loaded_input=True)
        r=observe(self.binding,'N0','SYNTHETIC-WRONG-INPUT',backend,backend)
        self.assertFalse(any(event[0]=='advance' for event in backend.log))
        self.assertTrue(backend.closed)
        self.assertEqual(r['failure']['kind'],'INTEGRITY')
        self.assertFalse(q.qualify_pair(r,self.d0, references=REFERENCES)['qualification_evaluated'])

    def test_falsy_malformed_status_fields_never_mean_success(self):
        for key,value in [('failure',False),('failure',''),('cleanup_failures',0),
                          ('cleanup_failures',False),('output_finalized',1),('lifecycle',{})]:
            with self.subTest(key=key,value=value):
                r=copy.deepcopy(self.n0); r[key]=value
                with self.assertRaises(ValueError): core.validate_run(r, references=REFERENCES)
                self.assertFalse(q.qualify_pair(r,self.d0, references=REFERENCES)['qualification_evaluated'])

    def test_exact_callback_order_full_horizon_and_boundaries(self):
        backend=FakeBackend(self.binding,'D0'); calls=[]
        original=core.adapter.make_cutoff_observer
        def observer_factory(**kwargs):
            observer=original(**kwargs); before=observer.before_step; after=observer.after_step
            def before_step(view,t):
                calls.append(('before',t,backend.lane.getDisallowed('A1B1_0'))); return before(view,t)
            def after_step(view,start,end):
                calls.append(('after',start,end)); return after(view,start,end)
            observer.before_step=before_step; observer.after_step=after_step
            return observer
        with patch.object(core.adapter,'make_cutoff_observer',observer_factory):
            r=observe(self.binding,'D0','SYNTHETIC-ORDER',backend,backend)
        self.assertEqual(len(calls),3000)
        for start in range(1500):
            self.assertEqual(calls[2*start][:2],('before',start))
            self.assertEqual(calls[2*start+1],('after',start,start+1))
        self.assertEqual(calls[598],('before',299,[]))
        self.assertEqual(calls[600],('before',300,['passenger']))
        self.assertEqual(calls[1200],('before',600,[]))
        self.assertEqual(backend.log[-2:],[('close',1500),('output',1500)])
        self.assertEqual(core.validate_run(r, references=REFERENCES)['measurement_status'],'VALID')

    def test_n0_full_horizon_has_no_permission_mutation(self):
        backend=FakeBackend(self.binding,'N0')
        r=observe(self.binding,'N0','SYNTHETIC-NORMAL',backend,backend)
        self.assertEqual(r['lifecycle'],[])
        self.assertFalse(any(x[0] in ('allowed','disallowed') for x in backend.log))
        self.assertEqual(r['observations']['final_time_seconds'],1500)
        self.assertEqual(r['observations']['queue_trace'][-1],[1500,0])

    def test_hand_computable_complete_pair(self):
        for r,mean,queue in ((self.n0,101,540),(self.d0,102,567)):
            m=core.validate_run(r, references=REFERENCES)
            self.assertEqual(m['measurement_status'],'VALID')
            self.assertEqual(m['metrics']['arrived_trips'],540)
            self.assertEqual(m['metrics']['restricted_mean_trip_time_seconds'],mean)
            self.assertEqual(m['metrics']['cumulative_queue_vehicle_seconds'],queue)
        self.assertEqual(q.qualify_pair(self.n0,self.d0, references=REFERENCES)['pair_status'],'QUALIFIES')

    def test_cutoff_populations_captured_before_cleanup(self):
        r=good_record(active_count=2,pending_count=3)
        m=core.validate_run(r, references=REFERENCES)
        self.assertEqual(m['measurement_status'],'VALID')
        self.assertEqual(m['metrics']['arrived_trips'],535)
        self.assertEqual(m['metrics']['active_trips_at_cutoff'],2)
        self.assertEqual(m['metrics']['not_departed_trips_at_cutoff'],3)
        for row in m['ledger'].values():
            if row['terminal_category'] in ('active','not_departed'):
                self.assertEqual(row['restricted_trip_time_seconds'],1500-row['scheduled_departure_seconds'])

    def test_censored_visits_remain_open_not_completed_duration(self):
        r=good_record(condition_label='D0',censored_exposed_count=1)
        self.assertEqual(core.validate_run(r, references=REFERENCES)['measurement_status'],'VALID')
        visits=[v for row in r['summary']['per_vehicle'].values() for v in row['edge_visits'] if v['visit_status']=='RIGHT_CENSORED_AT_CUTOFF']
        self.assertEqual(len(visits),1)
        self.assertIsNone(visits[0]['exit_observed_at_seconds'])
        self.assertIsNone(visits[0]['observed_edge_time_seconds'])

    def test_exact_waiting_overflow_counterexample_crosses_real_boundary(self):
        r=good_record(waiting_overflow=True,queue_budget=0)
        m=core.validate_run(r, references=REFERENCES)
        self.assertEqual(m['measurement_status'],'INTEGRITY_FAILURE')
        self.assertIn('AGGREGATE_NATIVE_WAITING_NONFINITE',m['integrity_errors'])
        self.assertIsNone(m['metrics']['sumo_tripinfo_waiting_time_seconds_total'])
        self.assertEqual(len(m['ledger']),540)
        self.assertTrue(all(row['restricted_trip_time_seconds']==101 for row in m['ledger'].values()))
        decision=q.qualify_pair(r,self.d0, references=REFERENCES)
        self.assertFalse(decision['qualification_evaluated'])
        self.assertEqual(decision['stop_status'],'FAIL')

    def test_truncated_tripinfo_is_deficient_not_nonqualification(self):
        r=good_record(missing_output=True)
        self.assertEqual(core.validate_run(r, references=REFERENCES)['measurement_status'],'EVIDENCE_DEFICIENCY')
        decision=q.qualify_pair(r,self.d0, references=REFERENCES)
        self.assertEqual(decision['pair_status'],'EVIDENCE_DEFICIENCY')
        self.assertFalse(decision['qualification_evaluated'])

    def test_missing_step_and_duplicate_step_are_invalid(self):
        r=good_record(jump_step=100)
        self.assertEqual(r['failure']['stage'],'OBSERVATION')
        self.assertEqual(core.validate_run(r, references=REFERENCES)['measurement_status'],'INTEGRITY_FAILURE')
        backend=FakeBackend(self.binding); backend.simulationStep=lambda:None
        r=observe(self.binding,'N0','SYNTHETIC-DUPLICATE',backend,backend)
        self.assertTrue(backend.closed)
        self.assertEqual(core.validate_run(r, references=REFERENCES)['measurement_status'],'INTEGRITY_FAILURE')

    def test_partial_permission_failure_still_restores_and_closes(self):
        backend=FakeBackend(self.binding,'D0',fail_permission=True,close_failure=True)
        r=observe(self.binding,'D0','SYNTHETIC-FAILURE',backend,backend)
        self.assertEqual(r['failure'],{'kind':'TECHNICAL','stage':'PERMISSION_OPERATION','code':'OSError'})
        self.assertEqual(backend.permissions['A1B1_0'],{'allowed':[],'disallowed':[]})
        self.assertTrue(backend.closed)
        self.assertEqual(r['cleanup_failures'][0]['stage'],'CONNECTION_CLOSE')

    def test_cleanup_failure_cannot_turn_valid_accounting_into_success(self):
        r=good_record(close_failure=True)
        self.assertEqual(r['measurement']['measurement_status'],'VALID')
        self.assertEqual(core.validate_run(r, references=REFERENCES)['measurement_status'],'EVIDENCE_DEFICIENCY')
        self.assertFalse(q.qualify_pair(r,self.d0, references=REFERENCES)['qualification_evaluated'])

    def test_setup_failure_closes_supplied_connection(self):
        backend=FakeBackend(self.binding)
        class Broken:
            @property
            def simulation(self): raise OSError('synthetic inaccessible domain')
            def close(self,wait=True): backend.close(wait)
        r=observe(self.binding,'N0','SYNTHETIC-SETUP',Broken(),backend)
        self.assertTrue(backend.closed)
        self.assertEqual(r['failure']['kind'],'TECHNICAL')

    def test_unexpected_setters_rejected_by_read_only_surface(self):
        backend=FakeBackend(self.binding); view=core.ReadOnlyConnection(backend)
        for domain,name in [('vehicle','setRoute'),('vehicle','setSpeed'),('vehicle','changeLane'),('lane','setDisallowed')]:
            with self.subTest(name=name),self.assertRaises(ValueError): getattr(getattr(view,domain),name)

    def test_control_mutation_and_collision_evidence_fail_integrity(self):
        for options in ({'controls_changed_at':10},{'collision_at':20},{'restricted_entry':True,'condition_label':'D0'}):
            with self.subTest(options=options):
                r=good_record(**options)
                self.assertEqual(core.validate_run(r, references=REFERENCES)['measurement_status'],'INTEGRITY_FAILURE')

    def test_changed_measurement_label_or_metric_is_not_trusted(self):
        for key,value in [('restricted_mean_trip_time_seconds',0),('cumulative_queue_vehicle_seconds',999)]:
            with self.subTest(key=key):
                r=copy.deepcopy(self.n0); r['measurement']['metrics'][key]=value
                self.assertEqual(core.validate_run(r, references=REFERENCES)['measurement_status'],'INTEGRITY_FAILURE')

    def test_exposure_summary_cannot_be_substituted_for_observed_events(self):
        r=copy.deepcopy(self.d0)
        v=r['summary']['unique_edge_entries']['during'][0]
        r['summary']['per_vehicle'][v]['edge_visits'][0]['observed_edge_time_seconds']+=1
        self.assertEqual(core.validate_run(r, references=REFERENCES)['measurement_status'],'INTEGRITY_FAILURE')

    def test_changed_preactivation_occupancy_and_missing_samples_rejected(self):
        for kind in ('occupancy','sample','callback'):
            with self.subTest(kind=kind):
                r=copy.deepcopy(self.n0)
                if kind=='occupancy': r['preactivation']['lane_occupancy']['A1B1_0']+=1
                elif kind=='sample': r['controls']['steps'][0].pop('monitor_states')
                else: r['observations']['step_intervals'].pop()
                self.assertEqual(core.validate_run(r, references=REFERENCES)['measurement_status'],'INTEGRITY_FAILURE')

    def test_synthetic_end_to_end_actual_components_and_independent_readback(self):
        session=q.SelectionSession(references=REFERENCES)
        pairs=[]
        with tempfile.TemporaryDirectory(dir=OUTPUTS) as directory:
            for seed in core.contract()['calibration_seeds']:
                b=core.build_binding(core.repository_root(),seed,'C1')
                core.materialize_input(b,Path(directory))
                pairs.append((good_record(seed=seed),good_record(seed=seed,condition_label='D0')))
            self.assertEqual(session.add_level('C1',pairs)['status'],'PROVISIONAL')
            self.assertEqual(session.add_repeats(good_record(condition_label='N0-CAL-R'),good_record(condition_label='D0-CAL-R'))['status'],'PENDING_READBACK')
            payload={**evidence.PAYLOAD_BASE,'record_kind':'SELECTION','record':session.to_record()}
            receipt=evidence.write_once(Path(directory),'synthetic-selection.json',payload, references=REFERENCES)
            self.assertEqual(evidence.readback(receipt, references=REFERENCES),payload)
            # Independent JSON decoder and hash, not the writer's serializer oracle.
            raw=(Path(directory)/'synthetic-selection.json').read_bytes()
            import hashlib
            self.assertEqual(hashlib.sha256(raw).hexdigest(),receipt['sha256'])
            self.assertEqual(json.loads(raw)['record']['decision']['status'],'PENDING_READBACK')
            final=session.finalize(receipt)
            self.assertEqual(final['status'],'PASS')
            self.assertEqual(final['synthetic_selected_level'],'C1')
            self.assertIsNone(final['selected_calibrated_od_concentration'])
            self.assertIs(final['ready_to_run'],False)


if __name__=='__main__': unittest.main()
