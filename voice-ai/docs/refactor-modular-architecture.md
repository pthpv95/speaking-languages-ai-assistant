# Refactor: Modular Architecture

## Problem
`main.py` was a 1147-line monolith containing config, language profiles, tone presets,
3 TTS engines, route handlers, WebSocket logic, and push notification management.

## Solution
Split into a well-structured FastAPI package following standard conventions.

## New Structure

```
voice-ai/
├── app/
│   ├── __init__.py
│   ├── main.py              # App factory, lifespan (replaces @on_event), router wiring
│   ├── config.py             # Env loading, all settings constants
│   ├── profiles.py           # Language profiles (ASR model, TTS voice, system prompt)
│   ├── tones.py              # Tone presets per language + get_tone_config()
│   ├── dependencies.py       # FastAPI Depends: get_current_user, Groq clients
│   ├── llm.py                # build_system_prompt(), maybe_summarize()
│   ├── tts/
│   │   ├── __init__.py       # Re-exports synthesize_audio, strip_for_tts
│   │   ├── engine.py         # TTS dispatcher + wav_to_mp3, strip_for_tts
│   │   ├── edge.py           # Edge TTS (Microsoft Azure, free)
│   │   ├── piper.py          # Piper TTS (local ONNX, offline)
│   │   └── groq.py           # Groq Orpheus TTS (API, English-only)
│   └── routers/
│       ├── __init__.py
│       ├── static.py         # /, /health, /config, PWA assets
│       ├── voice.py          # /transcribe, /chat, /tts
│       ├── conversations.py  # /api/users, /api/conversations CRUD
│       ├── websocket.py      # /ws/chat streaming pipeline
│       └── push.py           # VAPID keys, subscribe, send-push
├── db.py                     # Unchanged — async SQLite wrapper
├── index.html
├── .env
└── main_old.py               # Archived original (safe to delete)
```

## Key Improvements

1. **Lifespan** — replaced deprecated `@app.on_event("startup")` with `@asynccontextmanager` lifespan
2. **App factory** — `create_app()` function enables testing with different configs
3. **Dependency injection** — `get_current_user` used via `Depends()` instead of manual calls
4. **Router separation** — each domain has its own `APIRouter` with tags for OpenAPI grouping
5. **TTS abstraction** — each engine is a separate module; `engine.py` dispatches + handles fallbacks
6. **Single responsibility** — config, data constants, LLM logic, and routes each in their own module

## Entry Point Change
```
# Old
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# New
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Updated in: launch.json, start.sh, Dockerfile, docker-compose.yml

## Lessons Learned

- FastAPI's `lifespan` context manager is the modern replacement for `on_event("startup")`/`on_event("shutdown")` — it's cleaner and supports proper teardown
- Using `Depends()` for user extraction makes route signatures explicit about their requirements and enables easy mocking in tests
- Extracting the WebSocket pipeline's inner loop into `_run_pipeline()` makes the handler readable and testable independently
- Keeping `db.py` at the package root (not inside `app/`) avoids circular imports since both `app/` modules and standalone scripts reference it
