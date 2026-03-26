# Python Crypto Investment Manager

## Quick Start

```bash
pip install flask flask-socketio
python app.py
# Open: http://localhost:5000   Login: admin / admin123
```

## File Structure

```
CryptoManager/          (8 Python files — no coingecko.py)
├── config.py           ← ALL settings including CoinGecko config
├── database.py         ← SQLite + CoinGecko API (merged)
├── app.py              ← Flask web server
├── main.py             ← CLI menu
├── milestone1_setup.py
├── milestone2_mix_calculator.py
├── milestone3_risk_predictor.py
├── milestone4_spreading_rules.py
├── milestone5_backtest.py
├── templates/          ← login.html + dashboard.html
├── static/             ← css + js
└── reports/            ← CSV exports saved here
```

## How CoinGecko is wired

- Every CoinGecko setting is in `config.COINGECKO` (URL, API key, endpoints, limits, watchlist)
- All fetch functions (get_prices, get_trending, search_coins) live in `database.py`
- No separate coingecko.py — just two files: config.py + database.py

## CLI (run milestones individually)

```bash
python main.py                         # menu
python milestone1_setup.py             # weeks 1-2
python milestone2_mix_calculator.py    # weeks 3-4
python milestone3_risk_predictor.py    # weeks 5-6
python milestone4_spreading_rules.py   # weeks 7-8
```
