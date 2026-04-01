# 🪙 Python Crypto Investment Manager

> A full-stack cryptocurrency portfolio management system built with **Python + Flask + SQLite**.  
> Features live CoinGecko prices, Monte Carlo portfolio optimisation, parallel risk analysis, ML-based price prediction, portfolio rebalancing rules, MA-crossover backtesting, and a real-time web dashboard — all backed by a single local SQLite database.

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Project Structure](#-project-structure)
- [Tech Stack](#-tech-stack)
- [Database Schema](#-database-schema)
- [Quick Start](#-quick-start)
- [Environment Variables](#-environment-variables)
- [Running the Web Dashboard](#-running-the-web-dashboard)
- [Running the CLI Milestones](#-running-the-cli-milestones)
  - [Milestone 1 — Setup & Live Data](#milestone-1--setup--live-data)
  - [Milestone 2 — Investment Mix Calculator](#milestone-2--investment-mix-calculator)
  - [Milestone 3 — Risk Checker & Predictor](#milestone-3--risk-checker--predictor)
  - [Milestone 4 — Spreading Rules & Backtest](#milestone-4--spreading-rules--backtest)
- [API Endpoints](#-api-endpoints)
- [Configuration Reference](#-configuration-reference)
- [Default Users](#-default-users)
- [Email Alerts Setup](#-email-alerts-setup)
- [Project Milestones](#-project-milestones)
- [Known Limitations](#-known-limitations)

---

## 🔍 Overview

CryptoManager is a portfolio management tool for cryptocurrency investors. It connects to the **CoinGecko free API** to fetch live prices for a configurable watchlist of coins, stores all data locally in a **SQLite database**, and exposes both a **CLI interface** for running milestone modules and a **Flask web dashboard** for a visual, real-time experience.

The system is split across 4 milestones that build on each other:

| Milestone | Module | What it does |
|-----------|--------|-------------|
| 1 | `milestone1_setup.py` | Initialise DB, fetch live prices, store snapshots |
| 2 | `milestone2_mix_calculator.py` | Monte Carlo portfolio optimisation |
| 3 | `milestone3_risk_predictor.py` | Risk analysis, ML prediction, email alerts |
| 4 | `milestone4_spreading_rules.py` + `milestone5_backtest.py` | Rebalancing rules, stress test, backtesting |

---

## ✨ Features

### 📡 Live Data
- Fetches real-time prices for 8 cryptocurrencies via **CoinGecko `/coins/markets`** API
- Stores timestamped price snapshots in SQLite for historical analysis
- Fetches CoinGecko **trending coins** 
- Rate-limit safe: configurable minimum gap between API calls (default 2s)
- Optional paid API key support via `COINGECKO_API_KEY`

### 💼 Portfolio Management
- Add, update, and delete coin positions with amount and average buy price
- Live P&L calculation (unrealised) per position
- Allocation % per coin based on current market value
- Per-user portfolio isolation (multi-user support)
- Trade history log with **FIFO realised P&L** calculation
- Coin notes — attach personal notes to any coin

### 📊 Investment Mix Calculator (Monte Carlo)
- Runs **1,000 random weight iterations** across all watchlist coins
- Computes portfolio return, risk (population standard deviation), and **Sharpe ratio** for each combination
- Identifies and saves three optimal portfolios:
  - **Best Sharpe Ratio** — best risk-adjusted return
  - **Best Expected Return** — highest raw return
  - **Lowest Risk** — minimum volatility
- All three strategies run **in parallel** via `ThreadPoolExecutor`
- Results saved to `mix_results` table; exportable to CSV

### ⚠️ Risk Analysis
- Calculates 6 risk metrics per coin:
  - **Volatility** (population standard deviation of returns)
  - **Mean return** (average percentage change per snapshot)
  - **Sharpe ratio** (mean return / volatility)
  - **Maximum drawdown** (largest peak-to-trough % loss)
  - **Momentum trend** (BULLISH / BEARISH / NEUTRAL based on 5-period window)
  - **MA signal** (BUY 🟢 / SELL 🔴 / HOLD 🟡 from short vs long moving average)
- Risk tier classification: **LOW** (vol < 3%) / **MEDIUM** (3–8%) / **HIGH** (> 8%)
- Runs for all 8 coins **in parallel** using 4 ThreadPoolExecutor workers
- Stores snapshots in `risk_snapshots` table

### 🔮 Price Prediction
- **Linear Regression** prediction from scratch (no sklearn):
  - Computes slope and intercept over full price history
  - Forecasts next 5 periods with confidence band (±residual pstdev)
- **Moving Average crossover** prediction:
  - Short MA (5-period) and Long MA (15-period)
  - Generates BUY / SELL / HOLD signal
- All predictions run in parallel and saved to `predictions` table
- Exported to timestamped CSV in `reports/`

### 📧 Email Alerts
- Fires alerts when a coin's 24h price change exceeds the configured threshold
- Supports **Gmail SMTP** (`starttls`) and **Resend API** providers
- Configurable via `.env` — set `EMAIL_ENABLED=true` to activate
- User-defined price alerts (above/below a target price) via web UI

### 📐 Portfolio Spreading Rules
- Enforces **max 40% / min 5%** single-coin allocation rules
- **Drift detector** — compares current allocation vs equal-weight target and flags any coin drifting > 10 percentage points
- Generates SELL / BUY / HOLD action list
- Logs all rebalance events to `rebalance_log` table

### 📉 Stress Testing
- Simulates portfolio value under 3 market scenarios:
  - **Bull market**: +30% across all positions
  - **Bear market**: −40% across all positions
  - **Flash crash**: −20% across all positions
- Shows P&L in both $ and % for each scenario

### 🤖 MA-Crossover Backtesting
- Simulates buy/sell decisions on historical price data using **golden cross / death cross** strategy:
  - Short MA crosses above Long MA → **BUY**
  - Short MA crosses below Long MA → **SELL**
- Tracks cash, holdings, equity curve, and max drawdown
- Reports: total return %, final value, number of trades, win rate, max drawdown per coin
- Available in both CLI (`milestone5_backtest.py`) and web dashboard

### 🌐 Real-Time Web Dashboard
- **Flask + Flask-SocketIO** backend with live WebSocket price broadcasting every 60 seconds
- Multi-user login system with session management
- Role-based access: Admin / Trader / Viewer
- Dark/light theme toggle (persisted per user)
- Dynamic watchlist: search and add/remove coins from CoinGecko
- Live price cards with 24h change indicators
- Portfolio chart, risk table, prediction display, news feed
- **Fear & Greed Index** from Alternative.me API
- **Crypto news** from CryptoPanic API (with CoinGecko fallback)
- Interactive backtest configurator in the UI

---

## 📁 Project Structure

```
CryptoManager/
│
├── app.py                      # Flask web server + SocketIO real-time feed
├── main.py                     # CLI runner — executes all 4 milestones in sequence
├── config.py                   # All settings (loaded from .env)
├── database.py                 # SQLite storage + CoinGecko API layer
│
├── milestone1_setup.py         # Week 1–2: DB init, live fetch, trending, parallel fetch
├── milestone2_mix_calculator.py# Week 3–4: Monte Carlo portfolio optimisation
├── milestone3_risk_predictor.py# Week 5–6: Risk analysis, prediction, email alerts, CSV export
├── milestone4_spreading_rules.py # Week 7–8: Portfolio rules, drift detection, stress test
├── milestone5_backtest.py      # Week 7–8: MA-crossover backtest strategy
│
├── templates/
│   ├── login.html              # Login + registration page
│   └── dashboard.html          # Main web dashboard (single-page)
│
├── static/
│   ├── css/main.css            # Dashboard styles
│   └── js/
│       ├── dashboard.js        # All frontend logic (charts, WebSocket, API calls)
│       └── login.js            # Login/register UI logic
│
├── data/
│   └── crypto_data.db          # SQLite database (auto-created on first run)
│
├── reports/                    # CSV exports saved here (timestamped filenames)
├── exports/                    # Log files
│
├── .env                        # Environment variables (NOT committed to git)
├── .env.example                # Template for setting up .env
└── requirements.txt            # Python dependencies
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Web Framework | Flask 3.x |
| Real-time | Flask-SocketIO 5.x (threading mode) |
| Database | SQLite 3 (via `sqlite3` stdlib) |
| Data API | CoinGecko REST API (free tier) |
| News API | CryptoPanic API + CoinGecko news fallback |
| Sentiment API | Alternative.me Fear & Greed Index |
| Email | Gmail SMTP (`smtplib`) or Resend API |
| Parallelism | `concurrent.futures.ThreadPoolExecutor` |
| HTTP | `urllib.request` (stdlib — no `requests` needed for core) |
| Frontend | Vanilla JS + HTML/CSS (no framework) |
| Config | `python-dotenv` |

> **No pandas, no numpy, no scikit-learn.** All statistics (mean, pstdev, linear regression, moving averages) are implemented from scratch using Python's `statistics` stdlib module and pure arithmetic.

---

## 🗄 Database Schema

The SQLite database (`data/crypto_data.db`) is auto-created on first run via `init_db()`. It contains 11 tables:

| Table | Purpose |
|-------|---------|
| `price_history` | Timestamped price snapshots per coin (price, market cap, volume, 24h change) |
| `portfolio` | User holdings (coin, amount, average buy price) — per-user |
| `mix_results` | Saved Monte Carlo portfolio mixes (weights, expected return, expected risk) |
| `risk_snapshots` | Risk metrics per coin (volatility, Sharpe, max drawdown, risk tier) |
| `predictions` | Linear regression and MA forecasts per coin |
| `alerts` | System-generated price movement alerts (threshold breaches) |
| `price_alerts` | User-defined price alerts (above/below a target price) |
| `trades` | Full trade history (buy/sell) for FIFO P&L calculation |
| `rebalance_log` | Log of all portfolio rebalance events |
| `coin_notes` | Per-user notes attached to individual coins |
| `users` | User accounts (username, hashed password + salt, role, theme preference) |
| `user_watchlist` | Per-user dynamic watchlist (additions/removals from the default config) |

All passwords are stored as **SHA-256(salt + password)** — never in plaintext.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- Internet connection (for CoinGecko API)

### 1. Clone the repository

```bash
git clone https://github.com/your-username/CryptoManager.git
cd CryptoManager
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your environment file

```bash
cp .env.example .env
```

Edit `.env` with your settings (see [Environment Variables](#-environment-variables) below).

### 5. Run the web dashboard

```bash
python app.py
```

Open your browser at **http://localhost:5000**  
Login with: `admin` / `admin123`

---

## 🔐 Environment Variables

Create a `.env` file in the project root. All variables are optional — the app runs with defaults if not set.

```env
# ── App ──────────────────────────────────────────────────────
APP_ENV=development
SECRET_KEY=change-this-to-a-random-secret-in-production
DEBUG=false

# ── CoinGecko API ────────────────────────────────────────────
# Leave empty to use the free tier (no key required)
# Get a free demo key at https://www.coingecko.com/en/api
COINGECKO_API_KEY=

# ── Database ─────────────────────────────────────────────────
DB_FILE=data/crypto_data.db

# ── Server ───────────────────────────────────────────────────
HOST=0.0.0.0
PORT=5000

# ── Price Alert Threshold ────────────────────────────────────
# Fire an alert when a coin moves this % in 24h
ALERT_THRESHOLD_PCT=5.0

# ── Email Alerts ─────────────────────────────────────────────
EMAIL_ENABLED=false

# Option 1: Gmail SMTP
EMAIL_PROVIDER=smtp
EMAIL_SENDER=your-gmail@gmail.com
EMAIL_APP_PASSWORD=your-gmail-app-password
EMAIL_RECIPIENT=your-email@gmail.com

# Option 2: Resend API (https://resend.com)
# EMAIL_PROVIDER=resend
# RESEND_API_KEY=re_your_api_key_here
# EMAIL_SENDER=onboarding@resend.dev
# EMAIL_RECIPIENT=your-email@gmail.com
```

> ⚠️ **Never commit your `.env` file to git.** It is listed in `.gitignore`.

---

## 🌐 Running the Web Dashboard

```bash
python app.py
```

The Flask server starts on **http://localhost:5000** with SocketIO live price broadcasting enabled.

**What happens on startup:**
1. `database.init_db()` runs — creates all tables if they don't exist, seeds 3 default users
2. Flask + SocketIO server starts
3. On first browser connection, a background thread starts that fetches live prices every **60 seconds** and broadcasts them to all connected clients via WebSocket

**Dashboard features:**
- Live price cards for all watchlist coins
- Portfolio tracker with P&L
- Risk analysis table
- Price prediction display
- Monte Carlo mix results
- MA-crossover backtest configurator
- Custom price alerts (set above/below triggers)
- Trade journal with FIFO P&L
- Crypto news feed with sentiment
- Fear & Greed Index
- Dark/Light theme toggle

---

## 💻 Running the CLI Milestones

You can run each milestone individually or run all four in sequence with `main.py`.

### Run all milestones in sequence

```bash
python main.py
```

---

### Milestone 1 — Setup & Live Data

```bash
python milestone1_setup.py
```

**What it does:**

1. **Initialises the database** — creates all SQLite tables via `init_db()`
2. **Displays the watchlist** — shows all 8 configured coins with API settings
3. **Bulk fetches live prices** — single CoinGecko API call for all coins simultaneously, stores snapshots in `price_history`
4. **Fetches trending coins** — shows the top 7 trending coins on CoinGecko right now

**Sample output:**
```
══════════════════════════════════════════════════════════
  Task 3 — Bulk Fetch (single API call, no rate-limit risk)
══════════════════════════════════════════════════════════
  ✓  BTC        $    83,412.0000  24h: -1.24%
  ✓  ETH        $     1,574.3100  24h: -2.87%
  ✓  BNB        $       584.2100  24h: +0.43%
  ✓  SOL        $       125.7400  24h: -3.11%
  ...
  Stored 8 snapshots  |  0 failed
```

> **Tip:** Run Milestone 1 several times before running Milestones 2–4. The analysis modules need at least 15–60 price snapshots per coin for meaningful results.

---

### Milestone 2 — Investment Mix Calculator

```bash
python milestone2_mix_calculator.py
```

**What it does:**

1. **Loads return history** — fetches up to 60 price snapshots per coin from DB, computes percentage returns
2. **Runs 1,000 Monte Carlo iterations** — randomly generates weight combinations (min 5% per coin), computes portfolio return, risk, and Sharpe ratio for each
3. **Identifies 3 winning mixes** — Best Sharpe Ratio, Best Expected Return, Lowest Risk
4. **Saves and displays results** — stores winning mixes in `mix_results` table with coin weights

**Sample output:**
```
  ── Best Sharpe Ratio ──
  Return : +0.0312%   Risk : 0.1847%   Sharpe : 0.1689

  Coin                 Weight  Allocation
  ──────────────────────────────────────
  bitcoin              0.1823      18.23%
  ethereum             0.2541      25.41%
  solana               0.0821       8.21%
  ...
```

**Requirements:** Needs at least **2 coins with price history** in the DB. Run Milestone 1 first.

---

### Milestone 3 — Risk Checker & Predictor

```bash
python milestone3_risk_predictor.py
```

**What it does:**

1. **Parallel risk check** — calculates 6 risk metrics for all 8 coins simultaneously using 4 ThreadPoolExecutor workers, saves to `risk_snapshots`
2. **Parallel prediction** — runs linear regression + MA crossover prediction for all coins in parallel, saves to `predictions`
3. **Alert check** — flags any coin with 24h price change exceeding `ALERT_THRESHOLD_PCT`; saves to `alerts` table
4. **CSV export** — generates 4 timestamped CSV files in `reports/`:
   - `prices_YYYYMMDD_HHMMSS.csv`
   - `risk_YYYYMMDD_HHMMSS.csv`
   - `predictions_YYYYMMDD_HHMMSS.csv`
   - `alerts_YYYYMMDD_HHMMSS.csv`
5. **Email alert** — sends email notification if any alerts fired (requires `EMAIL_ENABLED=true` in `.env`)

**Sample output:**
```
  🟡 ethereum           vol=2.31%  sharpe=+0.134  dd=4.82%  [LOW]
  🔴 solana             vol=9.14%  sharpe=-0.023  dd=18.3%  [HIGH]

  ── BITCOIN ──
     Current / Next  : $  83,412.0000  →  $  83,198.2000  (±312.4400)
     Trend / Signal  : BEARISH  |  SELL 🔴
```

---

### Milestone 4 — Spreading Rules & Backtest

```bash
python milestone4_spreading_rules.py
```

**What it does:**

1. **Shows current portfolio** — displays all positions with live prices, value, allocation %, and unrealised P&L
2. **Enforces allocation rules** — checks each coin against max 40% / min 5% limits; prints REDUCE/INCREASE warnings
3. **Drift detection** — compares current allocation vs equal-weight target (100% / n coins); flags drift > 10pp with BUY/SELL actions; logs to `rebalance_log`
4. **Stress test** — simulates portfolio under bull (+30%), bear (−40%), and flash crash (−20%) scenarios

```bash
python milestone5_backtest.py
```

**What it does:**

1. **MA-crossover backtest** — simulates golden cross BUY / death cross SELL strategy on each coin's full price history
2. **Trade log** — shows every simulated buy/sell with entry price, exit price, and P&L
3. **Summary** — reports total return %, final portfolio value, trade count, win rate, and max drawdown for each coin

---

## 🔌 API Endpoints

All endpoints require authentication (session cookie). Login via `POST /login` first.

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Login page |
| `POST` | `/login` | Authenticate — body: `{"username": "", "password": ""}` |
| `POST` | `/register` | Register new user — body: `{"username": "", "password": ""}` |
| `GET` | `/logout` | Clear session and redirect to login |
| `GET` | `/dashboard` | Main dashboard page |

### Prices & Market Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/prices` | Fetch live prices for user's watchlist, store snapshots |
| `GET` | `/api/history/<coin_id>` | Last 60 price snapshots for a coin |
| `GET` | `/api/fear-greed` | Fear & Greed Index from Alternative.me |
| `GET` | `/api/news?coin=BTC` | Crypto news (CryptoPanic → CoinGecko fallback) |

### Portfolio

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/portfolio` | All positions with live value, P&L, allocation % |
| `POST` | `/api/position` | Add/update position — body: `{"coin_id", "symbol", "amount", "avg_buy"}` |
| `DELETE` | `/api/position/<coin_id>` | Remove a position |
| `POST` | `/api/position/clear-all` | Delete all positions for current user |

### Trades & P&L

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/trades` | Trade history for current user |
| `POST` | `/api/trades` | Log a trade — body: `{"coin_id", "symbol", "side", "amount", "price", "fee", "note"}` |
| `GET` | `/api/trades/pnl` | Realised P&L per coin (FIFO) |

### Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/risk` | Risk metrics for all coins in watchlist |
| `GET` | `/api/predictions` | Price predictions for all coins |
| `GET` | `/api/mixes` | Last 10 saved portfolio mix results |
| `POST` | `/api/run-mixes` | Trigger Monte Carlo mix calculation |
| `GET` | `/api/stress` | Portfolio stress test results |
| `GET` | `/api/backtest?coin=bitcoin&short_w=5&long_w=15&capital=1000` | Run MA-crossover backtest |
| `POST` | `/api/export-csv` | Export current data to CSV files in `reports/` |

### Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/alerts` | System-generated volatility alerts |
| `GET` | `/api/price-alerts` | User's active price alerts |
| `GET` | `/api/price-alerts/history` | All alerts including triggered ones |
| `POST` | `/api/price-alerts` | Create alert — body: `{"coin_id", "symbol", "condition": "above"/"below", "target", "note"}` |
| `DELETE` | `/api/price-alerts/<id>` | Delete a price alert |

### Watchlist

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/watchlist` | User's current watchlist |
| `GET` | `/api/watchlist/search?q=bitcoin` | Search CoinGecko for a coin |
| `POST` | `/api/watchlist` | Add coin — body: `{"coin_id", "symbol", "name"}` |
| `DELETE` | `/api/watchlist/<coin_id>` | Remove coin from watchlist |

### Notes & Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/notes` | All coin notes for current user |
| `POST` | `/api/notes/<coin_id>` | Save note — body: `{"note": "..."}` |
| `POST` | `/api/theme` | Toggle theme — body: `{"theme": "dark"/"light"}` |

---

## ⚙️ Configuration Reference

All configuration lives in `config.py` and is loaded from `.env`. Key settings:

```python
WATCHLIST = [
    "bitcoin", "ethereum", "binancecoin", "solana",
    "cardano", "ripple", "matic-network", "chainlink"
]

MIX = {
    "iterations":     1000,   # Monte Carlo iterations
    "min_weight":     0.05,   # Minimum 5% allocation per coin
    "risk_free_rate": 0.02,   # Risk-free rate for Sharpe ratio
    "history_limit":  60,     # Max snapshots to load for mix calculation
}

RISK = {
    "alert_threshold_pct": 0.1,   # Fire alert if 24h change > this %
    "volatility_low":       3.0,   # Below 3% → LOW risk tier
    "volatility_high":      8.0,   # Above 8% → HIGH risk tier
    "history_limit":        60,    # Snapshots to use for risk calc
    "parallel_workers":     4,     # ThreadPoolExecutor workers
}

PREDICTION = {
    "history_limit":   40,    # Snapshots to use for prediction
    "ma_short_window":  5,    # Short MA window (periods)
    "ma_long_window":  15,    # Long MA window (periods)
    "linreg_periods":   5,    # How many future periods to forecast
}

SPREAD = {
    "max_single_alloc_pct": 40.0,   # Max % allowed for one coin
    "min_single_alloc_pct":  5.0,   # Min % required per coin
    "rebalance_drift_pct":  10.0,   # Trigger rebalance if drift > 10pp
    "stress_scenarios": {
        "bull_market":  30.0,
        "bear_market": -40.0,
        "flash_crash": -20.0,
    },
}
```

---

## 👤 Default Users

Three users are seeded automatically when the database is first created:

| Username | Password | Role | Access |
|----------|----------|------|--------|
| `admin` | `admin123` | Admin | Full access |
| `trader` | `trade456` | Trader | Portfolio, trades, watchlist |
| `demo` | `demo` | Viewer | Read-only |

> Change these passwords immediately in a production environment.

---

## 📧 Email Alerts Setup

### Option 1 — Gmail SMTP

1. Enable **2-Step Verification** on your Google account
2. Generate an **App Password**: Google Account → Security → App passwords
3. Set in `.env`:
   ```env
   EMAIL_ENABLED=true
   EMAIL_PROVIDER=smtp
   EMAIL_SENDER=your-gmail@gmail.com
   EMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   EMAIL_RECIPIENT=recipient@gmail.com
   ```

### Option 2 — Resend API

1. Sign up at [resend.com](https://resend.com) (free tier available)
2. Generate an API key
3. Set in `.env`:
   ```env
   EMAIL_ENABLED=true
   EMAIL_PROVIDER=resend
   RESEND_API_KEY=re_your_key_here
   EMAIL_SENDER=onboarding@resend.dev
   EMAIL_RECIPIENT=your-email@gmail.com
   ```
   Install the Resend library: `pip install resend`

---

## 📅 Project Milestones

This project was built as part of the **Infosys Springboard Internship** programme:

| Week | Milestone | Evaluation Criteria |
|------|-----------|---------------------|
| 1–2 | **Milestone 1** — Tools ready, DB set up, live data fetching, parallel execution | Tools ready, learning done, plans set |
| 3–4 | **Milestone 2** — Investment mix calculator, portfolio optimisation | Mix calculator correct, portfolio mixes checked |
| 5–6 | **Milestone 3** — Risk checker, prediction engine, email alerts, parallel tasks | Checker and reports work, concurrent execution good |
| 7–8 | **Milestone 4** — Spreading rules, stress test, backtesting | Rule setter works, handles complex market scenarios |

- **Project:** Crypto Portfolio Manager — Group-1  
- **Class Timing:** 5:30–6:30 PM  
- **Start Date:** 02 Feb 2026  
- **Demo Presentation:** 25 Mar 2026  
- **Mock Presentation:** 27 Mar 2026  

---

## ⚠️ Known Limitations

- **Price history depth** — The free CoinGecko API only returns the current price snapshot per call. Historical depth grows only as you run Milestone 1 repeatedly over time. Backtesting and prediction quality improve with more snapshots.
- **No OHLCV data** — The system uses closing price snapshots, not full candlestick data. MA crossover signals are approximate.
- **SQLite concurrency** — SQLite handles low-to-medium concurrent writes well, but is not designed for high-frequency production workloads.
- **Predictions are educational** — The linear regression and moving average models are simple by design. They are not financial advice.
- **CoinGecko rate limits** — The free tier is limited to ~30 calls/minute. The 2s gap between calls (`min_gap_sec`) prevents 429 errors.

---

## 📜 License

This project was built for educational purposes as part of an internship programme. All rights reserved.

---

*Built with Python 🐍 | Flask 🌶️ | SQLite 🗄️ | CoinGecko API 🦎*
