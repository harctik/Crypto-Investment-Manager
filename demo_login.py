"""Test-only admin / admin sign-in.

Off unless DEMO_LOGIN=1, and then only for requests made on this computer.
It signs in to the seeded "admin" account and does not change its stored password.
"""
import os

import database

DEMO_USERNAME = "admin"
DEMO_PASSWORD = "admin"

_LOOPBACK = {"127.0.0.1", "::1"}
_PROXY_HEADERS = ("X-Forwarded-For", "Forwarded", "X-Real-IP")
_HOSTING_MARKERS = ("RENDER", "VERCEL", "DYNO", "RAILWAY_ENVIRONMENT", "K_SERVICE")


def demo_login_allowed(client_host, headers) -> bool:
    if os.environ.get("DEMO_LOGIN") != "1" or os.environ.get("FLASK_ENV") == "production":
        return False
    if any(os.environ.get(name) for name in _HOSTING_MARKERS):
        return False
    if any(headers.get(name) for name in _PROXY_HEADERS):
        return False
    return client_host in _LOOPBACK


def demo_user(username, password, client_host, headers):
    """The seeded admin's row when the test sign-in applies, otherwise None."""
    if (username, password) != (DEMO_USERNAME, DEMO_PASSWORD) or not demo_login_allowed(client_host, headers):
        return None
    with database.conn() as c:
        row = c.execute(
            "SELECT * FROM users WHERE username=? AND role='Admin'", (DEMO_USERNAME,)
        ).fetchone()
    return dict(row) if row else None
