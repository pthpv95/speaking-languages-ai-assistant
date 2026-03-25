"""
Core voice endpoints — transcribe, chat, and TTS replay.
"""

import base64
import io
import logging
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from app.config import LLM_MAX_TOKENS, LLM_MODEL, LLM_TEMPERATURE, RECENT_MESSAGES
from app.dependencies import async_groq_client, get_current_user
from app.llm import build_system_prompt, maybe_summarize
from app.profiles import get_profile
from app.tones import get_tone_config
from app.tts import synthesize_audio
import db

logger = logging.getLogger("voice_ai")

router = APIRouter(tags=["voice"])


@router.post("/transcribe")
async def transcribe(
    request: Request,
    audio: UploadFile = File(...),
    conversation_id: int = Form(None),
):
    """Accept audio blob, send to Groq Whisper, return transcript."""
    t0 = time.monotonic()
    audio_bytes = await audio.read()

    if len(audio_bytes) < 1000:
        return JSONResponse({"transcript": "", "error": "audio too short"})

    # Determine language from conversation or default
    language = "chinese"
    if conversation_id:
        user = await get_current_user(request)
        conv = await db.get_conversation(conversation_id, user["id"])
        if conv:
            language = conv["language"]

    profile = get_profile(language)
    try:
        result = await async_groq_client.audio.transcriptions.create(
            model=profile["asr_model"],
            file=(
                audio.filename or "audio.webm",
                io.BytesIO(audio_bytes),
                audio.content_type or "audio/webm",
            ),
            language=profile["whisper_lang"],
            response_format="json",
            temperature=0.0,
        )
        transcript = result.text.strip()
        ms = (time.monotonic() - t0) * 1000
        logger.info(f"ASR ({ms:.0f}ms): {transcript!r}")
        return {"transcript": transcript}
    except Exception as e:
        logger.error(f"ASR error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def chat(
    transcript: str = Form(...),
    conversation_id: int = Form(...),
    user: dict = Depends(get_current_user),
):
    """Accept transcript, get LLM reply + TTS audio. Requires conversation_id."""
    if not transcript.strip():
        raise HTTPException(status_code=400, detail="empty transcript")

    conv = await db.get_conversation(conversation_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")

    language = conv["language"]
    tone = conv["tone"]
    t0 = time.monotonic()

    # Save user message
    await db.add_message(conversation_id, "user", transcript)

    # Auto-set title from first user message
    if conv["title"] == "New conversation":
        title = transcript[:50].strip()
        if len(transcript) > 50:
            title += "..."
        await db.update_conversation_title(conversation_id, title)

    # Build compacted message history
    all_messages = await db.get_all_messages(conversation_id)
    user_turn_count = sum(1 for m in all_messages if m["role"] == "user")

    tone_cfg = get_tone_config(language, tone)
    system_prompt = build_system_prompt(tone_cfg["system_prompt"], user_turn_count)
    messages = [{"role": "system", "content": system_prompt}]

    # Summarize older messages if conversation is long
    summary = await maybe_summarize(conversation_id, conv)
    if summary:
        messages.append({"role": "system", "content": f"Conversation so far: {summary}"})

    # Append recent messages verbatim
    recent = await db.get_messages(conversation_id, limit=RECENT_MESSAGES)
    messages += [{"role": m["role"], "content": m["content"]} for m in recent]

    # LLM call
    t_llm = time.monotonic()
    try:
        resp = await async_groq_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    llm_ms = (time.monotonic() - t_llm) * 1000
    logger.info(f"LLM ({llm_ms:.0f}ms): {reply[:80]!r}")

    # Save assistant message
    await db.add_message(conversation_id, "assistant", reply)

    # TTS synthesis
    t_tts = time.monotonic()
    try:
        audio_bytes, audio_mime = await synthesize_audio(reply, language, tone)
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    tts_ms = (time.monotonic() - t_tts) * 1000
    total_ms = (time.monotonic() - t0) * 1000
    logger.info(f"LLM={llm_ms:.0f}ms | TTS={tts_ms:.0f}ms | total={total_ms:.0f}ms")

    return {
        "reply": reply,
        "audio_base64": base64.b64encode(audio_bytes).decode(),
        "audio_mime": audio_mime,
        "llm_ms": round(llm_ms),
        "tts_ms": round(tts_ms),
        "total_ms": round(total_ms),
    }


@router.post("/tts")
async def tts_replay(
    text: str = Form(...),
    conversation_id: int = Form(...),
    user: dict = Depends(get_current_user),
):
    """Re-synthesize TTS for a given text. Used by the replay button."""
    conv = await db.get_conversation(conversation_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")

    t0 = time.monotonic()
    try:
        audio_bytes, audio_mime = await synthesize_audio(text, conv["language"], conv["tone"])
    except Exception as e:
        logger.error(f"TTS replay error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    ms = (time.monotonic() - t0) * 1000
    logger.info(f"TTS replay ({ms:.0f}ms)")

    return {
        "audio_base64": base64.b64encode(audio_bytes).decode(),
        "audio_mime": audio_mime,
        "tts_ms": round(ms),
    }
