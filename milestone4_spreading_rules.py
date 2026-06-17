"""
milestone4_spreading_rules.py — Portfolio Spreading & Rebalancing Rules

Upgraded with:
  - Risk-parity allocation (inverse volatility weighting)
  - Correlation-aware spreading
  - Momentum-based allocation adjustments
  - Monte Carlo stress testing (10,000 scenarios)
"""

import random, statistics, math
import database
from config import SPREAD, WATCHLIST, RISK

# ── Optional numpy ────────────────────────────────────────────────────────────
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _banner(t): print("\n" + "="*58 + f"\n  {t}\n" + "="*58)


def _pct_returns(prices):
    return [(prices[i] - prices[i-1]) / prices[i-1] * 100
            for i in range(1, len(prices))
            if prices[i-1] != 0]


def _portfolio_values(live: dict, user_id=1) -> dict:
    return {p["coin_id"]: p["amount"] * live.get(p["coin_id"], 0)
            for p in database.get_portfolio(user_id)}


def _current_alloc(live: dict, user_id=1) -> dict:
    vals  = _portfolio_values(live, user_id)
    total = sum(vals.values()) or 1
    return {cid: round(v / total * 100, 2) for cid, v in vals.items()}


# ══════════════════════════════════════════════════════════════════════════════
#  RISK-PARITY ALLOCATION
# ══════════════════════════════════════════════════════════════════════════════

