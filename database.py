"""
database.py — SQLite storage + CoinGecko API for CryptoManager.
All settings come from config.py — no hardcoded values anywhere.
"""

import sqlite3, os, urllib.request, urllib.parse, json, time, hashlib, secrets
from config import DATABASE, COINGECKO

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), DATABASE["file"])


# ══════════════════════════════════════════════════════════════════════════════
#  COINGECKO API
# ══════════════════════════════════════════════════════════════════════════════

_last_call = 0

def _get(endpoint: str, params: dict = None):
    global _last_call
    gap = time.time() - _last_call
    if gap < COINGECKO["min_gap_sec"]:
        time.sleep(COINGECKO["min_gap_sec"] - gap)
    url = COINGECKO["base_url"] + endpoint
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": COINGECKO["user_agent"]}
    if COINGECKO.get("api_key"):
        headers["x-cg-demo-api-key"] = COINGECKO["api_key"]
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=COINGECKO["timeout_sec"]) as r:
            _last_call = time.time()
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  [API ERROR] {e}")
        return {}

def get_prices(coin_ids: list) -> list:
    params = {
        **COINGECKO["markets_params"],
        "vs_currency": COINGECKO["vs_currency"],
        "ids":         ",".join(coin_ids),
        "per_page":    max(len(coin_ids), 1),
    }
    data = _get(COINGECKO["endpoints"]["markets"], params)
    if not isinstance(data, list):
        return []
    return [{
        "id":                          c.get("id", ""),
        "symbol":                      c.get("symbol", "").upper(),
        "name":                        c.get("name", ""),
        "current_price":               c.get("current_price") or 0,
        "market_cap":                  c.get("market_cap") or 0,
        "total_volume":                c.get("total_volume") or 0,
        "price_change_percentage_24h": c.get("price_change_percentage_24h") or 0,
    } for c in data]

def search_coins(query: str) -> list:
    data  = _get(COINGECKO["endpoints"]["search"], {"query": query})
    limit = COINGECKO["search_limit"]
    return [
        {"id": c.get("id"), "symbol": c.get("symbol", "").upper(),
         "name": c.get("name"), "rank": c.get("market_cap_rank")}
        for c in (data.get("coins") or [])[:limit]
    ]

def get_trending() -> list:
    data  = _get(COINGECKO["endpoints"]["trending"])
    limit = COINGECKO["trending_limit"]
    return [
        {"id": c["item"].get("id"), "name": c["item"].get("name"),
         "symbol": c["item"].get("symbol", "").upper()}
        for c in (data.get("coins") or [])[:limit]
    ]

def ping() -> bool:
    data = _get(COINGECKO["endpoints"]["ping"])
    return bool(data.get("gecko_says"))


# ══════════════════════════════════════════════════════════════════════════════
#  SQLITE — INIT
# ══════════════════════════════════════════════════════════════════════════════

def conn():
    c = sqlite3.connect(DB_FILE)
    c.row_factory = sqlite3.Row
    return c

def _migrate():
    """Safe migrations — adds columns to existing DBs without data loss."""
    migrations = [
        "ALTER TABLE portfolio ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE price_alerts ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE trades ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE coin_notes ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1",
    ]
    try:
        with conn() as c:
            for sql in migrations:
                try:
                    c.execute(sql)
                except Exception:
                    pass  # column already exists — safe to ignore
    except Exception:
        pass  # DB file doesn't exist yet — init_db will create it

# Run migration automatically whenever database.py is imported
_migrate()

