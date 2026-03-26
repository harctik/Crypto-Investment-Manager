import database
from config import SPREAD, WATCHLIST


def _banner(t): print("\n" + "═"*58 + f"\n  {t}\n" + "═"*58)

def _portfolio_values(live: dict) -> dict:
    return {p["coin_id"]: p["amount"] * live.get(p["coin_id"], 0)
            for p in database.get_portfolio()}


def _current_alloc(live: dict) -> dict:
    vals  = _portfolio_values(live)
    total = sum(vals.values()) or 1
    return {cid: round(v / total * 100, 2) for cid, v in vals.items()}

def task_show_portfolio(live: dict):
    _banner("Task 1 — Current Portfolio")
    positions = database.get_portfolio()
    if not positions:
        print("  (Empty — demo positions will be added)")
        return
    alloc = _current_alloc(live)
    total = sum(_portfolio_values(live).values())
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


def task_enforce_rules(live: dict) -> list:
    _banner("Task 2 — Rule Enforcement")
    print(f"  config.SPREAD  →  "
          f"max={SPREAD['max_single_alloc_pct']}%  "
          f"min={SPREAD['min_single_alloc_pct']}%\n")

    alloc   = _current_alloc(live)
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


def task_rebalance(live: dict, target: dict):
    _banner(f"Task 3 — Drift Detector  "
            f"(threshold={SPREAD['rebalance_drift_pct']}pp)")
    current = _current_alloc(live)
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


def task_stress_test(live: dict):
    _banner("Task 4 — Stress Scenarios  (config.SPREAD['stress_scenarios'])")
    positions = database.get_portfolio()
    total_now = sum(p["amount"] * live.get(p["coin_id"], 0) for p in positions)
    if total_now == 0:
        print("  (No portfolio value to stress-test)")
        return

    print(f"\n  Current value  :  ${total_now:,.2f}\n")
    print(f"  {'Scenario':<20} {'Shock':>8} {'New Value $':>14} "
          f"{'P&L $':>12} {'P&L %':>8}")
    print("  " + "-"*64)
    for name, pct in SPREAD["stress_scenarios"].items():
        new_val = total_now * (1 + pct / 100)
        pnl     = new_val - total_now
        print(f"  {name:<20} {pct:>+7.1f}%  {new_val:>14,.2f} "
              f"{pnl:>+12,.2f} {pct:>+7.1f}%")

    print(f"\n  Edit scenarios in  config.SPREAD['stress_scenarios']")


def _add_demo_positions(live: dict):
    if database.get_portfolio():
        return
    print("\n  (Portfolio empty — adding demo positions)")
    demos = [("bitcoin","BTC",0.05,65000), ("ethereum","ETH",0.5,3200),
             ("solana","SOL",5.0,150),     ("binancecoin","BNB",1.0,400)]
    for cid, sym, amt, avg in demos:
        if live.get(cid, 0) > 0:
            database.upsert_position(cid, sym, amt, avg)
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

    n = len(WATCHLIST)
    equal_target = {cid: round(100/n, 2) for cid in WATCHLIST}
    task_rebalance(live, equal_target)
    input("\n  Press Enter …")

    task_stress_test(live)


if __name__ == "__main__":
    run()
