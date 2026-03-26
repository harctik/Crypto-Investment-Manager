"""
app.py — CryptoManager Flask backend
Run: python app.py
"""

import os, sys, threading, time
from functools import wraps

from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for)
from flask_socketio import SocketIO, emit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database
import milestone2_mix_calculator as m2
import milestone3_risk_predictor  as m3
import milestone4_spreading_rules as m4
from config import WATCHLIST, RISK, SPREAD, REPORTS, MIX, APP

app = Flask(__name__)
app.secret_key = APP["secret_key"]
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"]   = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

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
def login_page():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def do_login():
    try:
        data     = request.get_json() or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")
        user     = database.verify_user(username, password)
        if user:
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
        for c in coins:
            database.save_price(c)
    return jsonify(coins or [])

@app.route("/api/history/<coin_id>")
@login_required
def api_history(coin_id):
    rows = database.get_history(coin_id, limit=60)
    rows.reverse()
    return jsonify(rows)


# ── API — portfolio ────────────────────────────────────────────────────────────

@app.route("/api/portfolio")
@login_required
def api_portfolio():
    uid       = current_user_id()
    wl        = get_watchlist()
    # Use cached prices from DB — fast, no API call
    live = {}
    for coin_id in wl:
        rows = database.get_history(coin_id, limit=1)
        if rows:
            live[coin_id] = rows[0]["price_usd"]
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
    wl = get_watchlist()
    return jsonify([r for c in wl for r in [m3.coin_risk(c)] if "error" not in r])

@app.route("/api/predictions")
@login_required
def api_predictions():
    wl = get_watchlist()
    return jsonify([p for c in wl for p in [m3.predict_coin(c)] if "error" not in p])

@app.route("/api/mixes")
@login_required
def api_mixes():
    return jsonify(database.get_mixes(limit=3))

def get_cached_prices(wl):
    """Get latest prices from DB cache — fast, no API call."""
    live = {}
    for coin_id in wl:
        rows = database.get_history(coin_id, limit=1)
        if rows:
            live[coin_id] = rows[0]["price_usd"]
    return live

