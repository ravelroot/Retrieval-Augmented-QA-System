import io
import json
import sqlite3
import zipfile

from tests.conftest import FIXTURES, login, upload

FAQ = """Política de trocas da Loja Aurora

O cliente pode trocar qualquer produto em até 30 dias corridos após a entrega, com a nota fiscal.

O frete da primeira troca é gratuito. A partir da segunda troca o frete é pago pelo cliente.

Produtos personalizados com gravação não podem ser trocados, exceto em caso de defeito de fabricação."""


def wait():
    from nexo import jobs
    jobs.wait_idle()


def new_base(client, headers, name="Atendimento Aurora"):
    r = client.post("/api/bases", headers=headers, json={"name": name, "description": "Políticas da loja",
                                                         "color": "#2b4c5a"})
    assert r.status_code == 201, r.text
    return r.json()


def docx_bytes(paragraphs: list[str], title: str = "Garantia Aurora") -> bytes:
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{p}</w:t></w:r></w:p>' for p in paragraphs)
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f'<w:body>{body}</w:body></w:document>')
    core = ('<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            f'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{title}</dc:title></cp:coreProperties>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", document)
        z.writestr("docProps/core.xml", core)
    return buffer.getvalue()


def test_default_base_and_formats(client):
    headers = login(client)
    bases = client.get("/api/bases", headers=headers).json()
    assert len(bases) == 1 and bases[0]["is_default"] is True and bases[0]["name"] == "Acervo geral"
    formats = client.get("/api/formats", headers=headers).json()
    assert {"pdf", "docx", "txt", "md", "csv", "json", "html"} <= set(formats["extensions"])
    doc = upload(client, headers)
    assert doc["base_id"] == bases[0]["id"] and doc["kind"] == "pdf"
    assert client.delete(f"/api/bases/{bases[0]['id']}", headers=headers).json()["code"] == "DEFAULT_BASE"


def test_base_with_files_texts_move_and_search(client):
    headers = login(client)
    base = new_base(client, headers)
    files = [
        ("files", ("garantia.docx", docx_bytes(["A garantia dos produtos Aurora é de 12 meses contra defeitos.",
                                                "Para acionar a garantia, envie fotos do defeito ao suporte."]),
                   "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
        ("files", ("precos.csv", "produto;preco;prazo\nCaneca térmica;89,90;5 dias úteis\nGarrafa inox;129,00;7 dias úteis\n"
                   .encode("utf-8"), "text/csv")),
        ("files", ("lojas.json", json.dumps({"lojas": [{"cidade": "Niterói", "horario": "9h às 18h"}]}).encode(),
                   "application/json")),
        ("files", ("entrega.md", "# Entregas\n\nEntregamos em todo o Brasil em até 10 dias úteis.".encode(),
                   "text/markdown")),
        ("files", ("contato.html", b"<html><head><title>Contato</title></head><body><p>Atendimento pelo telefone "
                                   b"0800 000 1234.</p><script>x()</script></body></html>", "text/html")),
    ]
    r = client.post(f"/api/bases/{base['id']}/documents", headers=headers, files=files)
    assert r.status_code == 201, r.text
    created = {d["filename"]: d for d in r.json()}
    assert created["garantia.docx"]["title"] == "Garantia Aurora"
    assert created["entrega.md"]["title"] == "Entregas"
    assert created["contato.html"]["title"] == "Contato"
    r = client.post(f"/api/bases/{base['id']}/texts", headers=headers, json={"title": "Trocas", "content": FAQ})
    assert r.status_code == 201 and r.json()["kind"] == "note"
    note = r.json()
    wait()
    items = client.get(f"/api/bases/{base['id']}/documents", headers=headers).json()
    assert len(items) == 6
    assert all(i["status"] == "READY" for i in items), [(i["filename"], i["error"]) for i in items]
    out = client.get(f"/api/bases/{base['id']}", headers=headers).json()
    assert out["documents"] == 6 and out["notes"] == 1 and out["files"] == 5 and out["chunks"] >= 6

    r = client.post("/api/search", headers=headers, json={"query": "trocar produto com nota fiscal", "base_id": base["id"],
                                                           "rerank": False})
    assert r.status_code == 200, r.text
    first = r.json()["results"][0]
    assert first["document_title"] == "Trocas" and first["kind"] == "note"

    assert client.get(f"/api/documents/{note['id']}/text", headers=headers).json()["content"] == FAQ
    r = client.put(f"/api/documents/{note['id']}/text", headers=headers,
                   json={"title": "Trocas e devoluções", "content": FAQ + "\n\nDevoluções em até 7 dias."})
    assert r.status_code == 200 and r.json()["status"] == "PENDING"
    wait()

    other = new_base(client, headers, "Outra base")
    r = client.patch(f"/api/documents/{created['precos.csv']['id']}", headers=headers, json={"base_id": other["id"]})
    assert r.status_code == 200 and r.json()["base_id"] == other["id"] and r.json()["status"] == "READY"
    r = client.post("/api/search", headers=headers, json={"query": "caneca térmica preço", "base_id": other["id"],
                                                           "rerank": False})
    assert r.json()["results"][0]["document_title"] == "precos"
    assert "Caneca térmica" in r.json()["results"][0]["excerpt"]

    dup = client.post(f"/api/bases/{base['id']}/documents", headers=headers,
                      files=[("files", ("entrega.md", "# Entregas\n\nEntregamos em todo o Brasil em até 10 dias úteis."
                                        .encode(), "text/markdown"))])
    assert dup.status_code == 409
    same_in_other = client.post(f"/api/bases/{other['id']}/documents", headers=headers,
                                files=[("files", ("entrega.md", "# Entregas\n\nEntregamos em todo o Brasil em até 10 "
                                                  "dias úteis.".encode(), "text/markdown"))])
    assert same_in_other.status_code == 201
    bad = client.post(f"/api/bases/{base['id']}/documents", headers=headers,
                      files=[("files", ("planilha.xlsx", b"PK...", "application/octet-stream"))])
    assert bad.status_code == 415 and bad.json()["code"] == "UNSUPPORTED"


def test_bot_answers_only_from_its_base_and_greets(client):
    headers = login(client)
    upload(client, headers)
    base = new_base(client, headers)
    client.post(f"/api/bases/{base['id']}/texts", headers=headers, json={"title": "Trocas", "content": FAQ})
    wait()
    r = client.post("/api/bots", headers=headers, json={
        "name": "Aurora", "base_id": base["id"], "description": "Atende clientes da loja",
        "instructions": "Seja cordial e objetivo.", "greeting": "Olá! Sou a Aurora. Como posso ajudar?",
        "fallback": "Não encontrei isso nas políticas da loja. Vou chamar alguém da equipe.", "color": "#3e6b2a"})
    assert r.status_code == 201, r.text
    bot = r.json()
    assert bot["base_name"] == "Atendimento Aurora" and bot["ready"] is True
    conv = client.post("/api/conversations", headers=headers, json={"bot_id": bot["id"]}).json()
    assert conv["bot_id"] == bot["id"]

    r = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers, json={"content": "Oi!"})
    assert r.json()["answer"]["content"] == bot["greeting"]
    r = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers,
                    json={"content": "Em quantos dias posso trocar um produto?"})
    answer = r.json()["answer"]
    assert answer["answered"] is True and "30 dias" in answer["content"]
    assert answer["sources"][0]["kind"] == "note"
    r = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers,
                    json={"content": "O que acontece se a atualização de firmware falhar?"})
    assert r.json()["answer"]["answered"] is False
    assert r.json()["answer"]["content"] == bot["fallback"]

    listed = client.get("/api/conversations?only=bots", headers=headers).json()
    assert [c["id"] for c in listed] == [conv["id"]]
    assert client.get("/api/conversations?only=general", headers=headers).json() == []
    r = client.post("/api/ask", headers=headers, json={"question": "O frete da troca é gratuito?", "bot_id": bot["id"]})
    assert r.status_code == 200 and r.json()["answered"] is True

    assert client.delete(f"/api/bases/{base['id']}", headers=headers).json()["code"] == "BASE_IN_USE"
    assert client.delete(f"/api/bots/{bot['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/conversations/{conv['id']}", headers=headers).status_code == 404
    assert client.delete(f"/api/bases/{base['id']}", headers=headers).status_code == 204


