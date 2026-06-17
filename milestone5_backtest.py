"""
milestone5_backtest.py — Multi-Strategy Backtesting Engine

Strategies:
  1. MA Crossover (Golden Cross / Death Cross) — FIXED off-by-one bug
  2. RSI Mean-Reversion (buy oversold, sell overbought)
  3. Bollinger Band Breakout
  4. Ensemble Voting (weighted combination of all signals)
"""

import statistics
import database
from config import WATCHLIST, PREDICTION

# ── Import indicators from milestone3 ─────────────────────────────────────────
try:
    from milestone3_risk_predictor import RSI, bollinger_bands, MACD
except ImportError:
    # Inline fallbacks if milestone3 not available
    def RSI(prices, period=14):
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
            rsi[period] = round(100 - (100 / (1 + avg_gain / avg_loss)), 4)
        for i in range(period + 1, len(prices)):
            change = prices[i] - prices[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(change, 0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-change, 0)) / period
            if avg_loss == 0:
                rsi[i] = 100.0
            else:
                rsi[i] = round(100 - (100 / (1 + avg_gain / avg_loss)), 4)
        return rsi

    def bollinger_bands(prices, period=20, num_std=2):
        n = len(prices)
        upper, lower = [None]*n, [None]*n
        for i in range(period - 1, n):
            w = prices[i - period + 1 : i + 1]
            sma = sum(w) / period
            std = (sum((x - sma)**2 for x in w) / period)**0.5
            upper[i] = sma + num_std * std
            lower[i] = sma - num_std * std
        return {"upper": upper, "lower": lower}

    def MACD(prices, fast=12, slow=26, signal=9):
        return {"macd_line": [None]*len(prices), "signal_line": [None]*len(prices),
                "histogram": [None]*len(prices)}


def _banner(t): print("\n" + "="*58 + f"\n  {t}\n" + "="*58)


def _moving_average(prices: list, window: int) -> list:
    """FIXED: correct window that includes current price."""
    return [sum(prices[i - window + 1 : i + 1]) / window if i >= window - 1 else None
            for i in range(len(prices))]


# ══════════════════════════════════════════════════════════════════════════════
#  STRATEGY 1: MA CROSSOVER
# ══════════════════════════════════════════════════════════════════════════════

def backtest_ma_crossover(prices: list, short_w: int, long_w: int,
                          capital: float = 1000.0) -> dict:
    """Moving Average crossover: buy on golden cross, sell on death cross."""
    if len(prices) < long_w + 2:
        return {"error": f"Not enough data (need {long_w + 2}, have {len(prices)})"}

    short_ma = _moving_average(prices, short_w)
    long_ma  = _moving_average(prices, long_w)

    cash, holding, position = capital, 0.0, False
    trades, equity = [], []
    peak, max_dd = capital, 0.0

    for i in range(len(prices)):
        s, l, p = short_ma[i], long_ma[i], prices[i]
        if s is None or l is None:
            equity.append(cash)
            continue

        # Golden cross — BUY
        if (not position and s > l and
                (i == 0 or short_ma[i-1] is None or long_ma[i-1] is None
                 or short_ma[i-1] <= long_ma[i-1])):
            holding  = cash / p
            cash     = 0.0
            position = True
            trades.append({"type": "BUY", "price": p, "idx": i})

        # Death cross — SELL
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

    return _summarise(prices, capital, cash, holding, trades, equity, max_dd)


# ══════════════════════════════════════════════════════════════════════════════
#  STRATEGY 2: RSI MEAN-REVERSION
# ══════════════════════════════════════════════════════════════════════════════

