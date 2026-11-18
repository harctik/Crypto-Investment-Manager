<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0+-000000?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![CoinGecko](https://img.shields.io/badge/CoinGecko_API-8DC63F?style=for-the-badge&logo=coingecko&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

# 📈 Crypto Investment Manager

**A full-stack Python platform to track, analyze, and backtest cryptocurrency investment strategies in real time.**

[Features](#-features) · [Tech Stack](#-tech-stack) · [Quick Start](#-quick-start) · [Roadmap](#-milestones--roadmap) · [Contributing](#-contributing)

</div>

---

## ✨ Features

| | Feature | Description |
|---|---|---|
| 📊 | **Real-Time Price Tracking** | Live cryptocurrency prices via the CoinGecko API |
| 🧮 | **Portfolio Mix Calculator** | Optimal allocation across your crypto holdings |
| ⚠️ | **Risk Prediction Engine** | ML-powered risk assessment using scikit-learn & scipy |
| 🔀 | **Diversification Rules Engine** | Automated rules to maintain a healthy, spread portfolio |
| 🕰️ | **Historical Backtesting** | Simulate strategies against historical data |
| 🌐 | **Web Dashboard + CLI** | Flask-based web UI with real-time updates and a full CLI workflow |
| 📄 | **CSV Report Exports** | Export portfolio snapshots and analytics to CSV |

---

## 🛠️ Tech Stack

<div align="center">

| Category | Technologies |
|---|---|
| **Language** | ![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) |
| **Backend** | ![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white) ![Flask-SocketIO](https://img.shields.io/badge/Flask--SocketIO-010101?style=flat-square&logo=socketdotio&logoColor=white) ![Gunicorn](https://img.shields.io/badge/Gunicorn-499848?style=flat-square&logo=gunicorn&logoColor=white) |
| **Database** | ![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white) |
| **ML / Science** | ![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white) ![NumPy](https://img.shields.io/badge/NumPy-013243?style=flat-square&logo=numpy&logoColor=white) ![SciPy](https://img.shields.io/badge/SciPy-8CAAE6?style=flat-square&logo=scipy&logoColor=white) |
| **API** | ![CoinGecko](https://img.shields.io/badge/CoinGecko-8DC63F?style=flat-square&logo=coingecko&logoColor=white) |
| **Frontend** | ![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat-square&logo=html5&logoColor=white) ![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=flat-square&logo=css3&logoColor=white) ![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black) |

</div>

---

## 🏗️ Project Structure

```
CryptoManager/
├── config.py                       # All settings (app, DB, CoinGecko, risk params)
├── database.py                     # SQLite + CoinGecko API fetch layer
├── app.py                          # Flask web server & SocketIO
├── main.py                         # CLI menu entry point
├── milestone1_setup.py             # M1 — Project setup & data ingestion
├── milestone2_mix_calculator.py    # M2 — Portfolio allocation calculator
├── milestone3_risk_predictor.py    # M3 — Risk prediction engine
├── milestone4_spreading_rules.py   # M4 — Diversification rules engine
├── milestone5_backtest.py          # M5 — Historical backtesting
├── templates/
│   ├── landing.html                # Landing page
│   ├── login.html                  # Authentication page
│   └── dashboard.html              # Main dashboard
├── static/
│   ├── css/                        # Stylesheets
│   └── js/                         # Client-side scripts
├── data/
│   └── crypto_data.db              # SQLite database
└── reports/                        # CSV exports saved here
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- pip package manager
- *(Optional)* CoinGecko API key for higher rate limits

### Installation

```bash
# Clone the repository
git clone https://github.com/harctik/Crypto-Investment-Manager.git
cd Crypto-Investment-Manager

# Install dependencies
pip install -r requirements.txt

# (Optional) Configure environment variables
cp .env.example .env   # then edit .env with your CoinGecko API key
```

### Run the Web Dashboard

```bash
python app.py
# Open: http://localhost:5000
# Login: admin / admin123
```

### Run via CLI

```bash
python main.py                          # Interactive menu
python milestone1_setup.py              # Data ingestion
python milestone2_mix_calculator.py     # Portfolio allocation
python milestone3_risk_predictor.py     # Risk analysis
python milestone4_spreading_rules.py    # Diversification rules
python milestone5_backtest.py           # Backtesting engine
```

---

## 📸 Screenshots

<!-- Add screenshots here -->

*Screenshots of the dashboard and CLI workflow coming soon.*

---

## 🗺️ Milestones / Roadmap

| Milestone | Weeks | Description | Status |
|---|---|---|---|
| **M1 — Setup & Data Ingestion** | 1–2 | Project scaffolding, SQLite schema, CoinGecko API integration, Flask app bootstrap | ✅ Complete |
| **M2 — Mix Calculator** | 3–4 | Portfolio allocation engine — calculate optimal holding percentages across assets | ✅ Complete |
| **M3 — Risk Predictor** | 5–6 | ML-powered risk scoring using scikit-learn models, volatility analysis with SciPy | ✅ Complete |
| **M4 — Spreading Rules** | 7–8 | Diversification rules engine — automated guardrails against over-concentration | ✅ Complete |
| **M5 — Backtesting** | 9–10 | Historical strategy simulation — test allocation strategies against past market data | ✅ Complete |

---

## 🔧 How CoinGecko Is Wired

All CoinGecko configuration lives in **`config.py`** under the `COINGECKO` dict (URL, API key, endpoints, rate limits, watchlist). Every fetch function (`get_prices`, `get_trending`, `search_coins`) is in **`database.py`** — no separate CoinGecko module needed. Just two files keep the data layer clean.

---

## 🤝 Contributing

Contributions are welcome! Here's how:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

Please open an issue first to discuss what you'd like to change.

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

<div align="center">

**Built with ☕ and Python** · [harctik](https://github.com/harctik)

</div>
