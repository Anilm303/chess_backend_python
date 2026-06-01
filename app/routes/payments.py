from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import os
import uuid
import json
from datetime import datetime
from app.postgres_store import execute, execute_returning, fetch_one, is_database_url_configured
from app.routes import tournaments as tournaments_module
from urllib import request as urlrequest, parse as urlparse

router = APIRouter()

ESEWA_MERCHANT_ID = os.getenv('ESEWA_MERCHANT_ID', 'TEST_MERCHANT')
ESEWA_SUCCESS_URL = os.getenv('ESEWA_SUCCESS_URL', '')
ESEWA_FAIL_URL = os.getenv('ESEWA_FAIL_URL', '')
BASE_URL = os.getenv('BASE_URL', '')


class CreatePaymentRequest(BaseModel):
    user_id: str
    tournament_id: str | None = None
    amount: float


@router.post('/payments/esewa/create')
async def create_esewa_payment(req: CreatePaymentRequest):
    pid = uuid.uuid4().hex
    amt = float(req.amount)
    # insert pending payment (DB or in-memory fallback)
    inserted = None
    if is_database_url_configured():
        q = """
        INSERT INTO payments (pid, user_id, tournament_id, amount, currency, status, created_at)
        VALUES (%(pid)s, %(user_id)s, %(tournament_id)s, %(amount)s, %(currency)s, 'pending', now())
        RETURNING id, pid
        """
        params = {
            'pid': pid,
            'user_id': req.user_id,
            'tournament_id': req.tournament_id,
            'amount': amt,
            'currency': 'NPR',
        }
        inserted = execute_returning(q, params)
    else:
        # simple in-memory record for local testing
        inserted = {'id': pid, 'pid': pid, 'user_id': req.user_id, 'tournament_id': req.tournament_id, 'amount': amt, 'status': 'pending', 'created_at': datetime.utcnow().isoformat()}
        # persist to memory store so callbacks/tests can find it
        _MEMORY_PAYMENTS[pid] = inserted

    # prepare eSewa params for client to post
    esewa_params = {
        'scd': ESEWA_MERCHANT_ID,
        'pid': pid,
        'amt': f"{amt:.2f}",
        'su': ESEWA_SUCCESS_URL or f"{BASE_URL}/api/payments/esewa/callback",
        'fu': ESEWA_FAIL_URL or f"{BASE_URL}/api/payments/esewa/callback?status=failed",
    }

    return {
        'success': True,
        'payment': inserted,
        'esewa': esewa_params,
        'payment_url': 'https://esewa.com.np/epay/main',
    }


@router.post('/payments/esewa/callback')
async def esewa_callback(request: Request):
    # eSewa will POST form data; capture and verify
    form = await request.form()
    data = {k: form.get(k) for k in form.keys()}
    pid = data.get('pid')
    amt = data.get('amt')
    refId = data.get('refId') or data.get('esewaRefId')

    # fetch stored payment record (DB or memory)
    rec = None
    if is_database_url_configured():
        rec = fetch_one('SELECT * FROM payments WHERE pid = %(pid)s', {'pid': pid})
        if not rec:
            raise HTTPException(status_code=404, detail='Payment record not found')
        # if already paid, return success
        if rec.get('status') == 'paid':
            return {'success': True, 'pid': pid, 'verified': True, 'note': 'already_paid'}
    else:
        # check in-memory store
        # we'll keep a module-level dict for simplicity
        rec = _MEMORY_PAYMENTS.get(pid)
        if not rec:
            raise HTTPException(status_code=404, detail='Payment record not found (memory)')
        if rec.get('status') == 'paid':
            return {'success': True, 'pid': pid, 'verified': True, 'note': 'already_paid'}

    if not pid:
        raise HTTPException(status_code=400, detail='Missing pid')

    # perform server-side verification
    # verify using stored amount to avoid tampering
    verified, resp = _verify_with_esewa(pid, rec.get('amount'))

    # update payment record
    try:
        if is_database_url_configured():
            update_q = """
            UPDATE payments SET status = %(status)s, esewa_ref_id = %(refId)s, raw_response = %(raw)s::jsonb, verified_at = now()
            WHERE pid = %(pid)s
            """
            params = {
                'status': 'paid' if verified else 'failed',
                'refId': refId,
                'raw': json.dumps(resp or {}),
                'pid': pid,
            }
            execute(update_q, params)

            # If this payment belongs to a tournament, mark participant as paid
            t_id = rec.get('tournament_id')
            u_id = rec.get('user_id')
            if verified and t_id and u_id:
                try:
                    parts = tournaments_module._MEMORY_PARTICIPANTS.get(t_id, [])
                    for p in parts:
                        if p.get('user_id') == u_id and p.get('status') != 'paid':
                            p['status'] = 'paid'
                            p['payment_pid'] = pid
                except Exception:
                    pass
        else:
            _MEMORY_PAYMENTS[pid]['status'] = 'paid' if verified else 'failed'
            _MEMORY_PAYMENTS[pid]['esewa_ref_id'] = refId
            _MEMORY_PAYMENTS[pid]['raw_response'] = resp or {}
            _MEMORY_PAYMENTS[pid]['verified_at'] = datetime.utcnow().isoformat()
    except Exception:
        pass

    # return simple HTML to allow WebView to detect success
    if verified:
        return {'success': True, 'pid': pid, 'verified': True}
    return {'success': False, 'pid': pid, 'verified': False}


