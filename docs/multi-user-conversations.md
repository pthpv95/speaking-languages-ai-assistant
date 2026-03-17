# Multi-User Support with Conversation Threads

## Date: 2026-03-17

## Overview
Transformed the single-user MVP (in-memory history, global state) into a multi-user app with persistent conversation threads using SQLite.

## Architecture

### Database (voice-ai/db.py)
- **SQLite** via `aiosqlite` for async access
- WAL journal mode for concurrent read performance
- 3 tables: `users`, `conversations`, `messages`
- Each conversation stores its own `language` and `tone` settings
- Messages linked to conversations via foreign key with CASCADE delete

### Backend Changes (voice-ai/main.py)
- **Removed**: global `history` list, `current_language`, `current_tone` globals
- **Removed endpoints**: `POST /language`, `POST /tone`, `DELETE /history`
- **Added**: `@app.on_event("startup")` initializes DB tables
- **Added**: `get_user(request)` dependency extracts `X-Username` header
- **Added REST API**:
  - `POST /api/users` — create/lookup user by username
  - `GET /api/conversations` — list user's conversations (newest first)
  - `POST /api/conversations` — create new conversation with language/tone
  - `GET /api/conversations/{id}` — get conversation + all messages
  - `PATCH /api/conversations/{id}` — update title, language, or tone
- **Modified**: `/chat` requires `conversation_id`, loads last 10 messages from DB, saves user+assistant messages, auto-titles from first user message
- **Modified**: `/transcribe` accepts optional `conversation_id` to determine ASR language
- **Refactored**: `get_profile()` and `get_tone_config()` are now pure functions accepting `(language)` and `(language, tone)` params
- **Refactored**: `synthesize_audio()` accepts `language, tone` params

### Frontend Changes (voice-ai/index.html)
- **Layout**: Flex row with sidebar (280px) + main area
- **Username modal**: Overlay on first visit, stores username in localStorage
- **Sidebar**: Lists conversations with title, language badge, relative time
- **Conversation switching**: Click loads messages from API, updates lang/tone UI
- **Inline title editing**: Double-click to rename
- **`api()` wrapper**: Adds `X-Username` header to all requests, handles 401
- **Mobile**: Sidebar hidden by default, hamburger toggle, overlay

### User identification
Simple `X-Username` header — no passwords, no tokens. Suitable for MVP/demo. Production would need proper authentication.

## Key decisions
1. **Per-conversation settings**: Language and tone are stored per conversation, not globally. This lets users have English and Chinese conversations simultaneously.
2. **Auto-title**: First user message (truncated to 50 chars) becomes the conversation title automatically.
3. **No delete endpoint**: Omitted per plan — can be added later.
4. **History limit**: Last 10 messages sent to LLM for context (same as before).
