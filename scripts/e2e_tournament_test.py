"""Simple E2E script to test tournament create/join/payment/force-start flows.

Usage:
  python e2e_tournament_test.py --base http://localhost:8000

This script requires `requests` (add to requirements or pip install requests).
"""
import requests
import time
import sys
import argparse


def main(base):
    base = base.rstrip('/')
    print('Using base URL:', base)

    # 1) create tournament
    create_payload = {
        'title': 'E2E Test Tournament',
        'game_type': 'ludo',
        'entry_fee': 10,
        'max_players': 2,
    }
    r = requests.post(f'{base}/api/tournaments/create', json=create_payload)
    print('create:', r.status_code, r.text)
    tid = r.json().get('tournament', {}).get('id')
    if not tid:
        print('Failed to create tournament')
        return

    # 2) simulate two users joining and paying
    users = ['user_e2e_1', 'user_e2e_2']
    payments = []
    for u in users:
        jr = requests.post(f'{base}/api/tournaments/{tid}/join', json={'user_id': u})
        print('join', u, jr.status_code, jr.text)
        requires = jr.json().get('requires_payment', False)
        if requires:
            # create payment
            pr = requests.post(f'{base}/api/payments/esewa/create', json={'user_id': u, 'tournament_id': tid, 'amount': 10})
            print('create payment', pr.status_code, pr.text)
            pid = pr.json().get('payment', {}).get('pid')
            payments.append(pid)

    # 3) mark payments as paid (test helper)
    for pid in payments:
        if not pid:
            continue
        tr = requests.post(f'{base}/api/payments/esewa/test_mark_paid', json={'pid': pid})
        print('test_mark_paid', pid, tr.status_code, tr.text)

    # 4) force start tournament
    fr = requests.post(f'{base}/api/tournaments/{tid}/force_start')
    print('force_start', fr.status_code, fr.text)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://localhost:8000')
    args = p.parse_args()
    main(args.base)
