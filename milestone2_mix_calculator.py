"""
milestone2_mix_calculator.py — Portfolio Mix Calculator with Mean-Variance Optimization

Upgraded from random Monte-Carlo sampling to proper MVO using scipy.optimize.
Computes covariance matrix, efficient frontier, and optimal Sharpe portfolio.
Falls back to random sampling if numpy/scipy are unavailable.
"""

import random, statistics, math
import concurrent.futures
import database
from config import MIX, WATCHLIST

# ── Try numpy/scipy; fall back gracefully ─────────────────────────────────────
try:
    import numpy as np
    from scipy.optimize import minimize
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("  [WARN] numpy/scipy not installed — using legacy random sampling")


def _banner(t): print("\n" + "="*58 + f"\n  {t}\n" + "="*58)

def _pct_returns(prices: list) -> list:
    return [(prices[i] - prices[i-1]) / prices[i-1] * 100
            for i in range(1, len(prices))
            if prices[i-1] != 0]


# ══════════════════════════════════════════════════════════════════════════════
#  NUMPY-BASED MEAN-VARIANCE OPTIMIZATION
# ══════════════════════════════════════════════════════════════════════════════

def compute_covariance_matrix(returns_dict: dict) -> tuple:
    """
    Compute covariance matrix from returns dict.
    Returns (coin_list, mean_returns_array, cov_matrix).
    """
    coins = list(returns_dict.keys())
    # Align to shortest length
    min_len = min(len(returns_dict[c]) for c in coins)
    matrix = np.array([returns_dict[c][:min_len] for c in coins])  # shape (n_assets, n_periods)
    mean_rets = np.mean(matrix, axis=1)
    cov = np.cov(matrix)
    # Ensure 2D even for 2 assets
    if cov.ndim == 0:
        cov = np.array([[cov]])
    return coins, mean_rets, cov


def _portfolio_return(weights, mean_rets):
    """Expected portfolio return."""
    return np.dot(weights, mean_rets)


def _portfolio_volatility(weights, cov):
    """Portfolio standard deviation (risk)."""
    return np.sqrt(np.dot(weights, np.dot(cov, weights)))


def _neg_sharpe(weights, mean_rets, cov, rf=0.02):
    """Negative Sharpe ratio (we minimize this)."""
    ret = _portfolio_return(weights, mean_rets)
    vol = _portfolio_volatility(weights, cov)
    if vol < 1e-10:
        return 999
    return -(ret - rf) / vol


def max_sharpe_portfolio(mean_rets, cov, rf=0.02, min_w=0.05) -> dict:
    """Find the portfolio with maximum Sharpe ratio using constrained optimization."""
    n = len(mean_rets)
    # Constraints: weights sum to 1
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    # Bounds: each weight between min_w and 1
    bounds = [(min_w, 1.0)] * n
    # Initial guess: equal weight
    w0 = np.array([1.0 / n] * n)

    result = minimize(
        _neg_sharpe, w0, args=(mean_rets, cov, rf),
        method="SLSQP", bounds=bounds, constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-12}
    )

    weights = result.x
    ret = _portfolio_return(weights, mean_rets)
    vol = _portfolio_volatility(weights, cov)
    sharpe = (ret - rf) / vol if vol > 0 else 0

    return {
        "weights": weights.tolist(),
        "exp_ret": round(float(ret), 6),
        "exp_risk": round(float(vol), 6),
        "sharpe": round(float(sharpe), 6),
    }


def min_volatility_portfolio(mean_rets, cov, min_w=0.05) -> dict:
    """Find the minimum volatility portfolio."""
    n = len(mean_rets)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(min_w, 1.0)] * n
    w0 = np.array([1.0 / n] * n)

    result = minimize(
        lambda w: _portfolio_volatility(w, cov), w0,
        method="SLSQP", bounds=bounds, constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-12}
    )

    weights = result.x
    ret = _portfolio_return(weights, mean_rets)
    vol = _portfolio_volatility(weights, cov)
    sharpe = (ret - MIX["risk_free_rate"]) / vol if vol > 0 else 0

    return {
        "weights": weights.tolist(),
        "exp_ret": round(float(ret), 6),
        "exp_risk": round(float(vol), 6),
        "sharpe": round(float(sharpe), 6),
    }


def max_return_portfolio(mean_rets, cov, min_w=0.05) -> dict:
    """Find the portfolio that maximises expected return within constraints."""
    n = len(mean_rets)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(min_w, 1.0)] * n
    w0 = np.array([1.0 / n] * n)

    result = minimize(
        lambda w: -_portfolio_return(w, mean_rets), w0,
        method="SLSQP", bounds=bounds, constraints=constraints,
        options={"maxiter": 500}
    )

    weights = result.x
    ret = _portfolio_return(weights, mean_rets)
    vol = _portfolio_volatility(weights, cov)
    sharpe = (ret - MIX["risk_free_rate"]) / vol if vol > 0 else 0

    return {
        "weights": weights.tolist(),
        "exp_ret": round(float(ret), 6),
        "exp_risk": round(float(vol), 6),
        "sharpe": round(float(sharpe), 6),
    }


