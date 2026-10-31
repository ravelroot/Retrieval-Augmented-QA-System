from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateIndex, CreateTable

log = logging.getLogger("nexo.migrations")

DEFAULT_BASE_NAME = "Acervo geral"
DEFAULT_BASE_DESCRIPTION = "Base padrão. Recebe os documentos enviados sem escolher uma base."

DOCUMENT_COLUMNS = ["id", "title", "filename", "sha256", "size_bytes", "pages", "chunks", "status", "error", "uploaded_by",
                    "created_at", "indexed_at"]


def _columns(engine: Engine, table: str) -> set[str]:
    insp = inspect(engine)
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def ensure_default_base(engine: Engine) -> str:
    from nexo.db import new_id, utcnow
    with engine.begin() as conn:
        found = conn.execute(text("SELECT id FROM nx_knowledge_base WHERE is_default = :t ORDER BY created_at"),
                             {"t": True}).first()
        if found:
            return found[0]
        base_id = new_id()
        now = utcnow()
        conn.execute(text("INSERT INTO nx_knowledge_base (id, name, description, color, is_default, created_by, "
                          "created_at, updated_at) VALUES (:id, :name, :description, :color, :d, :by, :now, :now)"),
                     {"id": base_id, "name": DEFAULT_BASE_NAME, "description": DEFAULT_BASE_DESCRIPTION,
                      "color": "#000000", "d": True, "by": "admin", "now": now})
        return base_id


def _rebuild_sqlite_documents(engine: Engine, base_id: str) -> None:
    from nexo.db import DocumentRow
    table = DocumentRow.__table__
    ddl = str(CreateTable(table).compile(engine)).replace("CREATE TABLE nx_document", "CREATE TABLE nx_document_novo", 1)
    cols = ", ".join(DOCUMENT_COLUMNS)
    raw = engine.raw_connection()
    try:
        driver = raw.driver_connection
        driver.isolation_level = None
        cur = driver.cursor()
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.execute("BEGIN")
        try:
            cur.execute(ddl)
            cur.execute(f"INSERT INTO nx_document_novo ({cols}, base_id, kind, extension) "
                        f"SELECT {cols}, ?, 'pdf', 'pdf' FROM nx_document", (base_id,))
            cur.execute("DROP TABLE nx_document")
            cur.execute("ALTER TABLE nx_document_novo RENAME TO nx_document")
            for index in table.indexes:
                cur.execute(str(CreateIndex(index).compile(engine)))
            problems = cur.execute("PRAGMA foreign_key_check").fetchall()
            if problems:
                raise RuntimeError(f"Chaves estrangeiras inválidas após a migração: {problems[:3]}")
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
        finally:
            cur.execute("PRAGMA foreign_keys=ON")
            driver.isolation_level = ""
    finally:
        raw.close()


def _upgrade_other_documents(engine: Engine, base_id: str) -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE nx_document ADD COLUMN base_id VARCHAR(32)"))
        conn.execute(text("ALTER TABLE nx_document ADD COLUMN kind VARCHAR(10) DEFAULT 'pdf'"))
        conn.execute(text("ALTER TABLE nx_document ADD COLUMN extension VARCHAR(10) DEFAULT 'pdf'"))
        conn.execute(text("ALTER TABLE nx_document ADD COLUMN content TEXT"))
        conn.execute(text(f"ALTER TABLE nx_document ADD COLUMN updated_at {'DATETIME' if engine.dialect.name == 'mysql' else 'TIMESTAMP'}"))
        conn.execute(text("UPDATE nx_document SET base_id = :b, kind = 'pdf', extension = 'pdf'"), {"b": base_id})
        for uc in insp.get_unique_constraints("nx_document"):
            if uc.get("column_names") == ["sha256"] and uc.get("name"):
                conn.execute(text(f"ALTER TABLE nx_document DROP CONSTRAINT {uc['name']}"))
        for ix in insp.get_indexes("nx_document"):
            if ix.get("unique") and ix.get("column_names") == ["sha256"] and ix.get("name"):
                conn.execute(text(f"DROP INDEX {ix['name']}" if engine.dialect.name != "mysql"
                                  else f"DROP INDEX {ix['name']} ON nx_document"))
        conn.execute(text("ALTER TABLE nx_document ADD CONSTRAINT uk_document_base_sha256 UNIQUE (base_id, sha256)"))
        conn.execute(text("ALTER TABLE nx_document ADD CONSTRAINT fk_document_base FOREIGN KEY (base_id) "
                          "REFERENCES nx_knowledge_base (id) ON DELETE CASCADE"))
        conn.execute(text("CREATE INDEX ix_nx_document_base_id ON nx_document (base_id)"))


def _upgrade_conversations(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE nx_conversation ADD COLUMN bot_id VARCHAR(32) "
                          "REFERENCES nx_bot (id) ON DELETE CASCADE"))
        conn.execute(text("CREATE INDEX ix_nx_conversation_bot_id ON nx_conversation (bot_id)"))


def migrate(engine: Engine) -> None:
    from nexo.db import Base
    document_cols = _columns(engine, "nx_document")
    conversation_cols = _columns(engine, "nx_conversation")
    Base.metadata.create_all(engine)
    base_id = ensure_default_base(engine)
    if document_cols and "base_id" not in document_cols:
        log.info("Migrando nx_document para bases de conhecimento.")
        if engine.dialect.name == "sqlite":
            _rebuild_sqlite_documents(engine, base_id)
        else:
            _upgrade_other_documents(engine, base_id)
    if conversation_cols and "bot_id" not in conversation_cols:
        log.info("Migrando nx_conversation para agentes.")
        _upgrade_conversations(engine)
