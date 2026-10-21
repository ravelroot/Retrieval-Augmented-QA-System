import json

from tests.conftest import login


def test_default_admin_can_log_in(client):
    headers = login(client)
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["username"] == "admin"
    assert me["role"] == "admin"


def test_wrong_password_is_rejected_and_locks_after_five_attempts(client):
    for _ in range(5):
        r = client.post("/api/auth/login", json={"username": "admin", "password": "errada123"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"username": "admin", "password": "Nexo@2026"})
    assert r.status_code == 429
    assert r.json()["code"] == "LOCKED"


def test_register_saves_user_in_file(client):
    r = client.post("/api/auth/register", json={"name": "Maria Teste", "username": "maria", "password": "senhaForte1"})
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "user"
    from nexo.config import get_settings
    saved = json.loads(get_settings().users_file.read_text(encoding="utf-8"))
    names = [u["username"] for u in saved["usuarios"]]
    assert names == ["admin", "maria"]
    assert all(u["password_hash"].startswith("$2") for u in saved["usuarios"])
    assert "senhaForte1" not in get_settings().users_file.read_text(encoding="utf-8")
    login(client, "maria", "senhaForte1")


def test_register_validates_input(client):
    r = client.post("/api/auth/register", json={"name": "A", "username": "x", "password": "123"})
    assert r.status_code == 400
    r = client.post("/api/auth/register", json={"name": "Joao", "username": "joao", "password": "semnumero"})
    assert r.json()["code"] == "WEAK_PASSWORD"
    client.post("/api/auth/register", json={"name": "Joao", "username": "joao", "password": "senhaForte1"})
    r = client.post("/api/auth/register", json={"name": "Joao 2", "username": "joao", "password": "senhaForte1"})
    assert r.status_code == 409


def test_routes_require_token(client):
    assert client.get("/api/documents").status_code == 401
    r = client.get("/api/documents", headers={"Authorization": "Bearer invalido"})
    assert r.status_code == 401
    assert r.json()["code"] == "SESSION_EXPIRED"


def test_change_password(client):
    headers = login(client)
    r = client.put("/api/auth/password", headers=headers,
                   json={"current_password": "Nexo@2026", "new_password": "NovaSenha2026"})
    assert r.status_code == 204
    login(client, "admin", "NovaSenha2026")


def test_options_reports_default_admin_until_password_changes(client):
    assert client.get("/api/auth/options").json() == {"registration": True, "default_admin": True}
    headers = login(client)
    client.put("/api/auth/password", headers=headers,
               json={"current_password": "Nexo@2026", "new_password": "NovaSenha2026"})
    assert client.get("/api/auth/options").json()["default_admin"] is False
