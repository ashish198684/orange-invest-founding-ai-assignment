"""Read-only provider inspection after one-time synthetic fixture initialization."""
import argparse
import json
from datetime import timedelta
from .tools import ProviderMock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=['inspect', 'reset-demo'], default='inspect')
    parser.add_argument('--db', default='data/provider.sqlite3')
    args = parser.parse_args()
    if args.action == 'reset-demo':
        from app.storage import Store
        # Explicit local mock reset only; never called on startup.
        with Store(args.db).connect(write=True) as db:
            for table in ('provider_operation_outcomes', 'provider_bookings',
                          'provider_holds', 'provider_slots', 'providers', 'provider_config'):
                db.execute('DELETE FROM ' + table)
        ProviderMock(args.db)
        print(json.dumps({'stage': 'G1 provider demo reset', 'database': args.db}))
        return
    provider = ProviderMock(args.db)
    now = provider._now()
    result = provider.search_providers('plumber', 'Indiranagar', {
        'start': now.isoformat(), 'end': (now + timedelta(days=8)).isoformat()})
    print(json.dumps({'stage': 'G1 provider inspection only', 'providers': result}, indent=2))


if __name__ == '__main__':
    main()
