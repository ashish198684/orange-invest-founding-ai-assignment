"""Independent consolidation of executed SQL, HTTP, trace and restore evidence."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
FIRST=ROOT/'artifacts/receipts/g3x_release_pooled_20261102'
REPEAT=ROOT/'artifacts/receipts/g3x_repeat_load_20261103'
def read(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    build=read(ROOT/'BUILD_INFO.json');code=build['code_git_sha']
    assert all(digest(ROOT/name)==expected for name,expected in build['source_sha256'].items())
    assert read(FIRST/'receipt.json')['status']==read(REPEAT/'receipt.json')['status']=='PASS'
    clean=read(FIRST/'clean_source/receipt.json')
    assert clean['code_git_sha']==code and clean['baseline_tests']==65 and clean['baseline_exit_code']==0
    assert clean['g3x_tests_run']==39 and clean['failures']==clean['errors']==clean['skipped']==0
    loads=[]
    for parent,prefix in [(FIRST,'load'),(REPEAT,'repeat')]:
        for count in [1,100]:
            folder=parent/(prefix+'_'+str(count));report=read(folder/'results.json')
            assert report['initial_state']=={'workflows':0,'provider_bookings':0}
            assert report['simultaneously_persisted_active_workflows']==count
            assert report['http_latency']['max_ms']<20000
            for key in ['provider_slot_violations','logical_intent_violations','approval_violations','approval_payload_mismatches']:assert not report[key]
            state=read(folder/'independent_sql.json');ops=state['authority.operations']
            approvals={a['approval_id']:a for a in state['authority.approval_snapshots']}
            effects=defaultdict(set)
            for booking in state['provider.provider_bookings']:
                matches=[o for o in ops if json.loads(o['snapshot_json'])['hold_id']==booking['hold_id']]
                assert len(matches)==1
                op=matches[0];snapshot=json.loads(op['snapshot_json']);approval=approvals[op['approval_id']]
                assert approval['status']=='GRANTED' and op['snapshot_json']==approval['snapshot_json']
                assert hashlib.sha256(op['snapshot_json'].encode()).hexdigest()==op['payload_fingerprint']==approval['payload_fingerprint']
                assert op['user_id']==snapshot['user_id']==booking['user_id']
                assert snapshot['provider_id']==booking['provider_id'] and snapshot['new_slot']==booking['slot']
                assert snapshot['price_amount']==booking['quoted_price']
                effects[op['workflow_id']].add(booking['id'])
            assert all(len(ids)==1 for ids in effects.values())
            assert all(o['attempts']<=3 for o in ops)
            assert all(j['claims']<=6 for j in state['authority.jobs'])
            if count==100:
                duplicate=report['duplicate_confirmation_experiment']
                assert duplicate['requests']==100 and duplicate['distinct_operations']==duplicate['bookings']==1
                assert duplicate['final_status']=='BOOKED' and duplicate['latency']['max_ms']<20000
                assert report['distinct_worker_processes_observed']>=2
            report['evidence_directory']=folder.relative_to(ROOT).as_posix()
            report['snapshot_bookings']=len(state['provider.provider_bookings'])
            samples=read(folder/'queue_samples.json')
            report['peak_pending_jobs']=max((sum(x['n'] for x in s['counts'] if x['state'] in {'READY','LEASED'}) for s in samples),default=0)
            resources=read(parent/('resources_'+str(count)+'.json'));peaks={}
            for sample in resources:
                for line in sample['stdout'].splitlines():
                    row=json.loads(line);role=row['Name'].rsplit('-',2)[-2]
                    peak=peaks.setdefault(role,{'cpu_percent':0,'memory_mib':0})
                    peak['cpu_percent']=max(peak['cpu_percent'],float(row['CPUPerc'].rstrip('%')))
                    value=row['MemUsage'].split(' / ')[0]
                    for unit,factor in [('GiB',1024),('MiB',1),('KiB',1/1024),('B',1/1048576)]:
                        if value.endswith(unit):
                            peak['memory_mib']=max(peak['memory_mib'],float(value[:-len(unit)])*factor);break
            report['sampled_resource_peaks']=peaks;loads.append(report)
    restore=read(FIRST/'restore/restore_verification.json')
    assert restore['first_readback']['status']==restore['duplicate_delivery']['status']=='BOOKED'
    assert restore['first_readback']['booking_id']==restore['duplicate_delivery']['booking_id']
    assert len(restore['live_provider_bookings'])==1 and restore['migration_versions']==[1,2,3]
    assert read(FIRST/'restore/rollback_check.json')['empty_schema_rollback_rebuild']=='PASS'
    traces=list((FIRST/'clean_source/traces').glob('*.jsonl'));events=[]
    for p in traces:events.extend(map(json.loads,p.read_text().splitlines()))
    assert all(e['code_git_sha']==code for e in events)
    assert all(e['model_call_count']<=8 and e['tool_call_count']<=16 for e in events)
    required={'timestamp','workflow_id','tool_name','sanitized_args','sanitized_result','error_class','duration_ms','decision_reason','exit_reason'}
    assert all(required<=e.keys() for e in events)
    corpus='\n'.join(p.read_text() for p in traces)+(FIRST/'clean_source/otel_spans.json').read_text()
    assert all(s not in corpus for s in ['synthetic-private-token','private-memory-sentinel','Indiranagar'])
    inspected=[]
    for name in ['test_http_timeout_after_success_receipt','test_real_zombie_worker_after_committed_provider_cannot_overwrite_replacement','test_memory_cross_replica_forget_stale_replay_and_privacy']:
        case=FIRST/'clean_source/cases'/name;correlation=read(case/'correlation.json');state=read(case/'sql_state.json')
        own=[e for e in events if e['user_id_hash']==correlation['actor_hash']]
        inspected.append({'case':name,'snapshot_sha256':digest(case/'sql_state.json'),
            'bookings':len(state['provider.provider_bookings']),'jobs':[(j['state'],j['claims'],j['generation']) for j in state['authority.jobs']],
            'memory_values':[m['value_json'] for m in state['authority.memory_facts']],
            'event_types':sorted({e['event_type'] for e in own}),
            'exit_reasons':sorted({e['exit_reason'] for e in own if e['exit_reason']})})
    old_mutations=subprocess.check_output(['git','diff','--name-only','--diff-filter=MD','855e372f11e2329774fff9efe6060ece6035891d','HEAD','--','artifacts/receipts','source','AGENTS.md'],cwd=ROOT,text=True).splitlines()
    assert not old_mutations,old_mutations
    report={'gate':'G3X','status':'PASS','acceptance':'CTO adjudication pending','stopped_after':'G3X',
        'canonical_id':'ORANGE-FOUNDINGAI-20261102-003','canonical_sha256_at_audit':digest(ROOT/'CANONICAL.md'),
        'code_commit':code,'clean_checkout_commit':read(FIRST/'receipt.json')['code_commit'],
        'tests':{'baseline':65,'g3x':39,'skipped':0,'failures':0,'errors':0,'exits':0},'loads':loads,
        'trace_files':len(traces),'trace_events':len(events),'exported_otel_spans':clean['exported_otel_spans'],
        'inspected_cases':inspected,'historical_receipt_mutations':old_mutations,
        'restore':'Same live provider booking after restored authority reconciliation and duplicate delivery; versions 1/2/3 reapplied. Empty disposable schema rebuild only, not a production downgrade.',
        'limitations':['Two small single-machine measurements; no 100x throughput or production HA claim.',
          'Long full-workload journey latency, preapproval tool timeouts and honest unknowns are retained.',
          'OTLP export is bounded best-effort; an exporter timeout was observed. Local JSONL is the retained trace.',
          'Synthetic local auth, no OIDC/TLS production security claim; API card issuance does not prove browser rendering.',
          'Logical memory suppression is not forensic erasure of MVCC pages/backups. Old backups require deletion suppressions before operational restoration.',
          'G4 browser/Groq/user-agent evaluations and G5 final deliverables/video are NOT STARTED. Submission remains NO-GO.']}
    (OUT/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'sha256.json').write_text(json.dumps({p.relative_to(ROOT).as_posix():digest(p) for directory in [FIRST,REPEAT,OUT] for p in directory.rglob('*') if p.is_file() and p.name!='sha256.json'},indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'loads','inspected_cases'}},indent=2))
if __name__=='__main__':main()