def backtest_rsi(prices: list, period: int = 14,
                 buy_threshold: float = 30, sell_threshold: float = 70,
                 capital: float = 1000.0) -> dict:
    """Buy when RSI drops below buy_threshold, sell when RSI rises above sell_threshold."""
    if len(prices) < period + 5:
        return {"error": f"Not enough data (need {period + 5}, have {len(prices)})"}

    rsi_vals = RSI(prices, period)

    cash, holding, position = capital, 0.0, False
    trades, equity = [], []
    peak, max_dd = capital, 0.0

    for i in range(len(prices)):
        p = prices[i]
        rsi = rsi_vals[i]

        if rsi is not None:
            # BUY when oversold
            if not position and rsi < buy_threshold:
                holding  = cash / p
                cash     = 0.0
                position = True
                trades.append({"type": "BUY", "price": p, "idx": i, "rsi": rsi})

            # SELL when overbought
            elif position and rsi > sell_threshold:
                proceeds  = holding * p
                buy_price = trades[-1]["price"]
                pnl       = proceeds - (holding * buy_price)
                trades[-1].update({"sell_price": p, "pnl": round(pnl, 4), "win": pnl > 0})
                trades.append({"type": "SELL", "price": p, "pnl": round(pnl, 4), "rsi": rsi})
                cash      = proceeds
                holding   = 0.0
                position  = False

        val    = (holding * p) + cash
        peak   = max(peak, val)
        dd     = (peak - val) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)
        equity.append(round(val, 2))

    return _summarise(prices, capital, cash, holding, trades, equity, max_dd)


# ══════════════════════════════════════════════════════════════════════════════
#  STRATEGY 3: BOLLINGER BAND BREAKOUT
# ══════════════════════════════════════════════════════════════════════════════

def backtest_bollinger(prices: list, period: int = 20, num_std: int = 2,
                       capital: float = 1000.0) -> dict:
    """Buy when price touches lower band, sell when price touches upper band."""
    if len(prices) < period + 5:
        return {"error": f"Not enough data (need {period + 5}, have {len(prices)})"}

    bb = bollinger_bands(prices, period, num_std)

    cash, holding, position = capital, 0.0, False
    trades, equity = [], []
    peak, max_dd = capital, 0.0

    for i in range(len(prices)):
        p = prices[i]

        if bb["lower"][i] is not None and bb["upper"][i] is not None:
            # BUY near lower band
            if not position and p <= bb["lower"][i]:
                holding  = cash / p
                cash     = 0.0
                position = True
                trades.append({"type": "BUY", "price": p, "idx": i})

            # SELL near upper band
            elif position and p >= bb["upper"][i]:
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

    return _summarise(prices, capital, cash, holding, trades, equity, max_dd)


# ══════════════════════════════════════════════════════════════════════════════
#  STRATEGY 4: ENSEMBLE VOTING
# ══════════════════════════════════════════════════════════════════════════════

