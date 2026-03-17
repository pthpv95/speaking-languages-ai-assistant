"""
Voice AI MVP Backend — Multi-user with conversation threads
  POST /transcribe             — audio blob -> transcript (Groq Whisper)
  POST /chat                   — transcript -> AI reply text + MP3 audio (Groq LLM + edge-tts)
  GET  /                       — serves index.html
  GET  /health                 — status check
  GET  /config                 — available languages & tones
  POST /api/users              — create/lookup user
  GET  /api/conversations      — list user's conversations
  POST /api/conversations      — create new conversation
  GET  /api/conversations/{id} — get conversation + messages
  PATCH /api/conversations/{id} — update title, language, or tone
"""

import asyncio, io, json, os, time, logging
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI

import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("voice_ai")

app = FastAPI(title="Voice AI MVP")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Load config from .env ──────────────────────────────────────────────────────

def _load_env():
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

_load_env()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not set — check .env")

# ── Language profiles ──────────────────────────────────────────────────────────

PROFILES = {
    "english": {
        "whisper_lang": "en",
        "asr_model":    "whisper-large-v3-turbo",
        "tts_voice":    "en-US-JennyNeural",
        "system_prompt": """
You are Jamie — a fun, witty English tutor from London. Lessons feel like chatting with a smart friend.

TURN 1: Greet warmly, ask their name, level (beginner/intermediate/advanced), and what they want to improve.

TURNS 2-3: Just chat naturally. No lesson yet — build rapport first.
  [REPLY] 1–2 sentences responding naturally. Match their energy.
  [PROMPT] One question to keep the conversation going.

TURN 4 AND BEYOND — use this structure:
  [REPLY]  1–2 sentences responding naturally. Match their energy.
  [LESSON] Include a lesson every 2-3 turns (NOT every turn). Pick ONE:
    Vocab: teach 1 word/expression in context
    Phrasal: 1 idiom natives actually use, e.g. "hang on = wait"
    Correction: "[their version]" -> "[native version]" + why
    Pronunciation: flag a tricky word with a phonetic hint
    Culture: one nugget about usage, origin, or native perception
  [PROMPT] One question to keep the conversation going.

  When no lesson: just [REPLY] + [PROMPT]. Keep it conversational.

RULES:
- MAX 3 sentences + 1 prompt. Be concise.
- Only include [LESSON] every 2-3 turns, not every response.
- Fix only ONE mistake per turn. Celebrate before correcting.
- Never lecture. Off-topic chat IS the lesson.
- Never repeat taught material — always something fresh.
- Adapt: beginner = simple + praise, advanced = nuance + challenge.
""",
    },
    "chinese": {
        "whisper_lang": "zh",
        "asr_model":    "whisper-large-v3-turbo",
        "tts_voice":    "zh-CN-XiaoxiaoNeural",
        "system_prompt": """
You are a friendly Mandarin coach. Reply in 1-2 short sentences in simplified Chinese.
Ask a follow-up question.
Only add a [LESSON] language tip every 2-3 turns, not every response. First 2-3 turns: just chat naturally, no lesson.
""",
    },
}

# ── TTS Tone presets ──────────────────────────────────────────────────────────

