"""
Voice AI MVP Backend
  POST /transcribe  — audio blob → transcript (Groq Whisper)
  POST /chat        — transcript → AI reply text + MP3 audio (Groq LLM + edge-tts)
  GET  /            — serves index.html
  GET  /health      — status check
"""

import asyncio, io, os, time, logging
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("voice_ai")

app = FastAPI(title="Voice AI MVP")
app.add_middleware(CORSMiddleware, allow_origins=["*"])

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
LANGUAGE     = os.environ.get("LANGUAGE", "english").lower()

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not set — check .env")

# ── Language profiles ──────────────────────────────────────────────────────────

PROFILES = {
    "english": {
        "whisper_lang": "en",
        "asr_model":    "whisper-large-v3-turbo",
        "tts_voice":    "en-US-JennyNeural",
        "system_prompt": (
            "You are Alex, a friendly English speaking coach. "
            "Reply in 1-2 short sentences. "
            "After your reply add one tip in brackets, e.g. [Tip: 'gonna' = 'going to']. "
            "Ask a follow-up question to keep the conversation going."
        ),
    },
    "chinese": {
        "whisper_lang": "zh",
        "asr_model":    "whisper-large-v3-turbo",
        "tts_voice":    "zh-CN-XiaoxiaoNeural",
        "system_prompt": (
            "你是小美，一位亲切的普通话口语教练。"
            "用1-2句简短的中文回复。"
            "每次在末尾加语言提示，格式：【提示：...】"
            "主动提问，保持对话流畅。"
        ),
    },
    "spanish": {
        "whisper_lang": "es",
        "asr_model":    "whisper-large-v3-turbo",
        "tts_voice":    "es-ES-ElviraNeural",
        "system_prompt": (
            "Eres Elena, profesora de español. "
            "Responde en 1-2 oraciones cortas. "
            "Añade un consejo en corchetes, p.ej. [Consejo: ser vs estar]. "
            "Haz una pregunta de seguimiento."
        ),
    },
    "french": {
        "whisper_lang": "fr",
        "asr_model":    "whisper-large-v3-turbo",
        "tts_voice":    "fr-FR-DeniseNeural",
        "system_prompt": (
            "Tu es Claire, professeure de français. "
            "Réponds en 1-2 phrases courtes. "
            "Ajoute un conseil entre crochets, p.ex. [Conseil: tu vs vous]. "
            "Pose une question de suivi."
        ),
    },
    "japanese": {
        "whisper_lang": "ja",
        "asr_model":    "whisper-large-v3-turbo",
        "tts_voice":    "ja-JP-NanamiNeural",
        "system_prompt": (
            "あなたはさくら、日本語コーチです。"
            "1〜2文の短い日本語で返答してください。"
            "毎回ヒントを追加：【ヒント：...】"
            "フォローアップの質問をしてください。"
        ),
    },
}

current_language = LANGUAGE
profile = PROFILES.get(current_language, PROFILES["english"])
logger.info(f"Language: {current_language} | ASR: {profile['asr_model']} | TTS: {profile['tts_voice']}")

def get_profile():
    return PROFILES.get(current_language, PROFILES["english"])

# ── Groq client (shared) ───────────────────────────────────────────────────────

client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)

# In-memory conversation history (single user, resets on server restart)
history: list[dict] = []
MAX_HISTORY = 10   # keep last 10 messages to control token cost


# ── Helper: TTS synthesis ──────────────────────────────────────────────────────

async def synthesize_mp3(text: str) -> bytes:
    """Convert text to MP3 bytes using edge-tts."""
    import edge_tts
    buf = io.BytesIO()
    tts = edge_tts.Communicate(text, voice=get_profile()["tts_voice"])
    async for chunk in tts.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the single-page frontend."""
    html_path = Path(__file__).parent / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found — run Phase 5 first")
    return HTMLResponse(html_path.read_text())


@app.get("/health")
async def health():
    p = get_profile()
    return {
        "status":   "ok",
        "language": current_language,
        "asr":      p["asr_model"],
        "tts":      p["tts_voice"],
    }


@app.get("/config")
async def config():
    """Frontend calls this to know the active language and available languages."""
    p = get_profile()
    return {
        "language": current_language,
        "tts_voice": p["tts_voice"],
        "available": list(PROFILES.keys()),
    }


@app.post("/language")
async def switch_language(language: str = Form(...)):
    """Switch active language and clear conversation history."""
    global current_language
    lang = language.strip().lower()
    if lang not in PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown language: {lang}. Available: {list(PROFILES.keys())}")
    current_language = lang
    history.clear()
    p = get_profile()
    logger.info(f"Switched to: {lang} | ASR: {p['asr_model']} | TTS: {p['tts_voice']}")
    return {"language": lang, "tts_voice": p["tts_voice"]}


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """
    Accept an audio blob from the browser (webm/ogg/wav),
    send to Groq Whisper, return transcript text.
    """
    t0 = time.monotonic()
    audio_bytes = await audio.read()

    if len(audio_bytes) < 1000:
        return JSONResponse({"transcript": "", "error": "audio too short"})

    p = get_profile()
    try:
        result = await client.audio.transcriptions.create(
            model=p["asr_model"],
            file=(audio.filename or "audio.webm", io.BytesIO(audio_bytes), audio.content_type or "audio/webm"),
            language=p["whisper_lang"],
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


@app.post("/chat")
async def chat(transcript: str = Form(...)):
    """
    Accept transcript text, get LLM reply, synthesize TTS audio.
    Returns JSON: { reply, mp3_base64, asr_ms, llm_ms, tts_ms, total_ms }
    """
    if not transcript.strip():
        raise HTTPException(status_code=400, detail="empty transcript")

    t0 = time.monotonic()

    # Build message history
    history.append({"role": "user", "content": transcript})
    messages = [{"role": "system", "content": get_profile()["system_prompt"]}]
    messages += history[-MAX_HISTORY:]

    # LLM call
    t_llm = time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=150,        # short = fast + natural for conversation
            temperature=0.7,
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    llm_ms = (time.monotonic() - t_llm) * 1000
    logger.info(f"LLM ({llm_ms:.0f}ms): {reply[:80]!r}")
    history.append({"role": "assistant", "content": reply})

    # TTS synthesis
    t_tts = time.monotonic()
    try:
        mp3_bytes = await synthesize_mp3(reply)
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    tts_ms    = (time.monotonic() - t_tts) * 1000
    total_ms  = (time.monotonic() - t0) * 1000

    logger.info(f"LLM={llm_ms:.0f}ms | TTS={tts_ms:.0f}ms | total={total_ms:.0f}ms")

    import base64
    return {
        "reply":       reply,
        "mp3_base64":  base64.b64encode(mp3_bytes).decode(),
        "llm_ms":      round(llm_ms),
        "tts_ms":      round(tts_ms),
        "total_ms":    round(total_ms),
    }


@app.delete("/history")
async def clear_history():
    """Reset conversation history."""
    history.clear()
    return {"status": "cleared"}
