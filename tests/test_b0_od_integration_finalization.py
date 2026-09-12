"""Schema-2 acceptance through actual core/Adapter/writer with synthetic bytes.

No process is launched: process observations and the closed diagnostic event
format are explicitly synthetic. Original characterization remains untouched.
"""
import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from scripts.b0.od_integration_v1 import integration as core, finalization as f, evidence, qualification as q
from b0_od_integration_fixtures import FakeBackend, REFERENCES, observe
from test_b0_od_integration_qualification import record, pairs


def artifact(run, key):
    output = run['finalization']['output_identity']
    ref = output['artifacts'][key]
    return evidence.WORKSPACE / output['output_directory'] / ref['name']


def replace_bytes(result, directory, key, raw):
    ref = result['output_identity']['artifacts'][key]
    (directory / ref['name']).write_bytes(raw)
    ref.update(byte_count=len(raw), sha256=hashlib.sha256(raw).hexdigest())


class TerminalBackend(FakeBackend):
    def __init__(self, binding, condition_label='N0', *, mode='clean', **options):
        self.mode = mode
        self.expected_snapshot = (dict(byte_count=3, sha256=hashlib.sha256(b'old').hexdigest())
                                  if mode == 'content' else None)
        super().__init__(binding, condition_label, **options)

    def tripinfo_bytes(self):
        raw = super().tripinfo_bytes()
        if self.mode in ('truncated', 'structure', 'missing_id', 'empty_id', 'duplicate_id', 'missing_row'):
            if self.mode == 'truncated': return raw[:-15]
            if self.mode == 'structure': return b'<wrong><tripinfo/></wrong>'
            root = ET.fromstring(raw)
            if self.mode == 'missing_id': del root[0].attrib['id']
            if self.mode == 'empty_id': root[0].set('id', '')
            if self.mode == 'duplicate_id': root[1].set('id', root[0].get('id'))
            if self.mode == 'missing_row': root.remove(root[0])
            return ET.tostring(root)
        return raw

    def finalize_output(self, result):
        if self.mode == 'unavailable':
            self.log.append(('output', self.time))
            return
        super().finalize_output(result)
        if self.mode in ('collision', 'collision_missing', 'collision_exception', 'unknown_positive', 'warning', 'unknown', 'route', 'simulator_error'):
            events = (['warning'] if self.mode == 'warning' else ['unknown'] if self.mode == 'unknown' else
                      ['invalid_routes'] if self.mode == 'route' else ['simulator_errors'] if self.mode == 'simulator_error' else
                      ['collisions', 'unknown'] if self.mode == 'unknown_positive' else ['collisions'])
            data = dict(mapping=f.SYNTHETIC_MAPPING, evidence_kind='SYNTHETIC', complete=True, events=events)
            replace_bytes(result, self.output_path, 'diagnostics', evidence._encode(data))
            result['diagnostics'] = dict(coverage='INCOMPLETE' if 'unknown' in events else 'COMPLETE',
                                       counts={k:events.count(k) for k in f.COUNTS})
        if self.mode == 'collision_missing':
            (self.output_path / 'retained.xml').unlink()
            result['output_identity']['artifacts']['tripinfo'] = None
            result['tripinfo']['availability'] = 'MISSING'
        if self.mode in ('object', 'content', 'nonzero', 'not_exited'):
            observations = result['output_identity']['output_observations']
            if self.mode == 'object':
                original = self.output_path / 'original.xml'
                original.replace(self.output_path / 'prior-original.xml')
                original.write_bytes((self.output_path / 'retained.xml').read_bytes())
                stat = original.stat()
                observations['observed'].update(device=stat.st_dev, inode=stat.st_ino)
            if self.mode in ('object', 'content'): result['tripinfo']['identity'] = 'CONTRADICTED'
            if self.mode == 'nonzero': result['process']['exit_code'] = -9
            if self.mode == 'not_exited': result['process'] = dict(state='NOT_EXITED', exit_code=None)
            capture = dict(run_id=self.run_id, condition_label=self.capture_condition,
                binding_sha256=core.digest(self.binding), process=result['process'], output_observations=observations)
            replace_bytes(result, self.output_path, 'capture', evidence._encode(capture))
        if self.mode == 'collision_exception':
            result['findings'].append(dict(code='COLLISION_OBSERVED', evidence_keys=['diagnostics']))
        if self.mode == 'malformed_exception':
            result['findings'].append(dict(code=[], evidence_keys=[]))
        if self.mode in ('exception', 'collision_exception', 'malformed_exception'):
            self.retained_result = result
            raise RuntimeError('synthetic acquisition interruption, not a severity code')
        if self.mode == 'forged_owner_fields':
            result['collection_state'] = 'INTERRUPTED'
            result['tripinfo']['parsing'] = 'UNPARSEABLE'


