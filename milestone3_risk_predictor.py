import os, csv, smtplib, statistics, concurrent.futures
from datetime import datetime
from email.mime.text import MIMEText

import database
from config import RISK, PREDICTION, REPORTS, EMAIL, WATCHLIST


def _banner(t): print(f"\n{'═'*58}\n  {t}\n{'═'*58}")


def _linear_regression(x, y):
    n = len(x)
    sx, sy = sum(x), sum(y)
    sxy = sum(x[i] * y[i] for i in range(n))
    sxx = sum(xi**2 for xi in x)
    denom = n * sxx - sx**2
    if denom == 0:
        return 0.0, sy / n
    slope = (n * sxy - sx * sy) / denom
    return slope, (sy - slope * sx) / n


def _moving_average(prices, window):
    return [
        None if i < window - 1 else sum(prices[i - window + 1:i + 1]) / window
        for i in range(len(prices))
    ]


def _momentum_trend(prices, window=5):
    if len(prices) < window + 1:
        return "NEUTRAL"
    avg = sum(prices[-(window+1):-1]) / window
    change_pct = (prices[-1] - avg) / avg * 100
    return "BULLISH" if change_pct > 1.5 else "BEARISH" if change_pct < -1.5 else "NEUTRAL ➡"


def _ma_signal(prices, short_w, long_w):
    if len(prices) < long_w:
        return "HOLD"
    diff_pct = (sum(prices[-short_w:]) / short_w - sum(prices[-long_w:]) / long_w) / (sum(prices[-long_w:]) / long_w) * 100
    return "BUY  🟢" if diff_pct > 1.0 else "SELL 🔴" if diff_pct < -1.0 else "HOLD 🟡"


def predict_coin(coin_id):
    prices = [r["price_usd"] for r in reversed(
        database.get_history(coin_id, limit=PREDICTION["history_limit"])
    ) if r.get("price_usd", 0) > 0]

    if len(prices) < max(PREDICTION["ma_long_window"], 4):
        return {"coin_id": coin_id, "error": "not enough history for prediction"}

    n = len(prices)
    slope, intercept = _linear_regression(list(range(n)), prices)
    linreg_preds = [round(intercept + slope * xi, 6) for xi in range(n, n + PREDICTION["linreg_periods"])]
    confidence   = round(statistics.pstdev([prices[i] - (intercept + slope * i) for i in range(n)]), 6)

    short_w, long_w = PREDICTION["ma_short_window"], PREDICTION["ma_long_window"]
    short_ma = next((v for v in reversed(_moving_average(prices, short_w)) if v), None)
    long_ma  = next((v for v in reversed(_moving_average(prices, long_w))  if v), None)
    trend, signal = _momentum_trend(prices), _ma_signal(prices, short_w, long_w)

    result = {
        "coin_id":            coin_id,
        "current_price":      round(prices[-1], 6),
        "linreg_slope":       round(slope, 8),
        "slope_pct_per_snap": round(slope / prices[0] * 100 if prices[0] else 0, 4),
        "linreg_forecast":    linreg_preds,
        "linreg_next":        linreg_preds[0],
        "confidence_band":    f"±{confidence:.4f}",
        "short_ma":           round(short_ma, 6) if short_ma else None,
        "long_ma":            round(long_ma,  6) if long_ma  else None,
        "ma_next_pred":       round(short_ma, 6) if short_ma else prices[-1],
        "trend":              trend,
        "signal":             signal,
        "periods_ahead":      PREDICTION["linreg_periods"],
        "snapshots_used":     n,
    }
    database.save_prediction(coin_id, prices[-1], linreg_preds, result["ma_next_pred"], trend, signal)
    return result


