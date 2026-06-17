"""
milestone3_risk_predictor.py — Risk Analysis & ML Prediction Engine

Upgraded with:
  - scikit-learn Ridge regression with multi-feature engineering
  - RSI, MACD, Bollinger Bands technical indicators
  - Value-at-Risk (VaR) and Conditional VaR (Expected Shortfall)
  - Sortino Ratio and Calmar Ratio
  - Walk-forward validation
  - Graceful fallback to hand-coded linear regression if sklearn missing
"""

import os, csv, smtplib, statistics, math
import concurrent.futures
from datetime import datetime
from email.mime.text import MIMEText

import database
from config import RISK, PREDICTION, REPORTS, EMAIL, WATCHLIST, MIX

# ── Optional ML imports ───────────────────────────────────────────────────────
try:
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    print("  [WARN] scikit-learn not installed — using legacy linear regression")


def _banner(t): print("\n" + "="*58 + f"\n  {t}\n" + "="*58)
def _ts():       return datetime.now().strftime("%Y%m%d_%H%M%S")
def _ensure_reports(): os.makedirs(REPORTS["output_dir"], exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TECHNICAL INDICATORS
# ══════════════════════════════════════════════════════════════════════════════

def RSI(prices: list, period: int = 14) -> list:
    """Relative Strength Index — momentum oscillator (0-100)."""
    rsi = [None] * len(prices)
    if len(prices) < period + 1:
        return rsi

    gains, losses = [], []
    for i in range(1, period + 1):
        change = prices[i] - prices[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = round(100 - (100 / (1 + rs)), 4)

    for i in range(period + 1, len(prices)):
        change = prices[i] - prices[i - 1]
        gain = max(change, 0)
        loss = max(-change, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = round(100 - (100 / (1 + rs)), 4)

    return rsi


def MACD(prices: list, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """
    Moving Average Convergence Divergence.
    Returns {macd_line, signal_line, histogram} — each a list.
    """
    def ema(data, span):
        result = [None] * len(data)
        k = 2 / (span + 1)
        # Find first non-None
        start = 0
        for i, v in enumerate(data):
            if v is not None:
                start = i
                break
        if start + span > len(data):
            return result
        result[start + span - 1] = sum(data[start:start + span]) / span
        for i in range(start + span, len(data)):
            if data[i] is not None and result[i - 1] is not None:
                result[i] = data[i] * k + result[i - 1] * (1 - k)
        return result

    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)

    macd_line = [None] * len(prices)
    for i in range(len(prices)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = round(ema_fast[i] - ema_slow[i], 6)

    signal_line = ema(macd_line, signal)

    histogram = [None] * len(prices)
    for i in range(len(prices)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram[i] = round(macd_line[i] - signal_line[i], 6)

    return {"macd_line": macd_line, "signal_line": signal_line, "histogram": histogram}


def bollinger_bands(prices: list, period: int = 20, num_std: int = 2) -> dict:
    """
    Bollinger Bands — middle (SMA), upper, lower bands.
    Returns {middle, upper, lower, bandwidth, pct_b} — each a list.
    """
    n = len(prices)
    middle = [None] * n
    upper  = [None] * n
    lower  = [None] * n
    bandwidth = [None] * n
    pct_b  = [None] * n

    for i in range(period - 1, n):
        window = prices[i - period + 1 : i + 1]
        sma = sum(window) / period
        std = (sum((x - sma) ** 2 for x in window) / period) ** 0.5

        middle[i] = round(sma, 6)
        upper[i]  = round(sma + num_std * std, 6)
        lower[i]  = round(sma - num_std * std, 6)
        if sma > 0:
            bandwidth[i] = round((upper[i] - lower[i]) / sma * 100, 4)
        if upper[i] != lower[i]:
            pct_b[i] = round((prices[i] - lower[i]) / (upper[i] - lower[i]), 4)

    return {"middle": middle, "upper": upper, "lower": lower,
            "bandwidth": bandwidth, "pct_b": pct_b}


def compute_indicators(prices: list) -> dict:
    """Compute all technical indicators for a price series."""
    rsi_period = PREDICTION.get("rsi_period", 14)
    macd_fast  = PREDICTION.get("macd_fast", 12)
    macd_slow  = PREDICTION.get("macd_slow", 26)
    macd_sig   = PREDICTION.get("macd_signal", 9)
    bb_period  = PREDICTION.get("bollinger_period", 20)
    bb_std     = PREDICTION.get("bollinger_std", 2)

    rsi_vals  = RSI(prices, rsi_period)
    macd_vals = MACD(prices, macd_fast, macd_slow, macd_sig)
    bb_vals   = bollinger_bands(prices, bb_period, bb_std)

    return {
        "rsi":       rsi_vals,
        "macd":      macd_vals["macd_line"],
        "macd_signal": macd_vals["signal_line"],
        "macd_hist": macd_vals["histogram"],
        "bb_upper":  bb_vals["upper"],
        "bb_middle": bb_vals["middle"],
        "bb_lower":  bb_vals["lower"],
        "bb_bandwidth": bb_vals["bandwidth"],
        "bb_pct_b":  bb_vals["pct_b"],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  RISK METRICS — VaR, CVaR, Sortino, Calmar
# ══════════════════════════════════════════════════════════════════════════════

def _pct_returns(prices):
    return [(prices[i] - prices[i-1]) / prices[i-1] * 100
            for i in range(1, len(prices))
            if prices[i-1] != 0]


def _max_drawdown(prices):
    if not prices:
        return 0.0
    peak, dd = prices[0], 0.0
    for p in prices:
        peak = max(peak, p)
        if peak > 0:
            dd = max(dd, (peak - p) / peak * 100)
    return dd


def VaR(returns: list, confidence: float = 0.95) -> float:
    """
    Historical Value-at-Risk.
    The maximum expected loss at the given confidence level.
    Returns a positive number (loss magnitude).
    """
    if len(returns) < 5:
        return 0.0
    sorted_rets = sorted(returns)
    idx = int((1 - confidence) * len(sorted_rets))
    idx = max(0, min(idx, len(sorted_rets) - 1))
    return round(-sorted_rets[idx], 4)


def CVaR(returns: list, confidence: float = 0.95) -> float:
    """
    Conditional VaR (Expected Shortfall).
    Average loss in the worst (1-confidence)% of cases.
    """
    if len(returns) < 5:
        return 0.0
    sorted_rets = sorted(returns)
    cutoff = int((1 - confidence) * len(sorted_rets))
    cutoff = max(1, cutoff)
    tail = sorted_rets[:cutoff]
    return round(-sum(tail) / len(tail), 4) if tail else 0.0


def sortino_ratio(returns: list, rf: float = 0.02) -> float:
    """Sortino Ratio — like Sharpe but only penalises downside volatility."""
    if len(returns) < 2:
        return 0.0
    mean_ret = statistics.mean(returns)
    downside = [r for r in returns if r < rf]
    if not downside:
        return 999.0  # no downside risk
    downside_std = (sum((r - rf) ** 2 for r in downside) / len(downside)) ** 0.5
    if downside_std < 1e-10:
        return 999.0
    return round((mean_ret - rf) / downside_std, 4)


def calmar_ratio(returns: list, prices: list) -> float:
    """Calmar Ratio — return / max drawdown."""
    if len(returns) < 2 or not prices:
        return 0.0
    mean_ret = statistics.mean(returns)
    dd = _max_drawdown(prices)
    if dd < 1e-10:
        return 999.0
    return round(mean_ret / dd, 4)


# ══════════════════════════════════════════════════════════════════════════════
#  PREDICTION — LEGACY LINEAR REGRESSION (fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _linear_regression(x: list, y: list) -> tuple:
    n   = len(x)
    sx  = sum(x)
    sy  = sum(y)
    sxy = sum(x[i] * y[i] for i in range(n))
    sxx = sum(xi**2 for xi in x)
    denom  = n * sxx - sx**2
    if denom == 0:
        return 0.0, sy / n
    slope     = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def _moving_average(prices: list, window: int) -> list:
    ma = []
    for i in range(len(prices)):
        if i < window - 1:
            ma.append(None)
        else:
            ma.append(sum(prices[i - window + 1 : i + 1]) / window)
    return ma


def _momentum_trend(prices: list, window: int = 5) -> str:
    if len(prices) < window + 1:
        return "NEUTRAL"
    recent_avg = sum(prices[-(window+1):-1]) / window
    last       = prices[-1]
    change_pct = (last - recent_avg) / recent_avg * 100
    if change_pct > 1.5:
        return "BULLISH ↑"
    elif change_pct < -1.5:
        return "BEARISH ↓"
    return "NEUTRAL ➡"


def _ma_signal(prices: list, short_w: int, long_w: int) -> str:
    if len(prices) < long_w:
        return "HOLD"
    short_ma = sum(prices[-short_w:]) / short_w
    long_ma  = sum(prices[-long_w:])  / long_w
    diff_pct = (short_ma - long_ma) / long_ma * 100
    if diff_pct > 1.0:
        return "BUY  🟢"
    elif diff_pct < -1.0:
        return "SELL 🔴"
    return "HOLD 🟡"


# ══════════════════════════════════════════════════════════════════════════════
#  PREDICTION — ML-BASED (scikit-learn Ridge with feature engineering)
# ══════════════════════════════════════════════════════════════════════════════

def _build_features(prices: list) -> tuple:
    """
    Build feature matrix from price series for ML prediction.
    Features: returns, volatility, RSI, MACD, Bollinger %B, momentum.
    Returns (X, y, feature_names) where y is next-period return.
    """
    if not HAS_SKLEARN or len(prices) < 30:
        return None, None, None

    n = len(prices)
    returns = [0] + [(prices[i] - prices[i-1]) / prices[i-1] * 100
                     for i in range(1, n)]

    rsi_vals = RSI(prices, min(PREDICTION.get("rsi_period", 14), n // 3))
    macd_data = MACD(prices,
                     min(PREDICTION.get("macd_fast", 12), n // 3),
                     min(PREDICTION.get("macd_slow", 26), n // 2),
                     min(PREDICTION.get("macd_signal", 9), n // 3))
    bb_data = bollinger_bands(prices,
                              min(PREDICTION.get("bollinger_period", 20), n // 2),
                              PREDICTION.get("bollinger_std", 2))

    feature_names = [
        "return_1", "return_3_avg", "return_5_avg",
        "vol_5", "vol_10",
        "rsi", "macd", "macd_hist",
        "bb_pct_b", "bb_bandwidth",
        "momentum_3", "momentum_5",
        "price_vs_sma10", "price_vs_sma20",
    ]

    X_rows = []
    y_vals = []
    start_idx = max(20, PREDICTION.get("bollinger_period", 20))

    for i in range(start_idx, n - 1):
        # Skip rows with missing indicator values
        if rsi_vals[i] is None:
            continue

        ret_1 = returns[i]
        ret_3 = sum(returns[max(0,i-2):i+1]) / min(3, i+1)
        ret_5 = sum(returns[max(0,i-4):i+1]) / min(5, i+1)

        vol_5  = (sum(r**2 for r in returns[max(0,i-4):i+1]) / min(5, i+1)) ** 0.5
        vol_10 = (sum(r**2 for r in returns[max(0,i-9):i+1]) / min(10, i+1)) ** 0.5

        rsi_v = rsi_vals[i] if rsi_vals[i] is not None else 50.0
        macd_v = macd_data["macd_line"][i] if macd_data["macd_line"][i] is not None else 0.0
        macd_h = macd_data["histogram"][i] if macd_data["histogram"][i] is not None else 0.0

        bb_pb = bb_data["pct_b"][i] if bb_data["pct_b"][i] is not None else 0.5
        bb_bw = bb_data["bandwidth"][i] if bb_data["bandwidth"][i] is not None else 0.0

        mom_3 = (prices[i] - prices[max(0,i-3)]) / prices[max(0,i-3)] * 100 if prices[max(0,i-3)] > 0 else 0
        mom_5 = (prices[i] - prices[max(0,i-5)]) / prices[max(0,i-5)] * 100 if prices[max(0,i-5)] > 0 else 0

        sma10 = sum(prices[max(0,i-9):i+1]) / min(10, i+1)
        sma20 = sum(prices[max(0,i-19):i+1]) / min(20, i+1)
        price_sma10 = (prices[i] - sma10) / sma10 * 100 if sma10 > 0 else 0
        price_sma20 = (prices[i] - sma20) / sma20 * 100 if sma20 > 0 else 0

        features = [ret_1, ret_3, ret_5, vol_5, vol_10,
                    rsi_v, macd_v, macd_h, bb_pb, bb_bw,
                    mom_3, mom_5, price_sma10, price_sma20]
        X_rows.append(features)
        y_vals.append(returns[i + 1])  # next period return

    if len(X_rows) < 10:
        return None, None, None

    return np.array(X_rows), np.array(y_vals), feature_names


def predict_coin(coin_id: str) -> dict:
    """
    Predict next price movement for a coin.
    Uses ML (Ridge regression) if sklearn available and enough data,
    else falls back to legacy linear regression.
    """
    limit  = PREDICTION["history_limit"]
    rows   = database.get_history(coin_id, limit=limit)
    prices = [r["price_usd"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]

    if len(prices) < max(PREDICTION["ma_long_window"], 4):
        return {"coin_id": coin_id, "error": "not enough history for prediction"}

    n = len(prices)
    short_w  = PREDICTION["ma_short_window"]
    long_w   = PREDICTION["ma_long_window"]

    # ── ML Prediction (if available) ──────────────────────────────────────
    ml_prediction = None
    ml_confidence = None
    ml_features_used = 0

    if HAS_SKLEARN:
        X, y, feat_names = _build_features(prices)
        if X is not None and len(X) >= 10:
            # Walk-forward: train on all but last 20%, validate on last 20%
            split = max(int(len(X) * 0.8), 5)
            X_train, y_train = X[:split], y[:split]
            X_val,   y_val   = X[split:], y[split:]

            scaler = StandardScaler()
            X_train_s = scaler.fit_transform(X_train)

            model = Ridge(alpha=1.0)
            model.fit(X_train_s, y_train)

            # Validation score
            if len(X_val) > 0:
                X_val_s = scaler.transform(X_val)
                val_preds = model.predict(X_val_s)
                val_errors = y_val - val_preds
                ml_confidence = round(float(np.std(val_errors)), 4)

            # Predict next period
            last_features = X[-1:].copy()
            last_features_s = scaler.transform(last_features)
            predicted_return = float(model.predict(last_features_s)[0])

            ml_prediction = round(prices[-1] * (1 + predicted_return / 100), 6)
            ml_features_used = len(feat_names) if feat_names else 0

    # ── Legacy Linear Regression ──────────────────────────────────────────
    x_idx = list(range(n))
    slope, intercept = _linear_regression(x_idx, prices)

    periods      = PREDICTION["linreg_periods"]
    forecast_x   = list(range(n, n + periods))
    linreg_preds = [round(intercept + slope * xi, 6) for xi in forecast_x]

    fitted     = [intercept + slope * xi for xi in x_idx]
    residuals  = [prices[i] - fitted[i] for i in range(n)]
    try:
        resid_std = statistics.pstdev(residuals)
    except Exception:
        resid_std = 0
    confidence = round(resid_std, 6)

    # ── Moving Average signals ────────────────────────────────────────────
    short_ma_series = _moving_average(prices, short_w)
    long_ma_series  = _moving_average(prices, long_w)

    short_ma_last = next((v for v in reversed(short_ma_series) if v is not None), None)
    long_ma_last  = next((v for v in reversed(long_ma_series)  if v is not None), None)
    ma_next_pred  = round(short_ma_last, 6) if short_ma_last else prices[-1]

    signal = _ma_signal(prices, short_w, long_w)
    trend  = _momentum_trend(prices)

    # ── Technical Indicators (latest values) ──────────────────────────────
    indicators = compute_indicators(prices)
    rsi_last   = next((v for v in reversed(indicators["rsi"]) if v is not None), None)
    macd_last  = next((v for v in reversed(indicators["macd"]) if v is not None), None)
    macd_hist_last = next((v for v in reversed(indicators["macd_hist"]) if v is not None), None)
    bb_upper   = next((v for v in reversed(indicators["bb_upper"]) if v is not None), None)
    bb_lower   = next((v for v in reversed(indicators["bb_lower"]) if v is not None), None)
    bb_pctb    = next((v for v in reversed(indicators["bb_pct_b"]) if v is not None), None)

    # ── RSI-based signal override ─────────────────────────────────────────
    rsi_signal = "NEUTRAL"
    if rsi_last is not None:
        if rsi_last < 30:
            rsi_signal = "OVERSOLD 🟢"
        elif rsi_last > 70:
            rsi_signal = "OVERBOUGHT 🔴"

    slope_pct = slope / prices[0] * 100 if prices[0] else 0

    result = {
        "coin_id":           coin_id,
        "current_price":     round(prices[-1], 6),
        "linreg_slope":      round(slope, 8),
        "slope_pct_per_snap": round(slope_pct, 4),
        "linreg_forecast":   linreg_preds,
        "linreg_next":       linreg_preds[0],
        "confidence_band":   f"±{ml_confidence if ml_confidence else confidence:.4f}",
        "short_ma":          round(short_ma_last, 6) if short_ma_last else None,
        "long_ma":           round(long_ma_last, 6)  if long_ma_last  else None,
        "ma_next_pred":      ma_next_pred,
        "trend":             trend,
        "signal":            signal,
        "periods_ahead":     periods,
        "snapshots_used":    n,
        # New ML fields
        "ml_prediction":     ml_prediction,
        "ml_confidence":     ml_confidence,
        "ml_features":       ml_features_used,
        "method":            "Ridge+Indicators" if ml_prediction else "LinReg",
        # Technical indicators
        "rsi":               rsi_last,
        "rsi_signal":        rsi_signal,
        "macd":              macd_last,
        "macd_histogram":    macd_hist_last,
        "bb_upper":          bb_upper,
        "bb_lower":          bb_lower,
        "bb_pct_b":          bb_pctb,
    }

    # save to DB
    database.save_prediction(
        coin_id, prices[-1], linreg_preds, ma_next_pred, trend, signal)

    return result


def coin_risk(coin_id: str, btc_prices: list = None) -> dict:
    """
    Compute comprehensive risk metrics for a coin.
    Includes VaR, CVaR, Sortino, Calmar in addition to legacy metrics.
    If btc_prices provided, also calculates Beta vs BTC.
    """
    rows   = database.get_history(coin_id, limit=RISK["history_limit"])
    prices = [r["price_usd"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]
    if len(prices) < 2:
        return {"coin_id": coin_id, "error": "not enough history"}

    rets     = _pct_returns(prices)
    vol      = statistics.pstdev(rets) or 0.0001
    mean_ret = statistics.mean(rets)
    rf       = RISK.get("risk_free_rate", MIX.get("risk_free_rate", 0.02))
    sharpe   = (mean_ret - rf) / vol  # FIXED: now includes risk-free rate
    dd       = _max_drawdown(prices)

    tier = ("LOW" if vol < RISK["volatility_low"] else
            "MEDIUM" if vol < RISK["volatility_high"] else "HIGH")

    # Advanced risk metrics
    var_conf  = RISK.get("var_confidence", 0.95)
    var_val   = VaR(rets, var_conf)
    cvar_val  = CVaR(rets, var_conf)
    sortino   = sortino_ratio(rets, rf)
    calmar    = calmar_ratio(rets, prices)

    # Beta vs BTC (if btc_prices provided)
    beta = None
    if btc_prices and len(btc_prices) >= 2 and coin_id != "bitcoin":
        btc_rets = _pct_returns(btc_prices)
        # Align lengths
        min_len = min(len(rets), len(btc_rets))
        if min_len >= 2:
            coin_r = rets[-min_len:]
            btc_r  = btc_rets[-min_len:]
            btc_var = statistics.pvariance(btc_r) or 0.0001
            cov = sum((a - statistics.mean(coin_r)) * (b - statistics.mean(btc_r))
                      for a, b in zip(coin_r, btc_r)) / len(coin_r)
            beta = round(cov / btc_var, 4)

    database.save_risk(coin_id, vol, sharpe, dd, tier)

    result = {
        "coin_id":      coin_id,
        "price":        round(prices[-1], 6),
        "mean_ret_%":   round(mean_ret, 4),
        "volatility_%": round(vol, 4),
        "sharpe":       round(sharpe, 4),
        "max_dd_%":     round(dd, 4),
        "risk_tier":    tier,
        # New advanced metrics
        "var_%":        var_val,
        "cvar_%":       cvar_val,
        "sortino":      round(sortino, 4),
        "calmar":       round(calmar, 4),
        "var_confidence": var_conf,
        "data_points":  len(rets),
    }
    if beta is not None:
        result["beta"] = beta
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  INDICATOR API HELPER (for /api/indicators/<coin_id>)
# ══════════════════════════════════════════════════════════════════════════════

def get_coin_indicators(coin_id: str) -> dict:
    """Return full indicator series for charting on the frontend."""
    rows   = database.get_history(coin_id, limit=PREDICTION["history_limit"])
    prices = [r["price_usd"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]
    times  = [r["fetched_at"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]

    if len(prices) < 10:
        return {"coin_id": coin_id, "error": "not enough history"}

    ind = compute_indicators(prices)

    return {
        "coin_id":    coin_id,
        "timestamps": times,
        "prices":     prices,
        "rsi":        ind["rsi"],
        "macd":       ind["macd"],
        "macd_signal": ind["macd_signal"],
        "macd_hist":  ind["macd_hist"],
        "bb_upper":   ind["bb_upper"],
        "bb_middle":  ind["bb_middle"],
        "bb_lower":   ind["bb_lower"],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  TASK FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def task_parallel_risk(coin_ids: list) -> list:
    _banner(f"Task 1 — Parallel Risk Check  (workers={RISK['parallel_workers']})")
    results = []
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=RISK["parallel_workers"]) as pool:
        futures = {pool.submit(coin_risk, cid): cid for cid in coin_ids}
        for fut in concurrent.futures.as_completed(futures):
            r = fut.result()
            results.append(r)
            if "error" in r:
                print(f"  ⚠  {r['coin_id']}: {r['error']}")
            else:
                icon = {"LOW":"🟢","MEDIUM":"🟡","HIGH":"🔴"}.get(r["risk_tier"],"⚪")
                print(f"  {icon} {r['coin_id']:<18} "
                      f"vol={r['volatility_%']:.2f}%  "
                      f"sharpe={r['sharpe']:+.3f}  "
                      f"dd={r['max_dd_%']:.2f}%  "
                      f"VaR={r['var_%']:.2f}%  "
                      f"CVaR={r['cvar_%']:.2f}%  "
                      f"[{r['risk_tier']}]")
    print("  ✓  Risk snapshots saved  →  risk_snapshots table")
    return results

def task_run_predictions(coin_ids: list) -> list:
    _banner("Task 2 — Prediction Module (Parallel + ML)")
    method = "Ridge+Indicators" if HAS_SKLEARN else "Legacy LinReg"
    print(f"  Method  →  {method}")
    print(f"  Config  →  history={PREDICTION['history_limit']} snaps  "
          f"| MA windows={PREDICTION['ma_short_window']}/{PREDICTION['ma_long_window']}  "
          f"| forecast={PREDICTION['linreg_periods']} periods\n")

    predictions = []
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=RISK["parallel_workers"]) as pool:
        futures = {pool.submit(predict_coin, cid): cid for cid in coin_ids}
        for fut in concurrent.futures.as_completed(futures):
            p = fut.result()
            predictions.append(p)
            if "error" in p:
                print(f"  ⚠  {p['coin_id']}: {p['error']}")
                continue
            print(f"\n  ── {p['coin_id'].upper()} ──")
            print(f"     Current price      : ${p['current_price']:>14,.4f}")
            print(f"     LinReg next period : ${p['linreg_next']:>14,.4f}  "
                  f"(confidence {p['confidence_band']})")
            if p.get("ml_prediction"):
                print(f"     ML prediction      : ${p['ml_prediction']:>14,.4f}  "
                      f"({p['ml_features']} features)")
            print(f"     Trend              : {p['trend']}")
            print(f"     Signal             : {p['signal']}")
            if p.get("rsi") is not None:
                print(f"     RSI                : {p['rsi']:.1f}  {p['rsi_signal']}")
            if p.get("macd") is not None:
                print(f"     MACD               : {p['macd']:.4f}  "
                      f"hist={p['macd_histogram']:.4f}" if p.get("macd_histogram") else "")

    print(f"\n  ✓  Predictions saved  →  predictions table")
    return predictions

def task_check_alerts(coins: list, save: bool = True) -> list:
    _banner(f"Task 3 -- Alert Check  (threshold +/-{RISK['alert_threshold_pct']}%)")
    alerts = []
    for c in coins:
        chg = c.get("price_change_percentage_24h") or 0
        if abs(chg) >= RISK["alert_threshold_pct"]:
            direction = "UP" if chg > 0 else "DOWN"
            msg = f"{c['name']} moved {chg:+.2f}% in 24h ({direction})"
            alerts.append({"coin_id": c["id"], "symbol": c["symbol"],
                            "change_24h": round(chg,2),
                            "direction": direction, "message": msg})
            if save:
                database.save_alert(c["id"], direction, msg)
            print(f"   {msg}")
    if not alerts:
        print(f"  No coin moved ±{RISK['alert_threshold_pct']}% in 24h.")
    return alerts

def _write_csv(filename: str, rows: list, fields: list) -> str:
    _ensure_reports()
    path = os.path.join(REPORTS["output_dir"], filename)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return path


def task_export_csv(coins: list, risk_results: list,
                    predictions: list, alerts: list):
    _banner(f"Task 4 — CSV Export  →  {REPORTS['output_dir']}/")
    ts = _ts()

    p = _write_csv(f"prices_{ts}.csv", coins,
                   ["id","symbol","name","current_price",
                    "market_cap","total_volume","price_change_percentage_24h"])
    print(f"  ✓  {p}")

    valid_risk = [r for r in risk_results if "error" not in r]
    if valid_risk:
        p = _write_csv(f"risk_{ts}.csv", valid_risk,
                       ["coin_id","price","mean_ret_%",
                        "volatility_%","sharpe","max_dd_%","risk_tier",
                        "var_%","cvar_%","sortino","calmar"])
        print(f"  ✓  {p}")

    valid_pred = [pr for pr in predictions if "error" not in pr]
    if valid_pred:
        flat_preds = []
        for pr in valid_pred:
            flat_preds.append({
                "coin_id":          pr["coin_id"],
                "current_price":    pr["current_price"],
                "linreg_next":      pr["linreg_next"],
                "ml_prediction":    pr.get("ml_prediction", ""),
                "method":           pr.get("method", "LinReg"),
                "confidence_band":  pr["confidence_band"],
                "slope_%_per_snap": pr["slope_pct_per_snap"],
                "ma_next_pred":     pr["ma_next_pred"],
                "short_ma":         pr["short_ma"],
                "long_ma":          pr["long_ma"],
                "rsi":              pr.get("rsi", ""),
                "macd":             pr.get("macd", ""),
                "trend":            pr["trend"].strip(),
                "signal":           pr["signal"].split()[0],
                "5_period_forecast": " -> ".join(
                    f"{v:.4f}" for v in pr["linreg_forecast"]),
            })
        p = _write_csv(f"predictions_{ts}.csv", flat_preds,
                       ["coin_id","current_price","linreg_next","ml_prediction",
                        "method","confidence_band","slope_%_per_snap",
                        "ma_next_pred","short_ma","long_ma",
                        "rsi","macd","trend","signal","5_period_forecast"])
        print(f"  ✓  {p}")

    if alerts:
        p = _write_csv(f"alerts_{ts}.csv", alerts,
                       ["coin_id","symbol","change_24h","direction","message"])
        print(f"  ✓  {p}")


def task_send_email(alerts: list):
    _banner("Email Alerts")
    if not EMAIL["enabled"]:
        print("  Email disabled  →  set EMAIL_ENABLED=true in .env")
        return
    if not alerts:
        print("  No alerts to email.")
        return

    subject = f"CryptoManager Alert — {len(alerts)} coin(s) moved"
    body    = "\n".join(a["message"] for a in alerts)

    provider = EMAIL.get("provider", "smtp").lower()

    if provider == "resend":
        try:
            import resend
            resend.api_key = EMAIL["resend_api_key"]
            resend.Emails.send({
                "from":    EMAIL["sender"],
                "to":      EMAIL["recipient"],
                "subject": subject,
                "text":    body,
            })
            print(f"  ✓  Email sent via Resend to {EMAIL['recipient']}")
        except ImportError:
            print("  ✗  Resend not installed. Run: pip install resend")
        except Exception as e:
            print(f"  ✗  Resend failed: {e}")

    else:
        from email.mime.text import MIMEText as _MIMEText
        msg = _MIMEText(body)
        msg["Subject"] = subject
        msg["From"]    = EMAIL["sender"]
        msg["To"]      = EMAIL["recipient"]
        try:
            with smtplib.SMTP(EMAIL["smtp_host"], EMAIL["smtp_port"]) as s:
                s.starttls()
                s.login(EMAIL["sender"], EMAIL["password"])
                s.send_message(msg)
            print(f"  ✓  Email sent via SMTP to {EMAIL['recipient']}")
        except Exception as e:
            print(f"  ✗  Email failed: {e}")



def run():

    print("\n  Fetching live prices …")
    coins = database.get_prices(WATCHLIST)
    if coins:
        database.save_prices_batch(coins)
        print(f"  ✓  {len(coins)} prices stored")
    else:
        print("  ⚠  Could not fetch live prices")
        coins = []

    risk_results = task_parallel_risk(WATCHLIST)
    input("\n  Press Enter …")

    predictions = task_run_predictions(WATCHLIST)
    input("\n  Press Enter …")

    alerts = task_check_alerts(coins)
    input("\n  Press Enter …")

    task_export_csv(coins, risk_results, predictions, alerts)
    input("\n  Press Enter …")

    task_send_email(alerts)

if __name__ == "__main__":
    run()