def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS price_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            coin_id    TEXT NOT NULL,
            symbol     TEXT NOT NULL,
            name       TEXT NOT NULL,
            price_usd  REAL NOT NULL,
            market_cap REAL,
            volume_24h REAL,
            change_24h REAL,
            fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS mix_results (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            label      TEXT NOT NULL,
            coin_ids   TEXT NOT NULL,
            weights    TEXT NOT NULL,
            exp_return REAL,
            exp_risk   REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS risk_snapshots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            coin_id    TEXT NOT NULL,
            volatility REAL,
            sharpe     REAL,
            max_dd     REAL,
            risk_tier  TEXT,
            saved_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS predictions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            coin_id       TEXT NOT NULL,
            current_price REAL NOT NULL,
            pred_linreg   TEXT NOT NULL,
            pred_ma       REAL NOT NULL,
            trend         TEXT NOT NULL,
            signal        TEXT NOT NULL,
            saved_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            coin_id    TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            message    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS portfolio (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            coin_id    TEXT NOT NULL,
            symbol     TEXT NOT NULL,
            amount     REAL NOT NULL DEFAULT 0,
            avg_buy    REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, coin_id)
        );
        CREATE TABLE IF NOT EXISTS rebalance_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS price_alerts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            coin_id    TEXT NOT NULL,
            symbol     TEXT NOT NULL,
            condition  TEXT NOT NULL CHECK(condition IN ('above','below')),
            target     REAL NOT NULL,
            note       TEXT DEFAULT '',
            triggered  INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'Trader',
            avatar        TEXT NOT NULL DEFAULT 'U',
            theme         TEXT NOT NULL DEFAULT 'dark',
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS trades (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            coin_id    TEXT NOT NULL,
            symbol     TEXT NOT NULL,
            side       TEXT NOT NULL CHECK(side IN ('buy','sell')),
            amount     REAL NOT NULL,
            price      REAL NOT NULL,
            fee        REAL NOT NULL DEFAULT 0,
            note       TEXT DEFAULT '',
            traded_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS coin_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            coin_id    TEXT NOT NULL,
            note       TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, coin_id)
        );
        CREATE TABLE IF NOT EXISTS user_watchlist (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            coin_id    TEXT NOT NULL,
            symbol     TEXT NOT NULL,
            name       TEXT NOT NULL DEFAULT '',
            added_at   TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, coin_id)
        );
        """)
    print(f"  [DB] Ready  ->  {DB_FILE}")
    _seed_default_users()

def _migrate():
    """Safe migrations — adds columns/tables to existing DBs without data loss."""
    migrations = [
        "ALTER TABLE portfolio ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE price_alerts ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE trades ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE coin_notes ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1",
    ]
    with conn() as c:
        for sql in migrations:
            try:
                c.execute(sql)
            except Exception:
                pass  # column already exists — safe to ignore

def _seed_default_users():
    with conn() as c:
        count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            for username, password, role, avatar in [
                ("admin",  "admin123", "Admin",  "A"),
                ("trader", "trade456", "Trader", "T"),
                ("demo",   "demo",     "Viewer", "D"),
            ]:
                salt  = secrets.token_hex(16)
                phash = _hash_password(password, salt)
                c.execute(
                    "INSERT OR IGNORE INTO users (username,password_hash,salt,role,avatar) VALUES (?,?,?,?,?)",
                    (username, phash, salt, role, avatar))


# ══════════════════════════════════════════════════════════════════════════════
#  USERS
# ══════════════════════════════════════════════════════════════════════════════

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()

def verify_user(username: str, password: str):
    with conn() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        return None
    row = dict(row)
    if _hash_password(password, row["salt"]) == row["password_hash"]:
        return row
    return None

def create_user(username: str, password: str, role: str = "Trader") -> bool:
    salt  = secrets.token_hex(16)
    phash = _hash_password(password, salt)
    try:
        with conn() as c:
            c.execute(
                "INSERT INTO users (username,password_hash,salt,role,avatar) VALUES (?,?,?,?,?)",
                (username, phash, salt, role, username[0].upper()))
        return True
    except sqlite3.IntegrityError:
        return False

def update_user_theme(user_id: int, theme: str):
    with conn() as c:
        c.execute("UPDATE users SET theme=? WHERE id=?", (theme, user_id))


# ══════════════════════════════════════════════════════════════════════════════
#  PRICE HISTORY
# ══════════════════════════════════════════════════════════════════════════════

def save_price(coin: dict):
    with conn() as c:
        c.execute("""
            INSERT INTO price_history
                (coin_id,symbol,name,price_usd,market_cap,volume_24h,change_24h)
            VALUES (?,?,?,?,?,?,?)
        """, (coin["id"], coin["symbol"], coin["name"], coin["current_price"],
              coin["market_cap"], coin["total_volume"],
              coin["price_change_percentage_24h"]))

def get_history(coin_id: str, limit: int = 60) -> list:
    with conn() as c:
        rows = c.execute("""
            SELECT price_usd, change_24h, fetched_at FROM price_history
            WHERE coin_id=? ORDER BY fetched_at DESC LIMIT ?
        """, (coin_id, limit)).fetchall()
    return [dict(r) for r in rows]

def list_tracked() -> list:
    with conn() as c:
        rows = c.execute(
            "SELECT DISTINCT coin_id, symbol, name FROM price_history"
        ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
#  MIXES / RISK / PREDICTIONS / SYSTEM ALERTS
# ══════════════════════════════════════════════════════════════════════════════

def save_mix(label, coin_ids, weights, exp_return, exp_risk):
    with conn() as c:
        c.execute("""
            INSERT INTO mix_results (label,coin_ids,weights,exp_return,exp_risk)
            VALUES (?,?,?,?,?)
        """, (label, ",".join(coin_ids),
              ",".join(f"{w:.6f}" for w in weights), exp_return, exp_risk))

def get_mixes(limit=10):
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM mix_results ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

def save_risk(coin_id, vol, sharpe, dd, tier):
    with conn() as c:
        c.execute(
            "INSERT INTO risk_snapshots (coin_id,volatility,sharpe,max_dd,risk_tier) VALUES (?,?,?,?,?)",
            (coin_id, vol, sharpe, dd, tier))

def save_prediction(coin_id, current_price, pred_linreg, pred_ma, trend, signal):
    with conn() as c:
        c.execute("""
            INSERT INTO predictions (coin_id,current_price,pred_linreg,pred_ma,trend,signal)
            VALUES (?,?,?,?,?,?)
        """, (coin_id, current_price,
              ",".join(f"{p:.6f}" for p in pred_linreg),
              pred_ma, trend, signal))

def get_predictions(coin_id: str, limit: int = 5) -> list:
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM predictions WHERE coin_id=? ORDER BY saved_at DESC LIMIT ?",
            (coin_id, limit)).fetchall()
    return [dict(r) for r in rows]

def save_alert(coin_id, alert_type, message):
    with conn() as c:
        c.execute(
            "INSERT INTO alerts (coin_id,alert_type,message) VALUES (?,?,?)",
            (coin_id, alert_type, message))


# ══════════════════════════════════════════════════════════════════════════════
#  PORTFOLIO  (per-user)
# ══════════════════════════════════════════════════════════════════════════════

def upsert_position(coin_id, symbol, amount, avg_buy, user_id=1):
    with conn() as c:
        c.execute("""
            INSERT INTO portfolio (user_id,coin_id,symbol,amount,avg_buy)
            VALUES (?,?,?,?,?)
            ON CONFLICT(user_id,coin_id) DO UPDATE SET
                amount=excluded.amount, avg_buy=excluded.avg_buy,
                updated_at=datetime('now')
        """, (user_id, coin_id, symbol, amount, avg_buy))

def delete_position(coin_id, user_id=1):
    with conn() as c:
        c.execute("DELETE FROM portfolio WHERE coin_id=? AND user_id=?", (coin_id, user_id))

def clear_all_positions(user_id=1):
    with conn() as c:
        c.execute("DELETE FROM portfolio WHERE user_id=?", (user_id,))

def get_portfolio(user_id=1):
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM portfolio WHERE user_id=? ORDER BY updated_at", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]

def log_rebalance(description):
    with conn() as c:
        c.execute("INSERT INTO rebalance_log (description) VALUES (?)", (description,))


# ══════════════════════════════════════════════════════════════════════════════
#  PRICE ALERTS  (user-defined)
# ══════════════════════════════════════════════════════════════════════════════

def add_price_alert(coin_id, symbol, condition, target, note="", user_id=1):
    with conn() as c:
        c.execute("""
            INSERT INTO price_alerts (user_id,coin_id,symbol,condition,target,note)
            VALUES (?,?,?,?,?,?)
        """, (user_id, coin_id, symbol.upper(), condition, float(target), note))

def get_price_alerts(include_triggered=False, user_id=1):
    with conn() as c:
        if include_triggered:
            rows = c.execute(
                "SELECT * FROM price_alerts WHERE user_id=? ORDER BY created_at DESC",
                (user_id,)).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM price_alerts WHERE user_id=? AND triggered=0 ORDER BY created_at DESC",
                (user_id,)).fetchall()
    return [dict(r) for r in rows]

def delete_price_alert(alert_id, user_id=1):
    with conn() as c:
        c.execute("DELETE FROM price_alerts WHERE id=? AND user_id=?", (alert_id, user_id))

def check_and_fire_alerts(live_prices: dict) -> list:
    fired = []
    with conn() as c:
        rows = c.execute("SELECT * FROM price_alerts WHERE triggered=0").fetchall()
        for row in rows:
            r     = dict(row)
            price = live_prices.get(r["coin_id"])
            if price is None:
                continue
            hit = (r["condition"] == "above" and price >= r["target"]) or \
                  (r["condition"] == "below" and price <= r["target"])
            if hit:
                c.execute("UPDATE price_alerts SET triggered=1 WHERE id=?", (r["id"],))
                fired.append({**r, "current_price": price})
    return fired


# ══════════════════════════════════════════════════════════════════════════════
#  TRADES  (transaction log with FIFO P&L)
# ══════════════════════════════════════════════════════════════════════════════

def add_trade(user_id, coin_id, symbol, side, amount, price, fee=0, note=""):
    with conn() as c:
        c.execute("""
            INSERT INTO trades (user_id,coin_id,symbol,side,amount,price,fee,note)
            VALUES (?,?,?,?,?,?,?,?)
        """, (user_id, coin_id, symbol.upper(), side,
              float(amount), float(price), float(fee), note))

def get_trades(user_id=1, coin_id=None, limit=100):
    with conn() as c:
        if coin_id:
            rows = c.execute(
                "SELECT * FROM trades WHERE user_id=? AND coin_id=? ORDER BY traded_at DESC LIMIT ?",
                (user_id, coin_id, limit)).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM trades WHERE user_id=? ORDER BY traded_at DESC LIMIT ?",
                (user_id, limit)).fetchall()
    return [dict(r) for r in rows]

def get_realised_pnl(user_id=1):
    """FIFO realised P&L per coin."""
    trades = get_trades(user_id, limit=10000)
    coins  = {}
    for t in reversed(trades):
        cid = t["coin_id"]
        if cid not in coins:
            coins[cid] = {"symbol": t["symbol"], "buy_queue": [],
                          "realised": 0.0, "total_bought": 0.0, "total_sold": 0.0}
        c = coins[cid]
        if t["side"] == "buy":
            c["buy_queue"].append({"amount": t["amount"], "price": t["price"]})
            c["total_bought"] += t["amount"] * t["price"]
        else:
            sell_amt = t["amount"]
            c["total_sold"] += t["amount"] * t["price"]
            while sell_amt > 0 and c["buy_queue"]:
                buy     = c["buy_queue"][0]
                matched = min(sell_amt, buy["amount"])
                c["realised"] += matched * (t["price"] - buy["price"])
                buy["amount"] -= matched
                sell_amt      -= matched
                if buy["amount"] <= 0:
                    c["buy_queue"].pop(0)
    return [
        {"coin_id": cid, "symbol": v["symbol"],
         "realised_pnl":  round(v["realised"], 4),
         "total_bought":  round(v["total_bought"], 4),
         "total_sold":    round(v["total_sold"], 4)}
        for cid, v in coins.items()
    ]


# ══════════════════════════════════════════════════════════════════════════════
#  COIN NOTES
# ══════════════════════════════════════════════════════════════════════════════

def upsert_coin_note(user_id, coin_id, note):
    with conn() as c:
        c.execute("""
            INSERT INTO coin_notes (user_id,coin_id,note)
            VALUES (?,?,?)
            ON CONFLICT(user_id,coin_id) DO UPDATE SET
                note=excluded.note, updated_at=datetime('now')
        """, (user_id, coin_id, note))

def get_coin_notes(user_id=1) -> dict:
    with conn() as c:
        rows = c.execute(
            "SELECT coin_id, note, updated_at FROM coin_notes WHERE user_id=?",
            (user_id,)).fetchall()
    return {r["coin_id"]: {"note": r["note"], "updated_at": r["updated_at"]} for r in rows}

def get_coin_note(user_id, coin_id) -> str:
    with conn() as c:
        row = c.execute(
            "SELECT note FROM coin_notes WHERE user_id=? AND coin_id=?",
            (user_id, coin_id)).fetchone()
    return row["note"] if row else ""


# ══════════════════════════════════════════════════════════════════════════════
#  USER WATCHLIST  (dynamic, per-user)
# ══════════════════════════════════════════════════════════════════════════════

def get_user_watchlist(user_id=1) -> list:
    with conn() as c:
        rows = c.execute(
            "SELECT coin_id, symbol, name FROM user_watchlist WHERE user_id=? ORDER BY added_at",
            (user_id,)).fetchall()
    return [dict(r) for r in rows]

def add_to_watchlist(user_id, coin_id, symbol, name="") -> bool:
    try:
        with conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO user_watchlist (user_id,coin_id,symbol,name) VALUES (?,?,?,?)",
                (user_id, coin_id, symbol.upper(), name))
        return True
    except Exception:
        return False

def remove_from_watchlist(user_id, coin_id):
    with conn() as c:
        c.execute(
            "DELETE FROM user_watchlist WHERE user_id=? AND coin_id=?",
            (user_id, coin_id))