from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import uuid
from datetime import datetime
from app.postgres_store import execute, execute_returning, fetch_one, fetch_all, is_database_url_configured
from app.game_engine import Player, PlayerColor

router = APIRouter()


class CreateTournamentRequest(BaseModel):
    title: str
    game_type: str  # 'chess' or 'ludo'
    entry_fee: float = 0.0
    max_players: int = 2
    owner: str | None = None


@router.post('/tournaments/create')
async def create_tournament(req: CreateTournamentRequest):
    tid = uuid.uuid4().hex
    if is_database_url_configured():
        q = """
        INSERT INTO tournaments (id, title, game_type, entry_fee, max_players, owner, metadata, created_at)
        VALUES (%(id)s, %(title)s, %(game_type)s, %(entry_fee)s, %(max_players)s, %(owner)s, %(metadata)s, now())
        RETURNING id, title, game_type, entry_fee, max_players, owner, status, metadata, created_at
        """
        params = {
            'id': tid,
            'title': req.title,
            'game_type': req.game_type,
            'entry_fee': float(req.entry_fee),
            'max_players': int(req.max_players),
            'owner': req.owner,
            'metadata': {}
        }
        inserted = execute_returning(q, params)
        return {'success': True, 'tournament': inserted}

    # In-memory fallback
    if '_MEMORY_TOURNAMENTS' not in globals():
        global _MEMORY_TOURNAMENTS
        _MEMORY_TOURNAMENTS = {}
        global _MEMORY_PARTICIPANTS
        _MEMORY_PARTICIPANTS = {}

    rec = {
        'id': tid,
        'title': req.title,
        'game_type': req.game_type,
        'entry_fee': float(req.entry_fee),
        'max_players': int(req.max_players),
        'owner': req.owner,
        'status': 'open',
        'metadata': {},
        'created_at': datetime.utcnow().isoformat()
    }
    _MEMORY_TOURNAMENTS[tid] = rec
    _MEMORY_PARTICIPANTS[tid] = []
    return {'success': True, 'tournament': rec}


@router.get('/tournaments')
async def list_tournaments():
    if is_database_url_configured():
        rows = fetch_all('SELECT id, title, game_type, entry_fee, max_players, owner, status, metadata, created_at FROM tournaments ORDER BY created_at DESC')
        return {'success': True, 'tournaments': rows}
    return {'success': True, 'tournaments': list(_MEMORY_TOURNAMENTS.values())}


@router.get('/tournaments/{tid}')
async def get_tournament(tid: str):
    if is_database_url_configured():
        row = fetch_one('SELECT id, title, game_type, entry_fee, max_players, owner, status, metadata, created_at FROM tournaments WHERE id = %(id)s', {'id': tid})
        if not row:
            raise HTTPException(status_code=404, detail='Tournament not found')
        participants = fetch_all('SELECT user_id, status, payment_pid, joined_at FROM tournament_participants WHERE tournament_id = %(id)s', {'id': tid})
        row['participants'] = participants
        return {'success': True, 'tournament': row}

    t = _MEMORY_TOURNAMENTS.get(tid)
    if not t:
        raise HTTPException(status_code=404, detail='Tournament not found')
    parts = _MEMORY_PARTICIPANTS.get(tid, [])
    t['participants'] = parts
    return {'success': True, 'tournament': t}


class JoinRequest(BaseModel):
    user_id: str


