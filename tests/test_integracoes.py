import hashlib
import hmac
import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from sqlalchemy import func, select

from tests.conftest import login, upload
from tests.test_engine import make_engine

QUESTION = "O que acontece se a atualização de firmware falhar?"
OFF_TOPIC = "Quem venceu a copa do mundo de futebol?"
TITLE = "Manual do Roteador Fictício RX-200"


def register(client, username: str, password: str = "senhaForte1") -> dict:
    r = client.post("/api/auth/register", json={"name": f"Pessoa {username}", "username": username,
                                                "password": password})
    assert r.status_code == 201, r.text
    return login(client, username, password)


def new_conversation(client, headers: dict, document_ids: list[str] | None = None) -> dict:
    r = client.post("/api/conversations", headers=headers, json={"document_ids": document_ids or []})
    assert r.status_code == 201, r.text
    return r.json()


def ask(client, headers: dict, conversation_id: str, question: str) -> dict:
    r = client.post(f"/api/conversations/{conversation_id}/messages", headers=headers, json={"content": question})
    assert r.status_code == 200, r.text
    return r.json()["answer"]


def new_key(client, headers: dict, name: str = "Integração") -> dict:
    r = client.post("/api/keys", headers=headers, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def receiver():
    received: list[dict] = []
    reply = {"status": 200}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            received.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                             "body": body})
            self.send_response(reply["status"])
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"url": f"http://127.0.0.1:{server.server_port}/gancho", "received": received, "reply": reply}
    finally:
        server.shutdown()
        server.server_close()


def events(receiver, name: str) -> list[dict]:
    from nexo import webhooks
    webhooks.wait_idle()
    out = [json.loads(r["body"]) for r in receiver["received"]]
    return [e for e in out if e["event"] == name]


def test_search_returns_excerpts_without_calling_the_llm(client, monkeypatch):
    headers = login(client)
    r = client.post("/api/search", headers=headers, json={"query": "firmware"})
    assert r.status_code == 409
    assert r.json()["code"] == "NO_DOCUMENTS"
    doc = upload(client, headers)

    from nexo.rag.engine import RagEngine

    def no_llm(self):
        raise AssertionError("A busca não pode chamar o LLM.")

    monkeypatch.setattr(RagEngine, "llm", no_llm)
    r = client.post("/api/search", headers=headers,
                    json={"query": "  firmware falhar modo de recuperação ", "limit": 3})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["query"] == "firmware falhar modo de recuperação"
    assert isinstance(out["took_ms"], int)
    assert 1 <= len(out["results"]) <= 3
    first = out["results"][0]
    assert set(first) == {"rank", "document_id", "document_title", "page", "similarity", "rerank_score", "excerpt"}
    assert (first["rank"], first["page"], first["document_id"]) == (1, 4, doc["id"])
    assert first["document_title"] == TITLE
    assert "recuperação" in first["excerpt"]
    assert [x["rank"] for x in out["results"]] == list(range(1, len(out["results"]) + 1))

    r = client.post("/api/search", headers=headers,
                    json={"query": "firmware", "document_ids": [doc["id"]], "rerank": False, "limit": 1})
    assert len(r.json()["results"]) == 1
    r = client.post("/api/search", headers=headers, json={"query": "firmware", "document_ids": ["nao-existe"]})
    assert r.json()["code"] == "UNKNOWN_DOCUMENT"
    assert client.post("/api/search", headers=headers, json={"query": "firmware", "limit": 21}).status_code == 422
    assert client.post("/api/search", headers=headers, json={"query": ""}).status_code == 422
    assert client.post("/api/search", headers=headers, json={"query": "   "}).status_code == 400
    assert client.post("/api/search", json={"query": "firmware"}).status_code == 401


def test_retrieve_limit_replaces_top_n(tmp_path):
    e = make_engine(tmp_path, top_n=1)
    question = "roteador firmware temperatura reset botão porta rede"
    assert len(e.retrieve(question, None)) == 1
    assert len(e.retrieve(question, None, limit=5)) > 1
    sources = e.search(question, None, limit=2)
    assert [s.rank for s in sources] == [1, 2]


