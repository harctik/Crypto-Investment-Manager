"""Sign-in, account seeding, the live feed and generated market lines."""
import os
import secrets
import urllib.request

import pytest

import app as web
import config
import database
import demo_login

SEED_VARIABLES = [variable for _, variable, _ in database.SEED_ACCOUNTS]


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch, tmp_path):
    """An empty database for each test."""
    for name in ("DEMO_LOGIN", "FLASK_ENV", *SEED_VARIABLES, *demo_login._HOSTING_MARKERS):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(database, "DB_FILE", str(tmp_path / "fresh.db"))
    previous = getattr(database._local, "connection", None)
    database._local.connection = None
    database.init_db()
    web._login_attempts.clear()
    web._cache.clear()
    monkeypatch.setattr(web, "_bg_started", True)  # no background price thread
    yield
    database._local.connection.close()
    database._local.connection = previous


def users():
    with database.conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM users ORDER BY id")]


def new_client(name):
    """Register an account and return a signed-in client."""
    client, password = web.app.test_client(), secrets.token_urlsafe(12)
    assert client.post("/register", json={"username": name, "password": password}).get_json()["ok"]
    assert client.post("/login", json={"username": name, "password": password}).status_code == 200
    return client


@pytest.mark.parametrize("path", ["/", "/login"])
def test_public_pages_publish_no_sign_in(path):
    page = web.app.test_client().get(path).get_data(as_text=True)
    assert "Demo account" not in page
    assert "<code>admin</code>" not in page


def test_fresh_database_has_no_accounts():
    assert users() == []


def test_only_accounts_with_a_supplied_password_are_seeded(monkeypatch):
    password = secrets.token_urlsafe(12)
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", password)
    monkeypatch.setenv("SEED_TRADER_PASSWORD", "short")
    database.init_db()
    assert [u["username"] for u in users()] == ["admin"]
    assert database.verify_user("admin", password)
    assert database.get_portfolio(users()[0]["id"])


def test_seeding_leaves_existing_users_alone(monkeypatch):
    database.create_user("someone", secrets.token_urlsafe(12))
    before = users()
    for variable in SEED_VARIABLES:
        monkeypatch.setenv(variable, secrets.token_urlsafe(12))
    database.init_db()
    assert users() == before


def test_registration_works_and_starts_empty():
    client = new_client("newperson")
    assert client.get("/dashboard").status_code == 200
    assert database.get_portfolio(users()[0]["id"]) == []


def test_every_api_route_requires_sign_in():
    client = web.app.test_client()
    checked = 0
    for rule in web.app.url_map.iter_rules():
        if not rule.rule.startswith("/api/"):
            continue
        with web.app.test_request_context():
            from flask import url_for
            path = url_for(rule.endpoint, **{argument: 1 for argument in rule.arguments})
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            response = client.open(path, method=method, json={})
            assert response.status_code == 401, (method, path)
            checked += 1
    assert checked > 20
    assert client.get("/dashboard").status_code == 302


def test_no_default_user_id():
    with web.app.test_request_context("/"):
        with pytest.raises(Exception) as error:
            web.current_user_id()
    assert error.value.code == 401


def test_sign_in_error_hides_the_detail(monkeypatch):
    def broken(*args):
        raise RuntimeError("internal-detail-123")

    monkeypatch.setattr(database, "verify_user", broken)
    response = web.app.test_client().post("/login", json={"username": "a", "password": "b"})
    assert response.status_code == 500
    assert "internal-detail-123" not in response.get_data(as_text=True)


@pytest.mark.skipif(bool(os.getenv("SECRET_KEY")), reason="SECRET_KEY is set")
def test_session_key_is_random_without_secret_key():
    assert len(config.APP["secret_key"]) == 64


def sign_in_locally():
    return web.app.test_client().post(
        "/login", json={"username": demo_login.DEMO_USERNAME, "password": demo_login.DEMO_PASSWORD},
        environ_base={"REMOTE_ADDR": "127.0.0.1"})


def test_local_test_sign_in_creates_admin_only_when_enabled(monkeypatch):
    assert sign_in_locally().status_code == 401
    assert users() == []
    monkeypatch.setenv("DEMO_LOGIN", "1")
    assert sign_in_locally().status_code == 200
    assert [(u["username"], u["role"]) for u in users()] == [("admin", "Admin")]


@pytest.mark.parametrize("role,status", [("Admin", 200), ("Trader", 401)])
def test_local_test_sign_in_keeps_an_existing_account(monkeypatch, role, status):
    database.create_user("admin", secrets.token_urlsafe(12), role=role)
    before = users()
    monkeypatch.setenv("DEMO_LOGIN", "1")
    assert sign_in_locally().status_code == status
    assert users() == before


def test_live_feed_refuses_signed_out_visitors():
    assert not web.socketio.test_client(web.app).is_connected()


def test_fired_alerts_reach_only_their_owner():
    first, second = new_client("first"), new_client("second")
    one = web.socketio.test_client(web.app, flask_test_client=first)
    two = web.socketio.test_client(web.app, flask_test_client=second)
    assert one.is_connected() and two.is_connected()
    one.get_received()
    two.get_received()
    owner = users()[0]["id"]
    web._send_fired_alerts([{"user_id": owner, "coin_id": "bitcoin"}])
    assert [m["name"] for m in one.get_received()] == ["price_alert_fired"]
    assert two.get_received() == []


def market_lines(monkeypatch, coins):
    def offline(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", offline)
    monkeypatch.setattr(database, "get_prices", lambda ids: coins)
    return new_client("reader").get("/api/news").get_json()


def quote(**extra):
    return {"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "current_price": 100.0,
            "price_change_percentage_24h": 7.5, **extra}


def test_price_lines_are_labelled_as_generated(monkeypatch):
    [line] = market_lines(monkeypatch, [quote()])
    assert line["generated"] is True
    assert line["source"].startswith("Auto-generated")


def test_simulated_prices_are_not_reported_as_moves(monkeypatch):
    lines = market_lines(monkeypatch, [quote(simulated=True)])
    assert not any("BTC" in line["title"] for line in lines)


def test_fallback_prices_are_marked_simulated():
    assert all(coin["simulated"] for coin in database.get_prices(["bitcoin"]))


def test_dropdowns_use_coin_names():
    page = new_client("viewer").get("/dashboard").get_data(as_text=True)
    assert '<option value="matic-network">Polygon</option>' in page
    assert config.coin_name("some-new-coin") == "Some New Coin"
