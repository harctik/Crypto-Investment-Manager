# Keeps the repo root on sys.path, so a plain `pytest tests/` (as CI runs it) can import the app modules.
import os
import tempfile

# Tests use a throwaway database and never call CoinGecko while the app starts.
# Both must be set before the app modules are imported.
os.environ["DB_FILE"] = os.path.join(tempfile.mkdtemp(prefix="quantrisk-tests-"), "test.db")
for _name in ("SEED_ADMIN_PASSWORD", "SEED_TRADER_PASSWORD", "SEED_DEMO_PASSWORD"):
    os.environ[_name] = ""

import database  # noqa: E402

database._get = lambda *args, **kwargs: {}
database._seed_price_history = lambda: None
