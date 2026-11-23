import shutil
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pytest
from fastapi.testclient import TestClient

from tests.conftest import login, upload


@pytest.fixture()
def painel(client, tmp_path, monkeypatch):
    from nexo.api import app as app_module
    web = tmp_path / "dist"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    (web / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "segredo.txt").write_text("não", encoding="utf-8")
    monkeypatch.setattr(app_module, "WEB_DIR", web)
    with TestClient(app_module.create_app(janela_chave="chave-da-janela-de-teste")) as c:
        yield c


@pytest.fixture()
def servidor(client):
    from nexo import desktop
    from nexo.config import get_settings
    s = desktop.Servidor(get_settings())
    assert s.aguardar(30)
    yield s
    s.parar()


def test_painel_so_abre_pela_janela(painel):
    assert painel.get("/").status_code == 403
    assert painel.get("/assets/app.js").status_code == 403
    assert painel.get("/janela?chave=errada").status_code == 403
    assert painel.get("/janela?chave=chavé").status_code == 403
    r = painel.get("/janela?chave=chave-da-janela-de-teste", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    painel.cookies.set("nexo_janela", "chave-da-janela-de-teste")
    r = painel.get("/conversas")
    assert r.status_code == 200 and 'id="root"' in r.text and r.headers["cache-control"] == "no-store"
    assert painel.get("/assets/app.js").text == "console.log(1)"
    assert painel.get("/../segredo.txt").text != "não"
    assert painel.get("/api/inexistente").json()["code"] == "NOT_FOUND"
    assert painel.get("/api/health").status_code == 200


def test_sem_chave_nao_ha_painel(client):
    assert client.get("/").status_code == 404
    assert client.get("/janela?chave=qualquer").status_code == 404
    assert client.get("/api/health").status_code == 200


def test_nome_seguro():
    from nexo.desktop import nome_seguro
    assert nome_seguro("Manual técnico.PDF") == "Manual técnico.pdf"
    assert nome_seguro("..\\..\\Windows\\win.ini.txt") == "win.ini.txt"
    assert nome_seguro('a<b>:c|d?.md') == "a_b__c_d_.md"
    assert nome_seguro("con.txt") == "_con.txt"
    for ruim in ("virus.exe", "script.bat", "", None, ".pdf", "sem-extensao"):
        with pytest.raises(ValueError):
            nome_seguro(ruim)


def test_url_e_porta():
    from nexo.desktop import escolher_porta, url_local
    assert url_local("0.0.0.0", 8000) == "http://127.0.0.1:8000"
    assert url_local("::1", 9000) == "http://[::1]:9000"
    assert 0 < escolher_porta("127.0.0.1", 65530) < 65536


def test_instancia_unica(tmp_path):
    import os

    from nexo.desktop import travar
    fd = travar(tmp_path)
    assert fd is not None
    assert travar(tmp_path) is None
    assert (tmp_path / "instancia.json").read_text(encoding="utf-8").startswith('{"pid"')
    os.close(fd)


def test_tela_escapa_texto():
    from nexo.desktop import tela
    pagina = tela("Erro <b>", "<script>alert(1)</script>", erro=True)
    assert "<script>alert" not in pagina and "&lt;script&gt;" in pagina


def test_ponte_abre_documento_e_pagina(client, servidor, monkeypatch, tmp_path):
    from nexo import desktop
    headers = login(client)
    doc = upload(client, headers)
    token = headers["Authorization"].split()[1]
    janelas, sistema = [], []
    ponte = desktop.Ponte(tmp_path)
    monkeypatch.setattr(desktop.Ponte, "_janela_nova", lambda self, titulo, url: janelas.append((titulo, url)))
    monkeypatch.setattr(desktop, "abrir_no_sistema", sistema.append)
    assert ponte.abrir_documento(doc["id"], 2, token)["status"] == 503
    ponte._ligar(servidor.url, None)
    assert ponte.abrir_documento(doc["id"], 2, token) == {"ok": True}
    titulo, url = janelas[-1]
    assert url.startswith("file://") and url.endswith(".pdf#page=2") and titulo
    local = Path(url2pathname(urlsplit(url).path))
    assert local.read_bytes().startswith(b"%PDF") and tmp_path / "temp" in local.parents
    assert ponte.abrir_documento(doc["id"], True, token) == {"ok": True}
    assert not janelas[-1][1].endswith("#page=1")
    assert ponte.abrir_documento("../../etc", 1, token)["status"] == 400
    assert ponte.abrir_documento(doc["id"], 1, "token\r\nX: y")["status"] == 401
    assert ponte.abrir_documento(doc["id"], 1, "token.invalido.mesmo")["status"] == 401
    assert ponte.abrir_documento("a" * 32, 1, token)["status"] == 404
    assert ponte.abrir_pagina("/api/docs") == {"ok": True}
    assert janelas[-1][1] == servidor.url + "/api/docs"
    assert ponte.abrir_pagina("/../../etc/passwd")["status"] == 404
    note = client.post(f"/api/bases/{doc['base_id']}/texts", headers=headers, json={"title": "Nota", "content": "Texto."})
    assert note.status_code == 201, note.text
    assert ponte.abrir_documento(note.json()["id"], None, token)["status"] == 415
    assert sistema == []


def test_ponte_restaurar_exige_admin(client, servidor, tmp_path):
    from nexo import desktop

    class Janela:
        def __init__(self):
            self.destruida = False

        def create_file_dialog(self, *args, **kwargs):
            return (str(tmp_path / "backup.zip"),)

        def create_confirmation_dialog(self, *args):
            return True

        def destroy(self):
            self.destruida = True

    headers = login(client)
    admin_token = headers["Authorization"].split()[1]
    r = client.post("/api/users", headers=headers, json={"username": "leitor", "name": "Leitor", "password": "Consulta2026",
                                                         "role": "user"})
    assert r.status_code in (200, 201), r.text
    leitor = login(client, "leitor", "Consulta2026")["Authorization"].split()[1]
    janela = Janela()
    ponte = desktop.Ponte(tmp_path)
    ponte._ligar(servidor.url, janela)
    assert ponte.restaurar_backup(leitor)["status"] == 403
    (tmp_path / "backup.zip").write_bytes(b"isto nao e zip")
    assert ponte.restaurar_backup(admin_token)["status"] == 400
    r = client.get("/api/system/backup", headers=headers)
    (tmp_path / "backup.zip").write_bytes(r.content)
    assert ponte.restaurar_backup(admin_token) == {"ok": True}
    assert janela.destruida and ponte._reabrir
    assert (tmp_path / desktop.RESTAURACAO).is_file()


def test_restaurar_pendente(client, tmp_path, monkeypatch):
    from nexo import desktop, maintenance
    from nexo.config import get_settings
    settings = get_settings()
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    maintenance.create_backup(settings, raiz / desktop.RESTAURACAO)
    destino = tmp_path / "restaurado"
    monkeypatch.setenv("NEXO_DATA_DIR", str(destino))
    assert desktop.restaurar_pendente(raiz) is None
    assert (destino / "nexo.db").is_file() and (destino / "usuarios.json").is_file()
    assert not (raiz / desktop.RESTAURACAO).exists()
    (raiz / desktop.RESTAURACAO).write_bytes(b"corrompido")
    assert desktop.restaurar_pendente(raiz)
    assert not (raiz / desktop.RESTAURACAO).exists()
    assert desktop.restaurar_pendente(raiz) is None


def test_manifesto_do_backup(tmp_path):
    from nexo.maintenance import MaintenanceError, read_manifest
    caminho = tmp_path / "b.zip"
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("manifesto.json", '{"produto": "Nexo", "versao": "3.0.0"}')
        z.writestr("../fora.txt", "x")
    with pytest.raises(MaintenanceError):
        read_manifest(caminho)
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("manifesto.json", '{"produto": "Nexo", "versao": "3.0.0"}')
    assert read_manifest(caminho)["versao"] == "3.0.0"
    shutil.copy(caminho, tmp_path / "c.zip")
    (tmp_path / "c.zip").write_bytes(b"x")
    with pytest.raises(MaintenanceError):
        read_manifest(tmp_path / "c.zip")


def test_cli_sem_comando_abre_o_aplicativo(monkeypatch):
    from nexo import cli, desktop
    chamadas = []
    monkeypatch.setattr(desktop, "abrir", lambda reabrir=False: chamadas.append(reabrir))
    cli.main([])
    cli.main(["--reabrir"])
    assert chamadas == [False, True]


def test_primeira_abertura_ja_vem_configurada(client):
    from sqlalchemy import func, select

    from nexo import db, desktop, onboarding
    from nexo.config import get_settings
    settings = get_settings()
    assert desktop.primeira_abertura(settings) == 6
    assert onboarding.done_at(settings)
    with db.session() as s:
        assert s.scalar(select(func.count()).select_from(db.DocumentRow).where(db.DocumentRow.status == "PENDING")) == 6
        assert s.scalar(select(func.count()).select_from(db.BotRow).where(db.BotRow.name == "Agente de teste")) == 1
    assert desktop.primeira_abertura(settings) == 0
    from nexo.config import Settings
    assert Settings.model_fields["llm_provider"].default == "ollama"
    assert Settings.model_fields["llm_model"].default == "llama3.1"


def test_primeira_abertura_respeita_dados_existentes(client):
    from nexo import desktop, onboarding
    from nexo.config import get_settings
    upload(client, login(client))
    settings = get_settings()
    assert desktop.primeira_abertura(settings) == 0
    assert onboarding.done_at(settings)
