import hashlib
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.conftest import login
from tests.test_agentes import FAQ, new_base, wait


@pytest.fixture()
def fake_api():
    calls: list[dict] = []
    state = {"connection": "open"}

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, payload, status=200):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            calls.append({"method": "POST", "path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                          "body": body})
            if self.path.endswith("/messages"):
                self._reply({"messaging_product": "whatsapp", "messages": [{"id": f"wamid.{len(calls)}"}]})
            elif "/message/sendText/" in self.path:
                self._reply({"key": {"id": f"BAE{len(calls)}", "fromMe": True}, "status": "PENDING"}, 201)
            else:
                self._reply({"webhook": {"instanceName": "loja"}}, 201)

        def do_GET(self):
            calls.append({"method": "GET", "path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}})
            if "/instance/connectionState/" in self.path:
                self._reply({"instance": {"instanceName": "loja", "state": state["connection"]}})
            elif "/instance/connect/" in self.path:
                self._reply({"pairingCode": "WZYEH1YY", "code": "2@abc", "base64": "data:image/png;base64,AAAA"})
            else:
                self._reply({"display_phone_number": "+55 21 4000-0000", "verified_name": "Loja Aurora"})

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"url": f"http://127.0.0.1:{server.server_port}", "calls": calls, "state": state}
    finally:
        server.shutdown()
        server.server_close()


def setup_bot(client, headers):
    base = new_base(client, headers)
    client.post(f"/api/bases/{base['id']}/texts", headers=headers, json={"title": "Trocas", "content": FAQ})
    wait()
    return client.post("/api/bots", headers=headers, json={
        "name": "Aurora", "base_id": base["id"], "greeting": "Olá! Sou a Aurora.",
        "fallback": "Não encontrei isso nas políticas da loja."}).json()


def settle():
    from nexo import webhooks, whatsapp
    whatsapp.wait_idle()
    webhooks.wait_idle()


def test_simulator_auto_reply_handoff_and_human_takeover(client):
    headers = login(client)
    bot = setup_bot(client, headers)
    r = client.post("/api/whatsapp/channels", headers=headers, json={"name": "Loja", "provider": "simulador",
                                                                    "bot_id": bot["id"]})
    assert r.status_code == 201, r.text
    channel = r.json()
    assert channel["bot_name"] == "Aurora" and "?token=" in channel["webhook_path"]
    assert client.get(f"/api/whatsapp/channels/{channel['id']}/status", headers=headers).json()["state"] == "open"

    r = client.post(f"/api/whatsapp/channels/{channel['id']}/simulate", headers=headers,
                    json={"phone": "(21) 99999-1234", "name": "Ana", "text": "Posso trocar um produto com a nota fiscal?"})
    assert r.status_code == 202
    contact_id = r.json()["contact_id"]
    settle()
    assert client.get("/api/whatsapp/contacts?filter=unread", headers=headers).json()[0]["unread"] == 1
    detail = client.get(f"/api/whatsapp/contacts/{contact_id}", headers=headers).json()
    assert detail["phone"] == "21999991234" and detail["name"] == "Ana"
    assert [m["direction"] for m in detail["messages"]] == ["in", "out"]
    reply = detail["messages"][1]
    assert reply["author"] == "agente" and reply["answered"] is True and "30 dias" in reply["body"]
    assert "Fontes:" in reply["body"] and reply["sources"][0]["kind"] == "note"
    assert client.get("/api/whatsapp/contacts?filter=unread", headers=headers).json() == []

    client.post(f"/api/whatsapp/channels/{channel['id']}/simulate", headers=headers,
                json={"phone": "21999991234", "text": "Quero falar com um atendente"})
    settle()
    contact = client.get(f"/api/whatsapp/contacts?filter=waiting", headers=headers).json()
    assert len(contact) == 1 and contact[0]["needs_human"] is True and contact[0]["bot_enabled"] is False
    client.post(f"/api/whatsapp/channels/{channel['id']}/simulate", headers=headers,
                json={"phone": "21999991234", "text": "Alguém aí?"})
    settle()
    detail = client.get(f"/api/whatsapp/contacts/{contact_id}", headers=headers).json()
    assert detail["messages"][-1]["direction"] == "in"

    suggestion = client.post(f"/api/whatsapp/contacts/{contact_id}/suggest", headers=headers)
    assert suggestion.status_code == 200 and suggestion.json()["text"]
    r = client.post(f"/api/whatsapp/contacts/{contact_id}/messages", headers=headers,
                    json={"text": "Oi, Ana! Sou o Erik, posso ajudar."})
    assert r.status_code == 201 and r.json()["author"] == "admin" and r.json()["status"] == "sent"
    contact = client.get(f"/api/whatsapp/contacts?filter=human", headers=headers).json()[0]
    assert contact["needs_human"] is False and contact["bot_enabled"] is False

    r = client.patch(f"/api/whatsapp/contacts/{contact_id}", headers=headers, json={"bot_enabled": True})
    assert r.json()["bot_enabled"] is True
    client.post(f"/api/whatsapp/channels/{channel['id']}/simulate", headers=headers,
                json={"phone": "21999991234", "text": "Qual a cor do céu em Marte?"})
    settle()
    detail = client.get(f"/api/whatsapp/contacts/{contact_id}", headers=headers).json()
    assert detail["messages"][-1]["body"] == "Não encontrei isso nas políticas da loja."
    assert detail["needs_human"] is True
    summary = client.get("/api/whatsapp/summary", headers=headers).json()
    assert summary["contacts"] == 1 and summary["waiting"] == 1 and summary["bot_answers_today"] == 3


def test_cloud_webhook_verification_signature_and_send(client, fake_api, monkeypatch):
    from nexo import whatsapp
    monkeypatch.setattr(whatsapp, "GRAPH_URL", fake_api["url"])
    headers = login(client)
    bot = setup_bot(client, headers)
    channel = client.post("/api/whatsapp/channels", headers=headers, json={
        "name": "Oficial", "provider": "cloud", "bot_id": bot["id"], "phone_number_id": "1234567890",
        "access_token": "EAAGtokenSecreto", "app_secret": "segredo-do-app"}).json()
    assert channel["secrets"]["access_token"] == "••••reto" and channel["settings"]["api_version"] == "v24.0"
    assert channel["webhook_path"] == f"/api/whatsapp/webhook/{channel['id']}"
    path = channel["webhook_path"]

    ok = client.get(path, params={"hub.mode": "subscribe", "hub.verify_token": channel["verify_token"],
                                  "hub.challenge": "1158201444"})
    assert ok.status_code == 200 and ok.text == "1158201444"
    assert client.get(path, params={"hub.mode": "subscribe", "hub.verify_token": "errado",
                                    "hub.challenge": "x"}).status_code == 403

    payload = {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": "1234567890"},
        "contacts": [{"profile": {"name": "Bruno"}, "wa_id": "5521988887777"}],
        "messages": [{"from": "5521988887777", "id": "wamid.IN1", "timestamp": "1761868800", "type": "text",
                      "text": {"body": "O frete da primeira troca é gratuito?"}}]}}]}]}
    body = json.dumps(payload).encode()
    assert client.post(path, content=body, headers={"Content-Type": "application/json"}).status_code == 401
    signature = "sha256=" + hmac.new(b"segredo-do-app", body, hashlib.sha256).hexdigest()
    r = client.post(path, content=body, headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature})
    assert r.status_code == 200
    client.post(path, content=body, headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature})
    settle()
    sent = [c for c in fake_api["calls"] if c["method"] == "POST" and c["path"].endswith("/messages")]
    assert len(sent) == 1
    assert sent[0]["path"] == "/v24.0/1234567890/messages"
    assert sent[0]["headers"]["authorization"] == "Bearer EAAGtokenSecreto"
    assert sent[0]["body"]["to"] == "5521988887777" and sent[0]["body"]["type"] == "text"
    assert "gratuito" in sent[0]["body"]["text"]["body"]

    status = {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages", "value": {
        "statuses": [{"id": "wamid.1", "status": "read", "recipient_id": "5521988887777"}]}}]}]}
    body = json.dumps(status).encode()
    signature = "sha256=" + hmac.new(b"segredo-do-app", body, hashlib.sha256).hexdigest()
    client.post(path, content=body, headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature})
    contact = client.get("/api/whatsapp/contacts", headers=headers).json()[0]
    assert contact["name"] == "Bruno"
    detail = client.get(f"/api/whatsapp/contacts/{contact['id']}", headers=headers).json()
    assert detail["messages"][-1]["status"] == "read"
    state = client.get(f"/api/whatsapp/channels/{channel['id']}/status", headers=headers).json()
    assert state["state"] == "open" and "Loja Aurora" in state["detail"]