@router.post('/tournaments/{tid}/join')
async def join_tournament(tid: str, req: JoinRequest):
    # allow access to app state for room_manager/game_engine
    request: Request | None = None
    # If FastAPI passes Request as extra parameter, pick it up via kwargs - but here we'll rely on dependency injection if provided.
    # Fetch tournament
    tour = None
    if is_database_url_configured():
        tour = fetch_one('SELECT id, title, game_type, entry_fee, max_players, owner, status FROM tournaments WHERE id = %(id)s', {'id': tid})
        if not tour:
            raise HTTPException(status_code=404, detail='Tournament not found')
        # count participants
        count = fetch_one('SELECT COUNT(*) as c FROM tournament_participants WHERE tournament_id = %(id)s', {'id': tid})
        c = int(count['c']) if count else 0
        if c >= (tour.get('max_players') or 2):
            raise HTTPException(status_code=400, detail='Tournament is full')
        # insert participant with pending status
        q = 'INSERT INTO tournament_participants (tournament_id, user_id, status, joined_at) VALUES (%(tid)s, %(user)s, %(status)s, now()) RETURNING id'
        params = {'tid': tid, 'user': req.user_id, 'status': 'pending'}
        inserted = execute_returning(q, params)
        # if entry fee > 0, indicate payment required
        requires_payment = float(tour.get('entry_fee') or 0) > 0
        # After inserting participant, check if tournament is full and all participants paid -> start match
        try:
            # fetch participants
            parts = fetch_all('SELECT user_id, status FROM tournament_participants WHERE tournament_id = %(id)s', {'id': tid})
            ready = len(parts) >= (tour.get('max_players') or 2)
            if ready:
                # require 'paid' for paid tournaments
                if float(tour.get('entry_fee') or 0) > 0:
                    all_paid = all((p.get('status') == 'paid') for p in parts)
                else:
                    all_paid = True

                if all_paid:
                    try:
                        # create room and add players
                        rm = None
                        from fastapi import Request as _Req
                        # attempt to retrieve room_manager from the global app if available
                        try:
                            import inspect, sys
                            # traverse call stack to find FastAPI app reference if possible
                        except Exception:
                            pass
                        # safe import of main app state
                        try:
                            from app import main as _main
                            rm = getattr(_main, 'room_manager', None)
                        except Exception:
                            rm = None
                        if rm:
                            maxp = int(tour.get('max_players') or 2)
                            room = rm.create_room(room_name=f"Tourn_{tid}", creator_id=tour.get('owner') or parts[0].get('user_id'), max_players=maxp)
                            # add players with sequential colors
                            colors = list(PlayerColor)
                            for i, p in enumerate(parts):
                                uid = p.get('user_id')
                                color = colors[i % len(colors)]
                                player = Player(id=uid, name=uid, color=color)
                                try:
                                    room.add_player(player)
                                except Exception:
                                    pass
                            # start game
                            rm.start_room_game(room.room_id)
                            # update tournament status
                            execute('UPDATE tournaments SET status = %(status)s WHERE id = %(id)s', {'status': 'running', 'id': tid})
                            try:
                                from app import socketio
                                socketio.emit('tournament_update', {
                                    'tournament_id': tid,
                                    'status': 'running',
                                    'room_id': room.room_id,
                                    'roomId': room.room_id,
                                    'participant_count': len(parts),
                                    'max_players': maxp,
                                })
                            except Exception:
                                pass
                    except Exception:
                        pass

        except Exception:
            pass

        return {'success': True, 'participant': inserted, 'requires_payment': requires_payment, 'entry_fee': float(tour.get('entry_fee') or 0)}

    # in-memory fallback
    t = _MEMORY_TOURNAMENTS.get(tid)
    if not t:
        raise HTTPException(status_code=404, detail='Tournament not found')
    parts = _MEMORY_PARTICIPANTS.setdefault(tid, [])
    if len(parts) >= (t.get('max_players') or 2):
        raise HTTPException(status_code=400, detail='Tournament is full')
    p = {'user_id': req.user_id, 'status': 'pending', 'joined_at': datetime.utcnow().isoformat()}
    parts.append(p)
    requires_payment = float(t.get('entry_fee') or 0) > 0
    # if tournament filled, and all paid (or free), create room via RoomManager
    try:
        if len(parts) >= (t.get('max_players') or 2):
            all_paid = all((pp.get('status') == 'paid') for pp in parts) if float(t.get('entry_fee') or 0) > 0 else True
            if all_paid:
                try:
                    from app import main as _main
                    rm = getattr(_main, 'room_manager', None)
                    if rm:
                        maxp = int(t.get('max_players') or 2)
                        room = rm.create_room(room_name=f"Tourn_{tid}", creator_id=t.get('owner') or parts[0].get('user_id'), max_players=maxp)
                        colors = list(PlayerColor)
                        for i, pp in enumerate(parts):
                            uid = pp.get('user_id')
                            color = colors[i % len(colors)]
                            player = Player(id=uid, name=uid, color=color)
                            try:
                                room.add_player(player)
                            except Exception:
                                pass
                        rm.start_room_game(room.room_id)
                        t['status'] = 'running'
                        try:
                            from app import socketio
                            socketio.emit('tournament_update', {
                                'tournament_id': tid,
                                'status': 'running',
                                'room_id': room.room_id,
                                'roomId': room.room_id,
                                'participant_count': len(parts),
                                'max_players': int(t.get('max_players') or 2),
                            })
                        except Exception:
                            pass
                except Exception:
                    pass
    except Exception:
        pass

    return {'success': True, 'participant': p, 'requires_payment': requires_payment, 'entry_fee': float(t.get('entry_fee') or 0)}