def risk_parity_target(coin_ids: list) -> dict:
    """
    Compute risk-parity target allocation.
    Each asset is weighted inversely proportional to its volatility.
    Result: riskier assets get LESS allocation.
    """
    vols = {}
    for cid in coin_ids:
        rows   = database.get_history(cid, limit=RISK["history_limit"])
        prices = [r["price_usd"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]
        if len(prices) < 3:
            vols[cid] = 1.0  # assume moderate if no data
            continue
        rets = _pct_returns(prices)
        vol  = statistics.pstdev(rets) if len(rets) >= 2 else 1.0
        vols[cid] = max(vol, 0.01)  # floor to avoid division by zero

    # Inverse-volatility weighting
    inv_vols = {cid: 1.0 / v for cid, v in vols.items()}
    total_inv = sum(inv_vols.values())

    target = {}
    for cid in coin_ids:
        raw_pct = (inv_vols[cid] / total_inv) * 100
        # Clamp to spread rules
        clamped = max(SPREAD["min_single_alloc_pct"],
                      min(SPREAD["max_single_alloc_pct"], raw_pct))
        target[cid] = round(clamped, 2)

    # Normalise to 100%
    total_target = sum(target.values())
    if total_target > 0:
        target = {cid: round(v / total_target * 100, 2) for cid, v in target.items()}

    return target


# ══════════════════════════════════════════════════════════════════════════════
#  CORRELATION-AWARE SPREADING
# ══════════════════════════════════════════════════════════════════════════════

def correlation_matrix(coin_ids: list) -> dict:
    """Compute pairwise correlation between coins."""
    returns_data = {}
    for cid in coin_ids:
        rows   = database.get_history(cid, limit=RISK["history_limit"])
        prices = [r["price_usd"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]
        returns_data[cid] = _pct_returns(prices) if len(prices) >= 3 else []

    # Align to shortest length
    min_len = min((len(r) for r in returns_data.values() if r), default=0)
    if min_len < 3:
        return {"coins": coin_ids, "matrix": [], "warnings": []}

    aligned = {cid: returns_data[cid][:min_len] for cid in coin_ids if returns_data[cid]}
    coins_with_data = list(aligned.keys())

    corr_matrix = []
    warnings = []

    for i, c1 in enumerate(coins_with_data):
        row = []
        for j, c2 in enumerate(coins_with_data):
            if i == j:
                row.append(1.0)
                continue
            r1 = aligned[c1]
            r2 = aligned[c2]
            # Pearson correlation
            mean1 = statistics.mean(r1)
            mean2 = statistics.mean(r2)
            std1  = statistics.pstdev(r1) or 0.001
            std2  = statistics.pstdev(r2) or 0.001
            cov   = sum((r1[k] - mean1) * (r2[k] - mean2) for k in range(min_len)) / min_len
            corr  = round(cov / (std1 * std2), 4)
            row.append(corr)

            # Warn if too correlated (diversification risk)
            if i < j and abs(corr) > 0.8:
                warnings.append(
                    f"⚠ {c1} ↔ {c2} correlation = {corr:.2f} — "
                    f"{'high positive' if corr > 0 else 'high negative'}, "
                    f"reduces diversification benefit")

        corr_matrix.append(row)

    return {"coins": coins_with_data, "matrix": corr_matrix, "warnings": warnings}


# ══════════════════════════════════════════════════════════════════════════════
#  MOMENTUM-BASED ALLOCATION ADJUSTMENT
# ══════════════════════════════════════════════════════════════════════════════

def momentum_adjustments(coin_ids: list, base_target: dict) -> dict:
    """
    Adjust target allocation based on recent momentum.
    Coins with positive momentum get a boost, negative get reduced.
    """
    adjusted = dict(base_target)

    for cid in coin_ids:
        if cid not in adjusted:
            continue
        rows   = database.get_history(cid, limit=10)
        prices = [r["price_usd"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]
        if len(prices) < 3:
            continue

        # Recent 5-period momentum
        momentum = (prices[-1] - prices[0]) / prices[0] * 100 if prices[0] > 0 else 0

        # Adjust ±20% of base allocation based on momentum
        if momentum > 2:
            boost = min(momentum * 0.5, 20)  # cap boost at +20%
            adjusted[cid] *= (1 + boost / 100)
        elif momentum < -2:
            reduction = min(abs(momentum) * 0.5, 20)  # cap reduction at -20%
            adjusted[cid] *= (1 - reduction / 100)

    # Clamp and re-normalise
    for cid in adjusted:
        adjusted[cid] = max(SPREAD["min_single_alloc_pct"],
                            min(SPREAD["max_single_alloc_pct"], adjusted[cid]))

    total = sum(adjusted.values())
    if total > 0:
        adjusted = {cid: round(v / total * 100, 2) for cid, v in adjusted.items()}

    return adjusted


# ══════════════════════════════════════════════════════════════════════════════
#  MONTE CARLO STRESS TESTING
# ══════════════════════════════════════════════════════════════════════════════

def monte_carlo_stress(live: dict, n_sims: int = 10000, user_id=1) -> dict:
    """
    Monte Carlo stress test using historical return distributions.
    Simulates n_sims random market scenarios for the portfolio.
    """
    positions = database.get_portfolio(user_id)
    total_now = sum(p["amount"] * live.get(p["coin_id"], 0) for p in positions)
    if total_now == 0:
        return {"error": "No portfolio value"}

    # Load historical returns per coin
    returns_data = {}
    for p in positions:
        cid  = p["coin_id"]
        rows = database.get_history(cid, limit=RISK["history_limit"])
        prices = [r["price_usd"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]
        if len(prices) >= 3:
            returns_data[cid] = _pct_returns(prices)

    if not returns_data:
        return {"error": "Not enough history for simulation"}

    # Simulate scenarios
    scenario_pnls = []
    for _ in range(n_sims):
        scenario_value = 0
        for p in positions:
            cid   = p["coin_id"]
            price = live.get(cid, 0)
            if cid in returns_data and returns_data[cid]:
                # Random return from historical distribution
                rand_return = random.choice(returns_data[cid]) / 100
            else:
                rand_return = random.gauss(0, 0.05)

            new_price = price * (1 + rand_return)
            scenario_value += p["amount"] * new_price

        scenario_pnls.append(scenario_value - total_now)

    scenario_pnls.sort()
    n = len(scenario_pnls)

    # Percentile calculations
    pct_5   = scenario_pnls[int(n * 0.05)]
    pct_25  = scenario_pnls[int(n * 0.25)]
    pct_50  = scenario_pnls[int(n * 0.50)]
    pct_75  = scenario_pnls[int(n * 0.75)]
    pct_95  = scenario_pnls[int(n * 0.95)]
    worst   = scenario_pnls[0]
    best    = scenario_pnls[-1]
    avg_pnl = sum(scenario_pnls) / n

    # Probability of loss
    losses = [p for p in scenario_pnls if p < 0]
    prob_loss = len(losses) / n * 100

    return {
        "base_value":    round(total_now, 2),
        "simulations":   n_sims,
        "avg_pnl":       round(avg_pnl, 2),
        "worst_case":    round(worst, 2),
        "best_case":     round(best, 2),
        "percentile_5":  round(pct_5, 2),
        "percentile_25": round(pct_25, 2),
        "median":        round(pct_50, 2),
        "percentile_75": round(pct_75, 2),
        "percentile_95": round(pct_95, 2),
        "prob_loss_%":   round(prob_loss, 1),
        "var_95":        round(-pct_5, 2),    # 95% VaR
        "cvar_95":       round(-sum(scenario_pnls[:int(n * 0.05)]) / max(int(n * 0.05), 1), 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  TASK FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def task_show_portfolio(live: dict, user_id=1):
    _banner("Task 1 — Current Portfolio")
    positions = database.get_portfolio(user_id)
    if not positions:
        print("  (Empty — demo positions will be added)")
        return
    alloc = _current_alloc(live, user_id)
    total = sum(_portfolio_values(live, user_id).values())
    print(f"\n  {'Coin':<18} {'Amount':>10} {'Price':>12} "
          f"{'Value $':>12} {'Alloc %':>8} {'P&L %':>8}")
    print("  " + "-"*72)
    for p in positions:
        cid   = p["coin_id"]
        price = live.get(cid, 0)
        val   = p["amount"] * price
        cost  = p["amount"] * p["avg_buy"]
        pnl   = (val - cost) / cost * 100 if cost else 0
        print(f"  {cid:<18} {p['amount']:>10g} {price:>12,.4f} "
              f"{val:>12,.2f} {alloc.get(cid,0):>7.2f}% "
              f"{'+' if pnl>=0 else ''}{pnl:>7.2f}%")
    print("  " + "-"*72)
    print(f"  {'TOTAL':>54}  ${total:>11,.2f}")


def task_enforce_rules(live: dict, user_id=1) -> list:
    _banner("Task 2 — Rule Enforcement")
    print(f"  config.SPREAD  →  "
          f"max={SPREAD['max_single_alloc_pct']}%  "
          f"min={SPREAD['min_single_alloc_pct']}%\n")

    alloc   = _current_alloc(live, user_id)
    actions = []
    for cid, pct in alloc.items():
        if pct > SPREAD["max_single_alloc_pct"]:
            msg = (f"REDUCE {cid}: {pct:.2f}% > max "
                   f"{SPREAD['max_single_alloc_pct']}%")
            print(f"  ⚠  {msg}")
            actions.append(msg)
        elif pct < SPREAD["min_single_alloc_pct"]:
            msg = (f"INCREASE {cid}: {pct:.2f}% < min "
                   f"{SPREAD['min_single_alloc_pct']}%")
            print(f"  ⚠  {msg}")
            actions.append(msg)
        else:
            print(f"  ✓  {cid:<18} {pct:.2f}%  (OK)")
    if not actions:
        print("\n  All positions within bounds.")
    return actions


def task_rebalance(live: dict, target: dict, user_id=1):
    _banner(f"Task 3 — Drift Detector  "
            f"(threshold={SPREAD['rebalance_drift_pct']}pp)")
    current = _current_alloc(live, user_id)
    if not current:
        print("  (Portfolio is empty)")
        return

    print(f"\n  {'Coin':<18} {'Current %':>10} {'Target %':>10} "
          f"{'Drift pp':>10} {'Action':>8}")
    print("  " + "-"*58)

    changes = []
    for cid in set(list(current) + list(target)):
        cur   = current.get(cid, 0)
        tgt   = target.get(cid, 0)
        drift = cur - tgt
        needs = abs(drift) > SPREAD["rebalance_drift_pct"]
        action = ("SELL" if drift > 0 else "BUY") if needs else "hold"
        mark   = "⚡" if needs else " "
        print(f"  {mark} {cid:<18} {cur:>10.2f} {tgt:>10.2f} "
              f"{drift:>+10.2f} {action:>8}")
        if needs:
            changes.append(f"{action} {cid} (drift {drift:+.2f}pp)")

    if changes:
        desc = " | ".join(changes)
        database.log_rebalance(desc)
        print(f"\n  ✓  Logged  →  rebalance_log table")
        print(f"  {desc}")
    else:
        print(f"\n  Portfolio balanced — no drift exceeds "
              f"{SPREAD['rebalance_drift_pct']}pp.")


def task_risk_parity(live: dict, user_id=1):
    """Show risk-parity target vs current allocation."""
    _banner("Task 3b — Risk-Parity Target Allocation")
    coin_ids = list(_portfolio_values(live, user_id).keys())
    if not coin_ids:
        coin_ids = WATCHLIST

    rp_target = risk_parity_target(coin_ids)
    current   = _current_alloc(live, user_id)

    print(f"\n  {'Coin':<18} {'Current %':>10} {'Risk-Parity %':>14} {'Drift pp':>10}")
    print("  " + "-"*54)
    for cid in coin_ids:
        cur = current.get(cid, 0)
        tgt = rp_target.get(cid, 0)
        drift = cur - tgt
        print(f"  {cid:<18} {cur:>10.2f} {tgt:>14.2f} {drift:>+10.2f}")


def task_correlation_check(coin_ids: list = None):
    """Show correlation matrix and diversification warnings."""
    _banner("Task 3c — Correlation Analysis")
    if coin_ids is None:
        coin_ids = WATCHLIST

    corr_data = correlation_matrix(coin_ids)
    coins = corr_data["coins"]
    matrix = corr_data["matrix"]

    if not matrix:
        print("  Not enough data for correlation analysis.")
        return corr_data

    header = "  " + f"{'':18}" + " ".join(f"{c[:8]:>9}" for c in coins)
    print(header)
    for i, c in enumerate(coins):
        row_str = " ".join(f"{matrix[i][j]:>9.3f}" for j in range(len(coins)))
        print(f"  {c:<18}{row_str}")

    if corr_data["warnings"]:
        print()
        for w in corr_data["warnings"]:
            print(f"  {w}")
    else:
        print("\n  ✓  Good diversification — no pair exceeds ±0.80 correlation.")

    return corr_data


def task_stress_test(live: dict, user_id=1):
    _banner("Task 4 — Stress Scenarios + Monte Carlo")
    positions = database.get_portfolio(user_id)
    total_now = sum(p["amount"] * live.get(p["coin_id"], 0) for p in positions)
    if total_now == 0:
        print("  (No portfolio value to stress-test)")
        return

    # Fixed scenarios
    print(f"\n  Current value  :  ${total_now:,.2f}\n")
    print(f"  {'Scenario':<20} {'Shock':>8} {'New Value $':>14} "
          f"{'P&L $':>12} {'P&L %':>8}")
    print("  " + "-"*64)
    for name, pct in SPREAD["stress_scenarios"].items():
        new_val = total_now * (1 + pct / 100)
        pnl     = new_val - total_now
        print(f"  {name:<20} {pct:>+7.1f}%  {new_val:>14,.2f} "
              f"{pnl:>+12,.2f} {pct:>+7.1f}%")

    # Monte Carlo
    n_sims = SPREAD.get("monte_carlo_sims", 10000)
    print(f"\n  ── Monte Carlo Simulation ({n_sims:,} scenarios) ──")
    mc = monte_carlo_stress(live, n_sims, user_id)
    if "error" in mc:
        print(f"  {mc['error']}")
        return mc

    print(f"  Avg P&L          : ${mc['avg_pnl']:>+12,.2f}")
    print(f"  Worst case       : ${mc['worst_case']:>+12,.2f}")
    print(f"  Best case        : ${mc['best_case']:>+12,.2f}")
    print(f"  5th percentile   : ${mc['percentile_5']:>+12,.2f}")
    print(f"  95th percentile  : ${mc['percentile_95']:>+12,.2f}")
    print(f"  95% VaR          : ${mc['var_95']:>12,.2f}")
    print(f"  95% CVaR         : ${mc['cvar_95']:>12,.2f}")
    print(f"  Prob of loss     :  {mc['prob_loss_%']:.1f}%")

    return mc


def _add_demo_positions(live: dict, user_id=1):
    if database.get_portfolio(user_id):
        return
    print("\n  (Portfolio empty — adding demo positions)")
    demos = [("bitcoin","BTC",0.05,65000), ("ethereum","ETH",0.5,3200),
             ("solana","SOL",5.0,150),     ("binancecoin","BNB",1.0,400)]
    for cid, sym, amt, avg in demos:
        if live.get(cid, 0) > 0:
            database.upsert_position(cid, sym, amt, avg, user_id)
    print("  Demo positions added.")


def run():

    print("\n  Fetching live prices …")
    coins = database.get_prices(WATCHLIST)
    live  = {c["id"]: c["current_price"] for c in coins} if coins else {}

    _add_demo_positions(live)

    task_show_portfolio(live)
    input("\n  Press Enter …")

    task_enforce_rules(live)
    input("\n  Press Enter …")

    # Risk-parity target instead of simple equal-weight
    rp_target = risk_parity_target(WATCHLIST)
    task_rebalance(live, rp_target)
    input("\n  Press Enter …")

    task_risk_parity(live)
    input("\n  Press Enter …")

    task_correlation_check(WATCHLIST)
    input("\n  Press Enter …")

    task_stress_test(live)


if __name__ == "__main__":
    run()
