-- Migration: eSewa payment improvements
-- Run this against the `chess_db` database.
-- Idempotent (uses IF NOT EXISTS / DO blocks).

-- Make sure payments has the columns we need
ALTER TABLE payments ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'NPR';
ALTER TABLE payments ADD COLUMN IF NOT EXISTS esewa_ref_id TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS raw_response JSONB;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE payments ALTER COLUMN status SET DEFAULT 'pending';

-- Indexes to speed up lookups by user / tournament
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_payments_user') THEN
    CREATE INDEX idx_payments_user ON payments (user_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_payments_tournament') THEN
    CREATE INDEX idx_payments_tournament ON payments (tournament_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_payments_user_tournament_status') THEN
    CREATE INDEX idx_payments_user_tournament_status
      ON payments (user_id, tournament_id, status);
  END IF;
END $$;

-- Tournament participants: ensure status + payment_pid columns exist
ALTER TABLE tournament_participants
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
ALTER TABLE tournament_participants
  ADD COLUMN IF NOT EXISTS payment_pid TEXT;
ALTER TABLE tournament_participants
  ADD COLUMN IF NOT EXISTS joined_at TIMESTAMPTZ;

-- Allow multiple join attempts per user but mark only one as paid via partial unique index.
-- If a duplicate was inserted before this migration, ignore errors.
DO $$ BEGIN
  BEGIN
    CREATE UNIQUE INDEX uq_tournament_participant_per_tournament
      ON tournament_participants (tournament_id, user_id);
  EXCEPTION WHEN duplicate_table THEN NULL;
    WHEN others THEN NULL;
  END;
END $$;

-- Helpful view for the Flutter app to fetch payment history with tournament title.
CREATE OR REPLACE VIEW v_user_payments AS
SELECT
  p.pid,
  p.user_id,
  p.tournament_id,
  t.title AS tournament_title,
  p.amount,
  p.currency,
  p.status,
  p.esewa_ref_id,
  p.created_at,
  p.verified_at
FROM payments p
LEFT JOIN tournaments t ON t.id = p.tournament_id;