def backtest_ensemble(prices: list, short_w: int = 5, long_w: int = 15,
                      rsi_period: int = 14, bb_period: int = 20,
                      capital: float = 1000.0) -> dict:
    """
    Ensemble strategy: combines MA, RSI, and Bollinger signals.
    Buy when ≥2 of 3 strategies agree on BUY, sell when ≥2 agree on SELL.
    """
    min_data = max(long_w, rsi_period, bb_period) + 5
    if len(prices) < min_data:
        return {"error": f"Not enough data (need {min_data}, have {len(prices)})"}

    short_ma = _moving_average(prices, short_w)
    long_ma  = _moving_average(prices, long_w)
    rsi_vals = RSI(prices, rsi_period)
    bb       = bollinger_bands(prices, bb_period, 2)

    cash, holding, position = capital, 0.0, False
    trades, equity = [], []
    peak, max_dd = capital, 0.0

    for i in range(len(prices)):
        p = prices[i]
        buy_votes, sell_votes = 0, 0

        # MA signal
        if (short_ma[i] is not None and long_ma[i] is not None and
                i > 0 and short_ma[i-1] is not None and long_ma[i-1] is not None):
            if short_ma[i] > long_ma[i] and short_ma[i-1] <= long_ma[i-1]:
                buy_votes += 1
            elif short_ma[i] < long_ma[i] and short_ma[i-1] >= long_ma[i-1]:
                sell_votes += 1
            elif short_ma[i] > long_ma[i]:
                buy_votes += 0.5
            elif short_ma[i] < long_ma[i]:
                sell_votes += 0.5

        # RSI signal
        if rsi_vals[i] is not None:
            if rsi_vals[i] < 30:
                buy_votes += 1
            elif rsi_vals[i] > 70:
                sell_votes += 1
            elif rsi_vals[i] < 45:
                buy_votes += 0.3
            elif rsi_vals[i] > 55:
                sell_votes += 0.3

        # Bollinger signal
        if bb["lower"][i] is not None and bb["upper"][i] is not None:
            if p <= bb["lower"][i]:
                buy_votes += 1
            elif p >= bb["upper"][i]:
                sell_votes += 1

        # Execute based on consensus (need ≥1.5 votes)
        if not position and buy_votes >= 1.5:
            holding  = cash / p
            cash     = 0.0
            position = True
            trades.append({"type": "BUY", "price": p, "idx": i,
                           "votes": round(buy_votes, 1)})

        elif position and sell_votes >= 1.5:
            proceeds  = holding * p
            buy_price = trades[-1]["price"]
            pnl       = proceeds - (holding * buy_price)
            trades[-1].update({"sell_price": p, "pnl": round(pnl, 4), "win": pnl > 0})
            trades.append({"type": "SELL", "price": p, "pnl": round(pnl, 4),
                           "votes": round(sell_votes, 1)})
            cash      = proceeds
            holding   = 0.0
            position  = False

        val    = (holding * p) + cash
        peak   = max(peak, val)
        dd     = (peak - val) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)
        equity.append(round(val, 2))

    return _summarise(prices, capital, cash, holding, trades, equity, max_dd)


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _summarise(prices, capital, cash, holding, trades, equity, max_dd):
    final_val    = (holding * prices[-1]) + cash if holding else cash
    total_return = (final_val - capital) / capital * 100
    completed    = [t for t in trades if t["type"] == "SELL"]
    wins         = [t for t in completed if t.get("win")]
    win_rate     = len(wins) / len(completed) * 100 if completed else 0

    return {
        "capital":      capital,
        "final_value":  round(final_val, 2),
        "total_return": round(total_return, 2),
        "max_drawdown": round(max_dd, 2),
        "total_trades": len(completed),
        "win_rate":     round(win_rate, 1),
        "trades":       [t for t in trades if t["type"] == "SELL"],
        "snapshots":    len(prices),
    }