TONES = {
    "english": {
        "chill": {
            "label": "Chill Friend",
            "tts_engine": "groq",
            "voice": "diana",
            "speed": 1.0,
            "system_prompt": """
You are Max — a chill English buddy from California. Ultra relaxed, uses slang and contractions naturally ("y'know", "honestly"). Celebrates quietly ("nice, that's solid"), laughs off mistakes.

TURN 1: Casual intro, ask name, level, what they wanna work on. Like a DM, not a survey.

TURNS 2-3: Just vibe. [REPLY] + [PROMPT]. No lesson yet.

OTHER TURNS: [REPLY] 1–2 chill sentences -> [LESSON] (only every 2-3 turns, not every time) rotate: vocab / phrasal / correction / pronunciation / culture -> [PROMPT] casual question. When no lesson, just [REPLY] + [PROMPT].

RULES: Max 3 sentences + 1 prompt. Lessons every 2-3 turns only. One fix per turn. Never lecture. Never repeat taught material.
""",
        },
        "hype": {
            "label": "Hype Coach",
            "tts_engine": "groq",
            "voice": "hannah",
            "speed": 1.0,
            "system_prompt": """
You are Coach Sunny — an INCREDIBLY energetic English coach from New York. Celebrate EVERYTHING! ("Amazing!" "You crushed it!" "Let's GOOO!"). Mistakes are fun stepping stones.

TURN 1: Max-energy intro, ask name, level, what skill they want to crush.

TURNS 2-3: Just hype them up! [REPLY] + [PROMPT]. No lesson yet.

OTHER TURNS: [REPLY] 1–2 high-energy sentences, celebrate first -> [LESSON] (only every 2-3 turns, not every time) rotate: vocab / phrasal / correction / pronunciation / culture -> [PROMPT] exciting challenge. When no lesson, just [REPLY] + [PROMPT].

RULES: Max 3 sentences + 1 prompt. Lessons every 2-3 turns only. Celebrate before correcting. One fix per turn. Never repeat taught material.
""",
        },
        "storyteller": {
            "label": "Storyteller",
            "tts_engine": "groq",
            "voice": "austin",
            "speed": 1.0,
            "system_prompt": """
You are Grandpa Dave — a warm storyteller from Vermont. Everything reminds you of a story. You teach English by weaving lessons into tiny tales. Gentle humor, vivid imagery, dad jokes welcome.

TURN 1: Warm greeting, ask name, where they are in their "English journey", what adventure they want.

TURNS 2-3: Just tell stories and chat. [REPLY] + [PROMPT]. No lesson yet.

OTHER TURNS: [REPLY] 1–2 sentences with a mini-story woven in -> [LESSON] (only every 2-3 turns, not every time) rotate: vocab (through analogy) / phrasal (with origin) / correction (as "plot edit") / pronunciation / culture (story behind it) -> [PROMPT] invite them to continue the story. When no lesson, just [REPLY] + [PROMPT].

RULES: Max 3 sentences + 1 prompt. Lessons every 2-3 turns only. Micro-stories, not novels. One fix per turn. Never repeat taught material.
""",
        },
        "sassy": {
            "label": "Sassy Tutor",
            "tts_engine": "groq",
            "voice": "autumn",
            "speed": 1.0,
            "system_prompt": """
You are Mia — a sharp, witty, lovably sassy English tutor from Chicago. You roast AND help. Tease mistakes lovingly ("Oh honey, no. Let me save you."), backhanded compliments ("Look at you using past perfect! Who ARE you?!"). Never actually mean.

TURN 1: Sassy intro, ask name, level ("beginner, intermediate, or 'fluent but nobody told my grammar'?"), what to fix first.

TURNS 2-3: Just sass and chat. [REPLY] + [PROMPT]. No lesson yet.

OTHER TURNS: [REPLY] 1–2 sentences with humor -> [LESSON] (only every 2-3 turns, not every time) rotate: vocab (with sass) / phrasal (with attitude) / correction (roast then fix) / pronunciation / culture (spicy) -> [PROMPT] cheeky dare or question. When no lesson, just [REPLY] + [PROMPT].

RULES: Max 3 sentences + 1 prompt. Lessons every 2-3 turns only. One roast per turn, then move on. Never repeat taught material.
""",
        },
    },
    "chinese": {
        "chill": {
            "label": "Chill",
            "tts_engine": "edge",
            "voice": "zh-CN-XiaoxiaoNeural",
            "rate": "+0%", "pitch": "+0Hz",
            "system_prompt": """
You are a chill Mandarin buddy. Reply in 1-2 short sentences in simplified Chinese.
Ask a follow-up question. Keep it casual.
Only add a [LESSON] tip every 2-3 turns, not every response. First 2-3 turns: just chat, no lesson.
""",
        },
        "hype": {
            "label": "Hype",
            "tts_engine": "edge",
            "voice": "zh-CN-XiaoyiNeural",
            "rate": "+0%", "pitch": "+0Hz",
            "system_prompt": """
You are an energetic Mandarin coach! Celebrate everything! Reply in simplified Chinese.
1-2 short sentences. Ask a question. High energy!
Only add a [LESSON] tip every 2-3 turns, not every response. First 2-3 turns: just chat, no lesson.
""",
        },
        "storyteller": {
            "label": "Storyteller",
            "tts_engine": "edge",
            "voice": "zh-CN-YunyangNeural",
            "rate": "+0%", "pitch": "+0Hz",
            "system_prompt": """
You are a warm storyteller teaching Mandarin. Weave lessons into tiny tales.
Reply in simplified Chinese. 1-2 sentences. Ask a question.
Only add a [LESSON] tip every 2-3 turns, not every response. First 2-3 turns: just chat, no lesson.
""",
        },
        "sassy": {
            "label": "Sassy",
            "tts_engine": "edge",
            "voice": "zh-CN-YunxiNeural",
            "rate": "+0%", "pitch": "+0Hz",
            "system_prompt": """
You are a witty, lovably sassy Mandarin tutor. Tease mistakes lovingly.
Reply in simplified Chinese. 1-2 sentences. Ask a question.
Only add a [LESSON] tip every 2-3 turns, not every response. First 2-3 turns: just chat, no lesson.
""",
        },
    },
}

# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    await db.init_db()
    logger.info("Database initialized")

# ── Groq clients ──────────────────────────────────────────────────────────────

client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)

from openai import OpenAI as _SyncOpenAI
sync_client = _SyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)

MAX_HISTORY = 10


# ── User dependency ───────────────────────────────────────────────────────────

async def get_user(request: Request) -> dict:
    """Extract user from X-Username header. Returns {id, username}."""
    username = request.headers.get("x-username", "").strip()
    if not username:
        raise HTTPException(status_code=401, detail="X-Username header required")
    return await db.get_or_create_user(username)


# ── Pure functions for profile/tone lookup ─────────────────────────────────────

def get_profile(language: str) -> dict:
    return PROFILES.get(language, PROFILES["english"])

def get_tone_config(language: str, tone: str) -> dict:
    lang_tones = TONES.get(language, TONES["english"])
    return lang_tones.get(tone, list(lang_tones.values())[0])


# ── Helper: TTS synthesis ──────────────────────────────────────────────────────

def _wav_to_mp3(wav_bytes: bytes, speed: float = 1.0) -> bytes:
    """Convert WAV bytes to MP3 using lameenc."""
    import lameenc, wave
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        pcm = w.readframes(w.getnframes())
        rate = w.getframerate()
        channels = w.getnchannels()
    effective_rate = int(rate * speed)
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(128)
    encoder.set_in_sample_rate(effective_rate)
    encoder.set_channels(channels)
    encoder.set_quality(2)
    return encoder.encode(pcm) + encoder.flush()


def _strip_for_tts(text: str) -> str:
    """Extract spoken text for TTS — reads [REPLY] + [PROMPT], skips [LESSON]."""
    import re

    # Try structured markers first
    reply_match = re.search(r'\[REPLY\]\s*(.*?)(?=\[LESSON\]|\[PROMPT\]|$)', text, re.DOTALL | re.IGNORECASE)
    prompt_match = re.search(r'\[PROMPT\]\s*(.*?)$', text, re.DOTALL | re.IGNORECASE)
    lesson_match = re.search(r'\[LESSON\]\s*(.*?)(?=\[PROMPT\]|$)', text, re.DOTALL | re.IGNORECASE)
    # Chinese variants
    if not reply_match:
        reply_match = re.search(r'\[回复\]\s*(.*?)(?=\[课程\]|\[话题\]|$)', text, re.DOTALL)
    if not prompt_match:
        prompt_match = re.search(r'\[话题\]\s*(.*?)$', text, re.DOTALL)
    if not lesson_match:
        lesson_match = re.search(r'\[课程\]\s*(.*?)(?=\[话题\]|$)', text, re.DOTALL)

    parts = []
    if reply_match:
        parts.append(reply_match.group(1).strip())
    if prompt_match:
        parts.append(prompt_match.group(1).strip())

    if parts:
        result = ' '.join(parts)
    else:
        # No markers — strip emoji-prefixed lesson lines, keep everything else
        lines = text.split('\n')
        spoken = []
        for line in lines:
            s = line.strip()
            if s and not re.match(r'^[💬🗣✏️🔊🌍]', s):
                spoken.append(s)
        result = ' '.join(spoken)

    # Clean up any remaining markers
    result = re.sub(r'\[(?:REPLY|LESSON|PROMPT|回复|课程|话题)\]\s*', '', result)
    result = re.sub(r'[💬🗣✏️🔊🌍]\s*', '', result)
    return result.strip()


