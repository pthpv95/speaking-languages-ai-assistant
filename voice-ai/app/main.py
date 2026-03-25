"""
Voice AI MVP — application factory.

Entry point: uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.tones import TONES
from app.tts.piper import preload_voices
import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("voice_ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — init DB, preload TTS voices."""
    await db.init_db()
    logger.info("Database initialized")

    # Collect all tone configs that use Piper and preload in background
    piper_configs = [
        cfg
        for lang_tones in TONES.values()
        for cfg in lang_tones.values()
        if cfg.get("tts_engine") == "piper"
    ]
    asyncio.get_event_loop().run_in_executor(None, preload_voices, piper_configs)

    yield  # app is running

    logger.info("Shutting down")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    application = FastAPI(title="Voice AI MVP", lifespan=lifespan)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from app.routers import conversations, push, static, voice, websocket

    application.include_router(static.router)
    application.include_router(voice.router)
    application.include_router(conversations.router)
    application.include_router(websocket.router)
    application.include_router(push.router)

    return application


app = create_app()
