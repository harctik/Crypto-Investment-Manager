"""The test-only admin/admin sign-in must stay shut unless asked for, on this computer."""
import pytest

import app as web
import demo_login


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for name in ("DEMO_LOGIN", "FLASK_ENV", *demo_login._HOSTING_MARKERS):
        monkeypatch.delenv(name, raising=False)
    web._login_attempts.clear()


def sign_in(host="127.0.0.1", headers=None):
    return web.app.test_client().post(
        "/login", json={"username": "admin", "password": "admin"},
        headers=headers or {}, environ_base={"REMOTE_ADDR": host},
    )


def test_off_by_default():
    assert sign_in().status_code == 401


def test_works_on_this_computer_when_enabled(monkeypatch):
    monkeypatch.setenv("DEMO_LOGIN", "1")
    response = sign_in()
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


@pytest.mark.parametrize("host,headers", [
    ("203.0.113.9", {}),
    ("127.0.0.1", {"X-Forwarded-For": "127.0.0.1"}),
    ("127.0.0.1", {"X-Real-IP": "203.0.113.9"}),
])
def test_refused_from_elsewhere(monkeypatch, host, headers):
    monkeypatch.setenv("DEMO_LOGIN", "1")
    assert sign_in(host, headers).status_code == 401


@pytest.mark.parametrize("name,value", [("FLASK_ENV", "production"), ("VERCEL", "1"), ("RENDER", "true")])
def test_refused_in_production(monkeypatch, name, value):
    monkeypatch.setenv("DEMO_LOGIN", "1")
    monkeypatch.setenv(name, value)
    assert sign_in().status_code == 401
