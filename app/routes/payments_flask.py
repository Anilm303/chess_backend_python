import uuid
import hmac
import hashlib
import base64
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.postgres_store import execute, execute_returning, fetch_one, is_database_url_configured

payments_bp = Blueprint('payments', __name__)

# Environment configuration
ESEWA_MERCHANT_ID = os.getenv('ESEWA_MERCHANT_ID', 'EPAYTEST')
ESEWA_SECRET_KEY = os.getenv('ESEWA_SECRET_KEY', '8gBm/:&EnhH.1/q')
ESEWA_SUCCESS_URL = os.getenv('ESEWA_SUCCESS_URL', '')
ESEWA_FAIL_URL = os.getenv('ESEWA_FAIL_URL', '')
BASE_URL = os.getenv('BASE_URL', 'http://10.0.2.2:7860')

# eSewa sandbox (rc-epay) vs production
ESEWA_SANDBOX_URL = 'https://rc-epay.esewa.com.np/api/epay/main/v2/form'
ESEWA_PRODUCTION_URL = 'https://epay.esewa.com.np/api/epay/main/v2/form'


def _generate_signature(total_amount, transaction_uuid, product_code):
    """Generate HMAC-SHA256 signature for eSewa v2 API."""
    message = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
    hmac_obj = hmac.new(
        ESEWA_SECRET_KEY.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    )
    return base64.b64encode(hmac_obj.digest()).decode('utf-8')


@payments_bp.route('/esewa/create', methods=['POST'])
@jwt_required(optional=True)  # optional for testing; remove in production
def create_esewa_payment():
    """Create a pending eSewa payment and return parameters for the client (v2 API)."""
    # Extract request JSON
    data = request.get_json() or {}
    user_id = data.get('user_id') or get_jwt_identity()
    amount = data.get('amount')
    tournament_id = data.get('tournament_id')

    # Input validation
    if not user_id:
        return jsonify({'success': False, 'message': 'Missing user_id'}), 400
    if amount is None:
        return jsonify({'success': False, 'message': 'Missing amount'}), 400
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid amount'}), 400
    if amount <= 0:
        return jsonify({'success': False, 'message': 'Amount must be greater than 0'}), 400
    if not tournament_id:
        return jsonify({'success': False, 'message': 'Missing tournament_id'}), 400

    # Generate unique transaction UUID
    transaction_uuid = uuid.uuid4().hex
    product_code = ESEWA_MERCHANT_ID
    tax_amount = 0
    service_charge = 0
    delivery_charge = 0
    total_amount = amount + tax_amount + service_charge + delivery_charge

    # Format numbers to match exactly what is sent in payload (2 decimal places)
    formatted_total_amount = f"{total_amount:.2f}"

    # Generate HMAC-SHA256 signature
    signature = _generate_signature(formatted_total_amount, transaction_uuid, product_code)

    # Save payment record
    inserted = None
    if is_database_url_configured():
        q = """
            INSERT INTO payments (pid, user_id, tournament_id, amount, currency, status, created_at)
            VALUES (%(pid)s, %(user_id)s, %(tournament_id)s, %(amount)s, %(currency)s, 'pending', now())
            RETURNING id, pid
        """
        params = {
            'pid': transaction_uuid,
            'user_id': user_id,
            'tournament_id': tournament_id,
            'amount': amount,
            'currency': 'NPR',
        }
        inserted = execute_returning(q, params)
    else:
        inserted = {
            'id': transaction_uuid,
            'pid': transaction_uuid,
            'user_id': user_id,
            'tournament_id': tournament_id,
            'amount': amount,
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
        }
        try:
            from app.routes.payments import _MEMORY_PAYMENTS
            _MEMORY_PAYMENTS[transaction_uuid] = inserted
        except ImportError:
            pass

    # eSewa v2 payment URL (sandbox or production)
    payment_url = ESEWA_SANDBOX_URL if ESEWA_MERCHANT_ID == 'EPAYTEST' else ESEWA_PRODUCTION_URL

    # eSewa v2 form parameters
    success_url = ESEWA_SUCCESS_URL or f"{BASE_URL}/api/payments/esewa/callback"
    failure_url = ESEWA_FAIL_URL or f"{BASE_URL}/api/payments/esewa/callback?status=failed"

    esewa_params = {
        'amount': f"{amount:.2f}",
        'tax_amount': f"{tax_amount:.2f}",
        'total_amount': f"{total_amount:.2f}",
        'transaction_uuid': transaction_uuid,
        'product_code': product_code,
        'product_service_charge': f"{service_charge:.2f}",
        'product_delivery_charge': f"{delivery_charge:.2f}",
        'success_url': success_url,
        'failure_url': failure_url,
        'signed_field_names': 'total_amount,transaction_uuid,product_code',
        'signature': signature,
    }

    return jsonify({
        'success': True,
        'payment': inserted,
        'esewa': esewa_params,
        'payment_url': payment_url,
    }), 200


@payments_bp.route('/esewa/callback', methods=['GET', 'POST'])
def esewa_callback():
    """Handle eSewa payment callback (success/failure redirect)."""
    data = request.args.to_dict() if request.method == 'GET' else (request.get_json() or {})
    status = data.get('status', 'success')
    current_app.logger.info(f"eSewa callback received: {data}")
    return jsonify({'success': True, 'status': status, 'data': data}), 200
