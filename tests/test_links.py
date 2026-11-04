from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.conftest import FIXTURES, login

PAGES: dict[str, tuple[str, bytes]] = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/volta":
            self.send_response(302)
            self.send_header("Location", "/politica")
            self.end_headers()
            return
        if self.path == "/interno":
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data")
            self.end_headers()
            return
        found = PAGES.get(self.path)
        if found is None:
            self.send_response(404)
            self.end_headers()
            return
        kind, body = found
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        return


@pytest.fixture()
def site():
    PAGES.clear()
    PAGES["/politica"] = ("text/html; charset=utf-8", """<html><head><title>Política de trocas</title></head><body>
        <h1>Trocas e devoluções</h1><p>Trocas podem ser pedidas em até sete dias corridos após a entrega do produto.</p>
        <script>var rastreio = 1;</script></body></html>""".encode("utf-8"))
    PAGES["/manual.pdf"] = ("application/pdf", (FIXTURES / "manual-exemplo.pdf").read_bytes())
    PAGES["/foto.png"] = ("image/png", b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    PAGES["/vazio"] = ("text/plain", b"   ")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def base_of(client, headers) -> str:
    return next(b["id"] for b in client.get("/api/bases", headers=headers).json() if b["is_default"])


def test_private_links_are_blocked_by_default(client, site):
    headers = login(client)
    base = base_of(client, headers)
    r = client.post(f"/api/bases/{base}/links", headers=headers, json={"url": f"{site}/politica"})
    assert r.status_code == 403 and r.json()["code"] == "PRIVATE_URL" and "url" in r.json()["fields"]
    r = client.post(f"/api/bases/{base}/links", headers=headers, json={"url": "ftp://exemplo.com/arquivo.pdf"})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_URL"
    r = client.post(f"/api/bases/{base}/links", headers=headers, json={"url": "https://usuario:senha@exemplo.com/x"})
    assert r.status_code == 400


def test_import_refetch_and_errors(client, site):
    from nexo import jobs
    from nexo.config import get_settings
    get_settings().allow_private_urls = True
    headers = login(client)
    base = base_of(client, headers)
    r = client.post(f"/api/bases/{base}/links", headers=headers, json={"url": f"{site}/volta"})
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["title"] == "Política de trocas" and doc["extension"] == "html" and doc["kind"] == "file"
    assert doc["source_url"] == f"{site}/politica"
    jobs.wait_idle()
    ready = client.get(f"/api/documents/{doc['id']}", headers=headers).json()
    assert ready["status"] == "READY" and ready["chunks"] >= 1
    chunks = client.get(f"/api/documents/{doc['id']}/chunks", headers=headers).json()["items"]
    assert "sete dias corridos" in " ".join(c["text"] for c in chunks) and "rastreio" not in " ".join(c["text"] for c in chunks)

    r = client.post(f"/api/bases/{base}/links", headers=headers, json={"url": f"{site}/politica"})
    assert r.status_code == 409 and r.json()["code"] == "DUPLICATE"
    r = client.post(f"/api/documents/{doc['id']}/refetch", headers=headers)
    assert r.status_code == 200 and r.json()["changed"] is False
    PAGES["/politica"] = ("text/html", "<p>Trocas podem ser pedidas em até trinta dias após a entrega.</p>".encode("utf-8"))
    r = client.post(f"/api/documents/{doc['id']}/refetch", headers=headers)
    assert r.status_code == 200 and r.json()["changed"] is True and r.json()["document"]["status"] == "PENDING"
    jobs.wait_idle()
    chunks = client.get(f"/api/documents/{doc['id']}/chunks", headers=headers).json()["items"]
    assert "trinta dias" in chunks[0]["text"]

    r = client.post(f"/api/bases/{base}/links", headers=headers, json={"url": f"{site}/manual.pdf", "title": "Manual BC-40"})
    assert r.status_code == 201 and r.json()["kind"] == "pdf" and r.json()["title"] == "Manual BC-40"
    jobs.wait_idle()
    assert client.get(f"/api/documents/{r.json()['id']}", headers=headers).json()["status"] == "READY"

    assert client.post(f"/api/bases/{base}/links", headers=headers, json={"url": f"{site}/foto.png"}).status_code == 415
    assert client.post(f"/api/bases/{base}/links", headers=headers, json={"url": f"{site}/vazio"}).json()["code"] == "EMPTY"
    assert client.post(f"/api/bases/{base}/links", headers=headers, json={"url": f"{site}/nada"}).json()["code"] == "HTTP_ERROR"
    get_settings().allow_private_urls = False
    r = client.post(f"/api/bases/{base}/links", headers=headers, json={"url": f"{site}/interno"})
    assert r.status_code == 403
    text = client.post(f"/api/bases/{base}/texts", headers=headers, json={"title": "Nota", "content": "Conteúdo."}).json()
    assert client.post(f"/api/documents/{text['id']}/refetch", headers=headers).json()["code"] == "NOT_A_LINK"


def test_link_redirect_to_internal_is_blocked(client, site, monkeypatch):
    from nexo import links
    from nexo.config import get_settings
    settings = get_settings()
    real = links.validate
    calls = []

    def guarded(url, s):
        calls.append(url)
        if url.startswith(site):
            return links.urllib.parse.urlparse(url)
        return real(url, s)

    monkeypatch.setattr(links, "validate", guarded)
    with pytest.raises(links.LinkError) as err:
        links.fetch(f"{site}/interno", settings)
    assert err.value.code == "PRIVATE_URL" and any("169.254" in c for c in calls)
