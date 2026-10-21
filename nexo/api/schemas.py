from __future__ import annotations

from datetime import datetime

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
