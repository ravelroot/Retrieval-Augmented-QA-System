from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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
    password_changed_at: str | None = None


class ProfilePatch(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class UserCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)
    role: Literal["admin", "user"] = "user"


class PasswordResetIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class BulkIn(BaseModel):
    action: Literal["reindex", "delete", "move"]
    ids: list[str] = Field(min_length=1, max_length=500)
    base_id: str | None = Field(None, min_length=1, max_length=32)


class BulkOut(BaseModel):
    done: list[str]
    skipped: dict[str, str]


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
    source_url: str | None = None
    outdated: bool = False


class DocumentPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    base_id: str | None = Field(None, min_length=1, max_length=32)


class TextIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200000)


class TextOut(BaseModel):
    title: str
    content: str


class LinkIn(BaseModel):
    url: str = Field(min_length=8, max_length=1000)
    title: str | None = Field(None, max_length=200)


class RefetchOut(BaseModel):
    document: DocumentOut
    changed: bool


class ChunkOut(BaseModel):
    chunk_id: str
    index: int
    page: int
    text: str


class ChunksOut(BaseModel):
    document_id: str
    title: str
    kind: str
    total: int
    offset: int
    items: list[ChunkOut]


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
    suggestions: list[str] = Field(default_factory=list, max_length=6)


class BotPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    base_id: str | None = Field(None, min_length=1, max_length=32)
    description: str | None = Field(None, max_length=300)
    instructions: str | None = Field(None, max_length=4000)
    greeting: str | None = Field(None, max_length=500)
    fallback: str | None = Field(None, max_length=500)
    color: str | None = Field(None, max_length=16)
    cite_sources: bool | None = None
    suggestions: list[str] | None = Field(None, max_length=6)


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
    suggestions: list[str] = []


class SampleOut(BaseModel):
    base: BaseOut
    bot: BotOut
    added: int
    existed: bool


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
    my_comment: str | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    document_ids: list[str]
    messages: int
    bot_id: str | None = None
    pinned: bool = False


class ConversationOut(ConversationSummary):
    items: list[MessageOut]


class ConversationIn(BaseModel):
    title: str | None = Field(None, max_length=160)
    bot_id: str | None = Field(None, max_length=32)
    document_ids: list[str] = Field(default_factory=list, max_length=200)


class ConversationPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=160)
    document_ids: list[str] | None = Field(None, max_length=200)
    pinned: bool | None = None


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
    comment: str | None = None
    owner: str | None = None


class BotStat(BaseModel):
    bot_id: str | None
    name: str
    color: str | None = None
    questions: int
    answered: int
    answer_rate: float | None
    negative: int
    avg_latency_ms: int | None


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
    by_bot: list[BotStat] = []
    bot_id: str | None = None


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scope: Literal["full", "ask", "feed"] = "full"
    expires_days: int | None = Field(None, ge=1, le=3650)


class ApiKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    scope: str = "full"
    expires_at: datetime | None = None
    expired: bool = False


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


class QuickReplyIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=4000)


class QuickReplyPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=80)
    body: str | None = Field(None, min_length=1, max_length=4000)


class QuickReplyOut(BaseModel):
    id: str
    title: str
    body: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    can_edit: bool = False


class SettingItem(BaseModel):
    name: str
    group: str
    label: str
    hint: str
    kind: str
    value: Any
    default: Any
    overridden: bool
    reindex: bool
    min: float | None = None
    max: float | None = None


class SettingsOut(BaseModel):
    items: list[SettingItem]
    fixed: dict[str, str]
    outdated: int = 0


class SettingsPatch(BaseModel):
    values: dict[str, Any] = Field(min_length=1, max_length=40)


class SettingsResetIn(BaseModel):
    names: list[str] | None = Field(None, max_length=40)


class SettingsChanged(SettingsOut):
    changed: list[str]
    reindex_needed: bool = False


class CheckOut(BaseModel):
    id: str
    group: str
    label: str
    status: Literal["ok", "warn", "fail", "info"]
    detail: str
    hint: str | None = None


class DiagnosticsOut(BaseModel):
    checked_at: datetime
    deep: bool
    ok: int
    warn: int
    fail: int
    info: int
    checks: list[CheckOut]


class MaintenanceIn(BaseModel):
    action: Literal["reindex_failed", "reindex_outdated", "reindex_all", "clean_orphans", "purge_conversations", "vacuum"]
    days: int | None = Field(None, ge=1, le=3650)


class MaintenanceOut(BaseModel):
    action: str
    message: str
    count: int
    skipped: int


class AuditItem(BaseModel):
    id: int
    created_at: datetime
    actor: str
    action: str
    label: str
    target_type: str | None
    target_id: str | None
    detail: str | None
    ip: str | None


class AuditPage(BaseModel):
    total: int
    items: list[AuditItem]
    actions: dict[str, str]
