"""Independent, read-only SQL inspection of preserved synthetic G2 evidence DBs."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

def main(directory):
    root=Path(directory).resolve()
    results=[]
    for path in sorted(root.rglob('*.sqlite3')):
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            db.row_factory=sqlite3.Row
            integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
            foreign_keys=[list(r) for r in db.execute('PRAGMA foreign_key_check')]
            duplicate_slots=[dict(r) for r in db.execute("SELECT provider_id,slot,count(*) n FROM provider_bookings "
                            "WHERE status='booked' GROUP BY provider_id,slot HAVING count(*)>1")]
            duplicate_logical=[dict(r) for r in db.execute('SELECT h.workflow_id,count(DISTINCT b.id) n '
                'FROM workflow_holds h JOIN provider_bookings b ON h.hold_id=b.hold_id '
                'GROUP BY h.workflow_id HAVING count(DISTINCT b.id)>1')]
            missing_approval=[]
            for b in db.execute('SELECT b.* FROM provider_bookings b JOIN workflow_holds h ON h.hold_id=b.hold_id'):
                matches=[]
                for op in db.execute("SELECT o.*,a.status approval_status,a.snapshot_json approval_json FROM operations o "
                       "JOIN approval_snapshots a USING(approval_id) WHERE o.action='book'"):
                    s=json.loads(op['snapshot_json'])
                    if s['hold_id']==b['hold_id']:
                        valid=(op['approval_status']=='GRANTED' and op['user_id']==b['user_id']
                               and s['user_id']==b['user_id'] and s['provider_id']==b['provider_id']
                               and s['price_amount']==b['quoted_price'] and op['snapshot_json']==op['approval_json']
                               and hashlib.sha256(json.dumps(s,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()==op['payload_fingerprint'])
                        matches.append(valid)
                if matches!=[True]: missing_approval.append(b['id'])
            retry_violations=[dict(r) for r in db.execute('SELECT operation_id,attempts FROM operations WHERE attempts>3')]
            results.append(dict(database=str(path.relative_to(root)),integrity=integrity,foreign_key_violations=foreign_keys,
                duplicate_provider_slots=duplicate_slots,duplicate_logical_bookings=duplicate_logical,
                missing_matching_granted_approval=missing_approval,retry_cap_violations=retry_violations,
                provider_bookings=db.execute('SELECT count(*) FROM provider_bookings').fetchone()[0],
                operations=db.execute('SELECT count(*) FROM operations').fetchone()[0],
                passed=integrity=='ok' and not any([foreign_keys,duplicate_slots,duplicate_logical,missing_approval,retry_violations])))
    report={'kind':'read_only_SQL_evidence_inspection','databases':results,
            'checked':len(results),'passed':sum(r['passed'] for r in results)}
    (root/'independent_db_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if results and all(r['passed'] for r in results) else 1)

if __name__=='__main__': main(sys.argv[1])
