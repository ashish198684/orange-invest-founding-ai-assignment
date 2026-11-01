from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import inspect
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Barrier
import unittest
import tempfile
from app.provider_mock import ProviderError, ProviderMock, ProviderTimeout, ScenarioConfig
from app.provider_mock.fixtures import IST, SERVICES, AREAS
NOW = datetime(2026, 11, 1, 9, tzinfo=IST)
WINDOW = {'start': NOW.isoformat(), 'end': (NOW + timedelta(days=8)).isoformat()}

class Clock:

    def __init__(self):
        self.value = NOW

    def __call__(self):
        return self.value

def selection(p):
    option = p.search_providers('plumber', 'Indiranagar', WINDOW)[0]
    return (option['id'], option['free_slots'])

def booked(p, key='book-1', index=0):
    pid, slots = selection(p)
    hold = p.hold_slot(pid, slots[index])
    result = p.book(hold['hold_id'], key)
    return (result['booking_id'], pid, slots, hold)

def error(code, call):
    with unittest.TestCase().assertRaises(ProviderError) as exc:
        call()
    assert exc.exception.code == code
    return exc.exception

class ProviderContractTests(unittest.TestCase):

    def new_dir(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def new_setup(self):
        clock = Clock()
        path = self.new_dir() / 'provider.sqlite3'

        def make(branch='book_success', *, config=None, user='alice'):
            return ProviderMock(path, user_id=user, clock=clock, config=config or ScenarioConfig(book_branch=branch))
        return (path, clock, make)

    def test_exact_eight_tool_signatures(self):
        expected = {'search_providers': ['service', 'area', 'date_range'], 'get_provider': ['provider_id'], 'list_bookings': ['user_id'], 'hold_slot': ['provider_id', 'slot'], 'book': ['hold_id', 'idempotency_key'], 'get_booking_status': ['idempotency_key'], 'cancel': ['booking_id', 'idempotency_key'], 'reschedule': ['booking_id', 'new_slot', 'idempotency_key']}
        public = {n for n, f in inspect.getmembers(ProviderMock, inspect.isfunction) if not n.startswith('_')}
        assert public == set(expected)
        for name, args in expected.items():
            assert list(inspect.signature(getattr(ProviderMock, name)).parameters) == ['self', *args]

    def test_search_contract_and_filtering(self):
        for service in SERVICES:
            for area in AREAS:
                with self.subTest(service=service, area=area):
                    setup = self.new_setup()
                    _, _, make = setup
                    p = make()
                    options = p.search_providers(service, area, WINDOW)
                    assert 3 <= len(options) <= 8
                    assert len({v['price'] for v in options}) == 3
                    for v in options:
                        assert set(v) == {'id', 'price', 'rating', 'free_slots', 'attributes'}
                        assert v['attributes']['area'] == area and v['attributes']['service'] == service
                        assert v['free_slots'] and isinstance(v['rating'], float)
                    window = {'start': options[0]['free_slots'][0], 'end': options[0]['free_slots'][1]}
                    assert p.search_providers(service, area, window)[0]['free_slots'] == [window['start']]
                    assert p.search_providers(service, 'unsupported-area', WINDOW) == []

    def test_untrusted_review_is_free_text_without_side_effects(self):
        setup = self.new_setup()
        _, _, make = setup
        p = make()
        pid, _ = selection(p)
        detail = p.get_provider(pid)
        assert all((isinstance(r, str) for r in detail['reviews']))
        assert any(('ignore approvals' in r for r in detail['reviews']))
        assert p.list_bookings('alice') == []

    def test_hold_exact_ttl_quote_and_availability(self):
        setup = self.new_setup()
        _, clock, make = setup
        p = make(config=ScenarioConfig(book_branch='book_success', quote_delta=250))
        pid, slots = selection(p)
        original = p.get_provider(pid)['price']
        h = p.hold_slot(pid, slots[0])
        assert set(h) == {'hold_id', 'expires_at', 'quoted_price'}
        assert datetime.fromisoformat(h['expires_at']) - clock() == timedelta(minutes=10)
        assert h['quoted_price'] == original + 250
        assert slots[0] not in selection(p)[1]
        error('slot_unavailable', lambda: p.hold_slot(pid, slots[0]))
        clock.value += timedelta(minutes=10)
        assert slots[0] in selection(p)[1]
        assert p.hold_slot(pid, slots[0])['hold_id'] != h['hold_id']

    def test_hold_expiry_boundary(self):
        for seconds, expires in [(599, False), (600, True), (601, True)]:
            with self.subTest(seconds=seconds, expires=expires):
                setup = self.new_setup()
                _, clock, make = setup
                p = make()
                pid, slots = selection(p)
                h = p.hold_slot(pid, slots[0])
                clock.value += timedelta(seconds=seconds)
                if expires:
                    error('hold_expired', lambda: p.book(h['hold_id'], 'key'))
                    assert p.get_booking_status('key') == {'status': 'failed'}
                    assert p.list_bookings('alice') == []
                else:
                    assert p.book(h['hold_id'], 'key')['booking_id']

    def test_all_forced_book_branches_persist_before_error(self):
        for branch, status, code, count in [('book_success', 'booked', None, 1), ('slot_taken', 'failed', 'slot_taken', 0), ('hold_expired', 'failed', 'hold_expired', 0), ('timeout_after_success', 'booked', 'timeout', 1), ('timeout_without_booking', 'not_found', 'timeout', 0)]:
            with self.subTest(branch=branch, status=status, code=code, count=count):
                setup = self.new_setup()
                path, clock, make = setup
                p = make(branch)
                pid, slots = selection(p)
                h = p.hold_slot(pid, slots[0])
                if code:
                    exc = error(code, lambda: p.book(h['hold_id'], 'key'))
                    if code == 'timeout':
                        assert isinstance(exc, (TimeoutError, ProviderTimeout)) and exc.http_status == 504
                else:
                    assert p.book(h['hold_id'], 'key')['booking_id']
                restarted = ProviderMock(path, user_id='alice', clock=clock)
                assert restarted.get_booking_status('key')['status'] == status
                assert len(restarted.list_bookings('alice')) == count
                with restarted.store.connect() as db:
                    assert db.execute('SELECT count(*) FROM provider_operation_outcomes').fetchone()[0] == 1
                    assert db.execute('SELECT count(*) FROM provider_bookings').fetchone()[0] == count

    def test_timeout_after_success_same_key_replay_after_expiry_and_restart(self):
        setup = self.new_setup()
        path, clock, make = setup
        p = make('timeout_after_success')
        pid, slots = selection(p)
        h = p.hold_slot(pid, slots[0])
        error('timeout', lambda: p.book(h['hold_id'], 'stable'))
        truth = p.get_booking_status('stable')
        clock.value += timedelta(hours=1)
        restarted = ProviderMock(path, user_id='alice', clock=clock)
        assert restarted.book(h['hold_id'], 'stable') == {'booking_id': truth['booking_id']}
        assert len(restarted.list_bookings('alice')) == 1
        error('slot_taken', lambda: restarted.book(h['hold_id'], 'new-key'))

    def test_same_key_dedupe_changed_payload_and_cross_action(self):
        setup = self.new_setup()
        _, _, make = setup
        p = make()
        bid, pid, slots, h = booked(p)
        assert p.book(h['hold_id'], 'book-1') == {'booking_id': bid}
        other = p.hold_slot(pid, slots[1])
        error('idempotency_payload_mismatch', lambda: p.book(other['hold_id'], 'book-1'))
        error('idempotency_payload_mismatch', lambda: p.cancel(bid, 'book-1'))
        assert len(p.list_bookings('alice')) == 1
        assert p.get_booking_status('missing') == {'status': 'not_found'}

    def test_cancel_503_retry_same_key_survives_restart(self):
        setup = self.new_setup()
        path, clock, make = setup
        p = make()
        bid, pid, slots, _ = booked(p)
        exc = error('transient_503', lambda: p.cancel(bid, 'cancel-1'))
        assert exc.http_status == 503
        assert p.list_bookings('alice')[0]['status'] == 'booked'
        restarted = ProviderMock(path, user_id='alice', clock=clock)
        assert restarted.cancel(bid, 'cancel-1') == {'status': 'cancelled'}
        assert restarted.cancel(bid, 'cancel-1') == {'status': 'cancelled'}
        assert restarted.list_bookings('alice')[0]['status'] == 'cancelled'
        assert restarted.get_booking_status('book-1') == {'status': 'failed'}
        assert slots[0] in selection(restarted)[1]
        with restarted.store.connect() as db:
            assert db.execute("SELECT attempts FROM provider_operation_outcomes WHERE action='cancel'").fetchone()[0] == 2

    def test_cancel_changed_payload_rejected_during_transient(self):
        setup = self.new_setup()
        _, _, make = setup
        p = make()
        bid, _, _, _ = booked(p)
        error('transient_503', lambda: p.cancel(bid, 'cancel'))
        error('idempotency_payload_mismatch', lambda: p.cancel('different-booking', 'cancel'))
        assert p.cancel(bid, 'cancel') == {'status': 'cancelled'}

    def test_reschedule_success_replay_and_changed_payload(self):
        setup = self.new_setup()
        path, clock, make = setup
        p = make()
        bid, pid, slots, _ = booked(p)
        response = p.reschedule(bid, slots[1], 'move')
        assert response == {'id': bid, 'provider': pid, 'service': 'plumber', 'slot': slots[1], 'status': 'booked'}
        restarted = ProviderMock(path, user_id='alice', clock=clock)
        assert restarted.reschedule(bid, slots[1], 'move') == response
        error('idempotency_payload_mismatch', lambda: p.reschedule(bid, slots[2], 'move'))
        assert p.list_bookings('alice') == [response]
        assert slots[0] in selection(p)[1] and slots[1] not in selection(p)[1]

    def test_configured_reschedule_conflict_retains_old_slot(self):
        setup = self.new_setup()
        _, _, make = setup
        target = (NOW + timedelta(days=1, hours=2)).isoformat()
        p = make(config=ScenarioConfig(book_branch='book_success', reschedule_conflicts=(target,)))
        bid, _, slots, _ = booked(p)
        assert target == slots[1]
        error('slot_conflict', lambda: p.reschedule(bid, target, 'move'))
        error('slot_conflict', lambda: p.reschedule(bid, target, 'move'))
        assert p.list_bookings('alice')[0]['slot'] == slots[0]

    def test_reschedule_occupied_and_held_slot_conflict(self):
        setup = self.new_setup()
        _, _, make = setup
        p = make()
        bid, pid, slots, _ = booked(p)
        h = p.hold_slot(pid, slots[1])
        error('slot_conflict', lambda: p.reschedule(bid, slots[1], 'held-target'))
        p.book(h['hold_id'], 'other')
        error('slot_conflict', lambda: p.reschedule(bid, slots[1], 'occupied-target'))
        assert p.list_bookings('alice')[0]['slot'] in (slots[0], slots[1])
        assert next((b for b in p.list_bookings('alice') if b['id'] == bid))['slot'] == slots[0]

    def test_user_isolation_hold_booking_status_and_key(self):
        setup = self.new_setup()
        path, clock, make = setup
        a = make()
        bid, pid, slots, h = booked(a)
        b = ProviderMock(path, user_id='bob', clock=clock)
        assert b.list_bookings('bob') == []
        error('forbidden', lambda: b.list_bookings('alice'))
        error('forbidden', lambda: b.get_booking_status('book-1'))
        error('forbidden', lambda: b.book(h['hold_id'], 'book-1'))
        assert error('forbidden', lambda: b.cancel(bid, 'stolen-cancel')).http_status == 403
        error('forbidden', lambda: b.reschedule(bid, slots[1], 'stolen-move'))
        h2 = a.hold_slot(pid, slots[2])
        error('forbidden', lambda: b.book(h2['hold_id'], 'stolen-hold'))
        assert a.list_bookings('alice')[0]['status'] == 'booked'

    def test_sqlite_constraints_and_restart_config(self):
        setup = self.new_setup()
        path, clock, make = setup
        p = make(config=ScenarioConfig(book_branch='book_success', quote_delta=100))
        bid, pid, slots, h = booked(p)
        with p.store.connect() as db:
            assert db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
            assert db.execute('PRAGMA foreign_keys').fetchone()[0] == 1
            assert db.execute('PRAGMA busy_timeout').fetchone()[0] == 5000
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        with self.assertRaises(sqlite3.IntegrityError):
            with p.store.connect(write=True) as db:
                db.execute('INSERT INTO provider_slots(provider_id,slot) VALUES (?,?)', ('nonexistent', slots[0]))
        with self.assertRaises(sqlite3.IntegrityError):
            with p.store.connect(write=True) as db:
                other = 'other-hold'
                db.execute('INSERT INTO provider_holds VALUES (?,?,?,?,?,?,?)', (other, 'bob', pid, slots[0], 1000, h['expires_at'], 'consumed'))
                db.execute('INSERT INTO provider_bookings VALUES (?,?,?,?,?,?,?,?)', ('duplicate', 'bob', pid, 'plumber', slots[0], 'booked', other, 1000))
        restarted = ProviderMock(path, user_id='alice', clock=clock)
        assert restarted.config == p.config
        assert len(restarted.list_bookings('alice')) == 1
        with self.assertRaisesRegex(ValueError, 'config differs'):
            ProviderMock(path, clock=clock, config=ScenarioConfig(seed=999))

    def test_simultaneous_holds_only_one_wins(self):
        setup = self.new_setup()
        path, clock, make = setup
        a = make()
        b = ProviderMock(path, user_id='bob', clock=clock)
        pid, slots = selection(a)
        barrier = Barrier(2)

        def acquire(p):
            barrier.wait()
            try:
                return p.hold_slot(pid, slots[0])
            except ProviderError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(acquire, [a, b]))
        assert sum((isinstance(r, dict) for r in results)) == 1
        assert results.count('slot_unavailable') == 1

    def test_concurrent_same_key_booking_returns_one_id(self):
        setup = self.new_setup()
        path, clock, make = setup
        a = make()
        b = ProviderMock(path, user_id='alice', clock=clock)
        pid, slots = selection(a)
        h = a.hold_slot(pid, slots[0])
        barrier = Barrier(2)

        def commit(p):
            barrier.wait()
            return p.book(h['hold_id'], 'same-key')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(commit, [a, b]))
        assert results[0] == results[1]
        assert len(a.list_bookings('alice')) == 1

    def test_concurrent_different_keys_cannot_commit_same_hold_twice(self):
        path, clock, make = self.new_setup()
        a = make()
        b = ProviderMock(path, user_id='alice', clock=clock)
        pid, slots = selection(a)
        hold = a.hold_slot(pid, slots[0])
        barrier = Barrier(2)

        def commit(pair):
            client, key = pair
            barrier.wait()
            try:
                return client.book(hold['hold_id'], key)
            except ProviderError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(commit, [(a, 'key-a'), (b, 'key-b')]))
        assert sum(isinstance(r, dict) for r in results) == 1
        assert results.count('slot_taken') == 1
        assert len(a.list_bookings('alice')) == 1

    def test_real_process_exit_after_provider_timeout_preserves_truth(self):
        setup = self.new_setup()
        path, clock, make = setup
        p = make('timeout_after_success')
        pid, slots = selection(p)
        hold = p.hold_slot(pid, slots[0])
        code = "\nimport os, sys\nfrom datetime import datetime\nfrom app.provider_mock import ProviderMock, ProviderTimeout\np=ProviderMock(sys.argv[1],user_id='alice',clock=lambda: datetime.fromisoformat(sys.argv[3]))\ntry:\n    p.book(sys.argv[2], 'crash-key')\nexcept ProviderTimeout:\n    os._exit(23)\nos._exit(99)\n"
        run = subprocess.run([sys.executable, '-c', code, str(path), hold['hold_id'], NOW.isoformat()], capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1])
        assert run.returncode == 23, run.stderr
        fresh = ProviderMock(path, user_id='alice', clock=clock)
        status = fresh.get_booking_status('crash-key')
        assert status['status'] == 'booked'
        assert fresh.book(hold['hold_id'], 'crash-key')['booking_id'] == status['booking_id']
        assert len(fresh.list_bookings('alice')) == 1

    def test_expired_hold_cannot_steal_reheld_slot(self):
        setup = self.new_setup()
        path, clock, make = setup
        a = make()
        pid, slots = selection(a)
        old = a.hold_slot(pid, slots[0])
        clock.value += timedelta(minutes=10)
        b = ProviderMock(path, user_id='bob', clock=clock)
        new = b.hold_slot(pid, slots[0])
        error('hold_expired', lambda: a.book(old['hold_id'], 'late'))
        assert b.book(new['hold_id'], 'winner')['booking_id']
        assert not a.list_bookings('alice')

    def test_slot_taken_remains_unavailable_after_restart(self):
        path, clock, make = self.new_setup()
        p = make('slot_taken')
        pid, slots = selection(p)
        hold = p.hold_slot(pid, slots[0])
        error('slot_taken', lambda: p.book(hold['hold_id'], 'raced'))
        fresh = ProviderMock(path, user_id='alice', clock=clock)
        assert slots[0] not in selection(fresh)[1]
        error('slot_unavailable', lambda: fresh.hold_slot(pid, slots[0]))
        assert fresh.get_booking_status('raced') == {'status': 'failed'}
        assert fresh.list_bookings('alice') == []

    def test_timeout_without_booking_replay_preserves_truth_and_payload(self):
        path, clock, make = self.new_setup()
        p = make('timeout_without_booking')
        pid, slots = selection(p)
        hold = p.hold_slot(pid, slots[0])
        error('timeout', lambda: p.book(hold['hold_id'], 'ambiguous'))
        fresh = ProviderMock(path, user_id='alice', clock=clock)
        error('timeout', lambda: fresh.book(hold['hold_id'], 'ambiguous'))
        error('idempotency_payload_mismatch', lambda: fresh.book('different', 'ambiguous'))
        assert fresh.get_booking_status('ambiguous') == {'status': 'not_found'}
        assert fresh.list_bookings('alice') == []

    def test_live_hold_survives_fresh_process(self):
        path, clock, make = self.new_setup()
        p = make()
        pid, slots = selection(p)
        hold = p.hold_slot(pid, slots[0])
        code = """
import json, sys
from datetime import datetime
from app.provider_mock import ProviderMock
p=ProviderMock(sys.argv[1],user_id='alice',clock=lambda: datetime.fromisoformat(sys.argv[3]))
print(json.dumps(p.book(sys.argv[2], 'fresh-process')))
"""
        run = subprocess.run([sys.executable, '-c', code, str(path), hold['hold_id'], NOW.isoformat()],
                             capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1])
        assert run.returncode == 0, run.stderr
        assert p.get_booking_status('fresh-process') == {'status': 'booked', **json.loads(run.stdout)}
        assert len(p.list_bookings('alice')) == 1

    def test_baseline_statistical_smoke_over_stable_seeds(self):
        counts = {b: 0 for b in ('book_success', 'slot_taken', 'timeout_after_success', 'timeout_without_booking')}
        for seed in range(10000):
            config = ScenarioConfig(seed=seed)
            branch = config.branch_for('statistical-smoke')
            assert branch == ScenarioConfig(seed=seed).branch_for('statistical-smoke')
            counts[branch] += 1
        assert 6800 < counts['book_success'] < 7200, counts
        assert 1300 < counts['slot_taken'] < 1700, counts
        timeouts = counts['timeout_after_success'] + counts['timeout_without_booking']
        assert 1300 < timeouts < 1700, counts
        assert 0.45 < counts['timeout_after_success'] / timeouts < 0.55, counts
        print('BASELINE_10000_SEEDS=' + json.dumps(counts, sort_keys=True))

    def test_baseline_tool_delivery_matches_seeded_branch(self):
        for seed in [1, 7, 42, 71, 99, 123, 500, 20261101]:
            with self.subTest(seed=seed):
                tmp_path = self.new_dir()
                config = ScenarioConfig(seed=seed)
                p = ProviderMock(tmp_path / 'baseline.sqlite3', user_id='alice', clock=lambda: NOW, config=config)
                pid, slots = selection(p)
                hold = p.hold_slot(pid, slots[0])
                branch = config.branch_for('baseline')
                if branch == 'book_success':
                    assert p.book(hold['hold_id'], 'baseline')['booking_id']
                else:
                    error('slot_taken' if branch == 'slot_taken' else 'timeout', lambda: p.book(hold['hold_id'], 'baseline'))
                assert len(p.list_bookings('alice')) == int(branch in ('book_success', 'timeout_after_success'))

    def test_invalid_date_windows_rejected(self):
        for bad_range in [{}, {'start': 'bad', 'end': 'bad'}, {'start': '2026-11-01T09:00:00', 'end': NOW.isoformat()}, {'start': NOW.isoformat(), 'end': NOW.isoformat()}]:
            with self.subTest(bad_range=bad_range):
                setup = self.new_setup()
                _, _, make = setup
                with self.assertRaises(ProviderError):
                    make().search_providers('plumber', 'Indiranagar', bad_range)

    def test_explicit_reset_demo_is_separate_from_startup(self):
        path, clock, make = self.new_setup()
        p = make()
        booked(p)
        assert len(ProviderMock(path, user_id='alice', clock=clock).list_bookings('alice')) == 1
        run = subprocess.run([sys.executable, '-m', 'app.provider_mock', 'reset-demo', '--db', str(path)],
                             capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1])
        assert run.returncode == 0, run.stderr
        assert json.loads(run.stdout)['stage'] == 'G1 provider demo reset'
        fresh = ProviderMock(path, user_id='alice', clock=clock)
        assert fresh.list_bookings('alice') == []
        assert fresh.get_booking_status('book-1') == {'status': 'not_found'}
        assert fresh.config == ScenarioConfig()

    def test_invalid_resource_and_key_errors_do_not_book(self):
        setup = self.new_setup()
        _, _, make = setup
        p = make()
        error('provider_not_found', lambda: p.get_provider('missing'))
        error('slot_unavailable', lambda: p.hold_slot('missing', (NOW + timedelta(days=1)).isoformat()))
        error('hold_not_found', lambda: p.book('missing', 'missing-hold'))
        error('invalid_idempotency_key', lambda: p.book('missing', ''))
        error('booking_not_found', lambda: p.cancel('missing', 'cancel'))
        error('booking_not_found', lambda: p.reschedule('missing', NOW.isoformat(), 'move'))
        assert p.list_bookings('alice') == []
if __name__ == '__main__':
    unittest.main()
