from __future__ import annotations

import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from backend.api.deps import get_conversation_service, get_current_user, get_optional_user
from backend.schemas import ChatResponse, TTSReplayResponse, TranscriptResponse

router = APIRouter(tags=["voice"])


@router.post("/tts", response_model=TTSReplayResponse)
async def tts_replay(
    text: str = Form(...),
    conversation_id: int = Form(...),
    user=Depends(get_current_user),
    conversation_service=Depends(get_conversation_service),
) -> TTSReplayResponse:
    try:
        response = await conversation_service.synthesize_replay(
            conversation_id=conversation_id,
            user_id=user["id"],
            text=text,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return TTSReplayResponse.model_validate(response)


@router.post("/transcribe", response_model=TranscriptResponse)
async def transcribe(
    request: Request,
    audio: UploadFile = File(...),
    conversation_id: int | None = Form(default=None),
    user=Depends(get_optional_user),
    conversation_service=Depends(get_conversation_service),
) -> TranscriptResponse:
    started_at = time.monotonic()
    audio_bytes = await audio.read()
    if len(audio_bytes) < 1000:
        return TranscriptResponse(transcript="", error="audio too short")

    try:
        transcript = await conversation_service.transcribe_for_conversation(
            audio_bytes=audio_bytes,
            filename=audio.filename or "audio.webm",
            content_type=audio.content_type or "audio/webm",
            conversation_id=conversation_id,
            user=user,
        )
    except Exception as exc:
        request.app.state.logger.error("ASR error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    elapsed_ms = round((time.monotonic() - started_at) * 1000)
    request.app.state.logger.info("ASR (%sms): %r", elapsed_ms, transcript)
    return TranscriptResponse(transcript=transcript)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    transcript: str = Form(...),
    conversation_id: int = Form(...),
    user=Depends(get_current_user),
    conversation_service=Depends(get_conversation_service),
) -> ChatResponse:
    try:
        response = await conversation_service.build_chat_response(
            conversation_id=conversation_id,
            user_id=user["id"],
            transcript=transcript,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse.model_validate(response)