def test_evolution_qr_webhook_and_phone_messages(client, fake_api):
    headers = login(client)
    bot = setup_bot(client, headers)
    channel = client.post("/api/whatsapp/channels", headers=headers, json={
        "name": "Meu número", "provider": "evolution", "bot_id": bot["id"], "base_url": fake_api["url"],
        "api_key": "chave-evolution", "instance": "loja"}).json()
    fake_api["state"]["connection"] = "close"
    qr = client.get(f"/api/whatsapp/channels/{channel['id']}/qrcode", headers=headers).json()
    assert qr["base64"].startswith("data:image/png;base64,") and qr["pairing_code"] == "WZYEH1YY"
    r = client.post(f"/api/whatsapp/channels/{channel['id']}/webhook", headers=headers,
                    json={"public_url": "https://nexo.exemplo.com.br"})
    assert r.json()["ok"] is True
    registered = [c for c in fake_api["calls"] if c["path"] == "/webhook/set/loja"][0]
    assert registered["headers"]["apikey"] == "chave-evolution"
    assert registered["body"]["events"] == ["MESSAGES_UPSERT"] and registered["body"]["enabled"] is True
    assert registered["body"]["url"] == "https://nexo.exemplo.com.br" + channel["webhook_path"]

    path = channel["webhook_path"]
    event = {"event": "messages.upsert", "instance": "loja", "data": {
        "key": {"remoteJid": "5521977776666@s.whatsapp.net", "fromMe": False, "id": "3EB0AAA"},
        "pushName": "Carla", "message": {"conversation": "Produto com gravação pode ser trocado?"},
        "messageTimestamp": 1761868800}}
    assert client.post(path.split("?")[0], json=event).status_code == 401
    assert client.post(path, json=event).status_code == 200
    group = {"event": "messages.upsert", "data": {"key": {"remoteJid": "1203630@g.us", "fromMe": False, "id": "G1"},
                                                  "message": {"conversation": "oi grupo"}}}
    client.post(path, json=group)
    settle()
    sent = [c for c in fake_api["calls"] if "/message/sendText/loja" in c["path"]]
    assert len(sent) == 1 and sent[0]["body"]["number"] == "5521977776666"
    assert "Fontes:" in sent[0]["body"]["text"]

    mine = {"event": "messages.upsert", "data": {"key": {"remoteJid": "5521977776666@s.whatsapp.net", "fromMe": True,
                                                         "id": "3EB0BBB"},
                                                 "message": {"extendedTextMessage": {"text": "Respondi pelo celular"}}}}
    client.post(path, json=mine)
    contacts = client.get("/api/whatsapp/contacts", headers=headers).json()
    assert len(contacts) == 1 and contacts[0]["name"] == "Carla"
    detail = client.get(f"/api/whatsapp/contacts/{contacts[0]['id']}", headers=headers).json()
    assert detail["messages"][-1]["author"] == "celular"


def test_whatsapp_admin_only_and_webhook_event(client):
    headers = login(client)
    client.post("/api/auth/register", json={"name": "Atendente", "username": "atendente", "password": "senhaForte1"})
    user = login(client, "atendente", "senhaForte1")
    r = client.post("/api/whatsapp/channels", headers=user, json={"name": "X", "provider": "simulador"})
    assert r.status_code == 403
    channel = client.post("/api/whatsapp/channels", headers=headers, json={"name": "X", "provider": "simulador"}).json()
    assert client.get("/api/whatsapp/channels", headers=user).status_code == 200
    r = client.post(f"/api/whatsapp/channels/{channel['id']}/simulate", headers=user,
                    json={"phone": "21912345678", "text": "Olá"})
    assert r.status_code == 202
    detail = client.get(f"/api/whatsapp/contacts/{r.json()['contact_id']}", headers=user).json()
    assert [m["direction"] for m in detail["messages"]] == ["in"]
    r = client.post("/api/webhooks", headers=headers, json={"url": "http://127.0.0.1:9/x",
                                                            "events": ["whatsapp.message", "whatsapp.handoff"]})
    assert r.status_code == 201 and r.json()["events"] == ["whatsapp.message", "whatsapp.handoff"]
