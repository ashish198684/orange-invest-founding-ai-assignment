"""Independent read-only SQL + raw-trace reconciliation for the final live/browser run."""
import argparse,base64,hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import psycopg
from psycopg.rows import dict_row
from app.runtime.pg import dsn
from app.runtime.observe import build_sha
from app.workflow import fingerprint
from app.agent.groq import MODEL,PROMPT_VERSION

def main():
    p=argparse.ArgumentParser();p.add_argument('--live-label',required=True);p.add_argument('--browser-user',required=True);p.add_argument('--label',required=True);a=p.parse_args()
    state=Path(os.environ.get('RUNTIME_STATE','data/runtime'));out=state/'receipts'/a.label;out.mkdir(exist_ok=False,parents=True)
    live=json.loads((state/'receipts'/a.live_label/'receipt.json').read_text());assert live['status']=='PASS'
    users=[live['approval']['snapshot']['user_id'],a.browser_user];truth={};events=[];sha=build_sha();assert sha!='UNCOMMITTED'
    with psycopg.connect(**dsn('orange_grader'),row_factory=dict_row) as db:
        for uid in users:
            tables={table:db.execute('SELECT * FROM '+table+' WHERE user_id=%s',(uid,)).fetchall() for table in ['authority.workflows','authority.approval_snapshots','authority.operations','authority.jobs','authority.memory_facts','provider.provider_bookings','provider.provider_operation_outcomes']}
            approvals={r['approval_id']:r for r in tables['authority.approval_snapshots']};ops=tables['authority.operations'];bookings=tables['provider.provider_bookings']
            assert len(bookings)==1
            for op in ops:
                approval=approvals[op['approval_id']];s=json.loads(op['snapshot_json'])
                assert approval['status']=='GRANTED' and approval['snapshot_json']==op['snapshot_json'];assert fingerprint(s)==op['payload_fingerprint']==approval['payload_fingerprint'];assert s['user_id']==uid
                assert op['status']=='COMMITTED' and op['verified_at'] is not None
                if op['action']=='book':assert s['price_amount']==bookings[0]['quoted_price'] and s['provider_id']==bookings[0]['provider_id']
                result=json.loads(op['result_json'])
                if op['action'] in {'book','reschedule'}:assert result['booking']['slot']==s['new_slot']
                if op['action']=='reschedule':assert bookings[0]['slot']==s['new_slot']
                if op['action']=='cancel':assert s['old_slot']==bookings[0]['slot'] and result['status']=='CANCELLED'
            if uid==a.browser_user:
                assert {o['action'] for o in ops}=={'book','reschedule','cancel'};assert bookings[0]['status']=='cancelled'
                assert any(r['status']=='VOID' for r in approvals.values())
                assert tables['authority.memory_facts'][0]['forgotten'] and tables['authority.memory_facts'][0]['value_json'] is None
            else:assert len(ops)==1 and bookings[0]['status']=='booked'
            truth[hashlib.sha256(uid.encode()).hexdigest()]=tables
    actors=set(truth);trace_dir=out/'traces';trace_dir.mkdir()
    for path in (state/'traces').glob('*.jsonl'):
        raw=path.read_text();rows=[json.loads(line) for line in raw.splitlines()]
        if rows and rows[0]['user_id_hash'] in actors:
            assert all(e['code_git_sha']==sha for e in rows);events.extend(rows);(trace_dir/path.name).write_text(raw)
    model=[e for e in events if e['event_type']=='model_result'];assert len(model)>=5
    assert all(e['model_id']==MODEL and e['model_prompt_version']==PROMPT_VERSION and e['model_mode']=='groq' and e['token_in'] is not None and e['token_out'] is not None and e['cost_usd'] is None for e in model)
    assert sum(e['event_type']=='provider_timeout' and e['tool_name']=='book' for e in events)>=2
    # Customer preference values do not enter raw traces, including final copy.
    for e in events:
        assert 'Koramangala' not in json.dumps(e) and 'Indiranagar' not in json.dumps(e)
    trace_ids={e['trace_id'] for e in model};spans=[]
    for line in (state/'otel.jsonl').read_text().splitlines():
        for resource in json.loads(line).get('resourceSpans',[]):
            for library in resource.get('scopeSpans',[]):
                for s in library.get('spans',[]):
                    if s['name']=='model.groq.proposal' and base64.b64decode(s['traceId']).hex() in trace_ids:spans.append(s)
    assert len(spans)>=len(model)
    (out/'sql_state.json').write_text(json.dumps(truth,default=str,indent=2));(out/'model_spans.json').write_text(json.dumps(spans,indent=2))
    report={'gate':'G4 independent live/browser audit','status':'PASS','code_commit':sha,'model_results':len(model),'model_spans':len(spans),'provider_bookings':2,'live_verified_bookings':1,'browser_verified_cancelled_bookings':1,'browser_committed_actions':3,'raw_trace_files':len(list(trace_dir.glob('*.jsonl'))),'checks':['exact granted fingerprints and user/provider/price','one book effect per logical request','reschedule/cancel readback','correct/forgotten memory tombstone','actual Groq v2 identity/usage/spans','timeout and authoritative readback','no raw preference values in traces']}
    (out/'receipt.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
