"""Test-only direct provider evidence, not a workflow trace or scripted-user eval."""
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.provider_mock import ProviderMock, ProviderTimeout, ScenarioConfig


def main():
    target = ROOT / 'artifacts' / 'receipts' / 'provider_timeout.sqlite3'
    if target.exists():
        raise SystemExit('Evidence DB already exists; preserve it and use tests to reproduce.')
    clock = lambda: datetime.fromisoformat('2026-11-01T09:00:00+05:30')
    p = ProviderMock(target, user_id='synthetic-evidence-user', clock=clock,
                     config=ScenarioConfig(book_branch='timeout_after_success'))
    option = p.search_providers('plumber', 'Indiranagar', {
        'start': '2026-11-01T00:00:00+05:30', 'end': '2026-11-09T00:00:00+05:30'})[0]
    hold = p.hold_slot(option['id'], option['free_slots'][0])
    try:
        p.book(hold['hold_id'], 'provider-evidence-key')
        raise AssertionError('Expected transport timeout')
    except ProviderTimeout as exc:
        observed_error = {'code': exc.code, 'http_status': exc.http_status}
    restarted = ProviderMock(target, user_id='synthetic-evidence-user', clock=clock)
    truth = restarted.get_booking_status('provider-evidence-key')
    replay = restarted.book(hold['hold_id'], 'provider-evidence-key')
    bookings = restarted.list_bookings('synthetic-evidence-user')
    assert truth['status'] == 'booked' and replay['booking_id'] == truth['booking_id']
    assert len(bookings) == 1
    with restarted.store.connect() as db:
        hold_state = dict(db.execute('SELECT * FROM provider_holds').fetchone())
        outcome_state = dict(db.execute('SELECT * FROM provider_operation_outcomes').fetchone())
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
    print(json.dumps({'evidence_kind': 'direct_provider_probe_only', 'database': str(target),
                      'observed_error': observed_error, 'authoritative_status': truth,
                      'same_key_replay': replay, 'bookings': bookings, 'hold_state': hold_state,
                      'operation_outcome': outcome_state, 'integrity_check': integrity}, indent=2))


if __name__ == '__main__':
    main()
