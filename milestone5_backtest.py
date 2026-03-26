import database
from config import WATCHLIST, PREDICTION


def _banner(t): print("\n" + "═"*58 + f"\n  {t}\n" + "═"*58)


def _moving_average(prices: list, window: int) -> list:
    return [sum(prices[i-window:i])/window if i >= window else None
            for i in range(len(prices))]


def backtest_coin(coin_id: str, short_w: int, long_w: int,
                  capital: float = 1000.0) -> dict:
    rows   = database.get_history(coin_id, limit=500)
    prices = [r["price_usd"] for r in reversed(rows)
              if r["price_usd"] and r["price_usd"] > 0]

    if len(prices) < long_w + 2:
        return {"coin_id": coin_id,
                "error": f"Not enough history (need {long_w + 2}, have {len(prices)})"}

    short_ma = _moving_average(prices, short_w)
    long_ma  = _moving_average(prices, long_w)

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
            equity.append(cash)
            continue

        # Golden cross — BUY signal
        if (not position and s > l and
                (i == 0 or short_ma[i-1] is None or long_ma[i-1] is None
                 or short_ma[i-1] <= long_ma[i-1])):
            holding  = cash / p
            cash     = 0.0
            position = True
            trades.append({"type": "BUY", "price": p, "idx": i})

        # Death cross — SELL signal
        elif (position and s < l and
              (i == 0 or short_ma[i-1] is None or long_ma[i-1] is None
               or short_ma[i-1] >= long_ma[i-1])):
            proceeds  = holding * p
            buy_price = trades[-1]["price"]
            pnl       = proceeds - (holding * buy_price)
            trades[-1].update({"sell_price": p, "pnl": round(pnl, 4), "win": pnl > 0})
            trades.append({"type": "SELL", "price": p, "pnl": round(pnl, 4)})
            cash      = proceeds
            holding   = 0.0
            position  = False

        val    = (holding * p) + cash
        peak   = max(peak, val)
        dd     = (peak - val) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)
        equity.append(round(val, 2))

    final_val    = (holding * prices[-1]) + cash if holding else cash
    total_return = (final_val - capital) / capital * 100
    completed    = [t for t in trades if t["type"] == "SELL"]
    wins         = [t for t in completed if t.get("win")]
    win_rate     = len(wins) / len(completed) * 100 if completed else 0

    return {
        "coin_id":      coin_id,
        "capital":      capital,
        "final_value":  round(final_val, 2),
        "total_return": round(total_return, 2),
        "max_drawdown": round(max_dd, 2),
        "total_trades": len(completed),
        "win_rate":     round(win_rate, 1),
        "trades":       [t for t in trades if t["type"] == "SELL"],
        "snapshots":    len(prices),
    }


def task_run_backtest(coin_ids: list, short_w: int, long_w: int,
                      capital: float = 1000.0) -> list:
    _banner(f"Task 1 — MA Crossover Backtest  (short={short_w}  long={long_w})")
    print(f"  Starting capital: ${capital:,.2f}\n")

    results = []
    for cid in coin_ids:
        r = backtest_coin(cid, short_w, long_w, capital)
        if "error" in r:
            print(f" {cid:<18} {r['error']}")
            continue

        ret   = r["total_return"]
        icon  = "🟢" if ret >= 0 else "🔴"
        print(f"  {icon} {cid:<18}  "
              f"return={ret:+.2f}%  "
              f"final=${r['final_value']:>10,.2f}  "
              f"trades={r['total_trades']:>3}  "
              f"win={r['win_rate']:.0f}%  "
              f"maxDD={r['max_drawdown']:.2f}%")
        results.append(r)

    return results


def task_show_trades(results: list):
    _banner("Task 2 — Simulated Trade Log")
    for r in results:
        print(f"\n  ── {r['coin_id'].upper()} ──")
        trades = r.get("trades", [])
        if not trades:
            print("  No completed trades.")
            continue
        print(f"  {'#':<4} {'Buy $':>12} {'Sell $':>12} {'P&L':>12} {'Result'}")
        print("  " + "-"*52)
        for i, t in enumerate(trades, 1):
            win = t.get("win", False)
            print(f"  {i:<4} "
                  f"${t.get('price', 0):>11,.4f} "
                  f"${t.get('sell_price', 0):>11,.4f} "
                  f"{'+' if t['pnl']>=0 else ''}${t['pnl']:>10,.4f} "
                  f"{'✓ WIN' if win else '✗ LOSS'}")


def task_summary(results: list, capital: float):
    _banner("Task 3 — Summary")
    if not results:
        print("  No results to summarise.")
        return

    print(f"  {'Coin':<20} {'Return':>10} {'Final $':>12} {'Trades':>8} "
          f"{'Win%':>7} {'MaxDD':>8}")
    print("  " + "-"*70)

    total_ret = 0
    for r in results:
        total_ret += r["total_return"]
        print(f"  {r['coin_id']:<20} "
              f"{r['total_return']:>+9.2f}%  "
              f"${r['final_value']:>11,.2f}  "
              f"{r['total_trades']:>7}  "
              f"{r['win_rate']:>6.1f}%  "
              f"{r['max_drawdown']:>7.2f}%")

    avg_ret = total_ret / len(results)
    print("  " + "-"*70)
    print(f"  {'Average return':<20} {avg_ret:>+9.2f}%")
    print(f"\n  Strategy: {'Short MA > Long MA = BUY, Short MA < Long MA = SELL'}")
    print(f"  Note: past performance does not predict future results.")


def run():

    short_w = PREDICTION["ma_short_window"]
    long_w  = PREDICTION["ma_long_window"]
    capital = 1000.0

    print(f"\n  Config: short MA={short_w}  long MA={long_w}  capital=${capital:,.0f}")

    results = task_run_backtest(WATCHLIST, short_w, long_w, capital)
    input("\n  Press Enter …")

    task_show_trades(results)
    input("\n  Press Enter …")

    task_summary(results, capital)

if __name__ == "__main__":
    run()