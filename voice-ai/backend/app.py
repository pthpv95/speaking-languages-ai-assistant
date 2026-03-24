from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_conversations import router as conversations_router
from backend.api.routes_public import router as public_router
from backend.api.routes_push import router as push_router
from backend.api.routes_realtime import router as realtime_router
from backend.api.routes_voice import router as voice_router
from backend.core.config import configure_logging, get_settings
from backend.repositories.db import SQLiteRepository
from backend.services.ai import AIService
from backend.services.conversation import ConversationService
from backend.services.push import PushService
from backend.services.tts import TTSService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger = configure_logging()

    repository = SQLiteRepository(settings.db_path)
    await repository.init_db()
    logger.info("Database initialized")

    ai_service = AIService(settings)
    tts_service = TTSService(settings, ai_service, logger)
    conversation_service = ConversationService(settings, repository, ai_service, tts_service, logger)
    push_service = PushService(settings, logger)

    app.state.settings = settings
    app.state.logger = logger
    app.state.repository = repository
    app.state.ai_service = ai_service
    app.state.tts_service = tts_service
    app.state.conversation_service = conversation_service
    app.state.push_service = push_service

    asyncio.get_running_loop().run_in_executor(None, tts_service.preload_piper_voices)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Voice AI MVP", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def log_request_timing(request: Request, call_next):
        started_at = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.monotonic() - started_at) * 1000)
            logger = getattr(request.app.state, "logger", None)
            if logger:
                logger.exception("HTTP %s %s failed in %sms", request.method, request.url.path, elapsed_ms)
            raise

        elapsed_ms = round((time.monotonic() - started_at) * 1000)
        logger = getattr(request.app.state, "logger", None)
        if logger:
            logger.info(
                "HTTP %s %s -> %s in %sms",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
        return response

    app.include_router(public_router)
    app.include_router(conversations_router)
    app.include_router(voice_router)
    app.include_router(realtime_router)
    app.include_router(push_router)
    return app


app = create_app()