def backtest_coin(coin_id: str, short_w: int, long_w: int,
                  capital: float = 1000.0) -> dict:
    """Run all strategies for a single coin and compare."""
    rows   = database.get_history(coin_id, limit=500)
    prices = [r["price_usd"] for r in reversed(rows)
              if r["price_usd"] and r["price_usd"] > 0]

    if len(prices) < long_w + 2:
        return {"coin_id": coin_id,
                "error": f"Not enough history (need {long_w + 2}, have {len(prices)})"}

    strategies = {}

    # Strategy 1: MA Crossover
    ma_result = backtest_ma_crossover(prices, short_w, long_w, capital)
    if "error" not in ma_result:
        strategies["ma_crossover"] = {**ma_result, "name": "MA Crossover"}

    # Strategy 2: RSI Mean-Reversion
    rsi_result = backtest_rsi(prices, period=PREDICTION.get("rsi_period", 14),
                              capital=capital)
    if "error" not in rsi_result:
        strategies["rsi_reversion"] = {**rsi_result, "name": "RSI Reversion"}

    # Strategy 3: Bollinger Bands
    bb_result = backtest_bollinger(prices,
                                   period=PREDICTION.get("bollinger_period", 20),
                                   capital=capital)
    if "error" not in bb_result:
        strategies["bollinger"] = {**bb_result, "name": "Bollinger Bands"}

    # Strategy 4: Ensemble
    ens_result = backtest_ensemble(prices, short_w, long_w,
                                   PREDICTION.get("rsi_period", 14),
                                   PREDICTION.get("bollinger_period", 20),
                                   capital)
    if "error" not in ens_result:
        strategies["ensemble"] = {**ens_result, "name": "Ensemble Voting"}

    # Buy & Hold benchmark
    bh_return = (prices[-1] - prices[0]) / prices[0] * 100
    strategies["buy_hold"] = {
        "name": "Buy & Hold",
        "capital": capital,
        "final_value": round(capital * (1 + bh_return / 100), 2),
        "total_return": round(bh_return, 2),
        "max_drawdown": 0,
        "total_trades": 0,
        "win_rate": 0,
        "trades": [],
        "snapshots": len(prices),
    }

    # Find best strategy
    best_key = max(strategies.keys(),
                   key=lambda k: strategies[k].get("total_return", -999))

    return {
        "coin_id":    coin_id,
        "strategies": strategies,
        "best":       best_key,
        "snapshots":  len(prices),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  TASK FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def task_run_backtest(coin_ids: list, short_w: int, long_w: int,
                      capital: float = 1000.0) -> list:
    _banner(f"Task 1 — Multi-Strategy Backtest  (short={short_w}  long={long_w})")
    print(f"  Starting capital: ${capital:,.2f}")
    print(f"  Strategies: MA Crossover, RSI Reversion, Bollinger Bands, Ensemble Voting\n")

    results = []
    for cid in coin_ids:
        r = backtest_coin(cid, short_w, long_w, capital)
        if "error" in r:
            print(f" {cid:<18} {r['error']}")
            continue

        print(f"  ── {cid.upper()} ({r['snapshots']} snapshots) ──")
        for key, s in r["strategies"].items():
            icon = "🟢" if s["total_return"] >= 0 else "🔴"
            best = "⭐" if key == r["best"] else "  "
            print(f"    {best}{icon} {s['name']:<20}  "
                  f"return={s['total_return']:+.2f}%  "
                  f"final=${s['final_value']:>10,.2f}  "
                  f"trades={s['total_trades']:>3}  "
                  f"win={s['win_rate']:.0f}%  "
                  f"maxDD={s['max_drawdown']:.2f}%")
        print()
        results.append(r)

    return results


def task_show_trades(results: list):
    _banner("Task 2 — Best Strategy Trade Log")
    for r in results:
        best_key = r.get("best", "ma_crossover")
        best_strat = r["strategies"].get(best_key, {})
        print(f"\n  ── {r['coin_id'].upper()} — {best_strat.get('name', 'N/A')} ──")
        trades = best_strat.get("trades", [])
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
                  f"{'+'if t['pnl']>=0 else ''}${t['pnl']:>10,.4f} "
                  f"{'✓ WIN' if win else '✗ LOSS'}")


def task_summary(results: list, capital: float):
    _banner("Task 3 — Strategy Comparison Summary")
    if not results:
        print("  No results to summarise.")
        return

    # Collect all strategy names
    all_strategies = set()
    for r in results:
        all_strategies.update(r["strategies"].keys())

    for strat_key in sorted(all_strategies):
        strat_name = None
        total_ret = 0
        count = 0
        print_rows = []
        for r in results:
            s = r["strategies"].get(strat_key)
            if not s:
                continue
            if strat_name is None:
                strat_name = s["name"]
            total_ret += s["total_return"]
            count += 1
            print_rows.append((r["coin_id"], s))

        if not count:
            continue

        print(f"\n  === {strat_name} ===")
        print(f"  {'Coin':<20} {'Return':>10} {'Final $':>12} {'Trades':>8} "
              f"{'Win%':>7} {'MaxDD':>8}")
        print("  " + "-"*70)
        for cid, s in print_rows:
            print(f"  {cid:<20} "
                  f"{s['total_return']:>+9.2f}%  "
                  f"${s['final_value']:>11,.2f}  "
                  f"{s['total_trades']:>7}  "
                  f"{s['win_rate']:>6.1f}%  "
                  f"{s['max_drawdown']:>7.2f}%")
        avg_ret = total_ret / count
        print(f"  {'Average':>20} {avg_ret:>+9.2f}%")

    print(f"\n  ⭐ = Best strategy per coin")
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