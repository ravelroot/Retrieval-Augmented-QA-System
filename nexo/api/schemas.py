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
    tutorial_done_at: str | None = None


class TutorialIn(BaseModel):
    done: bool


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
    base_id: str
    kind: str = "pdf"
    extension: str = "pdf"
    updated_at: datetime | None = None


class DocumentPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    base_id: str | None = Field(None, min_length=1, max_length=32)


class TextIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200000)


class TextOut(BaseModel):
    title: str
    content: str


class BaseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    color: str | None = Field(None, max_length=16)


class BasePatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    color: str | None = Field(None, max_length=16)


class BaseOut(BaseModel):
    id: str
    name: str
    description: str | None
    color: str
    is_default: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    documents: int = 0
    ready: int = 0
    processing: int = 0
    failed: int = 0
    notes: int = 0
    files: int = 0
    pages: int = 0
    chunks: int = 0
    bots: int = 0
    can_edit: bool = False


class BotIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    base_id: str = Field(min_length=1, max_length=32)
    description: str | None = Field(None, max_length=300)
    instructions: str | None = Field(None, max_length=4000)
    greeting: str | None = Field(None, max_length=500)
    fallback: str | None = Field(None, max_length=500)
    color: str | None = Field(None, max_length=16)
    cite_sources: bool = True


class BotPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    base_id: str | None = Field(None, min_length=1, max_length=32)
    description: str | None = Field(None, max_length=300)
    instructions: str | None = Field(None, max_length=4000)
    greeting: str | None = Field(None, max_length=500)
    fallback: str | None = Field(None, max_length=500)
    color: str | None = Field(None, max_length=16)
    cite_sources: bool | None = None


class BotOut(BaseModel):
    id: str
    name: str
    description: str | None
    base_id: str
    base_name: str
    instructions: str | None
    greeting: str | None
    fallback: str | None
    color: str
    cite_sources: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    conversations: int = 0
    ready: bool = False
    can_edit: bool = False


class SourceOut(BaseModel):
    rank: int
    document_id: str | None
    document_title: str
    page: int
    similarity: float | None
    rerank_score: float | None
    excerpt: str
    kind: str = "pdf"


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
    bot_id: str | None = None


class ConversationOut(ConversationSummary):
    items: list[MessageOut]


class ConversationIn(BaseModel):
    title: str | None = Field(None, max_length=160)
    bot_id: str | None = Field(None, max_length=32)
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
    base_id: str | None = Field(None, max_length=32)


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
    bot_id: str | None = Field(None, max_length=32)


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


class ChannelIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    provider: Literal["cloud", "evolution", "simulador"]
    bot_id: str | None = Field(None, max_length=32)
    auto_reply: bool = True
    phone: str | None = Field(None, max_length=32)
    api_version: str | None = Field(None, max_length=16)
    phone_number_id: str | None = Field(None, max_length=64)
    access_token: str | None = Field(None, max_length=2000)
    app_secret: str | None = Field(None, max_length=200)
    base_url: str | None = Field(None, max_length=300)
    api_key: str | None = Field(None, max_length=200)
    instance: str | None = Field(None, max_length=80)


class ChannelPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    provider: Literal["cloud", "evolution", "simulador"] | None = None
    bot_id: str | None = Field(None, max_length=32)
    auto_reply: bool | None = None
    active: bool | None = None
    phone: str | None = Field(None, max_length=32)
    api_version: str | None = Field(None, max_length=16)
    phone_number_id: str | None = Field(None, max_length=64)
    access_token: str | None = Field(None, max_length=2000)
    app_secret: str | None = Field(None, max_length=200)
    base_url: str | None = Field(None, max_length=300)
    api_key: str | None = Field(None, max_length=200)
    instance: str | None = Field(None, max_length=80)


class ChannelSettings(BaseModel):
    api_version: str | None
    phone_number_id: str | None
    base_url: str | None
    instance: str | None


class ChannelSecrets(BaseModel):
    access_token: str | None
    app_secret: str | None
    api_key: str | None


class ChannelOut(BaseModel):
    id: str
    name: str
    provider: str
    bot_id: str | None
    bot_name: str | None
    auto_reply: bool
    active: bool
    phone: str | None
    webhook_path: str
    verify_token: str
    settings: ChannelSettings
    secrets: ChannelSecrets
    created_at: datetime
    last_event_at: datetime | None
    last_error: str | None
    contacts: int = 0
    unread: int = 0
    waiting: int = 0


class ChannelStatusOut(BaseModel):
    state: Literal["open", "connecting", "close", "unknown"]
    detail: str | None = None


class QrOut(BaseModel):
    state: Literal["open", "connecting", "close", "unknown"]
    base64: str | None = None
    pairing_code: str | None = None


class WebhookSetupIn(BaseModel):
    public_url: str | None = Field(None, max_length=300)


class WebhookSetupOut(BaseModel):
    ok: bool
    url: str
    detail: str | None = None


class SimulateIn(BaseModel):
    phone: str = Field(min_length=3, max_length=32)
    name: str | None = Field(None, max_length=120)
    text: str = Field(min_length=1, max_length=4000)


class ContactOut(BaseModel):
    id: str
    channel_id: str
    phone: str
    name: str | None
    bot_enabled: bool
    needs_human: bool
    unread: int
    last_message: str | None = None
    last_direction: str | None = None
    last_message_at: datetime | None
    created_at: datetime


class WaMessageOut(BaseModel):
    id: str
    direction: str
    author: str
    body: str
    status: str
    error: str | None
    created_at: datetime
    answered: bool | None
    sources: list[SourceOut] = []


class ContactDetailOut(ContactOut):
    messages: list[WaMessageOut]


class ContactPatch(BaseModel):
    bot_enabled: bool | None = None
    needs_human: bool | None = None
    name: str | None = Field(None, max_length=120)


class SendIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class SuggestOut(BaseModel):
    text: str
    answered: bool
    sources: list[SourceOut]


class WaSummaryOut(BaseModel):
    channels: int
    contacts: int
    unread: int
    waiting: int
    bot_answers_today: int