def get_cached_coins(wl):
    """Return list of coin dicts from DB cache for alert/export use."""
    result = []
    for coin_id in wl:
        rows = database.get_history(coin_id, limit=1)
        if rows:
            result.append({
                "id": coin_id, "symbol": coin_id[:4].upper(),
                "name": coin_id, "current_price": rows[0]["price_usd"],
                "price_change_percentage_24h": rows[0].get("change_24h", 0) or 0,
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
    import urllib.request, json as _json
    try:
        req  = urllib.request.Request(
            "https://api.alternative.me/fng/?limit=1",
            headers={"User-Agent": "CryptoManager/1.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = _json.loads(r.read().decode())
        item = (data.get("data") or [{}])[0]
        return jsonify({
            "value":       int(item.get("value", 50)),
            "label":       item.get("value_classification", "Neutral"),
            "timestamp":   item.get("timestamp", ""),
        })
    except Exception as e:
        return jsonify({"value": 50, "label": "Unknown", "error": str(e)})

@app.route("/api/backtest")
@login_required
def api_backtest():
    coin_id  = request.args.get("coin", "bitcoin")
    short_w  = max(2,  int(request.args.get("short_w", 5)))
    long_w   = max(5,  int(request.args.get("long_w",  15)))
    capital  = max(10, float(request.args.get("capital", 1000)))

    rows   = database.get_history(coin_id, limit=500)
    prices = [r["price_usd"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]

    if len(prices) < long_w + 2:
        return jsonify({"error": f"Not enough history — need at least {long_w + 2} price snapshots. Run milestone1 more times to collect data."}), 400

    def ma(prices, w):
        return [sum(prices[i-w:i])/w if i >= w else None for i in range(len(prices))]

    short_ma = ma(prices, short_w)
    long_ma  = ma(prices, long_w)

    cash      = capital
    holding   = 0.0
    position  = False
    trades    = []
    equity    = []
    peak      = capital
    max_dd    = 0.0

    for i in range(len(prices)):
        s, l, p = short_ma[i], long_ma[i], prices[i]
        if s is None or l is None:
            equity.append({"i": i, "price": p, "value": cash})
            continue

        # Golden cross — BUY
        if not position and short_ma[i] > long_ma[i] and \
           (i == 0 or short_ma[i-1] is None or long_ma[i-1] is None
            or short_ma[i-1] <= long_ma[i-1]):
            holding  = cash / p
            cash     = 0
            position = True
            trades.append({"type": "BUY", "price": round(p, 4), "idx": i,
                           "timestamp": rows[len(rows)-1-i]["fetched_at"] if i < len(rows) else ""})

        # Death cross — SELL
        elif position and short_ma[i] < long_ma[i] and \
             (i == 0 or short_ma[i-1] is None or long_ma[i-1] is None
              or short_ma[i-1] >= long_ma[i-1]):
            proceeds = holding * p
            buy_price = trades[-1]["price"] if trades else p
            pnl       = proceeds - (holding * buy_price)
            trades[-1].update({"sell_price": round(p, 4), "pnl": round(pnl, 4),
                               "win": pnl > 0})
            trades.append({"type": "SELL", "price": round(p, 4), "idx": i,
                           "pnl": round(pnl, 4),
                           "timestamp": rows[len(rows)-1-i]["fetched_at"] if i < len(rows) else ""})
            cash     = proceeds
            holding  = 0
            position = False

        val   = (holding * p) + cash
        peak  = max(peak, val)
        dd    = (peak - val) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)
        equity.append({"i": i, "price": round(p, 4), "value": round(val, 2)})

    final_val    = (holding * prices[-1]) + cash if holding else cash
    total_return = (final_val - capital) / capital * 100
    completed    = [t for t in trades if t["type"] == "SELL"]
    win_rate     = len([t for t in completed if t.get("win")]) / len(completed) * 100 if completed else 0

    return jsonify({
        "coin_id":      coin_id,
        "capital":      capital,
        "final_value":  round(final_val, 2),
        "total_return": round(total_return, 2),
        "max_drawdown": round(max_dd, 2),
        "total_trades": len(completed),
        "win_rate":     round(win_rate, 1),
        "equity":       equity[-200:],  # last 200 points for chart
        "trades":       trades,
    })

@app.route("/api/news")
@login_required
def api_news():
    import urllib.request, urllib.parse, json as _json
    coin    = request.args.get("coin", "").strip()
    url     = "https://cryptopanic.com/api/v1/posts/?auth_token=free&public=true&kind=news"
    if coin:
        url += f"&currencies={coin.upper()}"
    try:
        req  = urllib.request.Request(url, headers={"User-Agent": "CryptoManager/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = _json.loads(r.read().decode())
        results = []
        for p in (data.get("results") or [])[:20]:
            votes    = p.get("votes", {})
            pos      = votes.get("positive", 0) or 0
            neg      = votes.get("negative", 0) or 0
            sentiment = "bullish" if pos > neg else "bearish" if neg > pos else "neutral"
            results.append({
                "title":     p.get("title", ""),
                "url":       p.get("url", ""),
                "source":    (p.get("source") or {}).get("title", ""),
                "published": p.get("published_at", ""),
                "sentiment": sentiment,
                "votes_pos": pos,
                "votes_neg": neg,
                "currencies": [c.get("code","") for c in (p.get("currencies") or [])],
            })
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        time.sleep(60)
        try:
            coins = database.get_prices(WATCHLIST)
            if coins:
                for c in coins:
                    database.save_price(c)
                socketio.emit("price_update", coins)
                socketio.emit("alert_update", m3.task_check_alerts(coins))
                live  = {c["id"]: c["current_price"] for c in coins}
                fired = database.check_and_fire_alerts(live)
                if fired:
                    socketio.emit("price_alert_fired", fired)
        except Exception as e:
            print(f"[Broadcast] {e}")

@socketio.on("connect")
def on_connect():
    global _bg_started
    if not _bg_started:
        threading.Thread(target=_broadcaster, daemon=True).start()
        _bg_started = True
    emit("connected", {"msg": "Live feed active"})


# ── Entry ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    database.init_db()
    print("\n CryptoManager  →  http://localhost:5000\n")
    socketio.run(app, host=APP["host"], port=APP["port"], debug=APP["debug"], use_reloader=False)