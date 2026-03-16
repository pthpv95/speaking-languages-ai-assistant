"""
Voice AI MVP Backend
  POST /transcribe  — audio blob → transcript (Groq Whisper)
  POST /chat        — transcript → AI reply text + MP3 audio (Groq LLM + edge-tts)
  GET  /            — serves index.html
  GET  /health      — status check
"""

import asyncio, io, json, os, time, logging
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
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
    """Generate VAPID keys once, store as PEM file + public key JSON."""
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
    # Avoid duplicates by endpoint
    endpoints = {s.get("endpoint") for s in push_subscriptions}
    if sub.get("endpoint") not in endpoints:
        push_subscriptions.append(sub)
        _save_subs(push_subscriptions)
        logger.info(f"Push subscription added ({len(push_subscriptions)} total)")
    return {"status": "subscribed"}


@app.post("/unsubscribe")
async def unsubscribe(request: Request):
    sub = await request.json()
    push_subscriptions[:] = [s for s in push_subscriptions if s.get("endpoint") != sub.get("endpoint")]
    _save_subs(push_subscriptions)
    logger.info(f"Push subscription removed ({len(push_subscriptions)} total)")
    return {"status": "unsubscribed"}


@app.post("/send-push")
async def send_push(request: Request):
    """Manual trigger to send a practice reminder to all subscribers."""
    from pywebpush import webpush, WebPushException
    data = await request.json()
    payload = json.dumps({
        "title": data.get("title", "Voice AI Coach"),
        "body": data.get("body", "Time to practice! Your language coach is ready."),
    })
    logger.info(f"Sending push to {len(push_subscriptions)} subscriber(s)")
    sent = 0
    for sub in push_subscriptions[:]:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_KEYS["private_pem_path"],
                vapid_claims={
                    "sub": "mailto:voiceai@example.com",
                },
            )
            sent += 1
            logger.info(f"Push sent OK")
        except WebPushException as e:
            logger.warning(f"Push failed: {e}")
            if hasattr(e, 'response') and e.response is not None and e.response.status_code in (404, 410):
                push_subscriptions.remove(sub)
                _save_subs(push_subscriptions)
        except Exception as e:
            logger.warning(f"Push error: {type(e).__name__}: {e}")
    return {"sent": sent, "total": len(push_subscriptions)}


@app.delete("/history")
async def clear_history():
    """Reset conversation history."""
    history.clear()
    return {"status": "cleared"}