def coin_risk(coin_id):
    prices = [r["price_usd"] for r in reversed(
        database.get_history(coin_id, limit=RISK["history_limit"])
    ) if r.get("price_usd", 0) > 0]

    if len(prices) < 2:
        return {"coin_id": coin_id, "error": "not enough history"}

    rets     = [(prices[i] - prices[i-1]) / prices[i-1] * 100
                for i in range(1, len(prices)) if prices[i-1] != 0]
    vol      = statistics.pstdev(rets) or 0.0001
    mean_ret = statistics.mean(rets)
    peak, dd = prices[0], 0.0
    for p in prices:
        peak = max(peak, p)
        dd   = max(dd, (peak - p) / peak * 100)

    tier = "LOW" if vol < RISK["volatility_low"] else "MEDIUM" if vol < RISK["volatility_high"] else "HIGH"
    database.save_risk(coin_id, vol, mean_ret / vol, dd, tier)

    return {
        "coin_id":      coin_id,
        "price":        round(prices[-1], 6),
        "mean_ret_%":   round(mean_ret, 4),
        "volatility_%": round(vol, 4),
        "sharpe":       round(mean_ret / vol, 4),
        "max_dd_%":     round(dd, 4),
        "risk_tier":    tier,
    }


def _run_parallel(fn, coin_ids):
    with concurrent.futures.ThreadPoolExecutor(max_workers=RISK["parallel_workers"]) as pool:
        return [f.result() for f in concurrent.futures.as_completed(
            {pool.submit(fn, cid): cid for cid in coin_ids}
        )]


def _write_csv(filename, rows, fields):
    os.makedirs(REPORTS["output_dir"], exist_ok=True)
    path = os.path.join(REPORTS["output_dir"], filename)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return path


def task_parallel_risk(coin_ids):
    _banner(f"Task 1 — Parallel Risk Check  (workers={RISK['parallel_workers']})")
    results = _run_parallel(coin_risk, coin_ids)
    for r in results:
        if "error" in r:
            print(f"  ⚠  {r['coin_id']}: {r['error']}")
        else:
            icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(r["risk_tier"], "⚪")
            print(f"  {icon} {r['coin_id']:<18} vol={r['volatility_%']:.2f}%  "
                  f"sharpe={r['sharpe']:+.3f}  dd={r['max_dd_%']:.2f}%  [{r['risk_tier']}]")
    print("  ✓  Risk snapshots saved  →  risk_snapshots table")
    return results


def task_run_predictions(coin_ids):
    _banner("Task 2 — Prediction Module (Parallel)")
    predictions = _run_parallel(predict_coin, coin_ids)
    for p in predictions:
        if "error" in p:
            print(f"  ⚠  {p['coin_id']}: {p['error']}")
            continue
        print(f"\n  ── {p['coin_id'].upper()} ──")
        print(f"     Current / Next     : ${p['current_price']:>14,.4f}  →  ${p['linreg_next']:>14,.4f}  ({p['confidence_band']})")
        print(f"     MA next est.       : ${p['ma_next_pred']:>14,.4f}  [Short: ${p['short_ma'] or 0:,.4f} / Long: ${p['long_ma'] or 0:,.4f}]")
        print(f"     Trend / Signal     : {p['trend']}  |  {p['signal']}")
        if len(p["linreg_forecast"]) > 1:
            print(f"     Forecast           : {'  →  '.join(f'${v:,.2f}' for v in p['linreg_forecast'])}")
    print("\n  ✓  Predictions saved  →  predictions table")
    return predictions


def task_check_alerts(coins):
    _banner(f"Task 3 — Alert Check  (threshold ±{RISK['alert_threshold_pct']}%)")
    alerts = []
    for c in coins:
        chg = c.get("price_change_percentage_24h") or 0
        if abs(chg) >= RISK["alert_threshold_pct"]:
            direction = "UP" if chg > 0 else "DOWN"
            msg = f"{c['name']} moved {chg:+.2f}% in 24h ({direction})"
            alerts.append({"coin_id": c["id"], "symbol": c["symbol"],
                           "change_24h": round(chg, 2), "direction": direction, "message": msg})
            database.save_alert(c["id"], direction, msg)
            print(f"  {msg}")
    if not alerts:
        print(f"  No coin moved ±{RISK['alert_threshold_pct']}% in 24h.")
    return alerts


