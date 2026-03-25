"""
WebSocket streaming pipeline — ASR → LLM (token streaming) → TTS.
"""

import base64
import io
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import LLM_MAX_TOKENS, LLM_MODEL, LLM_TEMPERATURE, RECENT_MESSAGES
from app.dependencies import async_groq_client
from app.llm import build_system_prompt, maybe_summarize
from app.profiles import get_profile
from app.tones import get_tone_config
from app.tts import synthesize_audio
import db

logger = logging.getLogger("voice_ai")

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    """
    Protocol:
      Client → Server:
        text: {"type":"start","conversation_id":123,"username":"alice"}
        binary: audio chunks (while recording)
        text: {"type":"stop"}
      Server → Client:
        text: {"type":"transcript","text":"..."}
        text: {"type":"token","text":"..."} (streamed LLM tokens)
        text: {"type":"sentence","text":"full reply","index":0}
        text: {"type":"audio","audio_base64":"...","audio_mime":"...","index":0}
        text: {"type":"done","reply":"...","llm_ms":...,"tts_ms":...,"total_ms":...}
    """
    await websocket.accept()
    audio_chunks: list[bytes] = []
    conversation_id: int | None = None
    username: str = ""

    try:
        while True:
            msg = await websocket.receive()

            # Binary frame: audio chunk
            if "bytes" in msg and msg["bytes"]:
                audio_chunks.append(msg["bytes"])
                continue

            # Text frame: JSON command
            if "text" not in msg:
                continue

            data = json.loads(msg["text"])
            msg_type = data.get("type")

            if msg_type == "start":
                audio_chunks.clear()
                conversation_id = data.get("conversation_id")
                username = data.get("username", "")
                continue

            if msg_type != "stop":
                continue

            # User stopped recording — run the pipeline
            if not conversation_id or not username:
                await websocket.send_json(
                    {"type": "error", "detail": "missing conversation_id or username"}
                )
                continue

            await _run_pipeline(websocket, audio_chunks, conversation_id, username)
            audio_chunks.clear()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


async def _run_pipeline(
    websocket: WebSocket,
    audio_chunks: list[bytes],
    conversation_id: int,
    username: str,
) -> None:
    """Execute the full ASR → LLM → TTS pipeline over WebSocket."""
    t0 = time.monotonic()

    # Look up user + conversation
    user = await db.get_or_create_user(username)
    conv = await db.get_conversation(conversation_id, user["id"])
    if not conv:
        await websocket.send_json({"type": "error", "detail": "conversation not found"})
        return

    language = conv["language"]
    tone = conv["tone"]
    profile = get_profile(language)

    # Step 1: ASR
    full_audio = b"".join(audio_chunks)
    if len(full_audio) < 1000:
        await websocket.send_json({"type": "error", "detail": "audio too short"})
        return

    t_asr = time.monotonic()
    try:
        result = await async_groq_client.audio.transcriptions.create(
            model=profile["asr_model"],
            file=("audio.webm", io.BytesIO(full_audio), "audio/webm"),
            language=profile["whisper_lang"],
            response_format="json",
            temperature=0.0,
        )
        transcript = result.text.strip()
    except Exception as e:
        logger.error(f"WS ASR error: {e}")
        await websocket.send_json({"type": "error", "detail": f"ASR failed: {e}"})
        return

    asr_ms = (time.monotonic() - t_asr) * 1000
    logger.info(f"WS [ASR] {asr_ms:.0f}ms | transcript: {transcript!r}")

    if not transcript:
        await websocket.send_json({"type": "error", "detail": "nothing heard"})
        return

    await websocket.send_json({"type": "transcript", "text": transcript, "asr_ms": round(asr_ms)})

    # Save user message + auto-title
    await db.add_message(conversation_id, "user", transcript)
    if conv["title"] == "New conversation":
        title = transcript[:50].strip() + ("..." if len(transcript) > 50 else "")
        await db.update_conversation_title(conversation_id, title)

    # Build LLM messages
    all_messages = await db.get_all_messages(conversation_id)
    user_turn_count = sum(1 for m in all_messages if m["role"] == "user")

    tone_cfg = get_tone_config(language, tone)
    system_prompt = build_system_prompt(tone_cfg["system_prompt"], user_turn_count)
    messages = [{"role": "system", "content": system_prompt}]

    summary = await maybe_summarize(conversation_id, conv)
    if summary:
        messages.append({"role": "system", "content": f"Conversation so far: {summary}"})

    recent = await db.get_messages(conversation_id, limit=RECENT_MESSAGES)
    messages += [{"role": m["role"], "content": m["content"]} for m in recent]

    # Step 2: Stream LLM tokens
    t_llm = time.monotonic()
    full_reply = ""

    try:
        stream = await async_groq_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if not delta:
                continue
            full_reply += delta
            await websocket.send_json({"type": "token", "text": delta})
    except Exception as e:
        logger.error(f"WS LLM error: {e}")
        await websocket.send_json({"type": "error", "detail": f"LLM failed: {e}"})
        return

    llm_ms = (time.monotonic() - t_llm) * 1000
    logger.info(f"WS [LLM] {llm_ms:.0f}ms | reply: {full_reply[:80]!r}")

    full_reply = full_reply.strip()
    await websocket.send_json({"type": "sentence", "text": full_reply, "index": 0})

    # Step 3: TTS the full reply
    tts_ms = 0.0
    if full_reply:
        t_tts = time.monotonic()
        try:
            audio_bytes, audio_mime = await synthesize_audio(full_reply, language, tone)
            tts_ms = (time.monotonic() - t_tts) * 1000
            logger.info(f"WS [TTS] {tts_ms:.0f}ms | audio: {len(audio_bytes)} bytes")

            await websocket.send_json({
                "type": "audio",
                "audio_base64": base64.b64encode(audio_bytes).decode(),
                "audio_mime": audio_mime,
                "index": 0,
            })
        except Exception as e:
            logger.warning(f"WS TTS error: {e}")

    # Save assistant reply
    await db.add_message(conversation_id, "assistant", full_reply)

    total_ms = (time.monotonic() - t0) * 1000
    logger.info(
        f"WS [TOTAL] {total_ms:.0f}ms | "
        f"ASR={asr_ms:.0f}ms LLM={llm_ms:.0f}ms TTS={tts_ms:.0f}ms"
    )

    await websocket.send_json({
        "type": "done",
        "reply": full_reply,
        "asr_ms": round(asr_ms),
        "llm_ms": round(llm_ms),
        "tts_ms": round(tts_ms),
        "total_ms": round(total_ms),
    })
