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
    assert r.status_code == 200
    fresh = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/auth/me", headers=headers).json()["code"] == "SESSION_REVOKED"
    assert client.get("/api/auth/me", headers=fresh).status_code == 200
    login(client, "admin", "NovaSenha2026")


def test_new_password_must_differ(client):
    headers = login(client)
    r = client.put("/api/auth/password", headers=headers,
                   json={"current_password": "Nexo@2026", "new_password": "Nexo@2026"})
    assert r.status_code == 400
    assert r.json()["code"] == "SAME_PASSWORD"


def test_revoke_other_sessions(client):
    first = login(client)
    second = login(client)
    r = client.post("/api/auth/sessions/revoke", headers=second)
    assert r.status_code == 200
    current = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/auth/me", headers=first).status_code == 401
    assert client.get("/api/auth/me", headers=second).status_code == 401
    assert client.get("/api/auth/me", headers=current).status_code == 200


def test_rename_profile(client):
    headers = login(client)
    r = client.patch("/api/auth/me", headers=headers, json={"name": "  Erik   Pimenta "})
    assert r.status_code == 200
    assert r.json()["name"] == "Erik Pimenta"
    r = client.patch("/api/auth/me", headers=headers, json={"name": "E"})
    assert r.status_code == 400
    assert "name" in r.json()["fields"]


def test_admin_creates_users_and_resets_passwords(client, monkeypatch):
    admin = login(client)
    r = client.post("/api/users", headers=admin, json={"name": "Ana Souza", "username": "ana",
                                                       "password": "Inicial2026", "role": "user"})
    assert r.status_code == 201, r.text
    assert r.json()["last_login_at"] is None
    r = client.post("/api/users", headers=admin, json={"name": "Ana 2", "username": "ana", "password": "Inicial2026"})
    assert r.status_code == 409
    ana = login(client, "ana", "Inicial2026")
    r = client.post("/api/users", headers=ana, json={"name": "Bia", "username": "bia", "password": "Inicial2026"})
    assert r.status_code == 403
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "ana", "password": "errada123"})
    assert client.post("/api/auth/login", json={"username": "ana", "password": "Inicial2026"}).status_code == 429
    r = client.put("/api/users/ana/password", headers=admin, json={"password": "Trocada2026"})
    assert r.status_code == 200, r.text
    assert r.json()["password_changed_at"]
    assert client.get("/api/auth/me", headers=ana).status_code == 401
    login(client, "ana", "Trocada2026")
    assert client.put("/api/users/ana/password", headers=admin, json={"password": "curta"}).status_code == 400
    assert client.put("/api/users/ninguem/password", headers=admin, json={"password": "Trocada2026"}).status_code == 404
    assert client.put("/api/users/admin/password", headers=admin, json={"password": "Trocada2026"}).status_code == 400


def test_options_reports_default_admin_until_password_changes(client):
    assert client.get("/api/auth/options").json() == {"registration": True, "default_admin": True}
    headers = login(client)
    client.put("/api/auth/password", headers=headers,
               json={"current_password": "Nexo@2026", "new_password": "NovaSenha2026"})
    assert client.get("/api/auth/options").json()["default_admin"] is False
