import json
import os
import stat

from tests.conftest import login, upload


def test_default_password_must_change(client):
    from nexo.config import get_settings
    get_settings().require_password_change = True
    headers = login(client)
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["must_change_password"] is True
    r = client.get("/api/bases", headers=headers)
    assert r.status_code == 403 and r.json()["code"] == "PASSWORD_CHANGE_REQUIRED"
    setup = client.get("/api/system/setup", headers=headers)
    assert setup.status_code == 200 and setup.json()["must_change_password"] is True
    r = client.put("/api/auth/password", headers=headers, json={"current_password": "Nexo@2026", "new_password": "NovaSenha123"})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["must_change_password"] is False
    fresh = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/bases", headers=fresh).status_code == 200
    steps = {s["id"]: s for s in client.get("/api/system/setup", headers=fresh).json()["steps"]}
    assert steps["password"]["done"] is True


def test_provider_settings_secrets_and_choices(client):
    headers = login(client)
    out = client.get("/api/system/settings", headers=headers).json()
    items = {i["name"]: i for i in out["items"]}
    assert items["llm_provider"]["kind"] == "choice" and {o["value"] for o in items["llm_provider"]["options"]} == {
        "ollama", "openai", "compativel", "extrativo"}
    assert items["openai_api_key"]["kind"] == "secret" and items["openai_api_key"]["configured"] is False

    r = client.put("/api/system/settings", headers=headers, json={"values": {"llm_provider": "mistral"}})
    assert r.status_code == 400 and r.json()["fields"]["llm_provider"] == "Escolha uma das opções."
    r = client.put("/api/system/settings", headers=headers, json={"values": {"llm_provider": "compativel"}})
    assert r.status_code == 400 and "openai_base_url" in r.json()["fields"]
    r = client.put("/api/system/settings", headers=headers, json={"values": {"openai_base_url": "groq.com"}})
    assert r.status_code == 400 and "http" in r.json()["fields"]["openai_base_url"]

    r = client.put("/api/system/settings", headers=headers, json={"values": {
        "openai_base_url": "https://api.groq.com/openai/v1/", "openai_api_key": "gsk-segredo-de-teste", "llm_model": "llama-3.1-8b"}})
    assert r.status_code == 200, r.text
    assert set(r.json()["changed"]) == {"openai_base_url", "openai_api_key", "llm_model"}
    item = next(i for i in r.json()["items"] if i["name"] == "openai_api_key")
    assert item["configured"] is True and item["value"] == "" and "gsk-segredo" not in r.text

    from nexo.config import get_settings
    settings = get_settings()
    assert settings.openai_base_url == "https://api.groq.com/openai/v1" and settings.openai_api_key == "gsk-segredo-de-teste"
    plain = json.loads(settings.overrides_file.read_text(encoding="utf-8"))["valores"]
    secret = json.loads(settings.secrets_file.read_text(encoding="utf-8"))["valores"]
    assert "openai_api_key" not in plain and secret == {"openai_api_key": "gsk-segredo-de-teste"}
    if os.name == "posix":
        assert stat.S_IMODE(settings.secrets_file.stat().st_mode) == 0o600

    r = client.put("/api/system/settings", headers=headers, json={"values": {"openai_api_key": "", "llm_temperature": 0.2}})
    assert r.status_code == 200 and r.json()["changed"] == ["llm_temperature"]
    assert settings.openai_api_key == "gsk-segredo-de-teste"
    audit = client.get("/api/audit?action=settings.", headers=headers).json()
    assert "gsk-segredo" not in json.dumps(audit)

    r = client.post("/api/system/settings/reset", headers=headers, json={"names": ["openai_api_key"]})
    assert r.status_code == 200 and settings.openai_api_key is None
    assert json.loads(settings.secrets_file.read_text(encoding="utf-8"))["valores"] == {}


def test_provider_probe_and_ollama_models(client):
    headers = login(client)
    r = client.post("/api/system/providers/test", headers=headers, json={"target": "embedding"})
    assert r.status_code == 200 and r.json()["ok"] is True and "dimensões" in r.json()["detail"]
    r = client.post("/api/system/providers/test", headers=headers, json={"target": "llm"})
    assert r.json()["ok"] is True and "extrativo" in r.json()["detail"].lower()
    r = client.post("/api/system/providers/test", headers=headers, json={"target": "reranker"})
    assert r.json()["ok"] is True and "desligado" in r.json()["detail"].lower()
    r = client.post("/api/system/providers/test", headers=headers,
                    json={"target": "llm", "values": {"llm_provider": "compativel"}})
    assert r.status_code == 400 and "openai_base_url" in r.json()["fields"]
    r = client.post("/api/system/providers/test", headers=headers,
                    json={"target": "llm", "values": {"llm_provider": "ollama", "ollama_url": "http://127.0.0.1:9"}})
    assert r.status_code == 200 and r.json()["ok"] is False
    r = client.get("/api/system/providers/ollama-models?url=http://127.0.0.1:9", headers=headers)
    assert r.status_code == 200 and r.json()["models"] == [] and r.json()["error"]
    from nexo.config import get_settings
    assert get_settings().llm_provider == "extrativo"