async def _tts_groq(text: str, voice: str, speed: float = 1.0) -> bytes:
    """Groq Orpheus TTS — very human-sounding, English only."""
    tts_text = _strip_for_tts(text)
    logger.info(f"TTS input: {len(tts_text)} chars -> {tts_text[:80]!r}")
    def _call():
        r = sync_client.audio.speech.create(
            model="canopylabs/orpheus-v1-english",
            voice=voice,
            input=tts_text,
            response_format="wav",
        )
        return r.read()
    wav_bytes = await asyncio.get_event_loop().run_in_executor(None, _call)
    return _wav_to_mp3(wav_bytes, speed=speed)


async def _tts_edge(text: str, voice: str, rate: str, pitch: str) -> bytes:
    """Edge TTS — good for non-English languages."""
    import edge_tts
    buf = io.BytesIO()
    tts = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    async for chunk in tts.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


EDGE_FALLBACK = {"voice": "en-US-AriaNeural", "rate": "+0%", "pitch": "+0Hz"}

async def synthesize_audio(text: str, language: str, tone: str) -> bytes:
    """Route to the right TTS engine based on conversation's language/tone."""
    tone_cfg = get_tone_config(language, tone)
    engine = tone_cfg.get("tts_engine", "edge")
    if engine == "groq":
        try:
            return await _tts_groq(text, tone_cfg["voice"], speed=tone_cfg.get("speed", 1.0))
        except Exception as e:
            if "rate_limit" in str(e) or "429" in str(e):
                logger.warning("Groq TTS rate-limited, falling back to edge-tts")
                return await _tts_edge(
                    text, EDGE_FALLBACK["voice"],
                    EDGE_FALLBACK["rate"], EDGE_FALLBACK["pitch"],
                )
            raise
    else:
        return await _tts_edge(
            text, tone_cfg["voice"],
            tone_cfg.get("rate", "+0%"), tone_cfg.get("pitch", "+0Hz"),
        )


# ── On-demand TTS (replay) ─────────────────────────────────────────────────────

