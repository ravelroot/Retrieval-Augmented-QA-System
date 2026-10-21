from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("NEXO_EMBED_PROVIDER", "hash")
    monkeypatch.setenv("NEXO_LLM_PROVIDER", "extrativo")
    monkeypatch.setenv("NEXO_RERANKER", "none")
    monkeypatch.setenv("NEXO_MIN_SIMILARITY", "0.1")
    monkeypatch.setenv("NEXO_SECRET", "segredo-de-teste-com-tamanho-suficiente-para-hs256")
    from nexo import db
    from nexo.api import deps
    from nexo.config import get_settings
    from nexo.rag import engine
    get_settings.cache_clear()
    deps.get_users.cache_clear()
    db.reset_engine()
    engine.reset_engine()
    from nexo.api.app import create_app
    with TestClient(create_app()) as c:
        yield c
    db.reset_engine()
    engine.reset_engine()
    get_settings.cache_clear()
    deps.get_users.cache_clear()


def login(client: TestClient, username: str = "admin", password: str = "Nexo@2026") -> dict:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def upload(client: TestClient, headers: dict, name: str = "manual-exemplo.pdf") -> dict:
    data = (FIXTURES / "manual-exemplo.pdf").read_bytes()
    r = client.post("/api/documents", headers=headers, files=[("files", (name, data, "application/pdf"))])
    assert r.status_code == 201, r.text
    from nexo import jobs
    jobs.wait_idle()
    return r.json()[0]