@router.post('/tournaments/{tid}/force_start')
async def force_start_tournament(tid: str):
    """Test helper: force-start a tournament (create room and start game)."""
    # load tournament
    if is_database_url_configured():
        tour = fetch_one('SELECT id, title, game_type, entry_fee, max_players, owner, status FROM tournaments WHERE id = %(id)s', {'id': tid})
        if not tour:
            raise HTTPException(status_code=404, detail='Tournament not found')
        parts = fetch_all('SELECT user_id, status FROM tournament_participants WHERE tournament_id = %(id)s', {'id': tid})
        try:
            from app import main as _main
            rm = getattr(_main, 'room_manager', None)
            if rm:
                room = rm.create_room(room_name=f"Tourn_{tid}", creator_id=tour.get('owner') or (parts[0].get('user_id') if parts else 'sys'), max_players=int(tour.get('max_players') or 2))
                colors = list(PlayerColor)
                for i, p in enumerate(parts):
                    uid = p.get('user_id')
                    color = colors[i % len(colors)]
                    player = Player(id=uid, name=uid, color=color)
                    try:
                        room.add_player(player)
                    except Exception:
                        pass
                rm.start_room_game(room.room_id)
                execute('UPDATE tournaments SET status = %(status)s WHERE id = %(id)s', {'status': 'running', 'id': tid})
                try:
                    from app import socketio
                    socketio.emit('tournament_update', {
                        'tournament_id': tid,
                        'status': 'running',
                        'room_id': room.room_id,
                        'roomId': room.room_id,
                        'participant_count': len(parts),
                        'max_players': int(tour.get('max_players') or 2),
                    })
                except Exception:
                    pass
                return {'success': True, 'roomId': room.room_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail='Room manager not available')

    # in-memory
    t = _MEMORY_TOURNAMENTS.get(tid)
    if not t:
        raise HTTPException(status_code=404, detail='Tournament not found')
    parts = _MEMORY_PARTICIPANTS.get(tid, [])
    try:
        from app import main as _main
        rm = getattr(_main, 'room_manager', None)
        if rm:
            room = rm.create_room(room_name=f"Tourn_{tid}", creator_id=t.get('owner') or (parts[0].get('user_id') if parts else 'sys'), max_players=int(t.get('max_players') or 2))
            colors = list(PlayerColor)
            for i, p in enumerate(parts):
                uid = p.get('user_id')
                color = colors[i % len(colors)]
                player = Player(id=uid, name=uid, color=color)
                try:
                    room.add_player(player)
                except Exception:
                    pass
            rm.start_room_game(room.room_id)
            t['status'] = 'running'
            try:
                from app import socketio
                socketio.emit('tournament_update', {
                    'tournament_id': tid,
                    'status': 'running',
                    'room_id': room.room_id,
                    'roomId': room.room_id,
                    'participant_count': len(parts),
                    'max_players': int(t.get('max_players') or 2),
                })
            except Exception:
                pass
            return {'success': True, 'roomId': room.room_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=500, detail='Room manager not available')
