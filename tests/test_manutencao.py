from __future__ import annotations

import csv
import io
import json
import sqlite3
import zipfile
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FIXTURES, login, upload


def register(client, username: str) -> dict:
    r = client.post("/api/auth/register", json={"name": f"Pessoa {username}", "username": username,
                                                "password": "senha-forte-1"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def default_base(client, headers) -> str:
    return next(b["id"] for b in client.get("/api/bases", headers=headers).json() if b["is_default"])


def add_text(client, headers, base_id: str, title: str, content: str) -> dict:
    r = client.post(f"/api/bases/{base_id}/texts", headers=headers, json={"title": title, "content": content})
    assert r.status_code == 201, r.text
    return r.json()


def test_migrates_database_from_2_2(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    conn = sqlite3.connect(data / "nexo.db")
    conn.executescript((FIXTURES / "schema-2.2.sql").read_text(encoding="utf-8"))
    conn.executescript("""
        INSERT INTO nx_knowledge_base VALUES ('b1', 'Acervo geral', NULL, '#000000', 1, 'admin', '2026-10-01 10:00:00',
          '2026-10-01 10:00:00');
        INSERT INTO nx_conversation (id, owner, bot_id, title, created_at, updated_at)
          VALUES ('c1', 'admin', NULL, 'Antiga', '2026-10-01 10:00:00', '2026-10-01 10:00:00');
        INSERT INTO nx_api_key VALUES ('k1', 'admin', 'Antiga', 'nxk_abc', 'hash', '2026-10-01 10:00:00', NULL);
    """)
    conn.commit()
    conn.close()
    monkeypatch.setenv("NEXO_DATA_DIR", str(data))
    from nexo import db
    from nexo.config import get_settings
    get_settings.cache_clear()
    db.reset_engine()
    try:
        with db.session() as s:
            assert s.get(db.ConversationRow, "c1").pinned is False
            key = s.get(db.ApiKeyRow, "k1")
            assert key.scope == "full" and key.expires_at is None
            s.add(db.AuditRow(actor="admin", action="auth.login"))
            s.add(db.QuickReplyRow(title="Oi", body="Olá!", created_by="admin"))
            s.commit()
        raw = sqlite3.connect(data / "nexo.db")
        columns = {r[1] for r in raw.execute("PRAGMA table_info(nx_document)").fetchall()}
        assert {"index_signature", "source_url"} <= columns
        assert {r[1] for r in raw.execute("PRAGMA table_info(nx_bot)").fetchall()} >= {"suggestions"}
        raw.close()
    finally:
        db.reset_engine()
        get_settings.cache_clear()


def test_runtime_settings(client):
    admin = login(client)
    maria = register(client, "maria")
    assert client.get("/api/system/settings", headers=maria).status_code == 403
    out = client.get("/api/system/settings", headers=admin).json()
    names = {i["name"] for i in out["items"]}
    assert {"top_k", "top_n", "chunk_size", "rate_limit", "retention_days", "llm_model"} <= names
    assert "Embeddings" in out["fixed"]

    r = client.put("/api/system/settings", headers=admin, json={"values": {"top_k": 3, "top_n": 5}})
    assert r.status_code == 400 and "top_n" in r.json()["fields"]
    r = client.put("/api/system/settings", headers=admin, json={"values": {"chunk_size": 256, "chunk_overlap": 300}})
    assert r.status_code == 400 and "chunk_overlap" in r.json()["fields"]
    r = client.put("/api/system/settings", headers=admin, json={"values": {"top_k": 0}})
    assert r.status_code == 400 and "top_k" in r.json()["fields"]
    r = client.put("/api/system/settings", headers=admin, json={"values": {"data_dir": "/tmp"}})
    assert r.status_code == 400

    r = client.put("/api/system/settings", headers=admin, json={"values": {"top_n": 2, "allow_registration": False}})
    assert r.status_code == 200, r.text
    assert set(r.json()["changed"]) == {"top_n", "allow_registration"}
    from nexo.config import get_settings
    settings = get_settings()
    assert settings.top_n == 2 and settings.allow_registration is False
    stored = json.loads(settings.overrides_file.read_text(encoding="utf-8"))
    assert stored["valores"] == {"top_n": 2, "allow_registration": False} and stored["alterado_por"] == "admin"
    assert client.get("/api/auth/options").json()["registration"] is False
    assert client.get("/api/system/status", headers=admin).json()["providers"]["top_n"] == 2

    from nexo import runtime
    settings.top_n = 4
    runtime.apply(settings)
    assert settings.top_n == 2

    r = client.post("/api/system/settings/reset", headers=admin, json={"names": ["top_n"]})
    assert r.status_code == 200 and r.json()["changed"] == ["top_n"]
    assert settings.top_n == 4 and settings.allow_registration is False
    r = client.post("/api/system/settings/reset", headers=admin, json={})
    assert settings.allow_registration is True
    assert json.loads(settings.overrides_file.read_text(encoding="utf-8"))["valores"] == {}


def test_chunk_change_marks_outdated_and_reindex(client):
    from nexo import jobs
    headers = login(client)
    doc = upload(client, headers)
    assert client.get(f"/api/documents/{doc['id']}", headers=headers).json()["outdated"] is False
    r = client.put("/api/system/settings", headers=headers, json={"values": {"chunk_size": 256, "chunk_overlap": 32}})
    assert r.status_code == 200
    assert r.json()["outdated"] == 1 and r.json()["reindex_needed"] is True
    assert client.get(f"/api/documents/{doc['id']}", headers=headers).json()["outdated"] is True
    assert client.get("/api/system/status", headers=headers).json()["documents"]["outdated"] == 1
    r = client.post("/api/system/maintenance", headers=headers, json={"action": "reindex_outdated"})
    assert r.status_code == 200 and r.json()["count"] == 1
    jobs.wait_idle()
    after = client.get(f"/api/documents/{doc['id']}", headers=headers).json()
    assert after["status"] == "READY" and after["outdated"] is False and after["chunks"] >= doc["chunks"]


def test_diagnostics(client):
    admin = login(client)
    maria = register(client, "maria")
    assert client.get("/api/system/diagnostics", headers=maria).status_code == 403
    report = client.get("/api/system/diagnostics", headers=admin).json()
    checks = {c["id"]: c for c in report["checks"]}
    assert checks["database"]["status"] == "ok"
    assert checks["default_admin"]["status"] == "fail"
    assert checks["llm"]["status"] == "warn" and checks["embedding"]["status"] == "warn"
    assert checks["backup"]["status"] == "warn"
    assert report["fail"] >= 1
    upload(client, admin)
    deep = client.get("/api/system/diagnostics?deep=true", headers=admin).json()
    checks = {c["id"]: c for c in deep["checks"]}
    assert deep["deep"] is True
    assert checks["embedding_call"]["status"] == "ok"
    assert checks["vectors"]["status"] == "ok"
    assert checks["files"]["status"] == "ok"


def test_maintenance_actions(client):
    from nexo import db, jobs
    from nexo.config import get_settings
    from nexo.rag.engine import get_engine
    headers = login(client)
    maria = register(client, "maria")
    assert client.post("/api/system/maintenance", headers=maria, json={"action": "vacuum"}).status_code == 403
    doc = upload(client, headers)
    settings = get_settings()
    stray = settings.uploads_dir / "sobrando.pdf"
    stray.write_bytes(b"%PDF-1.4 sobra")
    engine = get_engine(settings)
    engine.ingest_parts("fantasma", "Fantasma", "fantasma.txt", [(1, "Texto de um documento que não existe mais no banco.")])
    report = {c["id"]: c for c in client.get("/api/system/diagnostics?deep=true", headers=headers).json()["checks"]}
    assert report["orphans"]["status"] == "warn" and report["vectors"]["status"] == "warn"
    r = client.post("/api/system/maintenance", headers=headers, json={"action": "clean_orphans"})
    assert r.status_code == 200 and r.json()["count"] == 2
    assert not stray.exists() and "fantasma" not in engine.source_ids()
    assert doc["id"] in engine.source_ids()

    with db.session() as s:
        s.get(db.DocumentRow, doc["id"]).status = "FAILED"
        s.commit()
    r = client.post("/api/system/maintenance", headers=headers, json={"action": "reindex_failed"})
    assert r.json()["count"] == 1
    jobs.wait_idle()
    assert client.get(f"/api/documents/{doc['id']}", headers=headers).json()["status"] == "READY"

    old = client.post("/api/conversations", headers=headers, json={"title": "Velha"}).json()
    kept = client.post("/api/conversations", headers=headers, json={"title": "Fixada"}).json()
    fresh = client.post("/api/conversations", headers=headers, json={"title": "Nova"}).json()
    assert client.patch(f"/api/conversations/{kept['id']}", headers=headers, json={"pinned": True}).json()["pinned"]
    with db.session() as s:
        for cid in (old["id"], kept["id"]):
            s.get(db.ConversationRow, cid).updated_at = db.utcnow() - timedelta(days=40)
        s.commit()
    r = client.post("/api/system/maintenance", headers=headers, json={"action": "purge_conversations"})
    assert r.status_code == 400 and r.json()["code"] == "MAINTENANCE"
    r = client.post("/api/system/maintenance", headers=headers, json={"action": "purge_conversations", "days": 30})
    assert r.json()["count"] == 1
    left = [c["id"] for c in client.get("/api/conversations", headers=headers).json()]
    assert left == [kept["id"], fresh["id"]]

    r = client.post("/api/system/maintenance", headers=headers, json={"action": "vacuum"})
    assert r.status_code == 200 and "compactado" in r.json()["message"]
    assert client.post("/api/system/maintenance", headers=headers, json={"action": "outra"}).status_code == 422


def test_backup_and_restore(client, tmp_path):
    from nexo import maintenance
    headers = login(client)
    doc = upload(client, headers)
    add_text(client, headers, default_base(client, headers), "Horário", "Atendemos de segunda a sexta, das 8h às 18h.")
    assert client.get("/api/system/backup", headers=register(client, "maria")).status_code == 403
    r = client.get("/api/system/backup", headers=headers)
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(archive.namelist())
    assert {"manifesto.json", "nexo.db", "usuarios.json", f"uploads/{doc['id']}.pdf"} <= names
    manifest = json.loads(archive.read("manifesto.json"))
    assert manifest["documentos"] == 2 and manifest["inclui_banco"] is True
    zipped = tmp_path / "copia.zip"
    zipped.write_bytes(r.content)
    report = {c["id"]: c for c in client.get("/api/system/diagnostics", headers=headers).json()["checks"]}
    assert report["backup"]["status"] == "ok"

    target = tmp_path / "restaurado"
    result = maintenance.restore_backup(zipped, target)
    assert (target / "nexo.db").exists() and (target / "uploads" / f"{doc['id']}.pdf").exists()
    assert result["queued"] == 2 and result["previous"] is None
    raw = sqlite3.connect(target / "nexo.db")
    assert {r[0] for r in raw.execute("SELECT status FROM nx_document").fetchall()} == {"PENDING"}
    raw.close()
    with pytest.raises(maintenance.MaintenanceError):
        maintenance.restore_backup(zipped, target)
    again = maintenance.restore_backup(zipped, target, replace=True)
    assert again["previous"] and Path(again["previous"]).exists()

    evil = tmp_path / "ruim.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("manifesto.json", "{}")
        z.writestr("../fora.txt", "x")
    with pytest.raises(maintenance.MaintenanceError):
        maintenance.restore_backup(evil, tmp_path / "outro")
    assert not (tmp_path / "fora.txt").exists()


def test_audit_log(client):
    admin = login(client)
    maria = register(client, "maria")
    client.post("/api/auth/login", json={"username": "admin", "password": "errada-123"})
    base = client.post("/api/bases", headers=admin, json={"name": "Vendas"}).json()
    client.post("/api/keys", headers=admin, json={"name": "Portal"})
    client.delete(f"/api/bases/{base['id']}", headers=admin)
    assert client.get("/api/audit", headers=maria).status_code == 403
    page = client.get("/api/audit", headers=admin).json()
    actions = [i["action"] for i in page["items"]]
    assert {"auth.login", "auth.login_failed", "auth.register", "base.create", "base.delete", "key.create"} <= set(actions)
    assert actions.index("base.delete") < actions.index("base.create")
    created = next(i for i in page["items"] if i["action"] == "base.create")
    assert created["actor"] == "admin" and created["target_id"] == base["id"] and created["label"] == "Criou uma base"
    assert created["ip"] == "testclient"
    only = client.get("/api/audit?action=base.", headers=admin).json()
    assert only["total"] == 2 and {i["action"] for i in only["items"]} == {"base.create", "base.delete"}
    mine = client.get("/api/audit?actor=maria", headers=admin).json()
    assert {i["action"] for i in mine["items"]} == {"auth.register"}
    r = client.get("/api/audit/export?action=base.", headers=admin)
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[0][:4] == ["data_utc", "conta", "acao", "descricao"] and len(rows) == 3


def test_api_key_scope_and_expiry(client):
    from nexo import db
    headers = login(client)
    upload(client, headers)
    base_id = default_base(client, headers)
    ask = client.post("/api/keys", headers=headers, json={"name": "Portal", "scope": "ask", "expires_days": 30}).json()
    feed = client.post("/api/keys", headers=headers, json={"name": "ERP", "scope": "feed"}).json()
    assert ask["scope"] == "ask" and ask["expires_at"] and feed["expires_at"] is None
    k_ask = {"X-API-Key": ask["key"]}
    k_feed = {"X-API-Key": feed["key"]}
    question = {"question": "O que acontece se a atualização de firmware falhar?"}
    assert client.post("/api/ask", headers=k_ask, json=question).status_code == 200
    r = client.get("/api/documents", headers=k_ask)
    assert r.status_code == 403 and r.json()["code"] == "KEY_SCOPE"
    assert client.post("/api/keys", headers=k_ask, json={"name": "Outra"}).status_code == 403
    assert client.get("/api/system/settings", headers=k_ask).status_code == 403
    assert client.post(f"/api/bases/{base_id}/texts", headers=k_feed,
                       json={"title": "Preço", "content": "O plano custa cem reais."}).status_code == 201
    assert client.post("/api/ask", headers=k_feed, json={"question": "Preço?"}).status_code == 403
    full = client.post("/api/keys", headers=headers, json={"name": "Tudo"}).json()
    assert client.get("/api/system/settings", headers={"X-API-Key": full["key"]}).status_code == 200
    with db.session() as s:
        s.get(db.ApiKeyRow, ask["id"]).expires_at = db.utcnow() - timedelta(minutes=1)
        s.commit()
    r = client.post("/api/ask", headers=k_ask, json={"question": "Qual o torque?"})
    assert r.status_code == 401 and r.json()["code"] == "API_KEY_EXPIRED"
    listed = {k["id"]: k for k in client.get("/api/keys", headers=headers).json()}
    assert listed[ask["id"]]["expired"] is True and listed[feed["id"]]["expired"] is False
    assert client.post("/api/keys", headers=headers, json={"name": "X", "scope": "tudo"}).status_code == 422


def test_rate_limit(client):
    from nexo.config import get_settings
    headers = login(client)
    upload(client, headers)
    get_settings().rate_limit = 2
    body = {"question": "O que acontece se a atualização de firmware falhar?"}
    assert client.post("/api/ask", headers=headers, json=body).status_code == 200
    assert client.post("/api/search", headers=headers, json={"query": "torque"}).status_code == 200
    r = client.post("/api/ask", headers=headers, json=body)
    assert r.status_code == 429 and r.json()["code"] == "RATE_LIMITED"
    assert 1 <= int(r.headers["retry-after"]) <= 60
    maria = register(client, "maria")
    assert client.post("/api/ask", headers=maria, json=body).status_code == 200
    get_settings().rate_limit = 0
    assert client.post("/api/ask", headers=headers, json=body).status_code == 200


def test_cors_and_openapi_tags(client):
    from nexo.api.app import create_app
    from nexo.config import get_settings
    assert "access-control-allow-origin" not in client.options(
        "/api/ask", headers={"Origin": "https://intranet.exemplo.com", "Access-Control-Request-Method": "POST"}).headers
    get_settings().cors_origins = "https://intranet.exemplo.com/, https://outro.exemplo.com"
    try:
        with TestClient(create_app()) as other:
            r = other.options("/api/ask", headers={"Origin": "https://intranet.exemplo.com",
                                                    "Access-Control-Request-Method": "POST",
                                                    "Access-Control-Request-Headers": "X-API-Key"})
            assert r.headers["access-control-allow-origin"] == "https://intranet.exemplo.com"
            spec = other.get("/api/openapi.json").json()
    finally:
        get_settings().cors_origins = None
    tags = {op["tags"][0] for path in spec["paths"].values() for op in path.values() if op.get("tags")}
    assert {"Conversas", "WhatsApp", "Sistema e manutenção", "Agentes", "Documentos"} <= tags


def test_prometheus_metrics(client):
    headers = login(client)
    upload(client, headers)
    client.post("/api/ask", headers=headers, json={"question": "O que acontece se a atualização de firmware falhar?"})
    assert client.get("/api/health/metrics", headers=register(client, "maria")).status_code == 403
    r = client.get("/api/health/metrics", headers=headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    text = r.text
    assert 'nexo_info{version="' in text and 'nexo_documents{status="READY"} 1' in text
    assert "nexo_http_requests_total" in text and "nexo_chunks " in text


def test_pinned_conversations_and_comments(client):
    headers = login(client)
    upload(client, headers)
    a = client.post("/api/conversations", headers=headers, json={"title": "A"}).json()
    b = client.post("/api/conversations", headers=headers, json={"title": "B"}).json()
    assert [c["id"] for c in client.get("/api/conversations", headers=headers).json()] == [b["id"], a["id"]]
    r = client.patch(f"/api/conversations/{a['id']}", headers=headers, json={"pinned": True})
    assert r.json()["pinned"] is True and r.json()["updated_at"] == a["updated_at"]
    assert [c["id"] for c in client.get("/api/conversations", headers=headers).json()] == [a["id"], b["id"]]
    ex = client.post(f"/api/conversations/{a['id']}/messages", headers=headers,
                     json={"content": "O que acontece se a atualização de firmware falhar?"}).json()
    r = client.post(f"/api/messages/{ex['answer']['id']}/feedback", headers=headers,
                    json={"rating": -1, "comment": "Faltou a sequência de aperto."})
    assert r.json()["my_rating"] == -1 and r.json()["my_comment"] == "Faltou a sequência de aperto."
    metrics = client.get("/api/metrics", headers=headers).json()
    assert metrics["negative_recent"][0]["comment"] == "Faltou a sequência de aperto."
    rows = list(csv.reader(io.StringIO(client.get("/api/metrics/export", headers=headers).content.decode("utf-8-sig")),
                           delimiter=";"))
    assert rows[0][-1] == "comentario" and rows[1][-1] == "Faltou a sequência de aperto."


def test_bot_suggestions_duplicate_and_metrics_by_bot(client):
    headers = login(client)
    upload(client, headers)
    base_id = default_base(client, headers)
    r = client.post("/api/bots", headers=headers, json={
        "name": "Suporte", "base_id": base_id,
        "suggestions": ["Qual o torque?", "  qual o torque? ", "Como trocar o filtro?", "", "x" * 300]})
    bot = r.json()
    assert bot["suggestions"] == ["Qual o torque?", "Como trocar o filtro?", "x" * 200]
    r = client.patch(f"/api/bots/{bot['id']}", headers=headers, json={"suggestions": ["Só uma"]})
    assert r.json()["suggestions"] == ["Só uma"]
    copy = client.post(f"/api/bots/{bot['id']}/duplicate", headers=headers)
    assert copy.status_code == 201
    copy = copy.json()
    assert copy["name"] == "Suporte (cópia)" and copy["suggestions"] == ["Só uma"] and copy["id"] != bot["id"]
    assert copy["base_id"] == base_id

    conv = client.post("/api/conversations", headers=headers, json={"bot_id": bot["id"]}).json()
    client.post(f"/api/conversations/{conv['id']}/messages", headers=headers,
                json={"content": "O que acontece se a atualização de firmware falhar?"})
    general = client.post("/api/conversations", headers=headers, json={}).json()
    client.post(f"/api/conversations/{general['id']}/messages", headers=headers,
                json={"content": "Quem venceu a copa do mundo de futebol?"})
    m = client.get("/api/metrics", headers=headers).json()
    stats = {s["name"]: s for s in m["by_bot"]}
    assert stats["Suporte"]["questions"] == 1 and stats["Suporte"]["answered"] == 1
    assert stats["Conversas gerais"]["questions"] == 1 and stats["Conversas gerais"]["answered"] == 0
    only = client.get(f"/api/metrics?bot_id={bot['id']}", headers=headers).json()
    assert only["questions"] == 1 and only["bot_id"] == bot["id"] and len(only["by_bot"]) == 2
    assert client.get("/api/metrics?bot_id=geral", headers=headers).json()["unanswered"] == 1


def test_quick_replies(client):
    admin = login(client)
    maria = register(client, "maria")
    joao = register(client, "joao")
    r = client.post("/api/whatsapp/quick-replies", headers=maria, json={"title": "Boas-vindas", "body": "Olá, {nome}!"})
    assert r.status_code == 201 and r.json()["can_edit"] is True
    reply = r.json()
    assert client.post("/api/whatsapp/quick-replies", headers=admin,
                       json={"title": "boas-vindas", "body": "Outro"}).status_code == 409
    client.post("/api/whatsapp/quick-replies", headers=admin, json={"title": "Atendimento", "body": "Das 8h às 18h."})
    listed = client.get("/api/whatsapp/quick-replies", headers=joao).json()
    assert [x["title"] for x in listed] == ["Atendimento", "Boas-vindas"]
    assert not any(x["can_edit"] for x in listed)
    assert client.patch(f"/api/whatsapp/quick-replies/{reply['id']}", headers=joao, json={"body": "x"}).status_code == 403
    r = client.patch(f"/api/whatsapp/quick-replies/{reply['id']}", headers=admin, json={"body": "Oi, {nome}!"})
    assert r.json()["body"] == "Oi, {nome}!"
    assert client.patch(f"/api/whatsapp/quick-replies/{reply['id']}", headers=maria,
                        json={"title": "Atendimento"}).status_code == 409
    assert client.delete(f"/api/whatsapp/quick-replies/{reply['id']}", headers=maria).status_code == 204
    assert len(client.get("/api/whatsapp/quick-replies", headers=admin).json()) == 1


def test_document_chunks(client):
    headers = login(client)
    doc = upload(client, headers)
    doc = client.get(f"/api/documents/{doc['id']}", headers=headers).json()
    r = client.get(f"/api/documents/{doc['id']}/chunks?limit=2", headers=headers)
    assert r.status_code == 200
    out = r.json()
    assert out["total"] == doc["chunks"] and len(out["items"]) == min(2, doc["chunks"])
    assert out["items"][0]["index"] == 0 and out["items"][0]["text"] and out["items"][0]["page"] >= 1
    page = client.get(f"/api/documents/{doc['id']}/chunks?offset=1&limit=1", headers=headers).json()
    assert page["items"][0]["index"] == 1
    found = client.get(f"/api/documents/{doc['id']}/chunks?q=Reset", headers=headers).json()
    assert 1 <= found["total"] < doc["chunks"] and all("reset" in c["text"].lower() for c in found["items"])
    assert client.get("/api/documents/nada/chunks", headers=headers).status_code == 404


def test_cli_commands(client, capsys, tmp_path):
    from nexo import cli
    headers = login(client)
    upload(client, headers)
    cli.main(["versao"])
    assert "Nexo 2." in capsys.readouterr().out
    cli.main(["contas"])
    assert "admin" in capsys.readouterr().out
    with pytest.raises(SystemExit) as stop:
        cli.main(["diagnostico"])
    assert stop.value.code == 1
    assert "Senha padrão do administrador" in capsys.readouterr().out
    target = tmp_path / "copia" / "nexo.zip"
    cli.main(["backup", "--saida", str(target)])
    assert target.exists() and "Backup gravado" in capsys.readouterr().out
    cli.main(["reindexar"])
    assert "Nada para reindexar" in capsys.readouterr().out
    cli.main(["reindexar", "--todos"])
    assert "1 ok, 0 com falha" in capsys.readouterr().out


def test_json_logs(capsys):
    import logging
    from nexo import context
    from nexo.logs import JsonFormatter
    token = context.request_id.set("req-12345678")
    try:
        record = logging.LogRecord("nexo.access", logging.INFO, __file__, 1, "GET %s", ("/api/health",), None)
        record.status = 200
        data = json.loads(JsonFormatter().format(record))
    finally:
        context.request_id.reset(token)
    assert data["message"] == "GET /api/health" and data["request_id"] == "req-12345678" and data["status"] == 200


def test_sample_base(client):
    from nexo import jobs
    headers = login(client)
    r = client.post("/api/bases/sample", headers=headers)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["base"]["name"] == "Base de teste" and out["bot"]["name"] == "Agente de teste"
    assert out["added"] == 6 and out["existed"] is False and len(out["bot"]["suggestions"]) == 4
    jobs.wait_idle()
    docs = client.get(f"/api/bases/{out['base']['id']}/documents", headers=headers).json()
    assert {d["extension"] for d in docs} == {"pdf", "md", "html", "csv", "txt", "json"}
    assert all(d["status"] == "READY" for d in docs), [(d["filename"], d["error"]) for d in docs]
    titles = {d["title"] for d in docs}
    assert {"Garantia do Roteador RX-200", "Planos de suporte", "Perguntas frequentes do RX-200"} <= titles
    conv = client.post("/api/conversations", headers=headers, json={"bot_id": out["bot"]["id"]}).json()
    answer = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers,
                         json={"content": "Quanto tempo dura a garantia?"}).json()["answer"]
    assert answer["answered"] is True and "12 meses" in answer["content"]
    again = client.post("/api/bases/sample", headers=headers).json()
    assert again["existed"] is True and again["added"] == 0 and again["bot"]["id"] == out["bot"]["id"]
    assert len(client.get("/api/bases", headers=headers).json()) == 2
    actions = [i["action"] for i in client.get("/api/audit?action=base.sample", headers=headers).json()["items"]]
    assert actions == ["base.sample", "base.sample"]


def test_sample_base_cli(client, capsys):
    from nexo import cli
    login(client)
    cli.main(["base-de-teste"])
    out = capsys.readouterr().out
    assert "Indexando 6 arquivo(s)" in out and out.count(": ok") == 6
    cli.main(["base-de-teste"])
    assert "já existe" in capsys.readouterr().out
