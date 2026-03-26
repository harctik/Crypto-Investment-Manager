"""
config.py — All settings loaded from .env (with safe fallbacks).
Install python-dotenv:  pip install python-dotenv
"""

import os
from pathlib import Path

# ── Load .env file ────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv not installed — os.getenv() still works for system env vars

def _bool(key, default="false") -> bool:
    return os.getenv(key, default).lower() in ("true", "1", "yes")

def _float(key, default) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default

def _int(key, default) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


# ── App ───────────────────────────────────────────────────────────────────────
APP = {
    "name":       "CryptoManager",
    "env":        os.getenv("APP_ENV", "development"),
    "debug":      _bool("DEBUG", "false"),
    "secret_key": os.getenv("SECRET_KEY", "crypto-secure-key-2025-change-in-prod"),
    "host":       os.getenv("HOST", "0.0.0.0"),
    "port":       _int("PORT", 5000),
}

# ── Database ──────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DATABASE = {
    "file": os.getenv("DB_FILE", str(DATA_DIR / "crypto_data.db")),
}

# ── CoinGecko API ─────────────────────────────────────────────────────────────
COINGECKO = {
    "base_url":    "https://api.coingecko.com/api/v3",
    "api_key":     os.getenv("COINGECKO_API_KEY", ""),
    "timeout_sec": 10,
    "min_gap_sec": 2.0,
    "user_agent":  "CryptoManager/1.0",
    "vs_currency": "usd",
    "watchlist": [
        "bitcoin", "ethereum", "binancecoin", "solana",
        "cardano", "ripple", "matic-network", "chainlink"
    ],
    "endpoints": {
        "markets": "/coins/markets",
        "search":  "/search",
        "trending":"/search/trending",
        "coin":    "/coins/{id}",
        "ping":    "/ping",
    },
    "markets_params": {
        "order":     "market_cap_desc",
        "sparkline": "false",
        "page":      1,
    },
    "search_limit":   8,
    "trending_limit": 7,
}

WATCHLIST = COINGECKO["watchlist"]

API = {
    "base_url":    COINGECKO["base_url"],
    "vs_currency": COINGECKO["vs_currency"],
    "min_gap_sec": COINGECKO["min_gap_sec"],
    "timeout_sec": COINGECKO["timeout_sec"],
}

# ── Portfolio Mix Calculator ───────────────────────────────────────────────────
MIX = {
    "iterations":   1000,
    "min_weight":   0.05,
    "risk_free_rate": 0.02,
    "history_limit": 60,
}

# ── Risk Checker ──────────────────────────────────────────────────────────────
RISK = {
    "alert_threshold_pct": _float("ALERT_THRESHOLD_PCT", 0.1),
    "volatility_low":      3.0,
    "volatility_high":     8.0,
    "history_limit":       60,
    "parallel_workers":    4,
}

# ── Prediction Engine ─────────────────────────────────────────────────────────
PREDICTION = {
    "history_limit":   40,
    "ma_short_window":  5,
    "ma_long_window":  15,
    "linreg_periods":   5,
}

# ── Reports ───────────────────────────────────────────────────────────────────
REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(exist_ok=True)

REPORTS = {
    "output_dir": str(REPORT_DIR),
}

# ── Email Alerts ──────────────────────────────────────────────────────────────
EMAIL = {
    "enabled":        _bool("EMAIL_ENABLED", "false"),
    "provider":       os.getenv("EMAIL_PROVIDER", "smtp"),   # "resend" or "smtp"
    "resend_api_key": os.getenv("RESEND_API_KEY", ""),
    "smtp_host":      "smtp.gmail.com",
    "smtp_port":      587,
    "sender":         os.getenv("EMAIL_SENDER", ""),
    "password":       os.getenv("EMAIL_APP_PASSWORD", ""),
    "recipient":      os.getenv("EMAIL_RECIPIENT", ""),
}

# ── Portfolio Spread Rules ────────────────────────────────────────────────────
SPREAD = {
    "max_single_alloc_pct": 40.0,
    "min_single_alloc_pct":  5.0,
    "rebalance_drift_pct":  10.0,
    "stress_scenarios": {
        "bull_market":  30.0,
        "bear_market": -40.0,
        "flash_crash": -20.0,
    },
}