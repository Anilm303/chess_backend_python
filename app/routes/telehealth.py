from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.postgres_store import fetch_all, fetch_one, execute, execute_returning
import uuid

telehealth_bp = Blueprint('telehealth', __name__)

@telehealth_bp.route('/doctors', methods=['GET'])
@jwt_required()
def get_doctors():
    """List all available doctors"""
    query = """
        SELECT u.username, u.first_name, u.last_name, u.profile_image,
               d.specialty, d.fee_per_consultation, d.hospital_name
        FROM users u
        JOIN doctors d ON u.username = d.username
        WHERE d.is_available = TRUE
    """
    doctors = fetch_all(query)
    return jsonify({'success': True, 'doctors': doctors})

@telehealth_bp.route('/appointment/create', methods=['POST'])
@jwt_required()
def create_appointment():
    """Create a new appointment request"""
    data = request.get_json()
    patient_username = get_jwt_identity()
    doctor_username = data.get('doctor_username')

    if not doctor_username:
        return jsonify({'success': False, 'message': 'Doctor username is required'}), 400

    appointment_id = str(uuid.uuid4())
    query = """
        INSERT INTO appointments (id, patient_username, doctor_username, scheduled_at, status)
        VALUES (%(id)s, %(p)s, %(d)s, now(), 'pending')
        RETURNING id
    """
    execute(query, {'id': appointment_id, 'p': patient_username, 'd': doctor_username})

    return jsonify({'success': True, 'appointment_id': appointment_id})

@telehealth_bp.route('/appointments/me', methods=['GET'])
@jwt_required()
def get_my_appointments():
    """Get appointments for the current user (as patient or doctor)"""
    username = get_jwt_identity()
    query = """
        SELECT a.*, u.first_name as doctor_first_name, u.last_name as doctor_last_name
        FROM appointments a
        JOIN users u ON a.doctor_username = u.username
        WHERE a.patient_username = %(u)s OR a.doctor_username = %(u)s
        ORDER BY a.created_at DESC
    """
    rows = fetch_all(query, {'u': username})
    return jsonify({'success': True, 'appointments': rows})

@telehealth_bp.route('/appointment/<appointment_id>/check-call', methods=['GET'])
@jwt_required()
def check_call_permission(appointment_id):
    """Verify if the user has paid and can start the call"""
    username = get_jwt_identity()
    query = "SELECT * FROM appointments WHERE id = %(id)s"
    appointment = fetch_one(query, {'id': appointment_id})

    if not appointment:
        return jsonify({'success': False, 'message': 'Appointment not found'}), 404

    if appointment['patient_username'] != username and appointment['doctor_username'] != username:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    if not appointment['is_paid']:
        return jsonify({'success': False, 'can_call': False, 'message': 'Payment required'}), 200

    return jsonify({'success': True, 'can_call': True})

# --- Admin Panel Routes ---

@telehealth_bp.route('/admin/dashboard', methods=['GET'])
@jwt_required()
def admin_dashboard():
    """Get all doctors and appointments for admin"""
    current_user = get_jwt_identity()
    user = fetch_one("SELECT role FROM users WHERE username = %(u)s", {'u': current_user})
    if not user or user['role'] != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    doctors = fetch_all("SELECT * FROM doctors")
    appointments = fetch_all("SELECT a.*, u.first_name, u.last_name FROM appointments a JOIN users u ON a.patient_username = u.username ORDER BY a.created_at DESC")

    return jsonify({
        'success': True,
        'doctors': doctors,
        'appointments': appointments
    })
