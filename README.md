<div align="center">

<img src="banner.png" alt="QuantRisk Banner" width="100%" />

<br/><br/>

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0+-000000?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![CoinGecko](https://img.shields.io/badge/CoinGecko_API-8DC63F?style=for-the-badge&logo=coingecko&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-10_Passing-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

# QuantRisk: Autonomous Cryptocurrency Risk & Portfolio Optimization Engine

A quantitative portfolio management and risk engineering system built in Python, featuring Markowitz Mean-Variance Optimization, Monte Carlo simulation across 1,000+ asset trajectories, Value at Risk (VaR / CVaR) downside modeling, and algorithmic trading backtesting.

[Live Deployment](https://cryptomanagerapp.vercel.app) | [Architecture](#system-architecture) | [Quantitative Methodology](#quantitative-methodology) | [Repository Structure](#repository-structure) | [Quick Start](#quick-start) | [Test Suite](#test-suite) | [Attribution](#engineering-attribution)

</div>

---

## Technical Overview

Cryptocurrency markets present extreme volatility, non-Gaussian return distributions, and sudden correlation spikes during market selloffs. Off-the-shelf tracking dashboards treat all price shifts uniformly without accounting for tail-risk exposure or portfolio covariance.

QuantRisk was engineered from scratch during the **Infosys Springboard 6.0** program to provide institutional-style quantitative analytics:
1. **Mathematical Portfolio Optimization:** Computes empirical covariance matrices and executes Sequential Least Squares Programming (SLSQP) to establish the Markowitz Efficient Frontier.
2. **Extreme Tail-Risk Modeling:** Replaces Gaussian assumptions with historical and parametric Value at Risk (VaR) and Conditional VaR (Expected Shortfall).
3. **Stochastic Stress Testing:** Simulates 1,000+ stochastic price trajectories under simulated market shock conditions.
4. **Automated Incident Alerting:** Dispatches real-time breach notifications via the Resend API when portfolio volatility exceeds predefined tolerance boundaries.

---

## System Architecture

```
[ CoinGecko Market API ]
           |
           v
[ Data Ingestion Layer ] ---> [ SQLite Historical Persistence ]
                                           |
    +------------------+-------------------+------------------+
    |                  |                                      |
    v                  v                                      v
[ Milestone 2 ]  [ Milestone 3 ]                        [ Milestone 5 ]
Mean-Variance    Downside Tail Risk                     Algorithmic Strategy
Optimization     Analytics                              Backtesting Engine
    |                  |                                      |
    +---> Covariance   +---> Monte Carlo 1,000+ paths         +---> SMA Crossover
    +---> SLSQP Sharpe +---> Parametric & Historical VaR      +---> RSI Reversals
    +---> Frontier     +---> Conditional VaR (CVaR)           +---> Bollinger Bands
    |                  |                                      |
    +------------------+-------------------+------------------+
                                           |
                                           v
                       [ User Interfaces & Alerting ]
                       +---> Flask Web Dashboard
                       +---> Interactive CLI Menu
                       +---> Resend API Volatility Alerts
```

---

## Quantitative Methodology

### 1. Modern Portfolio Theory (MPT) Formulation
Given $n$ cryptocurrency assets with expected return vector $\boldsymbol{\mu}$ and covariance matrix $\boldsymbol{\Sigma}$:

$$\mathbb{E}[R_p] = \mathbf{w}^T \boldsymbol{\mu}$$

$$\sigma_p^2 = \mathbf{w}^T \boldsymbol{\Sigma} \mathbf{w}$$

The optimal portfolio allocation $\mathbf{w}^*$ maximizes the Sharpe ratio subject to capital allocation constraints:

$$\max_{\mathbf{w}} \frac{\mathbf{w}^T \boldsymbol{\mu} - R_f}{\sqrt{\mathbf{w}^T \boldsymbol{\Sigma} \mathbf{w}}} \quad \text{subject to} \quad \sum_{i=1}^{n} w_i = 1, \quad w_i \ge w_{\min}$$

### 2. Value at Risk (VaR) and Conditional VaR (CVaR)
Downside loss expectations are modeled at the 95% and 99% confidence intervals:

$$\text{VaR}_\alpha(L) = \inf \{ l \in \mathbb{R} : P(L > l) \le 1 - \alpha \}$$

$$\text{CVaR}_\alpha(L) = \mathbb{E}[L \mid L \ge \text{VaR}_\alpha(L)]$$

Unlike standard variance, CVaR accounts for the severity of catastrophic losses beyond the VaR threshold.

---

## Repository Structure

```
CryptoManager/
├── app.py                       # Flask web service and dashboard routing
├── config.py                    # CoinGecko endpoints, API settings, and asset parameters
├── database.py                  # SQLite relational schema, caching, and API connectors
├── main.py                      # Interactive terminal CLI execution menu
├── milestone1_setup.py          # Workspace initialization and validation
├── milestone2_mix_calculator.py  # Covariance matrix calculation, MPT, and SLSQP optimization
├── milestone3_risk_predictor.py  # Monte Carlo simulation, VaR, CVaR, Sortino, and Calmar ratios
├── milestone4_spreading_rules.py # Risk parity asset distribution and dynamic rebalancing rules
├── milestone5_backtest.py       # Algorithmic trading simulation (SMA, RSI, Bollinger Bands)
├── tests/                       # Automated pytest verification suite
└── .github/workflows/           # GitHub Actions CI pipeline
```

---

## Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/harctik/Crypto-Investment-Manager.git
cd Crypto-Investment-Manager
python -m venv venv

# Activate:
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Launch the Web Interface
```bash
python app.py
# Open: http://localhost:5000 (Default credentials: admin / admin123)
```

### 3. Run the CLI Engine
```bash
python main.py
```

---

## Test Suite

Automated unit tests in `tests/test_portfolio_math.py` verify mathematical precision across all milestones:

```bash
pytest tests/ -v
```

Verified test coverage includes:
- Portfolio return and volatility formulas.
- Random Dirichlet weight distributions summing strictly to 1.0.
- Symmetric positive semi-definite covariance matrices.
- SLSQP optimization under constraint bounds.
- Parametric VaR vs. empirical CVaR relations ($\text{CVaR} \ge \text{VaR}$).
- RSI oscillator bounds ($0 \le \text{RSI} \le 100$) and MACD signal convergence.

---

## Engineering Attribution

All mathematical modeling, risk calculations, backtesting algorithms, and software implementation in this repository were engineered end-to-end by **Avvari Naga Harthikanand (Harthik)** as part of the Infosys Springboard 6.0 program.

- **Developer:** Avvari Naga Harthikanand
- **LinkedIn:** https://www.linkedin.com/in/harthik
- **GitHub:** https://github.com/harctik
- **Email:** harthikanand90@gmail.com
- **Live Demo:** https://cryptomanagerapp.vercel.app
- **License:** MIT License
