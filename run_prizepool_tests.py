"""Run the prize-pool tournament tests in in-memory mode.

Usage:
    cd chess_backend
    python run_prizepool_tests.py
"""
import os
import sys
import unittest

# Force in-memory mode BEFORE any app module is imported.
os.environ.pop('DATABASE_URL', None)
os.environ['ESEWA_MERCHANT_ID'] = 'EPAYTEST'
os.environ['ENV'] = 'development'

# Block main.py from re-loading DATABASE_URL from .env at import time.
# We do this by monkey-patching app.postgres_store.is_database_url_configured
# *before* `main` is imported.
import app.postgres_store as _pg
_pg.is_database_url_configured = lambda: False

# Drop any cached app modules so they re-read the patched helper.
for mod in list(sys.modules):
    if mod == 'main' or mod.startswith('app.'):
        del sys.modules[mod]

# Re-patch because the re-import created a fresh module.
import app.postgres_store as _pg
_pg.is_database_url_configured = lambda: False

if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName('tests.test_tournament_prizepool')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