def terminal_run(mode='clean', condition='N0', **options):
    binding = core.build_binding(core.repository_root(), options.pop('seed', 20260904), 'C1')
    backend = TerminalBackend(binding, condition, mode=mode, **options)
    run = observe(binding, condition, 'SYNTHETIC-TERMINAL-'+condition, backend, backend)
    return run, backend


def assess(run):
    return core.assess_run(run, references=REFERENCES)


def envelope(run):
    a = assess(run)
    if a['stop_status'] is None:
        return dict(evidence.PAYLOAD_BASE, record_kind='RUN', record=run)
    return dict(evidence.PAYLOAD_BASE, record_kind='FAILURE', record=dict(
        failure_code='SYNTHETIC_TERMINAL_STOP', measurement_status=a['measurement']['measurement_status'],
        experiment_status=a['stop_status'], run=run, raw_evidence=None))


class FinalizationAcceptanceTests(unittest.TestCase):
    def assert_status(self, run, status):
        a = assess(run)
        self.assertEqual(a['stop_status'], status, a['reason_codes'])
        if status is not None:
            self.assertNotEqual(a['measurement']['measurement_status'], 'VALID')
        return a

    def roundtrip(self, run):
        parent = evidence.WORKSPACE / 'synthetic-test-outputs'
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            payload = envelope(run)
            receipt = evidence.write_once(Path(directory), 'run.json', payload, references=REFERENCES)
            self.assertEqual(receipt['schema_version'], 1)
            self.assertEqual(payload['schema_version'], 2)
            self.assertEqual(evidence.readback(receipt, references=REFERENCES), payload)
            self.assertEqual(receipt['persistence_status'], 'VERIFIED')
            return payload

    def test_clean_actual_collection_parser_accounting_pair_writer_readback(self):
        run, backend = terminal_run()
        self.assert_status(run, None)
        self.assertEqual(run['schema_version'], 2)
        self.assertEqual(run['finalization']['tripinfo']['parsing'], 'PARSED')
        self.assertEqual(len(run['observations']['tripinfo_records']), 540)
        self.assertEqual(run['measurement'], core._account(run))
        self.assertEqual(run['measurement']['metrics']['restricted_mean_trip_time_seconds'], 101)
        self.assertEqual(q.qualify_pair(run, record('D0'), references=REFERENCES)['pair_status'], 'QUALIFIES')
        self.assertEqual(backend.log[-2:], [('close',1500),('output',1500)])
        self.roundtrip(run)

    def test_late_object_contradiction_actual_pair_session_writer_readback(self):
        run, backend = terminal_run('object')
        a = self.assert_status(run, 'FAIL')
        self.assertIn('OUTPUT_OBJECT_MISMATCH', a['reason_codes'])
        self.assertNotIn('OUTPUT_BYTES_CHANGED', a['reason_codes'])
        self.assertEqual(len(run['observations']['tripinfo_records']), 540)
        self.assertEqual(run['failure']['kind'], 'INTEGRITY')
        self.assertEqual(q.qualify_pair(run, record('D0'), references=REFERENCES)['stop_status'], 'FAIL')
        incoming = pairs('C1'); incoming[0] = (run, incoming[0][1])
        session = q.SelectionSession(references=REFERENCES)
        self.assertEqual(session.add_level('C1', incoming)['status'], 'FAIL')
        with self.assertRaises(ValueError): session.add_level('C2', [])
        payload = self.roundtrip(run)
        self.assertEqual(payload['record']['experiment_status'], 'FAIL')
        self.assertEqual(payload['record']['run']['finalization'], run['finalization'])

    def test_content_snapshot_is_distinct_from_object_mismatch(self):
        run, _ = terminal_run('content')
        a = self.assert_status(run, 'FAIL')
        self.assertIn('OUTPUT_BYTES_CHANGED', a['reason_codes'])
        self.assertNotIn('OUTPUT_OBJECT_MISMATCH', a['reason_codes'])
        self.roundtrip(run)

    def test_retained_copy_inode_is_not_original_output_identity(self):
        run, backend = terminal_run()
        original = (backend.output_path / 'original.xml').stat()
        retained = artifact(run,'tripinfo').stat()
        self.assertNotEqual(original.st_ino, retained.st_ino)
        self.assert_status(run, None)

    def test_abort_late_witness_retains_first_abort_and_cleanup(self):
        run, _ = terminal_run('object', condition='D0', fail_step=350, close_failure=True)
        a = self.assert_status(run, 'FAIL')
        self.assertIn('OUTPUT_OBJECT_MISMATCH', a['reason_codes'])
        self.assertEqual(run['failure'], dict(kind='TECHNICAL',stage='OBSERVATION',code='OSError'))
        self.assertEqual(run['operational_abort']['time_before'],350)
        self.assertIn(dict(stage='CONNECTION_CLOSE',code='OSError'),run['cleanup_failures'])
        self.roundtrip(run)

    def test_earlier_integrity_survives_later_clean(self):
        run, _ = terminal_run('clean', collision_at=20)
        self.assert_status(run,'FAIL')
        self.assertEqual(run['finalization']['diagnostics']['counts'],dict.fromkeys(f.COUNTS,0))

    def test_prefix_abort_clean_unavailable_interrupted_never_valid(self):
        for mode in ('clean','unavailable','exception'):
            with self.subTest(mode=mode):
                run,_ = terminal_run(mode,fail_step=50)
                self.assert_status(run,'BLOCKED')
                result=q.qualify_pair(run,record('D0'),references=REFERENCES)
                self.assertEqual(result['stop_status'],'BLOCKED')
                self.assertFalse(result['qualification_evaluated'])

    def test_diagnostic_contradiction_wins_over_missing_tripinfo(self):
        run,_=terminal_run('collision_missing')
        a=self.assert_status(run,'FAIL')
        self.assertIn('COLLISION_OBSERVED',a['reason_codes'])
        self.assertIn('TRIPINFO_UNAVAILABLE',a['measurement']['evidence_deficiencies'])
        self.roundtrip(run)

    def test_recorded_witness_survives_exception_and_later_mutation(self):
        run,backend=terminal_run('collision_exception')
        self.assert_status(run,'FAIL')
        self.assertEqual(run['failure']['code'],'COLLISION_OBSERVED')
        self.assertEqual(run['finalization']['collection_state'],'INTERRUPTED')
        self.assertEqual({v['code'] for v in run['finalization']['findings']},
                         {'COLLISION_OBSERVED','FINALIZER_EXCEPTION'})
        backend.retained_result['findings'].clear()
        self.assertEqual(len(run['finalization']['findings']),2)
        self.roundtrip(run)

    def test_interrupted_full_collection_cannot_qualify(self):
        run,_=terminal_run('exception')
        self.assert_status(run,'INCONCLUSIVE')
        self.assertEqual(run['finalization']['tripinfo']['parsing'],'PARSED')
        self.assertFalse(run['output_finalized'])
        self.assertFalse(q.qualify_pair(run,record('D0'),references=REFERENCES)['qualification_evaluated'])
        self.roundtrip(run)

    def test_malformed_collector_finding_cannot_break_failure_retention(self):
        run,_=terminal_run('malformed_exception')
        self.assert_status(run,'FAIL')
        self.assertEqual(run['failure'],dict(kind='EVIDENCE',stage='TRIPINFO_FINALIZATION',code='FINALIZER_EXCEPTION'))
        self.assertEqual(run['finalization']['collection_state'],'INTERRUPTED')
        self.assertEqual(run['finalization']['findings'][0]['code'],[])
        self.assertEqual(run['observations']['final_time_seconds'],1500)
        with self.assertRaises(ValueError): evidence._validate_payload(envelope(run),references=REFERENCES)

    def test_first_close_failure_precedes_later_witness(self):
        run,_=terminal_run('collision_exception',close_failure=True)
        self.assert_status(run,'FAIL')
        self.assertEqual(run['failure'],dict(kind='EVIDENCE',stage='CONNECTION_CLOSE',code='OSError'))
        self.assertIn(dict(stage='CONNECTION_CLOSE',code='OSError'),run['cleanup_failures'])

    def test_normal_return_unavailable_is_not_clean(self):
        run,_=terminal_run('unavailable')
        self.assert_status(run,'INCONCLUSIVE')
        self.assertEqual(run['finalization']['collection_state'],'COMPLETED')
        self.assertFalse(run['output_finalized'])

    def test_parse_truncation_and_structure_are_not_id_contradictions(self):
        for mode in ('truncated','structure'):
            with self.subTest(mode=mode):
                run,_=terminal_run(mode)
                a=self.assert_status(run,'INCONCLUSIVE')
                self.assertEqual(run['finalization']['tripinfo']['parsing'],'UNPARSEABLE')
                self.assertNotIn('TRIPINFO_ID_CONTRADICTION',a['reason_codes'])
                self.roundtrip(run)

    def test_exact_missing_empty_duplicate_id_predicate_is_contradiction(self):
        for mode in ('missing_id','empty_id','duplicate_id'):
            with self.subTest(mode=mode):
                run,_=terminal_run(mode)
                self.assertIn('TRIPINFO_ID_CONTRADICTION',self.assert_status(run,'FAIL')['reason_codes'])
                self.roundtrip(run)

    def test_missing_scheduled_row_is_accounting_not_xml_id_predicate(self):
        run,_=terminal_run('missing_row')
        self.assert_status(run,'INCONCLUSIVE')
        self.assertNotIn('TRIPINFO_ID_CONTRADICTION',[v['code'] for v in run['finalization']['findings']])
        self.assertEqual(run['finalization']['tripinfo']['parsing'],'PARSED')
        self.assertEqual(run['measurement']['evidence_deficiencies'],[
            'ARRIVAL_TIME_UNAVAILABLE:veh_0000', 'DEPARTED_ACTUAL_TIME_UNAVAILABLE:veh_0000',
            'NATIVE_WAITING_MISSING:veh_0000'])

    def test_missing_undeparted_rows_follow_unchanged_adapter_accounting(self):
        run,_=terminal_run('clean',pending_count=5)
        self.assert_status(run,None)
        self.assertEqual(run['measurement'],core._account(run))
        self.assertEqual(len(run['observations']['tripinfo_records']),535)
        self.assertEqual(len(run['measurement']['ledger']),540)

    def test_nonzero_exit_or_not_exited_is_not_new_blocked_or_integrity_class(self):
        for mode in ('nonzero','not_exited'):
            with self.subTest(mode=mode):
                run,_=terminal_run(mode)
                self.assert_status(run,'INCONCLUSIVE')
                self.roundtrip(run)

    def test_synthetic_warnings_unknown_coverage_and_known_positives(self):
        for mode,status in (('warning',None),('unknown','INCONCLUSIVE'),('unknown_positive','FAIL'),('route','FAIL'),('simulator_error','FAIL')):
            with self.subTest(mode=mode):
                self.assert_status(terminal_run(mode)[0],status)

    def test_omitted_finding_does_not_suppress_derived_positive(self):
        for mode,code in (('collision','COLLISION_OBSERVED'),('object','OUTPUT_OBJECT_MISMATCH'),('content','OUTPUT_BYTES_CHANGED')):
            with self.subTest(mode=mode):
                run,_=terminal_run(mode)
                run['finalization']['findings']=[]
                self.assertIn(code,self.assert_status(run,'FAIL')['reason_codes'])

    def test_collector_cannot_own_parsing_or_collection_state(self):
        run,_=terminal_run('forged_owner_fields')
        self.assert_status(run,None)
        self.assertEqual(run['finalization']['collection_state'],'COMPLETED')
        self.assertEqual(run['finalization']['tripinfo']['parsing'],'PARSED')

    def test_closed_schema_unknown_and_boolean_fields_rejected(self):
        original,_=terminal_run()
        mutations=(('version',True),('collection_state','UNKNOWN'),('attempt','COMPLETED'),
                   ('process',dict(state='EXITED',exit_code=True)),
                   ('diagnostics',dict(coverage='COMPLETE',counts=dict.fromkeys(f.COUNTS,None))),
                   ('findings',[dict(code='UNSUPPORTED',evidence_keys=[])]))
        for key,value in mutations:
            with self.subTest(key=key):
                run=copy.deepcopy(original); run['finalization'][key]=value
                self.assert_status(run,'FAIL')

    def test_forged_assertions_rejected_without_claiming_simulator_defect(self):
        original,_=terminal_run()
        for mutation in ('process','counts','rows','parsing','match','finding','finding_wrong_key'):
            with self.subTest(mutation=mutation):
                run=copy.deepcopy(original); final=run['finalization']
                if mutation=='process': final['process']['exit_code']=1
                elif mutation=='counts': final['diagnostics']['counts']['collisions']=1
                elif mutation=='rows': run['observations']['tripinfo_records'][0]['waitingTime']='3'
                elif mutation=='parsing': final['tripinfo']['parsing']='NOT_ATTEMPTED'
                elif mutation=='match': final['output_identity']['output_observations']['expected']=None
                else: final['findings']=[dict(code='COLLISION_OBSERVED',evidence_keys=['capture'] if mutation=='finding_wrong_key' else ['diagnostics'])]
                a=self.assert_status(run,'FAIL')
                self.assertNotIn('COLLISION_OBSERVED',a['reason_codes'])

    def test_unreviewed_native_mapping_cannot_certify_complete(self):
        run,_=terminal_run()
        data=evidence._decode(artifact(run,'diagnostics').read_bytes())
        data['mapping']='UNREVIEWED_NATIVE_MAPPING'
        replace_bytes(run['finalization'],artifact(run,'diagnostics').parent,'diagnostics',evidence._encode(data))
        self.assertIn('UNSUPPORTED_DIAGNOSTIC_MAPPING',self.assert_status(run,'FAIL')['reason_codes'])

    def test_missing_read_context_no_fallback_or_qualification(self):
        run,_=terminal_run()
        a=core.assess_run(run)
        self.assertEqual(a['stop_status'],'INCONCLUSIVE')
        self.assertEqual(run['schema_version'],2)
        self.assertFalse(q.qualify_pair(run,record('D0'))['qualification_evaluated'])

    def test_missing_accessible_artifact_is_deficiency_and_other_witness_wins(self):
        for mode,status in (('clean','INCONCLUSIVE'),('collision','FAIL')):
            with self.subTest(mode=mode):
                run,_=terminal_run(mode)
                artifact(run,'tripinfo').unlink()
                self.assert_status(run,status)

    def test_terminal_severity_label_cannot_replace_lost_witness(self):
        run,_=terminal_run('collision')
        self.assertEqual(run['failure']['kind'],'INTEGRITY')
        artifact(run,'diagnostics').unlink()
        self.assert_status(run,'INCONCLUSIVE')
        self.assertEqual(run['failure']['code'],'COLLISION_OBSERVED')

    def test_unsupported_assertions_not_verified_failure_or_selection_evidence(self):
        run,_=terminal_run()
        run['finalization']['findings']=[dict(code='COLLISION_OBSERVED',evidence_keys=['diagnostics'])]
        self.assert_status(run,'FAIL')
        with self.assertRaises(ValueError): evidence._validate_payload(envelope(run),references=REFERENCES)
        incoming=pairs('C1'); incoming[0]=(run,incoming[0][1])
        session=q.SelectionSession(references=REFERENCES); session.add_level('C1',incoming)
        with self.assertRaises(ValueError): q.validate_selection_record(session.to_record(),references=REFERENCES)

    def test_reference_scope_capture_association_and_anchor_are_checked(self):
        for mutation in ('scope','capture','anchor'):
            with self.subTest(mutation=mutation):
                run,_=terminal_run()
                if mutation=='scope': run['run_id']='FOREIGN'
                else:
                    data=evidence._decode(artifact(run,'capture').read_bytes())
                    if mutation=='capture': data['run_id']='FOREIGN'
                    else:
                        data['output_observations']['expected']['inode']+=1
                        run['finalization']['output_identity']['output_observations']=copy.deepcopy(data['output_observations'])
                    replace_bytes(run['finalization'],artifact(run,'capture').parent,'capture',evidence._encode(data))
                self.assert_status(run,'FAIL')

    def test_oversize_corrupt_and_unsafe_references_fail_closed(self):
        for mutation in ('size','actual_size','hash','path','directory','symlink','hardlink','fifo'):
            with self.subTest(mutation=mutation):
                run,_=terminal_run()
                path=artifact(run,'tripinfo'); output=run['finalization']['output_identity']
                ref=output['artifacts']['tripinfo']
                if mutation=='size': ref['byte_count']=evidence.MAX_BYTES+1
                elif mutation=='actual_size':
                    with path.open('r+b') as stream: stream.truncate(evidence.MAX_BYTES+1)
                elif mutation=='hash': path.write_bytes(b'corrupt')
                elif mutation=='path': ref['name']='../foreign.xml'
                elif mutation=='directory': output['output_directory']='../foreign'
                elif mutation=='hardlink': os.link(path,path.with_name('extra-link.xml'))
                else:
                    path.unlink()
                    if mutation=='fifo': os.mkfifo(path)
                    else: path.symlink_to(path.with_name('original.xml'))
                self.assert_status(run,'FAIL')

    def test_repeat_with_different_artifact_identity_and_collection_state_retained(self):
        session=q.SelectionSession(references=REFERENCES)
        incoming=pairs('C1'); session.add_level('C1',incoming)
        n,d=record('N0-CAL-R'),record('D0-CAL-R')
        self.assertNotEqual(incoming[0][0]['finalization']['output_identity'],n['finalization']['output_identity'])
        self.assertEqual(session.add_repeats(n,d)['status'],'PENDING_READBACK')
        excluded=set(core.contract()['selected_deterministic_repeat']['operational_fields_excluded'])
        normalized=q._without_operational(n,excluded)
        self.assertIn('collection_state',normalized['finalization'])
        n['finalization']['collection_state']='INTERRUPTED'
        self.assertNotEqual(normalized,q._without_operational(n,excluded))

    def test_actual_repeat_late_contradiction_and_interruption_stops(self):
        for mode,abort,status in (('object',None,'FAIL'),('object',50,'FAIL'),('clean',50,'BLOCKED'),('exception',None,'FAIL')):
            with self.subTest(mode=mode,abort=abort):
                session=q.SelectionSession(references=REFERENCES); session.add_level('C1',pairs('C1'))
                run,_=terminal_run(mode,condition='N0-CAL-R',fail_step=abort)
                result=session.add_repeats(run,record('D0-CAL-R'))
                self.assertEqual(result['status'],status)
                self.assertEqual(q.validate_selection_record(session.to_record(),references=REFERENCES),result)
                with self.assertRaises(ValueError): session.add_level('C2',[])

    def test_pair_and_seed_integrity_precedes_blocked(self):
        run,_=terminal_run('collision')
        aborted=record('D0',fail_step=50)
        self.assertEqual(q.qualify_pair(run,aborted,references=REFERENCES)['stop_status'],'FAIL')
        incoming=pairs('C1'); incoming[0]=(record(fail_step=50),incoming[0][1])
        other,_=terminal_run('collision',seed=20260905); incoming[1]=(other,incoming[1][1])
        self.assertEqual(q.SelectionSession(references=REFERENCES).add_level('C1',incoming)['status'],'FAIL')

    def test_legacy_is_explicit_exact_unverified_and_never_selectable(self):
        # Deliberately constructed synthetic V1-shaped data, not a historical
        # run/result. No source code or current source hashes are monkeypatched.
        for abort,status in ((None,None),(50,'BLOCKED')):
            with self.subTest(abort=abort):
                legacy=record(fail_step=abort)
                legacy.pop('finalization'); legacy['schema_version']=1
                legacy['binding']['implementation_sha256']=dict(core.LEGACY_SOURCE_SHA256)
                before=copy.deepcopy(legacy)
                audit=core.audit_legacy_run(legacy,revision=core.LEGACY_REVISION)
                self.assertEqual(audit['audit_context'],'LEGACY_FINALIZATION_UNVERIFIED')
                self.assertEqual(audit['stop_status'],status)
                self.assertEqual(legacy,before)
                with self.assertRaises(ValueError): core.validate_run(legacy,references=REFERENCES)
                self.assertEqual(q.qualify_pair(legacy,record('D0'),references=REFERENCES)['stop_status'],'FAIL')
                incoming=pairs('C1'); incoming[0]=(legacy,incoming[0][1])
                with self.assertRaises(ValueError): q.SelectionSession(references=REFERENCES).add_level('C1',incoming)
                legacy['binding']['implementation_sha256']['integration.py']='0'*64
                with self.assertRaises(ValueError): core.audit_legacy_run(legacy,revision=core.LEGACY_REVISION)
        with self.assertRaises(ValueError): core.audit_legacy_run({},revision='UNREVIEWED')

    def test_schema_version_relationships_missing_field_and_mixed_history(self):
        run,_=terminal_run()
        for mutation in ('envelope','run','omission'):
            with self.subTest(mutation=mutation):
                payload=envelope(copy.deepcopy(run))
                if mutation=='envelope': payload['schema_version']=1
                elif mutation=='run': payload['record']['schema_version']=1
                else: payload['record'].pop('finalization')
                with self.assertRaises((ValueError,evidence.EvidenceError)):
                    evidence._validate_payload(payload,references=REFERENCES)
        session=q.SelectionSession(references=REFERENCES); session.add_level('C1',pairs('C1'))
        repeat=record('N0-CAL-R'); repeat['schema_version']=1
        with self.assertRaises(ValueError): session.add_repeats(repeat,record('D0-CAL-R'))

    def test_failure_cannot_force_blocked_or_omit_status(self):
        run,_=terminal_run('object',fail_step=50)
        for status in ('BLOCKED',None):
            with self.subTest(status=status):
                payload=envelope(run)
                if status is None: payload['record'].pop('experiment_status')
                else: payload['record']['experiment_status']=status
                with self.assertRaises(evidence.EvidenceError): evidence._validate_payload(payload,references=REFERENCES)

    def test_readback_rechecks_references_and_missing_support_is_not_success(self):
        run,_=terminal_run()
        with tempfile.TemporaryDirectory(dir=evidence.WORKSPACE/'synthetic-test-outputs') as directory:
            receipt=evidence.write_once(Path(directory),'run.json',envelope(run),references=REFERENCES)
            path=artifact(run,'tripinfo'); original=path.read_bytes()
            for raw in (None,b'changed'):
                with self.subTest(missing=raw is None):
                    if raw is None: path.unlink()
                    else: path.write_bytes(raw)
                    with self.assertRaises(evidence.EvidenceError): evidence.readback(receipt,references=REFERENCES)
                    path.write_bytes(original)
            self.assertEqual(evidence.readback(receipt,references=REFERENCES)['record'],run)

    def test_persistence_io_does_not_erase_a_revalidated_experiment_fail(self):
        run,_=terminal_run('object')
        with tempfile.TemporaryDirectory(dir=evidence.WORKSPACE/'synthetic-test-outputs') as directory:
            original=evidence._create
            def fail_data(fd,name,raw):
                if name=='run.json': raise OSError('synthetic write failure after validation')
                return original(fd,name,raw)
            with patch.object(evidence,'_create',side_effect=fail_data):
                with self.assertRaises(evidence.EvidenceError) as caught:
                    evidence.write_once(Path(directory),'run.json',envelope(run),references=REFERENCES)
            self.assertEqual(caught.exception.code,'IO_FAILURE')
            self.assertEqual(caught.exception.experiment_status,'FAIL')
            self.assertFalse((Path(directory)/'run.json.complete.json').exists())


if __name__=='__main__':
    unittest.main()