def efficient_frontier(mean_rets, cov, n_points=50, min_w=0.05) -> list:
    """
    Compute the efficient frontier — a set of optimal portfolios
    from min-risk to max-return.
    Returns list of {weights, exp_ret, exp_risk, sharpe}.
    """
    n = len(mean_rets)

    # Find the range of achievable returns
    min_vol = min_volatility_portfolio(mean_rets, cov, min_w)
    max_ret = max_return_portfolio(mean_rets, cov, min_w)

    target_returns = np.linspace(min_vol["exp_ret"], max_ret["exp_ret"], n_points)
    frontier = []

    for target in target_returns:
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},
            {"type": "eq", "fun": lambda w, t=target: _portfolio_return(w, mean_rets) - t},
        ]
        bounds = [(min_w, 1.0)] * n
        w0 = np.array([1.0 / n] * n)

        result = minimize(
            lambda w: _portfolio_volatility(w, cov), w0,
            method="SLSQP", bounds=bounds, constraints=constraints,
            options={"maxiter": 500, "ftol": 1e-12}
        )

        if result.success:
            weights = result.x
            ret = _portfolio_return(weights, mean_rets)
            vol = _portfolio_volatility(weights, cov)
            sharpe = (ret - MIX["risk_free_rate"]) / vol if vol > 0 else 0
            frontier.append({
                "weights": weights.tolist(),
                "exp_ret": round(float(ret), 6),
                "exp_risk": round(float(vol), 6),
                "sharpe": round(float(sharpe), 6),
            })

    return frontier


# ══════════════════════════════════════════════════════════════════════════════
#  LEGACY RANDOM SAMPLING (fallback when scipy missing)
# ══════════════════════════════════════════════════════════════════════════════

def _random_weights(n: int, min_w: float) -> list:
    while True:
        raw = [random.random() for _ in range(n)]
        tot = sum(raw)
        w   = [x / tot for x in raw]
        if all(x >= min_w for x in w):
            return w


def _portfolio_stats_legacy(weights: list, returns_matrix: list) -> tuple:
    n = min(len(r) for r in returns_matrix)
    port = [sum(weights[j] * returns_matrix[j][i]
                for j in range(len(weights)))
            for i in range(n)]
    if len(port) < 2:
        return 0.0, 0.0, 0.0
    ret   = statistics.mean(port)
    risk  = statistics.pstdev(port) or 0.0001
    sharpe = (ret - MIX["risk_free_rate"]) / risk
    return round(ret, 6), round(risk, 6), round(sharpe, 6)


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC TASK FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _load_single_coin(cid: str) -> tuple:
    """Load return history for a single coin — designed to run in a thread."""
    rows   = database.get_history(cid, limit=MIX["history_limit"])
    prices = [r["price_usd"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]
    ret    = _pct_returns(prices)
    return cid, ret


def task_load_returns(coin_ids: list) -> dict:
    _banner("Task 1 — Load Return History from DB (Parallel)")
    returns = {}
    # Use concurrent.futures to load all coin histories in parallel
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(coin_ids), 4)) as pool:
        futures = {pool.submit(_load_single_coin, cid): cid for cid in coin_ids}
        for fut in concurrent.futures.as_completed(futures):
            cid, ret = fut.result()
            if ret:
                returns[cid] = ret
                print(f"   {cid:<18}  {len(ret)} return periods loaded")
            else:
                print(f"   {cid:<18}  not enough history (run Milestone 1 first)")
    print(f"  ✓  {len(returns)} coins loaded in parallel")
    return returns


def task_run_mixes(returns: dict) -> dict:
    """
    Run portfolio optimisation.
    Uses Mean-Variance Optimization if scipy available, else random sampling.
    """
    if len(returns) < 2:
        print("  Need at least 2 coins with history. Run Milestone 1 first.")
        return {}

    if HAS_SCIPY:
        return _run_mvo(returns)
    else:
        return _run_legacy(returns)


