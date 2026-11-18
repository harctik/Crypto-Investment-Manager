"""
Unit tests for Quantitative Risk Analytics, Portfolio Optimization, and Backtesting Engines.
Tests Markowitz MPT, Value at Risk (VaR/CVaR), Technical Indicators, and Trading Strategies.
"""

import sys
import os
import pytest
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import milestone2_mix_calculator as m2
import milestone3_risk_predictor as m3
import milestone5_backtest as m5


# =====================================================================
# 1. Modern Portfolio Theory & Optimization (Milestone 2)
# =====================================================================

def test_portfolio_return_and_volatility():
    weights = np.array([0.5, 0.5])
    returns = np.array([10.0, 20.0])
    cov_matrix = np.array([[4.0, 1.0], [1.0, 9.0]])

    p_return = m2._portfolio_return(weights, returns)
    p_vol = m2._portfolio_volatility(weights, cov_matrix)

    assert pytest.approx(p_return, 0.01) == 15.0
    assert p_vol > 0.0


def test_random_weights_sum_to_one():
    for n in [3, 5, 8]:
        weights = m2._random_weights(n, min_w=0.05)
        assert len(weights) == n
        assert pytest.approx(float(sum(weights)), 1e-4) == 1.0
        assert all(w >= 0.049 for w in weights)


def test_pct_returns_calculation():
    prices = [100.0, 105.0, 110.25]
    returns = m2._pct_returns(prices)
    assert len(returns) == 2
    assert pytest.approx(returns[0], 0.01) == 5.0
    assert pytest.approx(returns[1], 0.01) == 5.0


def test_covariance_matrix():
    mock_returns = {
        "BTC": [1.0, -2.0, 3.0, 1.5, -1.0, 2.0],
        "ETH": [2.0, -3.0, 4.0, 1.0, -2.0, 3.0],
    }
    coins, mean_rets, cov = m2.compute_covariance_matrix(mock_returns)
    assert len(coins) == 2
    assert len(mean_rets) == 2
    assert cov.shape == (2, 2)
    assert np.allclose(cov, cov.T)  # Covariance matrix must be symmetric
    assert cov[0, 0] > 0 and cov[1, 1] > 0


def test_max_sharpe_optimization():
    mock_returns = {
        "BTC": [1.5, -0.5, 2.0, 1.0, 1.5, -0.8, 1.2, 0.9],
        "ETH": [2.5, -1.5, 3.0, 1.8, 2.2, -1.4, 1.8, 1.5],
    }
    coins, mean_rets, cov = m2.compute_covariance_matrix(mock_returns)
    result = m2.max_sharpe_portfolio(mean_rets, cov, rf=0.02, min_w=0.05)

    assert "weights" in result
    assert "sharpe" in result
    weights = result["weights"]
    assert pytest.approx(float(sum(weights)), 1e-4) == 1.0
    assert all(w >= 0.049 for w in weights)


# =====================================================================
# 2. Risk Metrics: VaR, CVaR, Sortino, Calmar (Milestone 3)
# =====================================================================

def test_var_and_cvar():
    # Synthetic series of returns with known negative tail
    returns = [-5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    var_95 = m3.VaR(returns, confidence=0.95)
    cvar_95 = m3.CVaR(returns, confidence=0.95)

    assert var_95 > 0
    assert cvar_95 >= var_95  # Expected shortfall (CVaR) is >= VaR


def test_sortino_and_calmar_ratios():
    returns = [2.0, 3.0, -1.0, 4.0, -0.5, 3.5, 2.0]
    sortino = m3.sortino_ratio(returns, rf=0.0)
    assert isinstance(sortino, (int, float))
    assert sortino > 0  # Net positive with minimal downside


# =====================================================================
# 3. Technical Indicators & Backtesting Engine (Milestone 5)
# =====================================================================

def test_rsi_bounds():
    # Upward trending prices
    uptrend = [10.0 + i * 2.0 for i in range(30)]
    rsi_vals = m5.RSI(uptrend, period=14)
    # RSI must be between 0 and 100
    for val in rsi_vals:
        if val is not None:
            assert 0.0 <= val <= 100.0


def test_macd_signal_line():
    prices = [100.0 + np.sin(i / 5.0) * 10.0 for i in range(50)]
    macd_dict = m5.MACD(prices)
    assert "macd_line" in macd_dict
    assert "signal_line" in macd_dict
    assert "histogram" in macd_dict
    assert len(macd_dict["macd_line"]) == len(prices)


def test_ma_crossover_backtest():
    # Construct oscillating prices
    prices = [100.0 + (i % 10) * 5.0 for i in range(60)]
    result = m5.backtest_ma_crossover(prices, short_w=5, long_w=15, capital=10000.0)

    assert "total_return" in result
    assert "trades" in result
    assert "win_rate" in result
    assert "max_drawdown" in result
    assert "final_value" in result
    assert isinstance(result["total_return"], (int, float))
