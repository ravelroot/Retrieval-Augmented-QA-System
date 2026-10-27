from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    username: str
    name: str
    role: str
    created_at: str
    last_login_at: str | None = None


class SessionOut(BaseModel):
    token: str
    expires_at: datetime
    user: UserOut


class DocumentOut(BaseModel):
    id: str
    title: str
    filename: str
    size_bytes: int
    pages: int
    chunks: int
    status: str
    error: str | None
    uploaded_by: str
    created_at: datetime
    indexed_at: datetime | None
    can_delete: bool = False


class DocumentPatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SourceOut(BaseModel):
    rank: int
    document_id: str | None
    document_title: str
    page: int
    similarity: float | None
    rerank_score: float | None
    excerpt: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    answered: bool | None
    grounded: bool | None
    model: str | None
    latency_ms: int | None
    created_at: datetime
    sources: list[SourceOut] = []
    my_rating: int | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    document_ids: list[str]
    messages: int


class ConversationOut(ConversationSummary):
    items: list[MessageOut]


class ConversationIn(BaseModel):
    title: str | None = Field(None, max_length=160)
    document_ids: list[str] = Field(default_factory=list, max_length=200)


class ConversationPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=160)
    document_ids: list[str] | None = Field(None, max_length=200)


class QuestionIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ExchangeOut(BaseModel):
    question: MessageOut
    answer: MessageOut
    conversation: ConversationSummary


class FeedbackIn(BaseModel):
    rating: int = Field(ge=-1, le=1)
    comment: str | None = Field(None, max_length=1000)


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    document_ids: list[str] = Field(default_factory=list, max_length=200)
    rerank: bool = True
    limit: int = Field(8, ge=1, le=20)


class SearchOut(BaseModel):
    query: str
    took_ms: int
    results: list[SourceOut]


class ConversationExport(ConversationOut):
    exported_at: datetime


class FeedbackCount(BaseModel):
    up: int
    down: int


class DailyCount(BaseModel):
    date: str
    questions: int
    unanswered: int


class DocumentCitations(BaseModel):
    document_id: str | None
    title: str
    citations: int


class UnansweredItem(BaseModel):
    question: str
    asked_at: datetime
    conversation_id: str


class NegativeItem(BaseModel):
    question: str
    answer: str
    asked_at: datetime
    conversation_id: str
    message_id: str


class MetricsOut(BaseModel):
    scope: Literal["all", "mine"]
    period_days: int
    questions: int
    answered: int
    unanswered: int
    answer_rate: float | None
    avg_latency_ms: int | None
    p95_latency_ms: int | None
    feedback: FeedbackCount
    conversations: int
    daily: list[DailyCount]
    top_documents: list[DocumentCitations]
    unanswered_recent: list[UnansweredItem]
    negative_recent: list[NegativeItem]


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ApiKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    key: str


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[str] = Field(default_factory=list, max_length=200)
    conversation_id: str | None = None


class AskOut(BaseModel):
    answer: str
    answered: bool
    grounded: bool | None
    model: str
    latency_ms: int
    conversation_id: str | None
    sources: list[SourceOut]


class WebhookIn(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    events: list[str] = Field(max_length=20)
    secret: str | None = Field(None, max_length=80)


class WebhookPatch(BaseModel):
    active: bool


class WebhookOut(BaseModel):
    id: str
    url: str
    events: list[str]
    active: bool
    created_at: datetime
    last_status: int | None
    last_error: str | None
    last_delivery_at: datetime | None


class WebhookCreated(WebhookOut):
    secret: str


class WebhookTestOut(BaseModel):
    status: int | None
    error: str | None


class RolePatch(BaseModel):
    role: Literal["admin", "user"]
