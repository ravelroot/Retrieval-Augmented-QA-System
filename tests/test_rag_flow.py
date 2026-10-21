from tests.conftest import FIXTURES, login, upload


def test_upload_index_and_answer_with_sources(client):
    headers = login(client)
    doc = upload(client, headers)
    docs = client.get("/api/documents", headers=headers).json()
    assert docs[0]["status"] == "READY", docs[0]["error"]
    assert docs[0]["pages"] == 5
    assert docs[0]["chunks"] >= 5
    assert docs[0]["title"] == "Manual do Roteador Fictício RX-200"

    conv = client.post("/api/conversations", headers=headers, json={"document_ids": [doc["id"]]}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers,
                    json={"content": "O que acontece se a atualização de firmware falhar?"})
    assert r.status_code == 200, r.text
    answer = r.json()["answer"]
    assert answer["answered"] is True
    assert "modo de recuperação" in answer["content"]
    assert answer["sources"][0]["page"] == 4
    assert answer["sources"][0]["document_id"] == doc["id"]
    assert r.json()["conversation"]["title"].startswith("O que acontece")

    r = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers,
                    json={"content": "Quem venceu a copa do mundo de futebol?"})
    out = r.json()["answer"]
    assert out["answered"] is False
    assert out["sources"] == []

    full = client.get(f"/api/conversations/{conv['id']}", headers=headers).json()
    assert [m["role"] for m in full["items"]] == ["user", "assistant", "user", "assistant"]


def test_feedback_and_conversation_isolation(client):
    headers = login(client)
    upload(client, headers)
    conv = client.post("/api/conversations", headers=headers, json={}).json()
    ans = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers,
                      json={"content": "Qual a temperatura de operação?"}).json()["answer"]
    r = client.post(f"/api/messages/{ans['id']}/feedback", headers=headers, json={"rating": 1})
    assert r.json()["my_rating"] == 1
    r = client.post(f"/api/messages/{ans['id']}/feedback", headers=headers, json={"rating": 0})
    assert r.json()["my_rating"] is None

    client.post("/api/auth/register", json={"name": "Outra Pessoa", "username": "outra", "password": "senhaForte1"})
    other = login(client, "outra", "senhaForte1")
    assert client.get(f"/api/conversations/{conv['id']}", headers=other).status_code == 404
    assert client.get("/api/conversations", headers=other).json() == []


def test_rejects_invalid_and_duplicate_files(client):
    headers = login(client)
    r = client.post("/api/documents", headers=headers, files=[("files", ("x.pdf", b"nao sou pdf", "application/pdf"))])
    assert r.status_code == 415
    upload(client, headers)
    data = (FIXTURES / "manual-exemplo.pdf").read_bytes()
    r = client.post("/api/documents", headers=headers, files=[("files", ("copia.pdf", data, "application/pdf"))])
    assert r.status_code == 409


def test_delete_document_removes_vectors_and_permissions(client):
    headers = login(client)
    doc = upload(client, headers)
    client.post("/api/auth/register", json={"name": "Leitor", "username": "leitor", "password": "senhaForte1"})
    reader = login(client, "leitor", "senhaForte1")
    assert client.delete(f"/api/documents/{doc['id']}", headers=reader).status_code == 403
    assert client.delete(f"/api/documents/{doc['id']}", headers=headers).status_code == 204
    from nexo.config import get_settings
    from nexo.rag.engine import get_engine
    assert get_engine(get_settings()).count() == 0
    assert client.get("/api/documents", headers=headers).json() == []


def test_question_without_documents_is_blocked(client):
    headers = login(client)
    conv = client.post("/api/conversations", headers=headers, json={}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers, json={"content": "Olá?"})
    assert r.status_code == 409
    assert r.json()["code"] == "NO_DOCUMENTS"
