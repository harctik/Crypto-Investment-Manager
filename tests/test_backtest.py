import math

import pytest

import milestone5_backtest as m

PRICES = [100 + 20 * math.sin(i / 6) + i * 0.1 for i in range(120)]

STRATEGIES = {
    "ma": lambda: m.backtest_ma_crossover(PRICES, 5, 15, 1000),
    "rsi": lambda: m.backtest_rsi(PRICES, capital=1000),
    "bollinger": lambda: m.backtest_bollinger(PRICES, capital=1000),
    "ensemble": lambda: m.backtest_ensemble(PRICES, 5, 15, capital=1000),
}


@pytest.mark.parametrize("name", STRATEGIES)
def test_trades_are_round_trips_and_win_rate_matches(name):
    result = STRATEGIES[name]()
    trades = result["trades"]
    assert result["total_trades"] == len(trades)
    for t in trades:
        assert t["win"] == (t["pnl"] > 0)
        assert (t["sell_price"] > t["price"]) == t["win"]
    expected = 100 * sum(t["pnl"] > 0 for t in trades) / len(trades) if trades else 0
    assert result["win_rate"] == round(expected, 1)


@pytest.mark.parametrize("name", STRATEGIES)
def test_equity_curve_is_returned(name):
    result = STRATEGIES[name]()
    assert len(result["equity"]) == len(PRICES)
    assert result["equity"][-1] == pytest.approx(result["final_value"], abs=0.01)
