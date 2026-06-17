"""
app.py — CryptoManager Flask backend
Run: python app.py
"""

import os, sys, threading, time

# Force UTF-8 console output on Windows (cp1252 crashes on unicode chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import urllib.request, urllib.parse, json as _json
from functools import wraps

from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for)
from flask_socketio import SocketIO, emit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database
import milestone2_mix_calculator as m2
import milestone3_risk_predictor  as m3
import milestone4_spreading_rules as m4
import milestone5_backtest         as m5
from config import WATCHLIST, RISK, SPREAD, REPORTS, MIX, APP

app = Flask(__name__)
app.secret_key = APP["secret_key"]
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"]   = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", manage_session=False)

# ── In-memory TTL cache for expensive analysis endpoints ────────────────────
_cache = {}  # key -> {"data": ..., "ts": time.time()}
_CACHE_TTL = 30  # seconds

# ── Simple in-memory rate limiter for login/register ───────────────────────
_login_attempts = {}  # ip -> {"count": int, "first_at": float}
_LOGIN_WINDOW   = 300  # 5-minute window
_LOGIN_MAX      = 10   # max attempts per window

def _cached(key, ttl=_CACHE_TTL):
    """Return cached data if fresh, else None."""
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < ttl:
        return entry["data"]
    return None

def _set_cache(key, data):
    _cache[key] = {"data": data, "ts": time.time()}

@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(500)
def json_error(e):
    return jsonify({"ok": False, "error": str(e)}), getattr(e, "code", 500)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

def current_user_id():
    return session.get("user_id", 1)

def get_watchlist():
    """Return per-user watchlist if populated, else fall back to config WATCHLIST."""
    uid  = current_user_id()
    rows = database.get_user_watchlist(uid)
    return [r["coin_id"] for r in rows] if rows else WATCHLIST


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/")
def landing_page():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")

@app.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def do_login():
    try:
        # Rate limit check
        ip = request.remote_addr
        now = time.time()
        info = _login_attempts.get(ip, {"count": 0, "first_at": now})
        if now - info["first_at"] > _LOGIN_WINDOW:
            info = {"count": 0, "first_at": now}
        if info["count"] >= _LOGIN_MAX:
            return jsonify({"ok": False, "error": "Too many login attempts. Try again in 5 minutes."}), 429
        info["count"] += 1
        _login_attempts[ip] = info

        data     = request.get_json() or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")
        user     = database.verify_user(username, password)
        if user:
            # Reset rate limit on success
            _login_attempts.pop(ip, None)
            session["user_id"]  = user["id"]
            session["username"] = user["username"]
            session["role"]     = user["role"]
            session["avatar"]   = user["avatar"]
            session["theme"]    = user.get("theme", "dark")
            return jsonify({"ok": True, "redirect": url_for("dashboard")})
        return jsonify({"ok": False, "error": "Invalid credentials"}), 401
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"ok": False, "error": f"Server error: {str(e)}"}), 500

@app.route("/register", methods=["POST"])
def do_register():
    data     = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required"}), 400
    if len(password) < 4:
        return jsonify({"ok": False, "error": "Password must be at least 4 characters"}), 400
    ok = database.create_user(username, password, role="Trader")
    if ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": f"Username '{username}' is already taken"}), 409

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/dashboard")
@login_required
def dashboard():
    wl = get_watchlist()
    return render_template("dashboard.html",
                           username=session["username"],
                           role=session["role"],
                           avatar=session["avatar"],
                           theme=session.get("theme", "dark"),
                           watchlist=wl)


# ── API — prices & history ─────────────────────────────────────────────────────

@app.route("/api/prices")
@login_required
def api_prices():
    wl    = get_watchlist()
    coins = database.get_prices(wl)
    if coins:
        database.save_prices_batch(coins)
    return jsonify(coins or [])

@app.route("/api/history/<coin_id>")
@login_required
def api_history(coin_id):
    rows = database.get_history(coin_id, limit=10000)
    rows.reverse()
    return jsonify(rows)


# ── API — portfolio ────────────────────────────────────────────────────────────