def test_embedding_change_rebuilds_vectors(client):
    from nexo import jobs
    headers = login(client)
    doc = upload(client, headers)
    from nexo.config import get_settings
    settings = get_settings()
    assert json.loads(settings.vectors_file.read_text(encoding="utf-8"))["espaco"]
    r = client.put("/api/system/settings", headers=headers, json={"values": {"embed_model": "lexico-v2"}})
    assert r.status_code == 200, r.text
    assert r.json()["rebuilt"] == 1
    jobs.wait_idle()
    after = client.get(f"/api/documents/{doc['id']}", headers=headers).json()
    assert after["status"] == "READY" and after["outdated"] is False
    r = client.post("/api/search", headers=headers, json={"query": "atualização de firmware falhar", "rerank": False})
    assert r.status_code == 200 and r.json()["results"]
    actions = [i["action"] for i in client.get("/api/audit", headers=headers).json()["items"]]
    assert "system.rebuild" in actions


def test_setup_checklist_and_finish(client):
    headers = login(client)
    state = client.get("/api/system/setup", headers=headers).json()
    assert state["done"] is False and state["total"] == len(state["steps"]) == 7
    steps = {s["id"]: s["done"] for s in state["steps"]}
    assert steps["content"] is False and steps["backup"] is False
    upload(client, headers)
    client.put("/api/system/settings", headers=headers, json={"values": {"backup_hours": 24}})
    steps = {s["id"]: s["done"] for s in client.get("/api/system/setup", headers=headers).json()["steps"]}
    assert steps["content"] is True and steps["backup"] is True
    r = client.post("/api/system/setup", headers=headers, json={"done": True})
    assert r.status_code == 200 and r.json()["done"] is True and r.json()["done_at"]
    r = client.post("/api/system/setup", headers=headers, json={"done": False})
    assert r.json()["done"] is False
    other = client.post("/api/auth/register", json={"name": "Pessoa Ana", "username": "ana", "password": "senha-forte-1"})
    ana = {"Authorization": f"Bearer {other.json()['token']}"}
    assert client.get("/api/system/setup", headers=ana).status_code == 403


def test_auto_backup_rotation_and_download(client):
    headers = login(client)
    upload(client, headers)
    client.put("/api/system/settings", headers=headers, json={"values": {"backup_keep": 2}})
    for _ in range(3):
        r = client.post("/api/system/backups", headers=headers)
        assert r.status_code == 201, r.text
    listed = client.get("/api/system/backups", headers=headers).json()
    assert len(listed["items"]) == 2 and listed["keep"] == 2 and listed["every_hours"] == 0
    name = listed["items"][0]["name"]
    assert name.startswith("nexo-auto-") and name.endswith(".zip")
    r = client.get(f"/api/system/backups/{name}", headers=headers)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert client.get("/api/system/backups/..%2F.segredo", headers=headers).status_code == 404
    from nexo import maintenance
    from nexo.config import get_settings
    settings = get_settings()
    runner = maintenance.AutoBackup(settings)
    assert runner.due() is False
    settings.backup_hours = 1
    assert runner.due() is False and runner.next_at() is not None
    diag = {c["id"]: c for c in client.get("/api/system/diagnostics", headers=headers).json()["checks"]}
    assert diag["auto_backup"]["status"] == "ok" and diag["backup"]["status"] == "ok"


def test_cli_configure_password_and_port(client, monkeypatch, capsys):
    import socket

    from nexo import cli
    from nexo.config import get_settings
    from nexo.users import UserStore
    answers = iter(["3", "", "llama-3.1-8b-instant"])
    secrets_typed = iter(["SenhaNova123", "SenhaNova123", "gsk-teste"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: next(secrets_typed))
    from nexo.rag import providers
    monkeypatch.setattr(providers, "probe", lambda target, s: {"ok": True, "detail": "ok", "latency_ms": 1})
    cli.main(["configurar"])
    settings = get_settings()
    users = UserStore(settings.users_file)
    assert users.default_admin_active() is False
    stored = (settings.data_dir / "ajustes.json").read_text(encoding="utf-8")
    assert "compativel" in stored and "api.groq.com" in stored and "gsk-teste" not in stored
    assert "gsk-teste" in settings.secrets_file.read_text(encoding="utf-8")
    assert "salvo" in capsys.readouterr().out

    typed = iter(["OutraSenha456", "OutraSenha456"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: next(typed))
    cli.main(["senha", "admin"])
    assert UserStore(settings.users_file).authenticate("admin", "OutraSenha456").username == "admin"

    from nexo import desktop
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        port = busy.getsockname()[1]
        assert desktop.porta_livre("127.0.0.1", port) is False
        assert desktop.escolher_porta("127.0.0.1", port) != port
    assert desktop.url_local(settings.host, settings.port).startswith("http://")


def test_rate_limiter_prunes_idle_keys():
    from nexo.api.deps import RateLimiter
    limiter = RateLimiter(window=0.01, max_keys=10)
    for i in range(50):
        limiter.hit(f"visitante-{i}", 5)
    import time
    time.sleep(0.02)
    limiter.hit("novo", 5)
    assert len(limiter._hits) <= 11
    assert limiter.hit("x", 1) is None and limiter.hit("x", 1) is not None