def task_export_csv(coins, risk_results, predictions, alerts):
    _banner(f"Task 4 — CSV Export  →  {REPORTS['output_dir']}/")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"  ✓  {_write_csv(f'prices_{ts}.csv', coins, ['id','symbol','name','current_price','market_cap','total_volume','price_change_percentage_24h'])}")

    valid_risk = [r for r in risk_results if "error" not in r]
    if valid_risk:
        print(f"  ✓  {_write_csv(f'risk_{ts}.csv', valid_risk, ['coin_id','price','mean_ret_%','volatility_%','sharpe','max_dd_%','risk_tier'])}")

    valid_pred = [p for p in predictions if "error" not in p]
    if valid_pred:
        flat = [{
            "coin_id": p["coin_id"], "current_price": p["current_price"],
            "linreg_next": p["linreg_next"], "confidence_band": p["confidence_band"],
            "slope_%_per_snap": p["slope_pct_per_snap"], "ma_next_pred": p["ma_next_pred"],
            "short_ma": p["short_ma"], "long_ma": p["long_ma"],
            "trend": p["trend"].strip(), "signal": p["signal"].split()[0],
            "5_period_forecast": " -> ".join(f"{v:.4f}" for v in p["linreg_forecast"]),
        } for p in valid_pred]
        print(f"  ✓  {_write_csv(f'predictions_{ts}.csv', flat, ['coin_id','current_price','linreg_next','confidence_band','slope_%_per_snap','ma_next_pred','short_ma','long_ma','trend','signal','5_period_forecast'])}")

    if alerts:
        print(f"  ✓  {_write_csv(f'alerts_{ts}.csv', alerts, ['coin_id','symbol','change_24h','direction','message'])}")


def task_send_email(alerts):
    _banner("Task 5 — Email Alerts")
    if not EMAIL["enabled"]:
        print("  Email disabled  →  set EMAIL_ENABLED=true in .env"); return
    if not alerts:
        print("  No alerts to email."); return

    subject = f"CryptoManager Alert — {len(alerts)} coin(s) moved"
    body    = "\n".join(a["message"] for a in alerts)

    if EMAIL.get("provider", "smtp").lower() == "resend":
        try:
            import resend
            resend.api_key = EMAIL["resend_api_key"]
            resend.Emails.send({"from": EMAIL["sender"], "to": EMAIL["recipient"],
                                "subject": subject, "text": body})
            print(f"  ✓  Email sent via Resend to {EMAIL['recipient']}")
        except ImportError:
            print("  ✗  Resend not installed. Run: pip install resend")
        except Exception as e:
            print(f"  ✗  Resend failed: {e}")
    else:
        msg = MIMEText(body)
        msg["Subject"], msg["From"], msg["To"] = subject, EMAIL["sender"], EMAIL["recipient"]
        try:
            with smtplib.SMTP(EMAIL["smtp_host"], EMAIL["smtp_port"]) as s:
                s.starttls(); s.login(EMAIL["sender"], EMAIL["password"]); s.send_message(msg)
            print(f"  ✓  Email sent via SMTP to {EMAIL['recipient']}")
        except Exception as e:
            print(f"  ✗  Email failed: {e}")


def run():
    print("\n  Fetching live prices …")
    coins = database.get_prices(WATCHLIST)
    if coins:
        for c in coins: database.save_price(c)
        print(f"  ✓  {len(coins)} prices stored")
    else:
        print("  ⚠  Could not fetch live prices")
        coins = []

    risk_results = task_parallel_risk(WATCHLIST);  input("\n  Press Enter …")
    predictions  = task_run_predictions(WATCHLIST); input("\n  Press Enter …")
    alerts       = task_check_alerts(coins);        input("\n  Press Enter …")

    task_export_csv(coins, risk_results, predictions, alerts); input("\n  Press Enter …")
    task_send_email(alerts)


if __name__ == "__main__":
    run()