@app.route("/api/portfolio")
@login_required
def api_portfolio():
    uid       = current_user_id()
    wl        = get_watchlist()
    # Use batch lookup — ONE query instead of N
    latest    = database.get_latest_prices(wl)
    live      = {cid: info["price_usd"] for cid, info in latest.items()}
    positions = database.get_portfolio(uid)
    result    = []
    total_val = 0.0
    for p in positions:
        price = live.get(p["coin_id"], p["avg_buy"])
        val   = p["amount"] * price
        cost  = p["amount"] * p["avg_buy"]
        pnl   = val - cost
        pnl_p = pnl / cost * 100 if cost else 0
        total_val += val
        result.append({**p, "price": price, "value": round(val, 2),
                        "pnl": round(pnl, 2), "pnl_pct": round(pnl_p, 2)})
    for r in result:
        r["alloc_pct"] = round(r["value"] / total_val * 100, 2) if total_val else 0
    return jsonify({"positions": result, "total": round(total_val, 2)})

@app.route("/api/position/<coin_id>", methods=["DELETE"])
@login_required
def api_delete_position(coin_id):
    uid = current_user_id()
    database.delete_position(coin_id, uid)
    return jsonify({"ok": True})

@app.route("/api/position/clear-all", methods=["POST"])
@login_required
def api_clear_positions():
    uid = current_user_id()
    database.clear_all_positions(uid)
    return jsonify({"ok": True})

@app.route("/api/position", methods=["POST"])
@login_required
def api_add_position():
    uid = current_user_id()
    d   = request.get_json()
    database.upsert_position(d["coin_id"], d["symbol"].upper(),
                              float(d["amount"]), float(d["avg_buy"]), uid)
    return jsonify({"ok": True})


# ── API — analysis ─────────────────────────────────────────────────────────────

@app.route("/api/risk")
@login_required
def api_risk():
    wl  = get_watchlist()
    key = f"risk:{','.join(wl)}"
    cached = _cached(key)
    if cached is not None:
        return jsonify(cached)
    # Pre-load BTC prices for Beta calculation (if coin_risk supports it)
    data = [r for c in wl for r in [m3.coin_risk(c)] if "error" not in r]
    _set_cache(key, data)
    return jsonify(data)

@app.route("/api/predictions")
@login_required
def api_predictions():
    wl  = get_watchlist()
    key = f"pred:{','.join(wl)}"
    cached = _cached(key)
    if cached is not None:
        return jsonify(cached)
    data = [p for c in wl for p in [m3.predict_coin(c)] if "error" not in p]
    _set_cache(key, data)
    return jsonify(data)

@app.route("/api/mixes")
@login_required
def api_mixes():
    wl  = get_watchlist()
    key = f"mixes:{','.join(wl)}"
    cached = _cached(key, ttl=60)
    if cached is not None:
        return jsonify(cached)
    returns = m2.task_load_returns(wl)
    mixes   = m2.task_run_mixes(returns)
    if mixes:
        # Build a serializable result
        result = {}
        for k in ["best_sharpe", "best_return", "lowest_risk", "risk_parity", "min_variance"]:
            m = mixes.get(k)
            if m and "coins" in m:
                result[k] = {
                    "coins": m["coins"],
                    "weights": [round(w, 4) for w in m["weights"]],
                    "exp_ret": m["exp_ret"],
                    "exp_risk": m["exp_risk"],
                    "sharpe": m["sharpe"],
                }
        result["correlation"] = mixes.get("correlation", {})
        result["frontier"] = mixes.get("frontier", [])
        _set_cache(key, result)
        return jsonify(result)
    return jsonify({})

def get_cached_prices(wl):
    """Get latest prices from DB cache — ONE batch query."""
    latest = database.get_latest_prices(wl)
    return {cid: info["price_usd"] for cid, info in latest.items()}