@app.post("/tts")
async def tts_replay(
    request: Request,
    text: str = Form(...),
    conversation_id: int = Form(...),
):
    """Re-synthesize TTS for a given text. Used by the replay button."""
    user = await get_user(request)
    conv = await db.get_conversation(conversation_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")

    t0 = time.monotonic()
    try:
        mp3_bytes = await synthesize_audio(text, conv["language"], conv["tone"])
    except Exception as e:
        logger.error(f"TTS replay error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    ms = (time.monotonic() - t0) * 1000
    logger.info(f"TTS replay ({ms:.0f}ms)")

    import base64
    return {"mp3_base64": base64.b64encode(mp3_bytes).decode(), "tts_ms": round(ms)}


# ── Static routes ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_path = Path(__file__).parent / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return HTMLResponse(html_path.read_text())


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/config")
async def config():
    """Return available languages and tones (no current state — per-conversation now)."""
    available_tones = {}
    for lang, tones in TONES.items():
        available_tones[lang] = {k: v["label"] for k, v in tones.items()}
    return {
        "available_languages": list(PROFILES.keys()),
        "available_tones": available_tones,
    }


# ── User & Conversation API ──────────────────────────────────────────────────

@app.post("/api/users")
async def create_user(request: Request):
    """Create or lookup user. Body: {"username": "..."}"""
    body = await request.json()
    username = body.get("username", "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username required")
    user = await db.get_or_create_user(username)
    return user


@app.get("/api/conversations")
async def list_conversations(request: Request):
    user = await get_user(request)
    convs = await db.list_conversations(user["id"])
    return convs


@app.post("/api/conversations")
async def create_conversation(request: Request):
    user = await get_user(request)
    body = await request.json()
    language = body.get("language", "chinese")
    tone = body.get("tone", "hype")
    conv = await db.create_conversation(user["id"], language, tone)
    return conv


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: int, request: Request):
    user = await get_user(request)
    conv = await db.get_conversation(conv_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    messages = await db.get_all_messages(conv_id)
    return {**conv, "messages": messages}


@app.patch("/api/conversations/{conv_id}")
async def update_conversation(conv_id: int, request: Request):
    user = await get_user(request)
    conv = await db.get_conversation(conv_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    body = await request.json()
    if "title" in body:
        await db.update_conversation_title(conv_id, body["title"])
    if "language" in body or "tone" in body:
        await db.update_conversation_settings(
            conv_id,
            language=body.get("language"),
            tone=body.get("tone"),
        )
    updated = await db.get_conversation(conv_id, user["id"])
    return updated


# ── Core voice endpoints ──────────────────────────────────────────────────────

@app.post("/transcribe")
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
        user = await get_user(request)
        conv = await db.get_conversation(conversation_id, user["id"])
        if conv:
            language = conv["language"]

    profile = get_profile(language)
    try:
        result = await client.audio.transcriptions.create(
            model=profile["asr_model"],
            file=(audio.filename or "audio.webm", io.BytesIO(audio_bytes), audio.content_type or "audio/webm"),
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


import re as _re

def _build_system_prompt(base_prompt: str, user_turn_count: int) -> str:
    """Dynamically strip [LESSON] instructions on non-lesson turns.
    Lessons appear on turns 4, 6, 9, 12, ... (roughly every 2-3 turns after turn 3).
    """
    is_lesson_turn = user_turn_count >= 4 and (user_turn_count % 3 == 1 or user_turn_count % 3 == 0)

    if is_lesson_turn:
        return base_prompt

    # Strip lesson-related lines from the prompt so LLM won't generate one
    # Remove entire [LESSON] section and references to it
    prompt = base_prompt
    # Remove multi-line [LESSON] blocks
    prompt = _re.sub(
        r'\[LESSON\].*?(?=\[PROMPT\]|\n\n[A-Z]|\Z)',
        '', prompt, flags=_re.DOTALL | _re.IGNORECASE
    )
    prompt = _re.sub(
        r'\[课程\].*?(?=\[话题\]|\n\n|\Z)',
        '', prompt, flags=_re.DOTALL
    )
    # Remove lines mentioning lesson frequency
    prompt = _re.sub(r'(?m)^.*(?:lesson|LESSON|课程).*every.*turns?.*$', '', prompt)
    prompt = _re.sub(r'(?m)^.*Only.*\[LESSON\].*$', '', prompt)
    prompt = _re.sub(r'(?m)^.*include.*lesson.*$', '', prompt, flags=_re.IGNORECASE)
    # Add explicit no-lesson instruction
    prompt += "\n\nIMPORTANT: This turn is a CONVERSATION-ONLY turn. Do NOT include any [LESSON] or teaching tip. Just reply naturally with [REPLY] and [PROMPT]."

    return prompt


@app.post("/chat")
async def chat(
    request: Request,
    transcript: str = Form(...),
    conversation_id: int = Form(...),
):
    """Accept transcript, get LLM reply + TTS audio. Requires conversation_id."""
    if not transcript.strip():
        raise HTTPException(status_code=400, detail="empty transcript")

    user = await get_user(request)
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

    # Build message history from DB
    history = await db.get_messages(conversation_id, limit=MAX_HISTORY)
    all_messages = await db.get_all_messages(conversation_id)
    user_turn_count = sum(1 for m in all_messages if m["role"] == "user")

    tone_cfg = get_tone_config(language, tone)
    system_prompt = _build_system_prompt(tone_cfg["system_prompt"], user_turn_count)
    messages = [{"role": "system", "content": system_prompt}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]

    # LLM call
    t_llm = time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=200,
            temperature=0.7,
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
        mp3_bytes = await synthesize_audio(reply, language, tone)
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    tts_ms   = (time.monotonic() - t_tts) * 1000
    total_ms = (time.monotonic() - t0) * 1000

    logger.info(f"LLM={llm_ms:.0f}ms | TTS={tts_ms:.0f}ms | total={total_ms:.0f}ms")

    import base64
    return {
        "reply":      reply,
        "mp3_base64": base64.b64encode(mp3_bytes).decode(),
        "llm_ms":     round(llm_ms),
        "tts_ms":     round(tts_ms),
        "total_ms":   round(total_ms),
    }


# ── PWA: Static files ──────────────────────────────────────────────────────────

@app.get("/manifest.json")
async def serve_manifest():
    return FileResponse(Path(__file__).parent / "manifest.json", media_type="application/manifest+json")

@app.get("/sw.js")
async def serve_sw():
    return FileResponse(Path(__file__).parent / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})

@app.get("/icon-192.png")
async def serve_icon_192():
    return FileResponse(Path(__file__).parent / "icon-192.png", media_type="image/png")

@app.get("/icon-512.png")
async def serve_icon_512():
    return FileResponse(Path(__file__).parent / "icon-512.png", media_type="image/png")


# ── PWA: Push Notifications ───────────────────────────────────────────────────

def _get_vapid_keys():
    pub_path = Path(__file__).parent / ".vapid_public_key.json"
    pem_path = Path(__file__).parent / ".vapid_private.pem"
    if pub_path.exists() and pem_path.exists():
        pub_data = json.loads(pub_path.read_text())
        return {"private_pem_path": str(pem_path), "public_key": pub_data["public_key"]}
    from py_vapid import Vapid
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    import base64
    vapid = Vapid()
    vapid.generate_keys()
    raw_pub = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    public_key = base64.urlsafe_b64encode(raw_pub).decode().rstrip("=")
    pem_path.write_bytes(vapid.private_pem())
    pub_path.write_text(json.dumps({"public_key": public_key}))
    return {"private_pem_path": str(pem_path), "public_key": public_key}

VAPID_KEYS = _get_vapid_keys()
_SUBS_FILE = Path(__file__).parent / ".push_subs.json"

def _load_subs() -> list[dict]:
    if _SUBS_FILE.exists():
        return json.loads(_SUBS_FILE.read_text())
    return []

def _save_subs(subs: list[dict]):
    _SUBS_FILE.write_text(json.dumps(subs))

push_subscriptions: list[dict] = _load_subs()
logger.info(f"Loaded {len(push_subscriptions)} push subscription(s)")


@app.get("/vapid-public-key")
async def vapid_public_key():
    return {"public_key": VAPID_KEYS["public_key"]}

@app.post("/subscribe")
async def subscribe(request: Request):
    sub = await request.json()
    endpoints = {s.get("endpoint") for s in push_subscriptions}
    if sub.get("endpoint") not in endpoints:
        push_subscriptions.append(sub)
        _save_subs(push_subscriptions)
    return {"status": "subscribed"}

@app.post("/unsubscribe")
async def unsubscribe(request: Request):
    sub = await request.json()
    push_subscriptions[:] = [s for s in push_subscriptions if s.get("endpoint") != sub.get("endpoint")]
    _save_subs(push_subscriptions)
    return {"status": "unsubscribed"}

@app.post("/send-push")
async def send_push(request: Request):
    from pywebpush import webpush, WebPushException
    data = await request.json()
    payload = json.dumps({
        "title": data.get("title", "Voice AI Coach"),
        "body": data.get("body", "Time to practice! Your language coach is ready."),
    })
    sent = 0
    for sub in push_subscriptions[:]:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_KEYS["private_pem_path"],
                vapid_claims={"sub": "mailto:voiceai@example.com"},
            )
            sent += 1
        except WebPushException as e:
            if hasattr(e, 'response') and e.response is not None and e.response.status_code in (404, 410):
                push_subscriptions.remove(sub)
                _save_subs(push_subscriptions)
        except Exception as e:
            logger.warning(f"Push error: {type(e).__name__}: {e}")
    return {"sent": sent, "total": len(push_subscriptions)}
