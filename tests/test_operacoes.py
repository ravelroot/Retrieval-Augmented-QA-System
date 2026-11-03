from __future__ import annotations

import csv
import io

from tests.conftest import login, upload


def register(client, username: str) -> dict:
    r = client.post("/api/auth/register", json={"name": f"Pessoa {username}", "username": username,
                                                "password": "senha-forte-1"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def add_text(client, headers, base_id: str, title: str, content: str) -> dict:
    r = client.post(f"/api/bases/{base_id}/texts", headers=headers, json={"title": title, "content": content})
    assert r.status_code == 201, r.text
    return r.json()


def test_bulk_reindex_move_and_delete(client):
    from nexo import jobs
    admin = login(client)
    maria = register(client, "maria")
    base = client.post("/api/bases", headers=admin, json={"name": "Suporte"}).json()
    other = client.post("/api/bases", headers=admin, json={"name": "Vendas"}).json()
    a = add_text(client, admin, base["id"], "Garantia", "A garantia do produto é de doze meses a partir da compra.")
    b = add_text(client, admin, base["id"], "Entrega", "Entregamos em todo o Brasil em até dez dias úteis.")
    c = add_text(client, maria, base["id"], "Trocas", "Trocas podem ser pedidas em até sete dias após a entrega.")
    jobs.wait_idle()

    r = client.post("/api/documents/bulk", headers=maria, json={"action": "reindex", "ids": [a["id"], c["id"], "x"]})
    assert r.status_code == 200
    out = r.json()
    assert out["done"] == [c["id"]]
    assert set(out["skipped"]) == {a["id"], "x"}
    jobs.wait_idle()

    r = client.post("/api/documents/bulk", headers=admin, json={"action": "move", "ids": [a["id"], b["id"]]})
    assert r.status_code == 400 and r.json()["code"] == "NO_BASE"
    r = client.post("/api/documents/bulk", headers=admin,
                    json={"action": "move", "ids": [a["id"], b["id"]], "base_id": other["id"]})
    assert r.json()["done"] == [a["id"], b["id"]]
    moved = client.get(f"/api/bases/{other['id']}/documents", headers=admin).json()
    assert {d["id"] for d in moved} == {a["id"], b["id"]}

    r = client.post("/api/documents/bulk", headers=admin, json={"action": "delete", "ids": [a["id"], c["id"]]})
    assert r.json()["done"] == [a["id"], c["id"]]
    left = {d["id"] for d in client.get("/api/documents", headers=admin).json()}
    assert a["id"] not in left and c["id"] not in left and b["id"] in left
    r = client.post("/api/documents/bulk", headers=admin, json={"action": "delete", "ids": []})
    assert r.status_code == 422


def test_conversation_search_by_content(client):
    headers = login(client)
    upload(client, headers)
    conv = client.post("/api/conversations", headers=headers, json={}).json()
    client.post(f"/api/conversations/{conv['id']}/messages", headers=headers,
                json={"content": "O que acontece se a atualização de firmware falhar?"})
    client.patch(f"/api/conversations/{conv['id']}", headers=headers, json={"title": "Roteador"})
    other = client.post("/api/conversations", headers=headers, json={"title": "Outra"}).json()
    found = client.get("/api/conversations?q=FIRMWARE", headers=headers).json()
    assert [c["id"] for c in found] == [conv["id"]]
    found = client.get("/api/conversations?q=outra", headers=headers).json()
    assert [c["id"] for c in found] == [other["id"]]
    assert len(client.get("/api/conversations?q=", headers=headers).json()) == 2
    assert client.get("/api/conversations?q=%25", headers=headers).json() == []
    assert client.get("/api/conversations?q=_", headers=headers).json() == []
    maria = register(client, "maria")
    assert client.get("/api/conversations?q=firmware", headers=maria).json() == []


def test_metrics_export_csv(client):
    headers = login(client)
    upload(client, headers)
    conv = client.post("/api/conversations", headers=headers, json={}).json()
    first = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers,
                        json={"content": "O que acontece se a atualização de firmware falhar?"}).json()
    client.post(f"/api/conversations/{conv['id']}/messages", headers=headers,
                json={"content": "Quem venceu a copa do mundo de futebol?"})
    client.post(f"/api/messages/{first['answer']['id']}/feedback", headers=headers, json={"rating": 1})
    r = client.get("/api/metrics/export?days=7", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[0][:6] == ["data_utc", "usuario", "conversa", "agente", "pergunta", "respondida"]
    assert len(rows) == 3
    assert rows[1][1] == "admin" and rows[1][5] == "sim" and rows[1][6] == "positiva"
    assert "manual" in rows[1][9].lower() or rows[1][9]
    assert rows[2][5] == "não"
    maria = register(client, "maria")
    rows = list(csv.reader(io.StringIO(client.get("/api/metrics/export", headers=maria).content.decode("utf-8-sig")),
                           delimiter=";"))
    assert len(rows) == 1