def get_cached_coins(wl):
    """Return list of coin dicts from DB cache for alert/export use — ONE batch query."""
    latest = database.get_latest_prices(wl)
    result = []
    for coin_id in wl:
        info = latest.get(coin_id)
        if info:
            result.append({
                "id": coin_id, "symbol": coin_id[:4].upper(),
                "name": coin_id, "current_price": info["price_usd"],
                "price_change_percentage_24h": info.get("change_24h", 0) or 0,
                "market_cap": 0, "total_volume": 0,
            })
    return result

@app.route("/api/alerts")
@login_required
def api_alerts():
    wl    = get_watchlist()
    coins = get_cached_coins(wl)
    return jsonify(m3.task_check_alerts(coins))

@app.route("/api/stress")
@login_required
def api_stress():
    uid       = current_user_id()
    wl        = get_watchlist()
    live      = get_cached_prices(wl)
    positions = database.get_portfolio(uid)
    total     = sum(p["amount"] * live.get(p["coin_id"], 0) for p in positions)
    scenarios = {name: {"pct": pct,
                         "pnl": round(total * pct / 100, 2),
                         "new_val": round(total * (1 + pct / 100), 2)}
                 for name, pct in SPREAD["stress_scenarios"].items()}
    return jsonify({"base": round(total, 2), "scenarios": scenarios})

@app.route("/api/run-mixes", methods=["POST"])
@login_required
def api_run_mixes():
    wl      = get_watchlist()
    returns = m2.task_load_returns(wl)
    mixes   = m2.task_run_mixes(returns)
    if mixes:
        m2.task_show_and_save(mixes)
        return jsonify({"ok": True, "message": f"{MIX['iterations']} iterations done"})
    return jsonify({"ok": False, "message": "Not enough history"}), 400

@app.route("/api/export-csv", methods=["POST"])
@login_required
def api_export_csv():
    wl      = get_watchlist()
    coins   = get_cached_coins(wl)
    risk_r  = [m3.coin_risk(c) for c in wl]
    pred_r  = [m3.predict_coin(c) for c in wl]
    alert_r = m3.task_check_alerts(coins)
    m3.task_export_csv(coins, risk_r, pred_r, alert_r)
    return jsonify({"ok": True, "dir": REPORTS["output_dir"]})


# ── API — new ML/analysis endpoints ─────────────────────────────────────────

@app.route("/api/indicators/<coin_id>")
@login_required
def api_indicators(coin_id):
    """Return full technical indicator series for a coin (RSI, MACD, Bollinger)."""
    key = f"ind:{coin_id}"
    cached = _cached(key, ttl=30)
    if cached is not None:
        return jsonify(cached)
    data = m3.get_coin_indicators(coin_id)
    if "error" not in data:
        _set_cache(key, data)
    return jsonify(data)

@app.route("/api/efficient-frontier")
@login_required
def api_efficient_frontier():
    """Return efficient frontier data for charting."""
    wl  = get_watchlist()
    key = f"frontier:{','.join(wl)}"
    cached = _cached(key, ttl=120)
    if cached is not None:
        return jsonify(cached)
    returns = m2.task_load_returns(wl)
    if len(returns) < 2:
        return jsonify({"error": "Need at least 2 coins with history"}), 400
    mixes = m2.task_run_mixes(returns)
    frontier = mixes.get("frontier", [])
    optimal  = mixes.get("best_sharpe", {})
    min_vol  = mixes.get("lowest_risk", {})
    result = {
        "frontier": [{"risk": pt["exp_risk"], "return": pt["exp_ret"],
                      "sharpe": pt["sharpe"]} for pt in frontier],
        "optimal":  {"risk": optimal.get("exp_risk", 0),
                     "return": optimal.get("exp_ret", 0),
                     "sharpe": optimal.get("sharpe", 0),
                     "coins": optimal.get("coins", []),
                     "weights": [round(w, 4) for w in optimal.get("weights", [])]},
        "min_vol":  {"risk": min_vol.get("exp_risk", 0),
                     "return": min_vol.get("exp_ret", 0),
                     "coins": min_vol.get("coins", []),
                     "weights": [round(w, 4) for w in min_vol.get("weights", [])]},
        "coins":    list(returns.keys()),
    }
    _set_cache(key, result)
    return jsonify(result)

