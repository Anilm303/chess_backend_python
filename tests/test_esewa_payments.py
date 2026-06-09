"""Smoke tests for the eSewa payment flow.

These tests use FastAPI's TestClient and run without a real database
(so we exercise the in-memory fallback path in `payments.py`).
"""
import os
import unittest
from unittest.mock import patch

# Ensure tests don't accidentally hit real eSewa
os.environ.setdefault('ESEWA_MERCHANT_ID', 'EPAYTEST')
os.environ.setdefault('ENV', 'development')

from fastapi.testclient import TestClient

# Import the FastAPI app
from main import app


class EsewaPaymentTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Clear in-memory state from prior tests
        from app.routes import payments as p_mod
        from app.routes import tournaments as t_mod
        p_mod._MEMORY_PAYMENTS.clear()
        t_mod._MEMORY_TOURNAMENTS.clear()
        t_mod._MEMORY_PARTICIPANTS.clear()

    def test_create_payment_minimal(self):
        res = self.client.post(
            '/api/payments/esewa/create',
            json={'user_id': 'u1', 'amount': 100.0},
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body['success'])
        self.assertIn('pid', body['esewa'])
        self.assertEqual(body['esewa']['scd'], 'EPAYTEST')
        self.assertEqual(body['esewa']['amt'], '100.00')
        self.assertTrue(body['payment_url'].endswith('/main'))

    def test_create_payment_validation_zero_amount(self):
        res = self.client.post(
            '/api/payments/esewa/create',
            json={'user_id': 'u1', 'amount': 0},
        )
        self.assertEqual(res.status_code, 422)

    def test_create_payment_idempotency(self):
        first = self.client.post(
            '/api/payments/esewa/create',
            json={'user_id': 'u1', 'tournament_id': 't1', 'amount': 50},
        ).json()
        second = self.client.post(
            '/api/payments/esewa/create',
            json={'user_id': 'u1', 'tournament_id': 't1', 'amount': 50},
        ).json()
        # The second call should reuse the first pid (idempotency).
        self.assertEqual(first['esewa']['pid'], second['esewa']['pid'])
        self.assertTrue(second.get('reused'))
        self.assertTrue(first['success'])

    def test_status_endpoint_returns_record(self):
        create = self.client.post(
            '/api/payments/esewa/create',
            json={'user_id': 'u2', 'tournament_id': 't9', 'amount': 200},
        ).json()
        pid = create['esewa']['pid']
        status = self.client.get(f'/api/payments/esewa/status/{pid}')
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()['status'], 'pending')

    def test_history_requires_auth(self):
        res = self.client.get('/api/payments/esewa/history')
        self.assertEqual(res.status_code, 401)

    def test_history_with_token(self):
        # Simulate a JWT with sub=u3
        import base64, json
        payload = base64.urlsafe_b64encode(json.dumps({'sub': 'u3'}).encode()).rstrip(b'=').decode()
        token = f'eyJhbGciOiJIUzI1NiJ9.{payload}.signature'
        self.client.post(
            '/api/payments/esewa/create',
            json={'user_id': 'u3', 'amount': 10},
        )
        res = self.client.get(
            '/api/payments/esewa/history',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['success'])
        # Only u3's payments are returned.
        for p in body['payments']:
            self.assertEqual(p.get('user_id'), 'u3')

    def test_test_mark_paid_endpoint(self):
        create = self.client.post(
            '/api/payments/esewa/create',
            json={'user_id': 'u4', 'tournament_id': 't4', 'amount': 75},
        ).json()
        pid = create['esewa']['pid']
        res = self.client.post(
            '/api/payments/esewa/test_mark_paid',
            json={'pid': pid},
        )
        self.assertEqual(res.status_code, 200)
        status = self.client.get(f'/api/payments/esewa/status/{pid}').json()
        self.assertEqual(status['status'], 'paid')

    def test_callback_unknown_pid(self):
        res = self.client.post(
            '/api/payments/esewa/callback',
            data={'pid': 'does-not-exist', 'amt': '1.00', 'refId': 'x'},
        )
        self.assertEqual(res.status_code, 404)

    def test_tournament_list(self):
        res = self.client.get('/api/tournaments')
        self.assertEqual(res.status_code, 200)
        self.assertIn('tournaments', res.json())


if __name__ == '__main__':
    unittest.main()
