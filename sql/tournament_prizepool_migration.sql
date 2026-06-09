-- Migration: tournament prize-pool state machine
-- Run this against the `chess_db` database.
-- Idempotent.

-- Tournaments: add prize-pool columns
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS prize_pool NUMERIC(12,2) DEFAULT 0;
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS winner_user_id TEXT;
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS platform_fee_pct NUMERIC(5,2) DEFAULT 10.00;
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ;
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Users: add wallet balance for prize payouts
ALTER TABLE users ADD COLUMN IF NOT EXISTS wallet_balance NUMERIC(12,2) DEFAULT 0;

-- Allow new tournament status values (open / waiting / in_progress / finished / cancelled).
-- The existing CHECK constraint (if any) needs to be replaced. We do this defensively:
DO $$ BEGIN
  BEGIN
    ALTER TABLE tournaments DROP CONSTRAINT IF EXISTS tournaments_status_check;
  EXCEPTION WHEN others THEN NULL;
  END;
END $$;

DO $$ BEGIN
  BEGIN
    ALTER TABLE tournaments
      ADD CONSTRAINT tournaments_status_check
      CHECK (status IN ('open','waiting','in_progress','finished','cancelled','closed','running'));
  EXCEPTION WHEN duplicate_object THEN NULL;
    WHEN others THEN NULL;
  END;
END $$;

-- Helpful view for the Flutter app's "My tournaments" screen.
CREATE OR REPLACE VIEW v_tournament_summary AS
SELECT
  t.id, t.title, t.game_type, t.entry_fee, t.max_players, t.owner,
  t.status, t.prize_pool, t.winner_user_id, t.platform_fee_pct,
  t.created_at, t.started_at, t.finished_at,
  (SELECT COUNT(*) FROM tournament_participants tp
     WHERE tp.tournament_id = t.id AND tp.status = 'paid') AS paid_players
FROM tournaments t;