def _run_mvo(returns: dict) -> dict:
    """Mean-Variance Optimization using scipy."""
    _banner(f"Task 2 — Mean-Variance Optimization (scipy)")
    coins, mean_rets, cov = compute_covariance_matrix(returns)
    min_w = MIX["min_weight"]
    rf    = MIX["risk_free_rate"]

    print(f"  Assets: {len(coins)}  |  Periods: {min(len(returns[c]) for c in coins)}")
    print(f"  Risk-free rate: {rf}%  |  Min weight: {min_w*100:.0f}%\n")

    # Covariance matrix summary
    print("  ── Correlation Matrix ──")
    stds = np.sqrt(np.diag(cov))
    stds[stds == 0] = 1
    corr = cov / np.outer(stds, stds)
    header = "  " + f"{'':18}" + " ".join(f"{c[:8]:>9}" for c in coins)
    print(header)
    for i, c in enumerate(coins):
        row_str = " ".join(f"{corr[i,j]:>9.3f}" for j in range(len(coins)))
        print(f"  {c:<18}{row_str}")
    print()

    # Find optimal portfolios
    print("  Optimising ... ", end="", flush=True)
    best_sharpe = max_sharpe_portfolio(mean_rets, cov, rf, min_w)
    best_sharpe["coins"] = coins
    print("Sharpe ✓ ", end="", flush=True)

    lowest_risk = min_volatility_portfolio(mean_rets, cov, min_w)
    lowest_risk["coins"] = coins
    print("MinVol ✓ ", end="", flush=True)

    best_return = max_return_portfolio(mean_rets, cov, min_w)
    best_return["coins"] = coins
    print("MaxRet ✓")

    # Efficient frontier
    n_pts = MIX.get("frontier_points", 50)
    frontier = efficient_frontier(mean_rets, cov, n_pts, min_w)
    for pt in frontier:
        pt["coins"] = coins
    print(f"  ✓  Efficient frontier: {len(frontier)} points computed")

    return {
        "best_sharpe": best_sharpe,
        "best_return": best_return,
        "lowest_risk": lowest_risk,
        "frontier":    frontier,
    }


def _run_legacy(returns: dict) -> dict:
    """Legacy random sampling fallback."""
    _banner(f"Task 2 — {MIX['iterations']} Random Mix Iterations (legacy)")
    coins  = list(returns.keys())
    matrix = [returns[c] for c in coins]
    min_w  = MIX["min_weight"]

    best_sharpe = {"sharpe": -999}
    best_return = {"exp_ret": -999}
    lowest_risk = {"exp_risk": 999}

    for i in range(MIX["iterations"]):
        w = _random_weights(len(coins), min_w)
        exp_ret, exp_risk, sharpe = _portfolio_stats_legacy(w, matrix)

        candidate = {"coins": coins, "weights": w,
                     "exp_ret": exp_ret, "exp_risk": exp_risk, "sharpe": sharpe}

        if sharpe   > best_sharpe["sharpe"]:  best_sharpe = candidate
        if exp_ret  > best_return["exp_ret"]: best_return = candidate
        if exp_risk < lowest_risk["exp_risk"]: lowest_risk = candidate

        if (i + 1) % 250 == 0:
            print(f"  … {i+1}/{MIX['iterations']}", end="\r")

    print(f"  ✓  {MIX['iterations']} iterations done.          ")
    return {"best_sharpe": best_sharpe,
            "best_return": best_return,
            "lowest_risk": lowest_risk}


def task_show_and_save(mixes: dict):
    _banner("Task 3 — Winning Mixes")
    if not mixes:
        return
    labels = {
        "best_sharpe": "Best Sharpe Ratio (MVO)",
        "best_return": "Best Expected Return",
        "lowest_risk": "Lowest Risk (Min Volatility)",
    }
    for key, label in labels.items():
        m = mixes.get(key)
        if not m:
            continue
        print(f"\n  ── {label} ──")
        print(f"  Return : {m['exp_ret']:+.4f}%   "
              f"Risk : {m['exp_risk']:.4f}%   "
              f"Sharpe : {m['sharpe']:.4f}")
        print(f"\n  {'Coin':<20} {'Weight':>8} {'Allocation':>12}")
        print("  " + "-"*42)
        weights = m["weights"]
        for cid, w in zip(m["coins"], weights):
            print(f"  {cid:<20} {w:>8.4f} {w*100:>11.2f}%")
        database.save_mix(label, m["coins"], weights,
                          m["exp_ret"], m["exp_risk"])
        print("  ✓  Saved to mix_results table.")

    # Log frontier size if available
    frontier = mixes.get("frontier", [])
    if frontier:
        print(f"\n  ✓  Efficient frontier ({len(frontier)} points) available via /api/efficient-frontier")


# ── Milestone runner ──────────────────────────────────────────────────────────
def run():
    returns = task_load_returns(WATCHLIST)
    input("\n  Press Enter …")

    mixes = task_run_mixes(returns)
    input("\n  Press Enter …")

    task_show_and_save(mixes)

if __name__ == "__main__":
    run()