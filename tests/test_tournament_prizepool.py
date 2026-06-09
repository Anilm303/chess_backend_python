"""End-to-end test for the prize-pool tournament flow.

Scenario:
  1. Two users join a tournament.
  2. Both pay their entry fees (we use /test_mark_paid for speed).
  3. After the second payment the tournament state must be 'in_progress'
     and the prize pool must equal 2 * entry_fee.
  4. The first user is declared the winner.
  5. The winner's wallet must be credited with (prize_pool - 10% platform fee).
"""
import os
import unittest

# IMPORTANT: this test forces in-memory mode. It MUST be run as
#   python -m unittest tests.test_tournament_prizepool
# with DATABASE_URL unset in the shell, OR via the `run_test.py` helper below.
os.environ['ESEWA_MERCHANT_ID'] = 'EPAYTEST'
os.environ['ENV'] = 'development'
os.environ.pop('DATABASE_URL', None)

# Reload settings-aware modules so they pick up the new env.
import importlib
import sys
for mod in list(sys.modules):
    if mod.startswith('app.'):
        del sys.modules[mod]
if 'main' in sys.modules:
    del sys.modules['main']

from fastapi.testclient import TestClient
from main import app
from app.models.user import User
from app.routes import tournaments as t_mod
from app.routes import payments as p_mod
# NOTE: the helper script `run_prizepool_tests.py` unsets DATABASE_URL before
# importing this module so that the app runs in in-memory mode.


def _make_user(username: str) -> str:
    """Register a user and return their username (id)."""
    User.register(username, f'{username}@example.com', 'Test', 'User', 'pass1234')
    return username


def _jwt(username: str) -> str:
    import base64, json
    payload = base64.urlsafe_b64encode(json.dumps({'sub': username}).encode()).rstrip(b'=').decode()
    return f'eyJhbGciOiJIUzI1NiJ9.{payload}.signature'


class TournamentPrizePoolTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        t_mod._MEMORY_TOURNAMENTS.clear()
        t_mod._MEMORY_PARTICIPANTS.clear()
        p_mod._MEMORY_PAYMENTS.clear()
        # Create the two test users
        for u in ('alice', 'bob'):
            try:
                User.register(u, f'{u}@example.com', 'Test', 'User', 'pass1234')
            except Exception:
                # Already exists from a previous run; reset their wallet.
                User._persist_wallet(u, 0.0)

    def test_full_prize_pool_flow(self):
        # 1. Alice creates a tournament with entry fee NPR 10
        res = self.client.post(
            '/api/tournaments',
            json={'title': 'NPR 10 duel', 'game_type': 'chess', 'entry_fee': 10, 'max_players': 2},
            headers={'Authorization': f'Bearer {_jwt("alice")}'},
        )
        self.assertEqual(res.status_code, 200, res.text)
        tid = res.json()['tournament_id']
        self.assertEqual(res.json()['tournament']['status'], 'open')

        # 2. Both players join
        for u in ('alice', 'bob'):
            r = self.client.post(
                f'/api/tournaments/{tid}/join',
                json={'user_id': u},
                headers={'Authorization': f'Bearer {_jwt(u)}'},
            )
            self.assertEqual(r.status_code, 200, r.text)

        # 3. Both players pay (use test endpoint to skip the eSewa call)
        for u in ('alice', 'bob'):
            # Create the payment first
            cr = self.client.post(
                '/api/payments/esewa/create',
                json={'user_id': u, 'tournament_id': tid, 'amount': 10},
                headers={'Authorization': f'Bearer {_jwt(u)}'},
            )
            self.assertEqual(cr.status_code, 200, cr.text)
            pid = cr.json()['esewa']['pid']
            # Mark it paid (this also notifies the tournament)
            r = self.client.post(
                '/api/payments/esewa/test_mark_paid',
                json={'pid': pid},
            )
            self.assertEqual(r.status_code, 200, r.text)

        # 4. The tournament must be in_progress with prize_pool = 20
        t = self.client.get(f'/api/tournaments/{tid}').json()
        self.assertEqual(t['tournament']['status'], 'in_progress')
        self.assertEqual(float(t['tournament']['prize_pool']), 20.0)

        # 5. Alice wins -> her wallet is credited with 20 - 10% = 18
        r = self.client.post(
            f'/api/tournaments/{tid}/declare_winner',
            json={'winner_user_id': 'alice'},
            headers={'Authorization': f'Bearer {_jwt("alice")}'},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body['winner_user_id'], 'alice')
        self.assertEqual(body['prize_pool'], 20.0)
        self.assertEqual(body['platform_fee'], 2.0)
        self.assertEqual(body['winner_prize'], 18.0)
        self.assertEqual(body['winner_wallet_balance'], 18.0)

        # 6. Bob's wallet stays at 0
        bobs_wallet = self.client.get(
            '/api/users/bob/wallet',
            headers={'Authorization': f'Bearer {_jwt("bob")}'},
        ).json()
        self.assertEqual(bobs_wallet['wallet_balance'], 0.0)

        # 7. Cannot declare winner twice
        r2 = self.client.post(
            f'/api/tournaments/{tid}/declare_winner',
            json={'winner_user_id': 'bob'},
            headers={'Authorization': f'Bearer {_jwt("bob")}'},
        )
        self.assertEqual(r2.status_code, 400)


class PaymentNotifyTests(unittest.TestCase):
    """Verify that a single payment auto-transitions the tournament state."""

    def setUp(self):
        self.client = TestClient(app)
        t_mod._MEMORY_TOURNAMENTS.clear()
        t_mod._MEMORY_PARTICIPANTS.clear()
        p_mod._MEMORY_PAYMENTS.clear()
        for u in ('charlie', 'dave'):
            try:
                User.register(u, f'{u}@example.com', 'Test', 'User', 'pass1234')
            except Exception:
                User._persist_wallet(u, 0.0)

    def test_one_paid_player_moves_to_waiting(self):
        res = self.client.post(
            '/api/tournaments',
            json={'title': 'Duel 2', 'entry_fee': 10, 'max_players': 2},
            headers={'Authorization': f'Bearer {_jwt("charlie")}'},
        )
        tid = res.json()['tournament_id']

        # Charlie joins + pays
        self.client.post(
            f'/api/tournaments/{tid}/join',
            json={'user_id': 'charlie'},
            headers={'Authorization': f'Bearer {_jwt("charlie")}'},
        )
        cr = self.client.post(
            '/api/payments/esewa/create',
            json={'user_id': 'charlie', 'tournament_id': tid, 'amount': 10},
            headers={'Authorization': f'Bearer {_jwt("charlie")}'},
        )
        pid = cr.json()['esewa']['pid']
        self.client.post('/api/payments/esewa/test_mark_paid', json={'pid': pid})

        t = self.client.get(f'/api/tournaments/{tid}').json()
        self.assertEqual(t['tournament']['status'], 'waiting')
        self.assertEqual(float(t['tournament']['prize_pool']), 10.0)


if __name__ == '__main__':
    unittest.main()
