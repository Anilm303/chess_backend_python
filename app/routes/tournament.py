# app/routes/tournament.py
import os
from flask import Blueprint, request, jsonify, current_app
from app.postgres_store import fetch_all, fetch_one, execute
from datetime import datetime

from flask_jwt_extended import jwt_required, get_jwt_identity

# Blueprint for tournament endpoints

tournament_bp = Blueprint('tournament', __name__)

# Helper to convert Decimal to float for JSON serialization
def _decimal_to_float(value):
    try:
        return float(value)
    except Exception:
        return value

# Create a tournament
@tournament_bp.route('/create', methods=['POST'])
@jwt_required()
def create_tournament():
    data = request.get_json(silent=True) or {}
    required = ['title', 'game_type', 'entry_fee', 'max_players']
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({
            'success': False,
            'message': f"Missing fields: {', '.join(missing)}"
        }), 400
    
    owner = get_jwt_identity()
    data['owner'] = owner

    # Insert tournament
    query = """
        INSERT INTO tournaments (id, title, game_type, entry_fee, max_players, owner, status, created_at)
        VALUES (gen_random_uuid()::text, %(title)s, %(game_type)s, %(entry_fee)s, %(max_players)s, %(owner)s, 'open', NOW())
        RETURNING id, title, game_type, entry_fee, max_players, owner, status, created_at
    """
    try:
        res = fetch_one(query, data)
        return jsonify({
            'success': True,
            'tournament': {k: _decimal_to_float(v) for k, v in res.items()}
        })
    except Exception as e:
        current_app.logger.exception('Failed to create tournament')
        return jsonify({'success': False, 'message': str(e)}), 500

# List all tournaments
@tournament_bp.route('', methods=['GET'])
@jwt_required(optional=True)
def list_tournaments():
    query = "SELECT * FROM tournaments ORDER BY created_at DESC"
    rows = fetch_all(query)

    # Calculate paid participants for each tournament
    tournaments = []
    for row in rows:
        t = {k: _decimal_to_float(v) for k, v in row.items()}
        # Count paid participants
        count_query = "SELECT COUNT(*)::int as count FROM tournament_participants WHERE tournament_id = %(tid)s AND status = 'paid'"
        count_res = fetch_one(count_query, {'tid': t['id']})
        t['paid_players'] = count_res['count'] if count_res else 0
        tournaments.append(t)

    return jsonify({'success': True, 'tournaments': tournaments})

# Get tournament details
@tournament_bp.route('/<tid>', methods=['GET'])
@jwt_required(optional=True)
def get_tournament(tid):
    query = "SELECT * FROM tournaments WHERE id = %(tid)s"
    row = fetch_one(query, {'tid': tid})
    if not row:
        return jsonify({'success': False, 'message': 'Tournament not found'}), 404

    t = {k: _decimal_to_float(v) for k, v in row.items()}

    # Get participants and paid count
    participants_query = "SELECT * FROM tournament_participants WHERE tournament_id = %(tid)s"
    participants = fetch_all(participants_query, {'tid': tid})

    t['paid_players'] = sum(1 for p in participants if p.get('status') == 'paid')

    return jsonify({
        'success': True,
        'tournament': t,
        'participants': participants
    })

# Join tournament – simple implementation (payment handled elsewhere)
@tournament_bp.route('/<tid>/join', methods=['POST'])
@jwt_required()
def join_tournament(tid):
    user_id = get_jwt_identity()
    # Insert participant record
    query = """
        INSERT INTO tournament_participants (tournament_id, user_id, status, joined_at)
        VALUES (%(tid)s, %(user_id)s, 'joined', NOW())
        RETURNING id, tournament_id, user_id, status, joined_at
    """
    try:
        participant = fetch_one(query, {'tid': tid, 'user_id': user_id})
        return jsonify({'success': True, 'participant': {k: _decimal_to_float(v) for k, v in participant.items()}})
    except Exception as e:
        current_app.logger.exception('Failed to join tournament')
        return jsonify({'success': False, 'message': str(e)}), 500