def test_export_markdown_and_json(client):
    headers = login(client)
    doc = upload(client, headers)
    conv = new_conversation(client, headers, [doc["id"]])
    ask(client, headers, conv["id"], QUESTION)
    ask(client, headers, conv["id"], OFF_TOPIC)

    r = client.get(f"/api/conversations/{conv['id']}/export", headers=headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "text/markdown; charset=utf-8"
    assert r.headers["content-disposition"] == \
        'attachment; filename="nexo-o-que-acontece-se-a-atualizacao-de-firmware-falhar.md"'
    md = r.text
    assert md.startswith(f"# {QUESTION}\n")
    assert f"- Escopo: {TITLE}" in md
    assert "- Data: " in md
    assert f"## {QUESTION}" in md and f"## {OFF_TOPIC}" in md
    assert md.count("**Fontes**") == 1
    assert f"- [1] {TITLE}, página 4" in md
    assert "modo de recuperação" in md

    r = client.get(f"/api/conversations/{conv['id']}/export", headers=headers, params={"format": "json"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    assert r.headers["content-disposition"] == \
        'attachment; filename="nexo-o-que-acontece-se-a-atualizacao-de-firmware-falhar.json"'
    data = r.json()
    assert data["exported_at"]
    full = client.get(f"/api/conversations/{conv['id']}", headers=headers).json()
    assert {k: v for k, v in data.items() if k != "exported_at"} == full

    assert client.get(f"/api/conversations/{conv['id']}/export", headers=headers,
                      params={"format": "pdf"}).status_code == 422
    other = register(client, "outra")
    assert client.get(f"/api/conversations/{conv['id']}/export", headers=other).status_code == 404


def test_export_slug_falls_back_for_titles_without_letters(client):
    headers = login(client)
    conv = client.post("/api/conversations", headers=headers, json={"title": "???"}).json()
    r = client.get(f"/api/conversations/{conv['id']}/export", headers=headers)
    assert r.headers["content-disposition"] == 'attachment; filename="nexo-conversa.md"'


def test_metrics_admin_sees_all_and_user_only_own(client):
    admin = login(client)
    doc = upload(client, admin)
    conv = new_conversation(client, admin)
    good = ask(client, admin, conv["id"], QUESTION)
    ask(client, admin, conv["id"], OFF_TOPIC)
    client.post(f"/api/messages/{good['id']}/feedback", headers=admin, json={"rating": -1})
    maria = register(client, "maria")
    conv2 = new_conversation(client, maria)
    other = ask(client, maria, conv2["id"], QUESTION)
    client.post(f"/api/messages/{other['id']}/feedback", headers=maria, json={"rating": 1})

    r = client.get("/api/metrics", headers=admin)
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["scope"] == "all" and m["period_days"] == 30
    assert (m["questions"], m["answered"], m["unanswered"]) == (3, 2, 1)
    assert m["answer_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert m["conversations"] == 2
    assert m["feedback"] == {"up": 1, "down": 1}
    assert isinstance(m["avg_latency_ms"], int) and isinstance(m["p95_latency_ms"], int)
    assert m["p95_latency_ms"] >= m["avg_latency_ms"]
    assert len(m["daily"]) == 30
    today = datetime.now(UTC).date().isoformat()
    assert m["daily"][-1] == {"date": today, "questions": 3, "unanswered": 1}
    assert m["daily"][0]["date"] < m["daily"][-1]["date"]
    assert sum(d["questions"] for d in m["daily"]) == 3
    assert m["top_documents"][0]["document_id"] == doc["id"]
    assert m["top_documents"][0]["title"] == TITLE
    assert m["top_documents"][0]["citations"] >= 2
    assert len(m["top_documents"]) <= 6
    assert [(u["question"], u["conversation_id"]) for u in m["unanswered_recent"]] == [(OFF_TOPIC, conv["id"])]
    assert m["unanswered_recent"][0]["asked_at"].startswith(today)
    [neg] = m["negative_recent"]
    assert neg["message_id"] == good["id"]
    assert (neg["question"], neg["answer"], neg["conversation_id"]) == (QUESTION, good["content"], conv["id"])

    mine = client.get("/api/metrics", headers=maria, params={"days": 7}).json()
    assert mine["scope"] == "mine" and mine["period_days"] == 7
    assert (mine["questions"], mine["answered"], mine["unanswered"]) == (1, 1, 0)
    assert mine["answer_rate"] == 1.0
    assert mine["conversations"] == 1
    assert mine["feedback"] == {"up": 1, "down": 0}
    assert len(mine["daily"]) == 7
    assert mine["unanswered_recent"] == [] and mine["negative_recent"] == []

    empty = client.get("/api/metrics", headers=register(client, "vazio"), params={"days": 1}).json()
    assert (empty["questions"], empty["answer_rate"], empty["avg_latency_ms"], empty["p95_latency_ms"]) == \
        (0, None, None, None)
    assert empty["daily"] == [{"date": today, "questions": 0, "unanswered": 0}]
    assert empty["top_documents"] == []
    assert client.get("/api/metrics", headers=admin, params={"days": 0}).status_code == 422
    assert client.get("/api/metrics", headers=admin, params={"days": 366}).status_code == 422


def test_api_keys_create_authenticate_and_revoke(client):
    admin = login(client)
    created = new_key(client, admin, "  Planilha   de leads ")
    key = created["key"]
    assert key.startswith("nxk_") and len(key) == 47
    assert created["prefix"] == key[:12]
    assert created["name"] == "Planilha de leads"
    assert created["last_used_at"] is None
    assert client.get("/api/keys", headers=admin).json() == [{k: v for k, v in created.items() if k != "key"}]

    from nexo import db
    with db.session() as s:
        row = s.get(db.ApiKeyRow, created["id"])
        assert row.key_hash == hashlib.sha256(key.encode()).hexdigest()
        assert key not in (row.key_hash, row.prefix, row.name)

    me = client.get("/api/auth/me", headers={"X-API-Key": key})
    assert me.status_code == 200 and me.json()["username"] == "admin"
    assert client.get("/api/documents", headers={"Authorization": f"Bearer {key}"}).status_code == 200
    assert client.get("/api/keys", headers=admin).json()[0]["last_used_at"] is not None
    status = client.get("/api/system/status", headers={"X-API-Key": key}).json()
    assert status["integrations"] == {"api_keys": 1, "webhooks": 0}

    maria = register(client, "maria")
    assert client.get("/api/keys", headers=maria).json() == []
    assert client.get("/api/system/status", headers=maria).json()["integrations"] == {"api_keys": 0, "webhooks": None}
    assert client.delete(f"/api/keys/{created['id']}", headers=maria).status_code == 404
    r = client.get("/api/auth/me", headers={"X-API-Key": "nxk_invalida"})
    assert r.status_code == 401 and r.json()["code"] == "INVALID_API_KEY"
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer nxk_invalida"}).status_code == 401

    assert client.delete(f"/api/keys/{created['id']}", headers=admin).status_code == 204
    assert client.get("/api/auth/me", headers={"X-API-Key": key}).status_code == 401
    assert client.get("/api/keys", headers=admin).json() == []
    assert client.post("/api/keys", headers=admin, json={"name": ""}).status_code == 422
    assert client.post("/api/keys", headers=admin, json={"name": "x" * 81}).status_code == 422
    assert client.post("/api/keys", headers=admin, json={"name": "   "}).status_code == 400


def test_api_key_stops_working_when_owner_is_removed(client):
    maria = register(client, "maria")
    key = new_key(client, maria)["key"]
    assert client.get("/api/auth/me", headers={"X-API-Key": key}).status_code == 200
    from nexo.api.deps import get_users
    get_users().delete("maria")
    r = client.get("/api/auth/me", headers={"X-API-Key": key})
    assert r.status_code == 401
    assert r.json()["code"] == "UNAUTHENTICATED"


def test_ask_without_and_with_conversation(client):
    admin = login(client)
    r = client.post("/api/ask", headers=admin, json={"question": QUESTION})
    assert r.status_code == 409 and r.json()["code"] == "NO_DOCUMENTS"
    doc = upload(client, admin)
    api = {"X-API-Key": new_key(client, admin)["key"]}

    r = client.post("/api/ask", headers=api, json={"question": QUESTION, "document_ids": [doc["id"]]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert set(out) == {"answer", "answered", "grounded", "model", "latency_ms", "conversation_id", "sources"}
    assert out["answered"] is True and out["conversation_id"] is None
    assert "modo de recuperação" in out["answer"]
    assert out["model"] == "extrativo"
    assert isinstance(out["latency_ms"], int)
    assert out["sources"][0]["page"] == 4 and out["sources"][0]["document_id"] == doc["id"]
    assert client.get("/api/conversations", headers=admin).json() == []
    from nexo import db
    with db.session() as s:
        assert s.scalar(select(func.count()).select_from(db.MessageRow)) == 0

    conv = new_conversation(client, admin)
    r = client.post("/api/ask", headers=api, json={"question": QUESTION, "conversation_id": conv["id"]})
    first = r.json()
    assert first["conversation_id"] == conv["id"] and first["answered"] is True
    r = client.post("/api/ask", headers=api, json={"question": OFF_TOPIC, "conversation_id": conv["id"]})
    assert r.json()["answered"] is False and r.json()["sources"] == []
    full = client.get(f"/api/conversations/{conv['id']}", headers=admin).json()
    assert [m["role"] for m in full["items"]] == ["user", "assistant", "user", "assistant"]
    assert full["title"] == QUESTION
    assert full["items"][1]["content"] == first["answer"]
    assert full["items"][1]["sources"] == first["sources"]

    maria = register(client, "maria")
    r = client.post("/api/ask", headers=maria, json={"question": QUESTION, "conversation_id": conv["id"]})
    assert r.status_code == 404
    r = client.post("/api/ask", headers=admin, json={"question": QUESTION, "document_ids": ["nao-existe"]})
    assert r.json()["code"] == "UNKNOWN_DOCUMENT"
    assert client.post("/api/ask", headers=admin, json={"question": "  "}).status_code == 400
    assert client.post("/api/ask", headers=admin, json={"question": ""}).status_code == 422


def test_webhooks_are_admin_only_and_validate_input(client, receiver):
    admin = login(client)
    user = register(client, "maria")
    body = {"url": receiver["url"], "events": ["document.ready"]}
    for r in (client.get("/api/webhooks", headers=user), client.post("/api/webhooks", headers=user, json=body)):
        assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"

    r = client.post("/api/webhooks", headers=admin, json={**body, "url": "ftp://exemplo.com/x"})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_URL" and "url" in r.json()["fields"]
    r = client.post("/api/webhooks", headers=admin, json={**body, "events": []})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_EVENTS"
    r = client.post("/api/webhooks", headers=admin, json={**body, "events": ["document.ready", "nada"]})
    assert r.json()["code"] == "INVALID_EVENTS"

    r = client.post("/api/webhooks", headers=admin,
                    json={**body, "events": ["feedback.negative", "document.ready", "document.ready"]})
    assert r.status_code == 201, r.text
    hook = r.json()
    assert hook["events"] == ["document.ready", "feedback.negative"]
    assert len(hook["secret"]) == 32
    assert hook["active"] is True and hook["last_status"] is None and hook["last_delivery_at"] is None
    [listed] = client.get("/api/webhooks", headers=admin).json()
    assert listed == {k: v for k, v in hook.items() if k != "secret"}

    path = f"/api/webhooks/{hook['id']}"
    assert client.patch(path, headers=user, json={"active": False}).status_code == 403
    assert client.post(f"{path}/test", headers=user).status_code == 403
    assert client.delete(path, headers=user).status_code == 403
    r = client.patch(path, headers=admin, json={"active": False})
    assert r.status_code == 200 and r.json()["active"] is False
    assert client.get("/api/system/status", headers=admin).json()["integrations"] == {"api_keys": 0, "webhooks": 1}
    assert client.get("/api/system/status", headers=user).json()["integrations"]["webhooks"] is None
    assert client.delete(path, headers=admin).status_code == 204
    assert client.get("/api/webhooks", headers=admin).json() == []
    assert client.delete(path, headers=admin).status_code == 404


def test_webhook_test_delivery_is_signed(client, receiver):
    from nexo import __version__
    admin = login(client)
    hook = client.post("/api/webhooks", headers=admin, json={"url": receiver["url"], "events": ["question.unanswered"],
                                                             "secret": "segredo-do-gancho"}).json()
    assert hook["secret"] == "segredo-do-gancho"
    r = client.post(f"/api/webhooks/{hook['id']}/test", headers=admin)
    assert r.status_code == 200
    assert r.json() == {"status": 200, "error": None}

    [req] = receiver["received"]
    assert req["path"] == "/gancho"
    expected = "sha256=" + hmac.new(b"segredo-do-gancho", req["body"], hashlib.sha256).hexdigest()
    assert req["headers"]["x-nexo-signature"] == expected
    assert req["headers"]["x-nexo-event"] == "ping"
    assert req["headers"]["content-type"] == "application/json"
    assert req["headers"]["user-agent"] == f"Nexo/{__version__}"
    payload = json.loads(req["body"])
    assert set(payload) == {"event", "created_at", "data"}
    assert payload["event"] == "ping" and payload["data"]["webhook_id"] == hook["id"]
    [listed] = client.get("/api/webhooks", headers=admin).json()
    assert listed["last_status"] == 200 and listed["last_error"] is None and listed["last_delivery_at"]

    receiver["reply"]["status"] = 500
    r = client.post(f"/api/webhooks/{hook['id']}/test", headers=admin).json()
    assert r["status"] == 500 and "500" in r["error"]
    [listed] = client.get("/api/webhooks", headers=admin).json()
    assert listed["last_status"] == 500 and listed["last_error"]

    dead = client.post("/api/webhooks", headers=admin,
                       json={"url": "http://127.0.0.1:1/x", "events": ["document.ready"]}).json()
    r = client.post(f"/api/webhooks/{dead['id']}/test", headers=admin).json()
    assert r["status"] is None and r["error"]


def test_webhook_events_are_fired(client, receiver):
    from nexo import jobs, webhooks
    admin = login(client)
    hook = client.post("/api/webhooks", headers=admin,
                       json={"url": receiver["url"], "events": list(webhooks.EVENTS), "secret": "s3gredo"}).json()

    doc = upload(client, admin)
    [ready] = events(receiver, "document.ready")
    assert ready["data"]["id"] == doc["id"] and ready["data"]["title"] == TITLE
    assert ready["data"]["pages"] == 5 and ready["data"]["chunks"] >= 5
    r = client.post("/api/documents", headers=admin,
                    files=[("files", ("quebrado.pdf", b"%PDF-1.4\nnada aqui\n", "application/pdf"))])
    assert r.status_code == 201
    jobs.wait_idle()
    [failed] = events(receiver, "document.failed")
    assert failed["data"]["id"] == r.json()[0]["id"] and failed["data"]["error"]

    conv = new_conversation(client, admin)
    good = ask(client, admin, conv["id"], QUESTION)
    assert events(receiver, "question.unanswered") == []
    ask(client, admin, conv["id"], OFF_TOPIC)
    client.post("/api/ask", headers=admin, json={"question": OFF_TOPIC})
    unanswered = events(receiver, "question.unanswered")
    assert sorted((e["data"]["conversation_id"] or "") for e in unanswered) == ["", conv["id"]]
    assert all(e["data"]["question"] == OFF_TOPIC and e["data"]["username"] == "admin" for e in unanswered)

    client.post(f"/api/messages/{good['id']}/feedback", headers=admin, json={"rating": -1})
    client.post(f"/api/messages/{good['id']}/feedback", headers=admin, json={"rating": -1, "comment": "Incompleta"})
    [negative] = events(receiver, "feedback.negative")
    assert negative["data"] == {"message_id": good["id"], "question": QUESTION, "answer": good["content"],
                                "username": "admin"}

    for req in receiver["received"]:
        assert req["headers"]["x-nexo-signature"] == \
            "sha256=" + hmac.new(b"s3gredo", req["body"], hashlib.sha256).hexdigest()
        assert req["headers"]["x-nexo-event"] == json.loads(req["body"])["event"]

    client.patch(f"/api/webhooks/{hook['id']}", headers=admin, json={"active": False})
    ask(client, admin, conv["id"], OFF_TOPIC)
    assert len(events(receiver, "question.unanswered")) == 2


def test_account_management(client):
    from nexo.api.deps import get_users
    from nexo.users import UserError
    admin = login(client)
    maria = register(client, "maria")
    r = client.get("/api/users", headers=maria)
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"
    listed = client.get("/api/users", headers=admin).json()
    assert [u["username"] for u in listed] == ["admin", "maria"]
    assert set(listed[0]) == {"username", "name", "role", "created_at", "last_login_at"}
    assert client.patch("/api/users/maria", headers=maria, json={"role": "admin"}).status_code == 403

    r = client.patch("/api/users/admin", headers=admin, json={"role": "user"})
    assert r.status_code == 400 and r.json()["code"] == "LAST_ADMIN"
    r = client.patch("/api/users/maria", headers=admin, json={"role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "admin" and r.json()["username"] == "maria"
    assert client.get("/api/users", headers=maria).status_code == 200
    r = client.patch("/api/users/admin", headers=admin, json={"role": "user"})
    assert r.status_code == 400 and r.json()["code"] == "SELF"
    assert client.patch("/api/users/maria", headers=admin, json={"role": "chefe"}).status_code == 422
    assert client.patch("/api/users/ninguem", headers=admin, json={"role": "admin"}).status_code == 404

    assert client.patch("/api/users/admin", headers=maria, json={"role": "user"}).json()["role"] == "user"
    assert client.get("/api/users", headers=admin).status_code == 403
    r = client.patch("/api/users/maria", headers=maria, json={"role": "user"})
    assert r.status_code == 400 and r.json()["code"] == "LAST_ADMIN"
    with pytest.raises(UserError) as e:
        get_users().set_role("maria", "user")
    assert e.value.code == "LAST_ADMIN"
    assert client.patch("/api/users/admin", headers=maria, json={"role": "admin"}).status_code == 200

    r = client.delete("/api/users/admin", headers=admin)
    assert r.status_code == 400 and r.json()["code"] == "SELF"
    joao = register(client, "joao")
    key = new_key(client, joao)["key"]
    new_conversation(client, joao)
    assert client.delete("/api/users/joao", headers=joao).status_code == 403
    assert client.delete("/api/users/joao", headers=admin).status_code == 204
    assert [u["username"] for u in client.get("/api/users", headers=admin).json()] == ["admin", "maria"]
    assert client.get("/api/auth/me", headers=joao).status_code == 401
    assert client.get("/api/auth/me", headers={"X-API-Key": key}).status_code == 401
    assert client.delete("/api/users/joao", headers=admin).status_code == 404
    assert client.get("/api/conversations", headers=register(client, "joao")).json() == []

    assert client.delete("/api/users/admin", headers=maria).status_code == 204
    from nexo.config import get_settings
    from nexo.users import UserStore
    assert UserStore(get_settings().users_file).get("admin") is None