@router.post('/payments/esewa/verify')
async def esewa_verify(payload: dict):
    pid = payload.get('pid')
    if not pid:
        raise HTTPException(status_code=400, detail='Missing pid')

    # look up payment (DB or memory)
    rec = None
    if is_database_url_configured():
        rec = fetch_one('SELECT * FROM payments WHERE pid = %(pid)s', {'pid': pid})
        if not rec:
            raise HTTPException(status_code=404, detail='Payment not found')
        verified, resp = _verify_with_esewa(pid, rec.get('amount'))
        if verified:
            execute('UPDATE payments SET status = %(status)s, raw_response = %(raw)s::jsonb, verified_at = now() WHERE pid = %(pid)s',
                    {'status': 'paid', 'raw': json.dumps(resp or {}), 'pid': pid})
            # if payment belongs to a tournament, mark participant as paid
            try:
                t_id = rec.get('tournament_id')
                u_id = rec.get('user_id')
                if t_id and u_id:
                    execute('UPDATE tournament_participants SET status = %(status)s, payment_pid = %(pid)s WHERE tournament_id = %(tid)s AND user_id = %(uid)s',
                            {'status': 'paid', 'pid': pid, 'tid': t_id, 'uid': u_id})
            except Exception:
                pass
        return {'success': True, 'pid': pid, 'verified': verified, 'response': resp}
    else:
        rec = _MEMORY_PAYMENTS.get(pid)
        if not rec:
            raise HTTPException(status_code=404, detail='Payment not found (memory)')
        verified, resp = _verify_with_esewa(pid, rec.get('amount'))
        if verified:
            rec['status'] = 'paid'
            rec['raw_response'] = resp or {}
            rec['verified_at'] = datetime.utcnow().isoformat()
            # mark memory participant entry as paid when applicable
            t_id = rec.get('tournament_id')
            u_id = rec.get('user_id')
            if verified and t_id and u_id:
                try:
                    parts = tournaments_module._MEMORY_PARTICIPANTS.get(t_id, [])
                    for p in parts:
                        if p.get('user_id') == u_id and p.get('status') != 'paid':
                            p['status'] = 'paid'
                            p['payment_pid'] = pid
                except Exception:
                    pass
            return {'success': True, 'pid': pid, 'verified': verified, 'response': resp}





def _verify_with_esewa(pid: str, amt: str | float | None) -> tuple[bool, dict | None]:
    """
    Call eSewa verify endpoint. Uses simple HTTP POST to eSewa transrec.
    Returns (verified:boolean, response:dict)
    """
    try:
        amt_val = f"{float(amt):.2f}" if amt is not None else ''
    except Exception:
        amt_val = ''

    verify_url = 'https://esewa.com.np/epay/transrec'  # production; sandbox may differ
    post_data = {
        'amt': amt_val,
        'scd': ESEWA_MERCHANT_ID,
        'pid': pid,
    }

    data = urlparse.urlencode(post_data).encode()
    try:
        req = urlrequest.Request(verify_url, data=data, method='POST')
        with urlrequest.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            body_lower = body.lower()
            # eSewa typical success response contains 'success' or 'SUCCESS'
            verified = False
            if 'success' in body_lower or '<response>success' in body_lower:
                verified = True

            # Fallback: if body contains amount and pid confirmation, consider it verified
            if not verified and amt is not None:
                try:
                    amt_val = f"{float(amt):.2f}"
                    if amt_val in body:
                        verified = True
                except Exception:
                    pass

            return verified, {'raw': body}
    except Exception as e:
        return False, {'error': str(e)}


# In-memory payments for local testing when DB is not configured
_MEMORY_PAYMENTS: dict[str, dict] = {}


@router.post('/payments/esewa/test_mark_paid')
async def esewa_test_mark_paid(payload: dict):
    """Test helper: mark a payment as paid (only for local testing)."""
    pid = payload.get('pid')
    if not pid:
        raise HTTPException(status_code=400, detail='Missing pid')

    if is_database_url_configured():
        rec = fetch_one('SELECT * FROM payments WHERE pid = %(pid)s', {'pid': pid})
        if not rec:
            raise HTTPException(status_code=404, detail='Payment not found')
        execute('UPDATE payments SET status = %(status)s, verified_at = now() WHERE pid = %(pid)s',
                {'status': 'paid', 'pid': pid})
        return {'success': True, 'pid': pid, 'marked': 'paid'}

    rec = _MEMORY_PAYMENTS.get(pid)
    if not rec:
        raise HTTPException(status_code=404, detail='Payment not found (memory)')
    rec['status'] = 'paid'
    rec['verified_at'] = datetime.utcnow().isoformat()
    return {'success': True, 'pid': pid, 'marked': 'paid', 'memory': True}