import sys, time
from config import WATCHLIST


def _banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          Python Crypto Investment Manager — Auto Run         ║
╠══════════════════════════════════════════════════════════════╣
║  Milestone 1 → Setup & Learn                                 ║
║  Milestone 2 → Investment Mix Calculator                     ║
║  Milestone 3 → Risk Checker & Predictor                      ║
║  Milestone 4 → Spreading Rules                               ║                           
╚══════════════════════════════════════════════════════════════╝
""")


def run_milestone1():

    import database
    from config import WATCHLIST

    database.init_db()

    print("\n  Fetching live prices …")
    coins = database.get_prices(WATCHLIST)
    if coins:
        for c in coins:
            database.save_price(c)
        print(f"  {len(coins)} prices stored")
        for c in coins:
            chg = c.get("price_change_percentage_24h", 0) or 0
            print(f"     {c['symbol']:<8} ${c['current_price']:>14,.4f}  24h: {chg:+.2f}%")
    else:
        print("  Could not fetch prices — check internet connection")

    print("\n  Fetching trending coins …")
    trending = database.get_trending()
    for i, t in enumerate(trending, 1):
        print(f"  {i}. {t['symbol']:<10} {t['name']}")

    print("\n complete")
    return coins or []


def run_milestone2():
    import milestone2_mix_calculator as m2
    from config import WATCHLIST, MIX

    returns = m2.task_load_returns(WATCHLIST)
    if len(returns) < 2:
        print("   Not enough history for mix calculation — run again after more snapshots are collected")
        return

    mixes = m2.task_run_mixes(returns)
    if mixes:
        m2.task_show_and_save(mixes)
        print(f"\n complete — {MIX['iterations']} iterations done")
    else:
        print("  Mix calculation failed")


def run_milestone3(coins):
    import milestone3_risk_predictor as m3
    from config import WATCHLIST

    if coins:
        import database
        for c in coins:
            database.save_price(c)

    risk_results = m3.task_parallel_risk(WATCHLIST)
    predictions  = m3.task_run_predictions(WATCHLIST)
    alerts       = m3.task_check_alerts(coins)
    m3.task_export_csv(coins, risk_results, predictions, alerts)
    m3.task_send_email(alerts)

    print(f"\n complete")
    return risk_results, predictions, alerts


def run_milestone4(coins):

    import milestone4_spreading_rules as m4
    from config import WATCHLIST

    live = {c["id"]: c["current_price"] for c in coins} if coins else {}

    m4._add_demo_positions(live)
    m4.task_show_portfolio(live)
    m4.task_enforce_rules(live)

    n = len(WATCHLIST)
    equal_target = {cid: round(100/n, 2) for cid in WATCHLIST}
    m4.task_rebalance(live, equal_target)
    m4.task_stress_test(live)

    print(f"\n complete")


def run_milestone5():
    import milestone5_backtest as m5
    from config import WATCHLIST, PREDICTION

    short_w = PREDICTION["ma_short_window"]
    long_w  = PREDICTION["ma_long_window"]

    results = m5.task_run_backtest(WATCHLIST, short_w, long_w, capital=1000.0)
    if results:
        m5.task_summary(results, capital=1000.0)
        print(f"\n complete")
    else:
        print("  ⚠  No backtest results — need more price history")


def main():
    _banner()

    start = time.time()
    print(f"  Started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Watchlist: {', '.join(WATCHLIST)}\n")

    try:
        coins = run_milestone1()
        time.sleep(1)

        run_milestone2()
        time.sleep(1)

        run_milestone3(coins)
        time.sleep(1)

        run_milestone4(coins)
        time.sleep(1)

        run_milestone5()

    except KeyboardInterrupt:
        print("\n\n  Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        import traceback
        print(f"\n  ✗  Error: {e}")
        traceback.print_exc()
        sys.exit(1)

    elapsed = time.time() - start


if __name__ == "__main__":
    main()