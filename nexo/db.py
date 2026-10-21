from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Table, Text,
                        UniqueConstraint, create_engine, event)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from nexo.config import get_settings


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


conversation_documents = Table(
    "nx_conversation_document",
    Base.metadata,
    Column("conversation_id", String(32), ForeignKey("nx_conversation.id", ondelete="CASCADE"), primary_key=True),
    Column("document_id", String(32), ForeignKey("nx_document.id", ondelete="CASCADE"), primary_key=True),
)


class DocumentRow(Base):
    __tablename__ = "nx_document"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    chunks: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ConversationRow(Base):
    __tablename__ = "nx_conversation"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(160), default="Nova conversa")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    documents: Mapped[list[DocumentRow]] = relationship(secondary=conversation_documents, lazy="selectin")
    messages: Mapped[list[MessageRow]] = relationship(back_populates="conversation", cascade="all, delete-orphan",
                                                      order_by="MessageRow.created_at", lazy="selectin")


class MessageRow(Base):
    __tablename__ = "nx_message"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(String(32), ForeignKey("nx_conversation.id", ondelete="CASCADE"),
                                                 index=True)
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    grounded: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    answered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    conversation: Mapped[ConversationRow] = relationship(back_populates="messages")
    sources: Mapped[list[SourceRow]] = relationship(back_populates="message", cascade="all, delete-orphan",
                                                    order_by="SourceRow.rank", lazy="selectin")
    feedback: Mapped[list[FeedbackRow]] = relationship(back_populates="message", cascade="all, delete-orphan",
                                                       lazy="selectin")


class SourceRow(Base):
    __tablename__ = "nx_message_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(32), ForeignKey("nx_message.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("nx_document.id", ondelete="SET NULL"),
                                                    nullable=True, index=True)
    document_title: Mapped[str] = mapped_column(String(200))
    chunk_id: Mapped[str] = mapped_column(String(80))
    page: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int] = mapped_column(Integer)
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    rerank_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    excerpt: Mapped[str] = mapped_column(Text)

    message: Mapped[MessageRow] = relationship(back_populates="sources")


class FeedbackRow(Base):
    __tablename__ = "nx_feedback"
    __table_args__ = (UniqueConstraint("message_id", "owner", name="uk_feedback_message_owner"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(32), ForeignKey("nx_message.id", ondelete="CASCADE"))
    owner: Mapped[str] = mapped_column(String(32))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    message: Mapped[MessageRow] = relationship(back_populates="feedback")


Index("ix_nx_message_conversation_created", MessageRow.conversation_id, MessageRow.created_at)

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def engine() -> Engine:
    global _engine, _factory
    if _engine is None:
        url = get_settings().sqlalchemy_url
        args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=args, pool_pre_ping=True)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _pragmas(conn, _):
                cur = conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.close()
        Base.metadata.create_all(_engine)
        _factory = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def session() -> Session:
    engine()
    assert _factory is not None
    return _factory()


def get_db() -> Iterator[Session]:
    db = session()
    try:
        yield db
    finally:
        db.close()


def reset_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _factory = None
