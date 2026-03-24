from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_current_user, get_repository
from backend.schemas import (
    ConversationCreatePayload,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationUpdatePayload,
    UserPayload,
    UserResponse,
)

router = APIRouter(prefix="/api", tags=["conversations"])


@router.post("/users", response_model=UserResponse)
async def create_user(payload: UserPayload, repository=Depends(get_repository)) -> UserResponse:
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username required")
    return UserResponse.model_validate(await repository.get_or_create_user(username))


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(user=Depends(get_current_user), repository=Depends(get_repository)) -> list[ConversationResponse]:
    conversations = await repository.list_conversations(user["id"])
    return [ConversationResponse.model_validate(item) for item in conversations]


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    payload: ConversationCreatePayload,
    user=Depends(get_current_user),
    repository=Depends(get_repository),
) -> ConversationResponse:
    conversation = await repository.create_conversation(user["id"], payload.language, payload.tone)
    return ConversationResponse.model_validate(conversation)


@router.get("/conversations/{conv_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conv_id: int,
    user=Depends(get_current_user),
    repository=Depends(get_repository),
) -> ConversationDetailResponse:
    conversation = await repository.get_conversation(conv_id, user["id"])
    if not conversation:
        raise HTTPException(status_code=404, detail="conversation not found")
    messages = await repository.get_all_messages(conv_id)
    return ConversationDetailResponse.model_validate({**conversation, "messages": messages})


@router.patch("/conversations/{conv_id}", response_model=ConversationResponse)
async def update_conversation(
    conv_id: int,
    payload: ConversationUpdatePayload,
    user=Depends(get_current_user),
    repository=Depends(get_repository),
) -> ConversationResponse:
    conversation = await repository.get_conversation(conv_id, user["id"])
    if not conversation:
        raise HTTPException(status_code=404, detail="conversation not found")

    if payload.title is not None:
        await repository.update_conversation_title(conv_id, payload.title)
    if payload.language is not None or payload.tone is not None:
        await repository.update_conversation_settings(conv_id, payload.language, payload.tone)

    updated = await repository.get_conversation(conv_id, user["id"])
    return ConversationResponse.model_validate(updated)
