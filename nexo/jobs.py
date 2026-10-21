from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import select

from nexo import db
from nexo.config import get_settings
from nexo.rag.engine import IngestionError, get_engine
from nexo.rag.providers import ProviderError

log = logging.getLogger("nexo.jobs")
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nexo-ingest")


def pdf_path(document_id: str) -> Path:
    return get_settings().uploads_dir / f"{document_id}.pdf"


def enqueue(document_id: str) -> None:
    _executor.submit(process, document_id)


def process(document_id: str) -> None:
    settings = get_settings()
    with db.session() as s:
        row = s.get(db.DocumentRow, document_id)
        if row is None:
            return
        row.status = "PROCESSING"
        row.error = None
        s.commit()
        title, filename = row.title, row.filename
    try:
        pages, chunks, pdf_title = get_engine(settings).ingest(document_id, title, filename, pdf_path(document_id))
    except (IngestionError, ProviderError) as e:
        _fail(document_id, str(e))
        return
    except Exception as e:
        log.exception("Falha ao indexar %s", document_id)
        _fail(document_id, f"Falha ao indexar: {e}")
        return
    with db.session() as s:
        row = s.get(db.DocumentRow, document_id)
        if row is None:
            get_engine(settings).delete(document_id)
            return
        row.status = "READY"
        row.pages = pages
        row.chunks = chunks
        row.indexed_at = db.utcnow()
        s.commit()


def _fail(document_id: str, message: str) -> None:
    with db.session() as s:
        row = s.get(db.DocumentRow, document_id)
        if row is not None:
            row.status = "FAILED"
            row.error = message[:2000]
            s.commit()


def resume_pending() -> int:
    with db.session() as s:
        ids = list(s.scalars(select(db.DocumentRow.id).where(db.DocumentRow.status.in_(["PENDING", "PROCESSING"]))))
    for i in ids:
        enqueue(i)
    return len(ids)


def wait_idle(timeout: float = 60.0) -> None:
    _executor.submit(lambda: None).result(timeout=timeout)
