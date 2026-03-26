import random, statistics
import database
from config import MIX, WATCHLIST


def _banner(t): print("\n" + "═"*58 + f"\n  {t}\n" + "═"*58)

def _pct_returns(prices: list) -> list:
    return [(prices[i] - prices[i-1]) / prices[i-1] * 100
            for i in range(1, len(prices))
            if prices[i-1] != 0]


def _random_weights(n: int, min_w: float) -> list:
    while True:
        raw = [random.random() for _ in range(n)]
        tot = sum(raw)
        w   = [x / tot for x in raw]
        if all(x >= min_w for x in w):
            return w


def _portfolio_stats(weights: list, returns_matrix: list) -> tuple:
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

def task_load_returns(coin_ids: list) -> dict:
    _banner("Task 1 — Load Return History from DB")
    returns = {}
    for cid in coin_ids:
        rows   = database.get_history(cid, limit=MIX["history_limit"])
        prices = [r["price_usd"] for r in reversed(rows) if r["price_usd"] and r["price_usd"] > 0]
        ret    = _pct_returns(prices)
        if ret:
            returns[cid] = ret
            print(f"   {cid:<18}  {len(ret)} return periods loaded")
        else:
            print(f"   {cid:<18}  not enough history (run Milestone 1 first)")
    return returns


def task_run_mixes(returns: dict) -> dict:
    _banner(f"Task 2 — {MIX['iterations']} Random Mix Iterations")
    if len(returns) < 2:
        print("  Need at least 2 coins with history. Run Milestone 1 first.")
        return {}

    coins  = list(returns.keys())
    matrix = [returns[c] for c in coins]
    min_w  = MIX["min_weight"]

    best_sharpe = {"sharpe": -999}
    best_return = {"exp_ret": -999}
    lowest_risk = {"exp_risk": 999}

    for i in range(MIX["iterations"]):
        w = _random_weights(len(coins), min_w)
        exp_ret, exp_risk, sharpe = _portfolio_stats(w, matrix)

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
        "best_sharpe": "Best Sharpe Ratio",
        "best_return": "Best Expected Return",
        "lowest_risk": "Lowest Risk",
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
        for cid, w in zip(m["coins"], m["weights"]):
            print(f"  {cid:<20} {w:>8.4f} {w*100:>11.2f}%")
        database.save_mix(label, m["coins"], m["weights"],
                          m["exp_ret"], m["exp_risk"])
        print("  ✓  Saved to mix_results table.")


# ── Milestone runner ──────────────────────────────────────────────────────────
def run():

    returns = task_load_returns(WATCHLIST)
    input("\n  Press Enter …")

    mixes = task_run_mixes(returns)
    input("\n  Press Enter …")

    task_show_and_save(mixes)

if __name__ == "__main__":
    run()