from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UserPayload(BaseModel):
    username: str


class ConversationCreatePayload(BaseModel):
    language: str = "chinese"
    tone: str = "hype"


class ConversationUpdatePayload(BaseModel):
    title: str | None = None
    language: str | None = None
    tone: str | None = None


class UserResponse(BaseModel):
    id: int
    username: str


class ConversationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    title: str
    language: str
    tone: str
    updated_at: str


class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: str | None = None


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse]


class HealthResponse(BaseModel):
    status: str


class ConfigResponse(BaseModel):
    available_languages: list[str]
    available_tones: dict[str, dict[str, str]]
    tts_engine_override: str | None


class TranscriptResponse(BaseModel):
    transcript: str
    error: str | None = None


class TTSReplayResponse(BaseModel):
    audio_base64: str
    audio_mime: str
    tts_ms: int


class ChatResponse(BaseModel):
    reply: str
    audio_base64: str
    audio_mime: str
    llm_ms: int
    tts_ms: int
    total_ms: int


class VapidPublicKeyResponse(BaseModel):
    public_key: str


class SubscriptionStatusResponse(BaseModel):
    status: str


class SendPushResponse(BaseModel):
    sent: int
    total: int