@app.route("/api/var")
@login_required
def api_var():
    """Portfolio Value-at-Risk calculation."""
    uid  = current_user_id()
    wl   = get_watchlist()
    live = get_cached_prices(wl)
    positions = database.get_portfolio(uid)
    total = sum(p["amount"] * live.get(p["coin_id"], 0) for p in positions)

    # Aggregate portfolio returns
    all_returns = []
    for p in positions:
        cid = p["coin_id"]
        weight = (p["amount"] * live.get(cid, 0)) / total if total > 0 else 0
        rows = database.get_history(cid, limit=RISK["history_limit"])
        prices = [r["price_usd"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]
        if len(prices) >= 3:
            rets = [(prices[i] - prices[i-1]) / prices[i-1] * 100
                    for i in range(1, len(prices)) if prices[i-1] != 0]
            if not all_returns:
                all_returns = [0.0] * len(rets)
            for j in range(min(len(rets), len(all_returns))):
                all_returns[j] += rets[j] * weight

    if len(all_returns) < 5:
        return jsonify({"error": "Not enough data for VaR calculation"}), 400

    var_val  = m3.VaR(all_returns, RISK.get("var_confidence", 0.95))
    cvar_val = m3.CVaR(all_returns, RISK.get("var_confidence", 0.95))
    var_dollar = round(total * var_val / 100, 2)
    cvar_dollar = round(total * cvar_val / 100, 2)

    return jsonify({
        "portfolio_value": round(total, 2),
        "var_pct":   var_val,
        "cvar_pct":  cvar_val,
        "var_dollar":  var_dollar,
        "cvar_dollar": cvar_dollar,
        "confidence":  RISK.get("var_confidence", 0.95),
        "data_points": len(all_returns),
    })

@app.route("/api/monte-carlo")
@login_required
def api_monte_carlo():
    """Monte Carlo stress simulation."""
    uid  = current_user_id()
    wl   = get_watchlist()
    live = get_cached_prices(wl)
    n_sims = min(int(request.args.get("sims", SPREAD.get("monte_carlo_sims", 10000))), 50000)
    result = m4.monte_carlo_stress(live, n_sims, uid)
    return jsonify(result)

@app.route("/api/correlation")
@login_required
def api_correlation():
    """Correlation matrix for watchlist coins."""
    wl = get_watchlist()
    key = f"corr:{','.join(wl)}"
    cached = _cached(key, ttl=120)
    if cached is not None:
        return jsonify(cached)
    result = m4.correlation_matrix(wl)
    _set_cache(key, result)
    return jsonify(result)

@app.route("/api/risk-parity")
@login_required
def api_risk_parity():
    """Risk-parity target allocation."""
    wl = get_watchlist()
    target = m4.risk_parity_target(wl)
    uid = current_user_id()
    live = get_cached_prices(wl)
    current = m4._current_alloc(live, uid)
    return jsonify({
        "target": target,
        "current": current,
        "coins": wl,
    })

@app.route("/api/backtest-compare")
@login_required
def api_backtest_compare():
    """Multi-strategy backtest comparison for a coin."""
    coin_id = request.args.get("coin", "bitcoin")
    short_w = max(2, int(request.args.get("short_w", 5)))
    long_w  = max(5, int(request.args.get("long_w", 15)))
    capital = max(10, float(request.args.get("capital", 1000)))
    result  = m5.backtest_coin(coin_id, short_w, long_w, capital)
    if "error" in result:
        return jsonify({"error": result["error"]}), 400
    return jsonify(result)


# ── API — price alerts ─────────────────────────────────────────────────────────

@app.route("/api/price-alerts", methods=["GET"])
@login_required
def api_get_price_alerts():
    return jsonify(database.get_price_alerts(include_triggered=False, user_id=current_user_id()))

@app.route("/api/price-alerts/history", methods=["GET"])
@login_required
def api_get_alert_history():
    return jsonify(database.get_price_alerts(include_triggered=True, user_id=current_user_id()))

@app.route("/api/price-alerts", methods=["POST"])
@login_required
def api_add_price_alert():
    d         = request.get_json() or {}
    coin_id   = d.get("coin_id", "").strip()
    symbol    = d.get("symbol", coin_id[:6].upper()).strip()
    condition = d.get("condition", "")
    target    = d.get("target")
    note      = d.get("note", "")
    if not coin_id or condition not in ("above", "below") or not target:
        return jsonify({"ok": False, "error": "coin_id, condition and target required"}), 400
    database.add_price_alert(coin_id, symbol, condition, float(target), note, current_user_id())
    return jsonify({"ok": True})

@app.route("/api/price-alerts/<int:alert_id>", methods=["DELETE"])
@login_required
def api_delete_price_alert(alert_id):
    database.delete_price_alert(alert_id, current_user_id())
    return jsonify({"ok": True})


# ── API — trades ───────────────────────────────────────────────────────────────

@app.route("/api/trades", methods=["GET"])
@login_required
def api_get_trades():
    uid     = current_user_id()
    coin_id = request.args.get("coin_id")
    return jsonify(database.get_trades(uid, coin_id=coin_id, limit=200))

@app.route("/api/trades", methods=["POST"])
@login_required
def api_add_trade():
    uid = current_user_id()
    d   = request.get_json() or {}
    coin_id = d.get("coin_id", "").strip()
    symbol  = d.get("symbol", coin_id[:6].upper()).strip()
    side    = d.get("side", "")
    amount  = d.get("amount")
    price   = d.get("price")
    fee     = d.get("fee", 0)
    note    = d.get("note", "")
    if not coin_id or side not in ("buy", "sell") or not amount or not price:
        return jsonify({"ok": False, "error": "coin_id, side (buy/sell), amount, price required"}), 400
    database.add_trade(uid, coin_id, symbol, side, float(amount), float(price), float(fee), note)
    return jsonify({"ok": True})

@app.route("/api/trades/pnl", methods=["GET"])
@login_required
def api_realised_pnl():
    return jsonify(database.get_realised_pnl(current_user_id()))


# ── API — coin notes ───────────────────────────────────────────────────────────

@app.route("/api/notes", methods=["GET"])
@login_required
def api_get_notes():
    return jsonify(database.get_coin_notes(current_user_id()))

@app.route("/api/notes/<coin_id>", methods=["POST"])
@login_required
def api_save_note(coin_id):
    d    = request.get_json() or {}
    note = d.get("note", "")
    database.upsert_coin_note(current_user_id(), coin_id, note)
    return jsonify({"ok": True})


# ── API — watchlist ────────────────────────────────────────────────────────────

@app.route("/api/watchlist", methods=["GET"])
@login_required
def api_get_watchlist():
    return jsonify(database.get_user_watchlist(current_user_id()))

@app.route("/api/watchlist/search")
@login_required
def api_search_coins():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    return jsonify(database.search_coins(q))

@app.route("/api/watchlist", methods=["POST"])
@login_required
def api_add_watchlist():
    d = request.get_json() or {}
    database.add_to_watchlist(
        current_user_id(),
        d.get("coin_id", ""),
        d.get("symbol", ""),
        d.get("name", ""))
    return jsonify({"ok": True})

@app.route("/api/watchlist/<coin_id>", methods=["DELETE"])
@login_required
def api_remove_watchlist(coin_id):
    database.remove_from_watchlist(current_user_id(), coin_id)
    return jsonify({"ok": True})


# ── API — theme ────────────────────────────────────────────────────────────────

@app.route("/api/fear-greed")
@login_required
def api_fear_greed():
    # Check cache first (60s TTL for external API)
    cached = _cached("fear-greed", ttl=60)
    if cached is not None:
        return jsonify(cached)
    try:
        req  = urllib.request.Request(
            "https://api.alternative.me/fng/?limit=1",
            headers={"User-Agent": "CryptoManager/1.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = _json.loads(r.read().decode())
        item = (data.get("data") or [{}])[0]
        result = {
            "value":       int(item.get("value", 50)),
            "label":       item.get("value_classification", "Neutral"),
            "timestamp":   item.get("timestamp", ""),
        }
        _set_cache("fear-greed", result)
        return jsonify(result)
    except Exception as e:
        return jsonify({"value": 50, "label": "Unknown", "error": str(e)})

@app.route("/api/backtest")
@login_required
def api_backtest():
    coin_id  = request.args.get("coin", "bitcoin")
    short_w  = max(2,  int(request.args.get("short_w", 5)))
    long_w   = max(5,  int(request.args.get("long_w",  15)))
    capital  = max(10, float(request.args.get("capital", 1000)))
    strategy = request.args.get("strategy", "ma").lower()

    # Load prices
    rows   = database.get_history(coin_id, limit=500)
    prices = [r["price_usd"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]

    if len(prices) < long_w + 2:
        return jsonify({"error": f"Not enough history - need at least {long_w + 2} price snapshots."}), 400

    # Route to correct strategy
    if strategy == "rsi":
        result = m5.backtest_rsi(prices, capital=capital)
    elif strategy == "bollinger":
        result = m5.backtest_bollinger(prices, capital=capital)
    elif strategy == "ensemble":
        result = m5.backtest_ensemble(prices, short_w, long_w, capital=capital)
    else:
        result = m5.backtest_ma_crossover(prices, short_w, long_w, capital)

    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    result["coin_id"] = coin_id
    result["strategy"] = strategy

    # Build equity data for chart
    equity_data = []
    trades_list = result.get("trades", [])
    for i, val in enumerate(result.get("equity", []) if "equity" in result else []):
        equity_data.append({"i": i, "value": val})

    result["equity"] = equity_data[-200:] if equity_data else []

    return jsonify(result)

@app.route("/api/news")
@login_required
def api_news():
    """Generate real-time crypto market news from live price data + trending."""
    coin_filter = request.args.get("coin", "").strip().lower()
    results = []
    now = int(time.time())

    # ── Source 1: CoinGecko Trending ──────────────────────────────────────
    try:
        trending = database._get("/search/trending")
        if isinstance(trending, dict) and trending.get("coins"):
            for i, item in enumerate(trending["coins"][:10]):
                c = item.get("item", {})
                name    = c.get("name", "")
                symbol  = (c.get("symbol") or "").upper()
                coin_id = c.get("id", "")
                price_chg = 0
                try:
                    price_chg = c.get("data", {}).get("price_change_percentage_24h", {}).get("usd", 0) or 0
                except Exception:
                    pass

                if coin_filter and coin_filter not in coin_id.lower() and coin_filter not in symbol.lower():
                    continue

                if price_chg > 3:      sentiment, action = "bullish", "surging"
                elif price_chg > 0:    sentiment, action = "bullish", "rising"
                elif price_chg < -3:   sentiment, action = "bearish", "dropping"
                elif price_chg < 0:    sentiment, action = "bearish", "declining"
                else:                  sentiment, action = "neutral", "steady"

                results.append({
                    "title":      f"{name} ({symbol}) is trending on CoinGecko - price {action} {price_chg:+.1f}% in 24h",
                    "url":        f"https://www.coingecko.com/en/coins/{coin_id}",
                    "source":     "CoinGecko Trending",
                    "published":  now - i * 120,
                    "sentiment":  sentiment,
                    "votes_pos":  0, "votes_neg": 0,
                    "currencies": [symbol],
                })
    except Exception:
        pass  # CoinGecko rate limited — skip trending

    # ── Source 2: Price movements from watchlist ─────────────────────────
    try:
        coins = database.get_prices(WATCHLIST)
        for c in (coins or []):
            cid   = c.get("id", "")
            sym   = (c.get("symbol") or "").upper()
            chg24 = c.get("price_change_percentage_24h", 0) or 0
            price = c.get("current_price", 0)

            if coin_filter and coin_filter not in cid.lower() and coin_filter not in sym.lower():
                continue

            if chg24 > 5:      sentiment, headline = "bullish",  f"{sym} rallies {chg24:+.2f}% to ${price:,.2f} in the last 24 hours"
            elif chg24 > 0:    sentiment, headline = "bullish",  f"{sym} gains {chg24:+.2f}%, now trading at ${price:,.2f}"
            elif chg24 < -5:   sentiment, headline = "bearish",  f"{sym} tumbles {chg24:.2f}% to ${price:,.2f} in 24-hour selloff"
            elif chg24 < 0:    sentiment, headline = "bearish",  f"{sym} slips {chg24:.2f}%, currently at ${price:,.2f}"
            else:              sentiment, headline = "neutral",  f"{sym} holds steady at ${price:,.2f} with minimal movement"

            results.append({
                "title":      headline,
                "url":        f"https://www.coingecko.com/en/coins/{cid}",
                "source":     "CryptoManager Live",
                "published":  now - 60,
                "sentiment":  sentiment,
                "votes_pos":  0, "votes_neg": 0,
                "currencies": [sym],
            })
    except Exception:
        pass  # API unavailable — skip price news

    # ── Source 3: Fear & Greed Index ──────────────────────────────────────
    if not coin_filter:
        try:
            req = urllib.request.Request("https://api.alternative.me/fng/?limit=1",
                                         headers={"User-Agent": "CryptoManager/1.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                d = _json.loads(r.read().decode())
            item = (d.get("data") or [{}])[0]
            val   = int(item.get("value", 50))
            label = item.get("value_classification", "Neutral")
            sentiment = "bullish" if val >= 70 else "bearish" if val <= 30 else "neutral"
            results.append({
                "title":      f"Crypto Fear & Greed Index at {val} ({label}) - market sentiment update",
                "url":        "https://alternative.me/crypto/fear-and-greed-index/",
                "source":     "Fear & Greed Index",
                "published":  now - 300,
                "sentiment":  sentiment,
                "votes_pos":  0, "votes_neg": 0,
                "currencies": [],
            })
        except Exception:
            pass

    if not results:
        return jsonify([{
            "title":      "Welcome to CryptoManager News - prices are loading...",
            "url":        "#",
            "source":     "CryptoManager",
            "published":  now,
            "sentiment":  "neutral",
            "votes_pos":  0, "votes_neg": 0,
            "currencies": [],
        }])

    results.sort(key=lambda x: x["published"], reverse=True)
    return jsonify(results[:20])


@app.route("/api/theme", methods=["POST"])
@login_required
def api_set_theme():
    theme = (request.get_json() or {}).get("theme", "dark")
    database.update_user_theme(current_user_id(), theme)
    session["theme"] = theme
    return jsonify({"ok": True})


# ── SocketIO ───────────────────────────────────────────────────────────────────

_bg_started = False

def _broadcaster():
    while True:
        try:
            coins = database.get_prices(WATCHLIST)
            if coins:
                database.save_prices_batch(coins)
                socketio.emit("price_update", coins)
                # Invalidate caches so next request gets fresh data
                _cache.pop(f"risk:{','.join(WATCHLIST)}", None)
                _cache.pop(f"pred:{','.join(WATCHLIST)}", None)
                socketio.emit("alert_update", m3.task_check_alerts(coins, save=False))
                live  = {c["id"]: c["current_price"] for c in coins}
                fired = database.check_and_fire_alerts(live)
                if fired:
                    socketio.emit("price_alert_fired", fired)
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"[Broadcast] {e}")
        time.sleep(60)

@socketio.on("connect")
def on_connect():
    global _bg_started
    if not _bg_started:
        threading.Thread(target=_broadcaster, daemon=True).start()
        _bg_started = True
    emit("connected", {"msg": "Live feed active"})


# ── Entry ──────────────────────────────────────────────────────────────────────

# Initialize DB on module import (needed for Vercel serverless)
database.init_db()

if __name__ == "__main__":
    # Run database maintenance (local dev only)
    from config import DATABASE
    retention = DATABASE.get("retention_days", 90)
    database.cleanup_old_history(retention)
    print("\n CryptoManager  ->  http://localhost:5000\n")
    socketio.run(app, host=APP["host"], port=APP["port"], debug=APP["debug"], use_reloader=False, allow_unsafe_werkzeug=True)