def test_bot_with_empty_base_is_blocked_and_permissions(client):
    headers = login(client)
    base = new_base(client, headers)
    bot = client.post("/api/bots", headers=headers, json={"name": "Vazio", "base_id": base["id"]}).json()
    assert bot["ready"] is False
    conv = client.post("/api/conversations", headers=headers, json={"bot_id": bot["id"]}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages", headers=headers, json={"content": "Qual o prazo?"})
    assert r.status_code == 409 and r.json()["code"] == "NO_DOCUMENTS"
    client.post("/api/auth/register", json={"name": "Leitor", "username": "leitor", "password": "senhaForte1"})
    reader = login(client, "leitor", "senhaForte1")
    assert client.patch(f"/api/bots/{bot['id']}", headers=reader, json={"name": "X"}).status_code == 403
    assert client.patch(f"/api/bases/{base['id']}", headers=reader, json={"name": "X"}).status_code == 403
    assert client.get("/api/bots", headers=reader).json()[0]["can_edit"] is False


def test_tutorial_flag(client):
    headers = login(client)
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["tutorial_done_at"] is None
    r = client.put("/api/auth/tutorial", headers=headers, json={"done": True})
    assert r.status_code == 200 and r.json()["tutorial_done_at"]
    assert client.get("/api/auth/me", headers=headers).json()["tutorial_done_at"]


OLD_SCHEMA = """
CREATE TABLE nx_document (id VARCHAR(32) NOT NULL, title VARCHAR(200) NOT NULL, filename VARCHAR(255) NOT NULL,
  sha256 VARCHAR(64) NOT NULL, size_bytes INTEGER NOT NULL, pages INTEGER NOT NULL, chunks INTEGER NOT NULL,
  status VARCHAR(20) NOT NULL, error TEXT, uploaded_by VARCHAR(32) NOT NULL, created_at DATETIME NOT NULL,
  indexed_at DATETIME, PRIMARY KEY (id), UNIQUE (sha256));
CREATE INDEX ix_nx_document_status ON nx_document (status);
CREATE INDEX ix_nx_document_uploaded_by ON nx_document (uploaded_by);
CREATE TABLE nx_conversation (id VARCHAR(32) NOT NULL, owner VARCHAR(32) NOT NULL, title VARCHAR(160) NOT NULL,
  created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, PRIMARY KEY (id));
CREATE TABLE nx_conversation_document (conversation_id VARCHAR(32) NOT NULL, document_id VARCHAR(32) NOT NULL,
  PRIMARY KEY (conversation_id, document_id),
  FOREIGN KEY(conversation_id) REFERENCES nx_conversation (id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES nx_document (id) ON DELETE CASCADE);
INSERT INTO nx_document VALUES ('d1', 'Manual antigo', 'antigo.pdf', 'abc', 10, 2, 3, 'READY', NULL, 'admin',
  '2026-10-01 10:00:00', '2026-10-01 10:01:00');
INSERT INTO nx_conversation VALUES ('c1', 'admin', 'Conversa antiga', '2026-10-01 10:00:00', '2026-10-01 10:00:00');
INSERT INTO nx_conversation_document VALUES ('c1', 'd1');
"""


def test_migrates_old_sqlite_database(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    conn = sqlite3.connect(data / "nexo.db")
    conn.executescript(OLD_SCHEMA)
    conn.commit()
    conn.close()
    monkeypatch.setenv("NEXO_DATA_DIR", str(data))
    from nexo import db
    from nexo.config import get_settings
    get_settings.cache_clear()
    db.reset_engine()
    try:
        with db.session() as s:
            doc = s.get(db.DocumentRow, "d1")
            default = s.get(db.KnowledgeBaseRow, doc.base_id)
            assert default.is_default and doc.kind == "pdf" and doc.extension == "pdf"
            conv = s.get(db.ConversationRow, "c1")
            assert conv.bot_id is None and [d.id for d in conv.documents] == ["d1"]
            other = db.KnowledgeBaseRow(name="Nova", created_by="admin")
            s.add(other)
            s.flush()
            s.add(db.DocumentRow(id="d2", title="Cópia", filename="antigo.pdf", sha256="abc", size_bytes=10,
                                 uploaded_by="admin", base_id=other.id))
            s.commit()
        raw = sqlite3.connect(data / "nexo.db")
        assert raw.execute("PRAGMA foreign_key_check").fetchall() == []
        indexes = {r[1] for r in raw.execute("PRAGMA index_list(nx_document)").fetchall()}
        assert "ix_nx_document_base_id" in indexes
        raw.close()
    finally:
        db.reset_engine()
        get_settings.cache_clear()
