from __future__ import annotations

import json
from types import SimpleNamespace

from tests.conftest import login, upload


class FakeLLM:
    def __init__(self, pieces: list[str]):
        self.pieces = pieces

    def complete(self, prompt: str):
        return SimpleNamespace(text="".join(self.pieces))

    def stream_complete(self, prompt: str):
        for piece in self.pieces:
            yield SimpleNamespace(delta=piece)


def events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        name, data = "", ""
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = line[6:]
        out.append((name, json.loads(data)))
    return out


def use_llm(pieces: list[str]) -> None:
    from nexo.config import get_settings
    from nexo.rag.engine import get_engine
    engine = get_engine(get_settings())
    engine._llm = FakeLLM(pieces)
    engine._llm_loaded = True


def test_stream_extractive_answer_is_saved(client):
    headers = login(client)
    upload(client, headers)
    conv = client.post("/api/conversations", headers=headers, json={}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages/stream", headers=headers,
                    json={"content": "O que acontece se a atualização de firmware falhar?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    got = events(r.text)
    assert got[0] == ("status", {"stage": "searching"})
    name, done = got[-1]
    assert name == "done"
    assert done["answer"]["answered"] is True
    assert "modo de recuperação" in done["answer"]["content"]
    assert done["conversation"]["messages"] == 2
    full = client.get(f"/api/conversations/{conv['id']}", headers=headers).json()
    assert [m["role"] for m in full["items"]] == ["user", "assistant"]


def test_stream_sends_deltas_from_llm(client):
    headers = login(client)
    upload(client, headers)
    use_llm(["O roteador entra ", "no modo de recuperação ", "[1]."])
    conv = client.post("/api/conversations", headers=headers, json={}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages/stream", headers=headers,
                    json={"content": "O que acontece se a atualização de firmware falhar?"})
    got = events(r.text)
    deltas = [d["text"] for n, d in got if n == "delta"]
    assert deltas == ["O roteador entra ", "no modo de recuperação ", "[1]."]
    assert ("status", {"stage": "writing"}) in got
    done = got[-1][1]
    assert done["answer"]["content"] == "O roteador entra no modo de recuperação [1]."
    assert done["answer"]["sources"]


def test_stream_not_found_uses_fallback_and_drops_sources(client):
    headers = login(client)
    upload(client, headers)
    use_llm(["Não encontrei essa informação nos documentos selecionados."])
    conv = client.post("/api/conversations", headers=headers, json={}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages/stream", headers=headers,
                    json={"content": "Qual a temperatura de operação do roteador?"})
    done = events(r.text)[-1][1]
    assert done["answer"]["answered"] is False
    assert done["answer"]["sources"] == []


def test_stream_validates_before_streaming(client):
    headers = login(client)
    conv = client.post("/api/conversations", headers=headers, json={}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages/stream", headers=headers, json={"content": "Oi?"})
    assert r.status_code == 409
    assert r.json()["code"] == "NO_DOCUMENTS"
    upload(client, headers)
    r = client.post(f"/api/conversations/{conv['id']}/messages/stream", headers=headers, json={"content": "   "})
    assert r.status_code == 400
    r = client.post("/api/conversations/inexistente/messages/stream", headers=headers, json={"content": "Oi?"})
    assert r.status_code == 404


def test_stream_reports_llm_errors(client):
    headers = login(client)
    upload(client, headers)

    class Broken(FakeLLM):
        def stream_complete(self, prompt: str):
            yield SimpleNamespace(delta="Começo")
            raise RuntimeError("conexão perdida")

    from nexo.config import get_settings
    from nexo.rag.engine import get_engine
    engine = get_engine(get_settings())
    engine._llm = Broken([])
    engine._llm_loaded = True
    conv = client.post("/api/conversations", headers=headers, json={}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages/stream", headers=headers,
                    json={"content": "O que acontece se a atualização de firmware falhar?"})
    name, data = events(r.text)[-1]
    assert name == "error"
    assert data["code"] == "LLM_FAILURE"
    full = client.get(f"/api/conversations/{conv['id']}", headers=headers).json()
    assert full["items"] == []


def test_regenerate_replaces_answer_in_place(client):
    headers = login(client)
    upload(client, headers)
    conv = client.post("/api/conversations", headers=headers, json={}).json()
    first = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers,
                        json={"content": "O que acontece se a atualização de firmware falhar?"}).json()["answer"]
    client.post(f"/api/messages/{first['id']}/feedback", headers=headers, json={"rating": -1})
    use_llm(["Nova resposta sobre o modo de recuperação [1]."])
    r = client.post(f"/api/messages/{first['id']}/regenerate", headers=headers)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["id"] == first["id"]
    assert out["content"] == "Nova resposta sobre o modo de recuperação [1]."
    assert out["my_rating"] is None
    full = client.get(f"/api/conversations/{conv['id']}", headers=headers).json()
    assert len(full["items"]) == 2
    assert full["items"][1]["content"] == out["content"]


def test_regenerate_rejects_other_users_and_questions(client):
    headers = login(client)
    upload(client, headers)
    conv = client.post("/api/conversations", headers=headers, json={}).json()
    exchange = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers,
                           json={"content": "Qual a temperatura de operação?"}).json()
    r = client.post(f"/api/messages/{exchange['question']['id']}/regenerate", headers=headers)
    assert r.status_code == 404
    other = client.post("/api/auth/register", json={"name": "Outra Pessoa", "username": "outra",
                                                    "password": "senha-forte-1"}).json()
    r = client.post(f"/api/messages/{exchange['answer']['id']}/regenerate",
                    headers={"Authorization": f"Bearer {other['token']}"})
    assert r.status_code == 404
