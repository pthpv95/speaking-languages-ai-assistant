from __future__ import annotations

import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    audio_chunks: list[bytes] = []
    conversation_id: int | None = None
    username = ""

    conversation_service = websocket.app.state.conversation_service
    logger = websocket.app.state.logger

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                audio_chunks.append(message["bytes"])
                continue

            if "text" not in message:
                continue

            payload = json.loads(message["text"])
            message_type = payload.get("type")

            if message_type == "start":
                audio_chunks.clear()
                conversation_id = payload.get("conversation_id")
                username = payload.get("username", "")
                continue

            if message_type != "stop":
                continue

            if not conversation_id or not username:
                await websocket.send_json({"type": "error", "detail": "missing conversation_id or username"})
                continue

            flow_started_at = time.monotonic()
            event_count = 0
            try:
                async for event in conversation_service.stream_chat_events(
                    conversation_id=conversation_id, username=username, audio_bytes=b"".join(audio_chunks)
                ):
                    event_count += 1
                    await websocket.send_json(event)
                logger.info(
                    "WS /ws/chat conversation_id=%s username=%s events=%s completed in %sms",
                    conversation_id,
                    username,
                    event_count,
                    round((time.monotonic() - flow_started_at) * 1000),
                )
            except Exception as exc:
                logger.error("WebSocket pipeline error: %s", exc)
                detail = getattr(exc, "detail", str(exc))
                await websocket.send_json({"type": "error", "detail": detail})
                logger.exception(
                    "WS /ws/chat conversation_id=%s username=%s failed in %sms",
                    conversation_id,
                    username,
                    round((time.monotonic() - flow_started_at) * 1000),
                )
                audio_chunks.clear()
                continue

            audio_chunks.clear()
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
