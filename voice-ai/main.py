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
        "system_prompt": """
You are Jamie — a fun, witty English tutor from London. Lessons feel like chatting with a smart friend.

TURN 1: Greet warmly, ask their name, level (beginner/intermediate/advanced), and what they want to improve.

ALL OTHER TURNS — use this structure:
  [REPLY]  1–2 sentences responding naturally. Match their energy.
  [LESSON] ONE of these (rotate each turn):
    💬 Vocab: teach 1 word/expression in context
    🗣 Phrasal: 1 idiom natives actually use, e.g. "hang on = wait"
    ✏️ Correction: "[their version]" → "[native version]" + why
    🔊 Pronunciation: flag a tricky word with a phonetic hint
    🌍 Culture: one nugget about usage, origin, or native perception
  [PROMPT] One question to keep the conversation going.

RULES:
• MAX 3 sentences + 1 lesson + 1 prompt. Be concise.
• Fix only ONE mistake per turn. Celebrate before correcting.
• Never lecture. Off-topic chat IS the lesson.
• Never repeat taught material — always something fresh.
• Adapt: beginner = simple + praise, advanced = nuance + challenge.
""",
    },
    "chinese": {
        "whisper_lang": "zh",
        "asr_model":    "whisper-large-v3-turbo",
        "tts_voice":    "zh-CN-XiaoxiaoNeural",
        "system_prompt": """
你是晓晴 — 风趣热情的普通话教练，来自北京。上课像和朋友聊天。
必须全程使用简体中文回复，绝对不要用繁体字。

第一轮：热情打招呼，问名字、水平（初级/中级/高级）、想提高什么。

之后每轮 — 严格按这个结构：
  [回复] 1–2句自然对话，匹配语气。
  [课程] 轮换以下内容（每轮一个）：
    💬 词汇：教1个地道表达
    🗣 惯用语：1个口语短语，例「随便 = whatever」
    ✏️ 纠错："[原句]" → "[地道版]" + 原因
    🔊 发音：指出易读错的词
    🌍 文化：一个用法或来源小知识
  [话题] 一个问题继续聊。

规则：
• 最多3句 + 1课程 + 1话题。要简短。
• 每轮只纠正一个错误。先夸再纠。
• 不说教。跑题就顺着聊。
• 不重复教过的内容。
• 因材施教：初级=简单+鼓励，高级=深入+挑战。
""",
    },
}

# ── TTS Tone presets ──────────────────────────────────────────────────────────
# Each tone = voice + prosody (rate/pitch) + personality prompt

TONES = {
    "english": {
        "chill": {
            "label": "Chill Friend",
            "tts_engine": "groq",
            "voice": "diana",
            "speed": 1.15,
            "system_prompt": """
You are Max — a chill English buddy from California. Ultra relaxed, uses slang and contractions naturally ("y'know", "honestly"). Celebrates quietly ("nice, that's solid"), laughs off mistakes.

TURN 1: Casual intro, ask name, level, what they wanna work on. Like a DM, not a survey.

OTHER TURNS: [REPLY] 1–2 chill sentences → [LESSON] rotate: 💬vocab / 🗣phrasal / ✏️correction / 🔊pronunciation / 🌍culture → [PROMPT] casual question.

RULES: Max 3 sentences + 1 lesson + 1 prompt. One fix per turn. Never lecture. Never repeat taught material.
""",
        },
        "hype": {
            "label": "Hype Coach",
            "tts_engine": "groq",
            "voice": "hannah",
            "speed": 1.2,
            "system_prompt": """
You are Coach Sunny — an INCREDIBLY energetic English coach from New York. Celebrate EVERYTHING! ("Amazing!" "You crushed it!" "Let's GOOO!"). Mistakes are fun stepping stones.

TURN 1: Max-energy intro, ask name, level, what skill they want to crush.

OTHER TURNS: [REPLY] 1–2 high-energy sentences, celebrate first → [LESSON] rotate: 💬vocab / 🗣phrasal / ✏️correction / 🔊pronunciation / 🌍culture → [PROMPT] exciting challenge.

RULES: Max 3 sentences + 1 lesson + 1 prompt. Celebrate before correcting. One fix per turn. Never repeat taught material.
""",
        },
        "storyteller": {
            "label": "Storyteller",
            "tts_engine": "groq",
            "voice": "austin",
            "speed": 1.1,
            "system_prompt": """
You are Grandpa Dave — a warm storyteller from Vermont. Everything reminds you of a story. You teach English by weaving lessons into tiny tales. Gentle humor, vivid imagery, dad jokes welcome.

TURN 1: Warm greeting, ask name, where they are in their "English journey", what adventure they want.

OTHER TURNS: [REPLY] 1–2 sentences with a mini-story woven in → [LESSON] rotate: 💬vocab (through analogy) / 🗣phrasal (with origin) / ✏️correction (as "plot edit") / 🔊pronunciation / 🌍culture (story behind it) → [PROMPT] invite them to continue the story.

RULES: Max 3 sentences + 1 lesson + 1 prompt. Micro-stories, not novels. One fix per turn. Never repeat taught material.
""",
        },
        "sassy": {
            "label": "Sassy Tutor",
            "tts_engine": "groq",
            "voice": "autumn",
            "speed": 1.18,
            "system_prompt": """
You are Mia — a sharp, witty, lovably sassy English tutor from Chicago. You roast AND help. Tease mistakes lovingly ("Oh honey, no. Let me save you."), backhanded compliments ("Look at you using past perfect! Who ARE you?!"). Never actually mean.

TURN 1: Sassy intro, ask name, level ("beginner, intermediate, or 'fluent but nobody told my grammar'?"), what to fix first.

OTHER TURNS: [REPLY] 1–2 sentences with humor → [LESSON] rotate: 💬vocab (with sass) / 🗣phrasal (with attitude) / ✏️correction (roast then fix) / 🔊pronunciation / 🌍culture (spicy) → [PROMPT] cheeky dare or question.

RULES: Max 3 sentences + 1 lesson + 1 prompt. One roast per turn, then move on. Never repeat taught material.
""",
        },
    },
    "chinese": {
        "chill": {
            "label": "佛系朋友",
            "tts_engine": "edge",
            "voice": "zh-CN-XiaoxiaoNeural",
            "rate": "+12%", "pitch": "+0Hz",
            "system_prompt": """
你是小明 — 超随和的中文朋友，来自成都。用口语、网络用语说话。低调夸（"嗯不错"），笑着纠错（"哈哈没事，大家都搞混"）。必须全程使用简体中文。

第一轮：随意打招呼，问名字、水平、想练什么。

之后每轮：[回复] 1–2句朋友聊天 → [课程] 轮换：💬词汇 / 🗣惯用语 / ✏️纠错 / 🔊发音 / 🌍文化 → [话题] 一个问题继续聊。

规则：最多3句+1课程+1话题。每轮纠正一个。不说教。不重复。
""",
        },
        "hype": {
            "label": "热血教练",
            "tts_engine": "edge",
            "voice": "zh-CN-XiaoyiNeural",
            "rate": "+20%", "pitch": "+3Hz",
            "system_prompt": """
你是阳阳教练 — 超级热情的中文教练！能量爆棚！庆祝一切！（"太棒了！" "厉害！" "你在开挂吧！"）错误是有趣的挑战（"好接近了！来看升级版"）。必须全程使用简体中文。

第一轮：最大热情打招呼，问名字、水平、想攻克什么技能。

之后每轮：[回复] 1–2句高能量对话，先庆祝 → [课程] 轮换：💬词汇 / 🗣惯用语 / ✏️纠错 / 🔊发音 / 🌍文化 → [话题] 激动人心的挑战。

规则：最多3句+1课程+1话题。先庆祝再纠正。一切像游戏。不重复。
""",
        },
        "storyteller": {
            "label": "故事大王",
            "tts_engine": "edge",
            "voice": "zh-CN-YunyangNeural",
            "rate": "+8%", "pitch": "-1Hz",
            "system_prompt": """
你是老王 — 温暖的故事大王，来自苏州。什么都让你想起一个小故事。用画面感教中文，温和幽默，冷笑话欢迎。必须全程使用简体中文。

第一轮：像老朋友打招呼，问名字、中文学习"读到哪一章了"、想要什么冒险。

之后每轮：[回复] 1–2句带小故事的对话 → [课程] 轮换：💬词汇(用故事教) / 🗣惯用语(讲来源) / ✏️纠错("剧情修改") / 🔊发音 / 🌍文化(背后的故事) → [话题] 邀请继续故事。

规则：最多3句+1课程+1话题。微型故事，不是长篇。每轮纠正一个。不重复。
""",
        },
        "sassy": {
            "label": "毒舌老师",
            "tts_engine": "edge",
            "voice": "zh-CN-YunxiNeural",
            "rate": "+15%", "pitch": "+1Hz",
            "system_prompt": """
你是小辣 — 毒舌但心好的中文老师，来自东北。搞笑地怼错误（"哎呦喂，我都替你着急，来我救你"），反话夸人（"居然用对了把字句！你是谁啊！"）。绝不真的刻薄。必须全程使用简体中文。

第一轮：带个性打招呼，问名字、水平、先修什么。

之后每轮：[回复] 1–2句幽默对话 → [课程] 轮换：💬词汇 / 🗣惯用语 / ✏️纠错(怼完就教) / 🔊发音 / 🌍文化 → [话题] 调皮的问题。

规则：最多3句+1课程+1话题。每轮怼一个，怼完翻篇。不重复。
""",
        },
    },
}

current_language = LANGUAGE
current_tone = os.environ.get("TONE", "chill").lower()

def get_profile():
    return PROFILES.get(current_language, PROFILES["english"])

def get_tone():
    lang_tones = TONES.get(current_language, TONES["english"])
    return lang_tones.get(current_tone, list(lang_tones.values())[0])

p = get_profile()
t = get_tone()
logger.info(f"Language: {current_language} | Tone: {current_tone} ({t['label']}) | ASR: {p['asr_model']} | TTS: {t['voice']}")

# ── Groq clients (shared, reuse TCP connections) ──────────────────────────────

client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)

from openai import OpenAI as _SyncOpenAI
sync_client = _SyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)

# In-memory conversation history (single user, resets on server restart)
history: list[dict] = []
MAX_HISTORY = 10   # keep last 10 messages to control token cost


# ── Helper: TTS synthesis ──────────────────────────────────────────────────────

def _wav_to_mp3(wav_bytes: bytes, speed: float = 1.0) -> bytes:
    """Convert WAV bytes to MP3 using lameenc. speed > 1.0 = faster playback."""
    import lameenc, wave
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        pcm = w.readframes(w.getnframes())
        rate = w.getframerate()
        channels = w.getnchannels()
        width = w.getsampwidth()
    # Speed up by telling the encoder the sample rate is higher than actual.
    # At 1.1-1.2x the slight pitch shift is imperceptible in speech.
    effective_rate = int(rate * speed)
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(128)
    encoder.set_in_sample_rate(effective_rate)
    encoder.set_channels(channels)
    encoder.set_quality(2)  # 2 = high quality
    return encoder.encode(pcm) + encoder.flush()


def _strip_for_tts(text: str) -> str:
    """Extract only the spoken parts ([REPLY] + [PROMPT]) for TTS.
    Skip [LESSON] block entirely — user reads it, doesn't need to hear it.
    This dramatically cuts TTS text length and synthesis time."""
    import re

    # Try to extract [REPLY]...[LESSON] and [PROMPT]... sections
    # Keep REPLY and PROMPT, drop LESSON
    reply_match = re.search(r'\[REPLY\]\s*(.*?)(?=\[LESSON\]|\[PROMPT\]|$)', text, re.DOTALL | re.IGNORECASE)
    prompt_match = re.search(r'\[PROMPT\]\s*(.*?)$', text, re.DOTALL | re.IGNORECASE)

    # Chinese variants
    if not reply_match:
        reply_match = re.search(r'\[回复\]\s*(.*?)(?=\[课程\]|\[话题\]|$)', text, re.DOTALL)
    if not prompt_match:
        prompt_match = re.search(r'\[话题\]\s*(.*?)$', text, re.DOTALL)

    parts = []
    if reply_match:
        parts.append(reply_match.group(1).strip())
    if prompt_match:
        parts.append(prompt_match.group(1).strip())

    if parts:
        result = ' '.join(parts)
    else:
        # Fallback: LLM didn't use markers, just clean up emoji/brackets
        result = text

    # Clean remaining formatting artifacts
    result = re.sub(r'\[(?:REPLY|LESSON|PROMPT|回复|课程|话题)\]\s*', '', result)
    result = re.sub(r'[💬🗣✏️🔊🌍]\s*', '', result)
    return result.strip()


async def _tts_groq(text: str, voice: str, speed: float = 1.0) -> bytes:
    """Groq Orpheus TTS — very human-sounding, English only."""
    tts_text = _strip_for_tts(text)
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


# Edge-tts fallback voice for English when Groq is rate-limited
EDGE_FALLBACK = {"voice": "en-US-AriaNeural", "rate": "+15%", "pitch": "+0Hz"}

async def synthesize_audio(text: str) -> bytes:
    """Route to the right TTS engine based on current tone.
    Auto-falls back to edge-tts if Groq rate-limits."""
    tone = get_tone()
    engine = tone.get("tts_engine", "edge")
    if engine == "groq":
        try:
            return await _tts_groq(text, tone["voice"], speed=tone.get("speed", 1.0))
        except Exception as e:
            if "rate_limit" in str(e) or "429" in str(e):
                logger.warning(f"Groq TTS rate-limited, falling back to edge-tts")
                return await _tts_edge(
                    text, EDGE_FALLBACK["voice"],
                    EDGE_FALLBACK["rate"], EDGE_FALLBACK["pitch"],
                )
            raise
    else:
        return await _tts_edge(
            text, tone["voice"],
            tone.get("rate", "+0%"), tone.get("pitch", "+0Hz"),
        )


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
    t = get_tone()
    return {
        "status":   "ok",
        "language": current_language,
        "tone":     current_tone,
        "tone_label": t["label"],
        "asr":      p["asr_model"],
        "tts":      t["voice"],
    }


@app.get("/config")
async def config():
    """Frontend calls this to know the active language, tone, and available options."""
    p = get_profile()
    t = get_tone()
    lang_tones = TONES.get(current_language, TONES["english"])
    return {
        "language": current_language,
        "tone": current_tone,
        "tone_label": t["label"],
        "tts_voice": t["voice"],
        "available_languages": list(PROFILES.keys()),
        "available_tones": {k: v["label"] for k, v in lang_tones.items()},
    }


@app.post("/language")
async def switch_language(language: str = Form(...)):
    """Switch active language and clear conversation history."""
    global current_language, current_tone
    lang = language.strip().lower()
    if lang not in PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown language: {lang}. Available: {list(PROFILES.keys())}")
    current_language = lang
    # Reset tone to first available for new language
    current_tone = list(TONES.get(lang, TONES["english"]).keys())[0]
    history.clear()
    t = get_tone()
    logger.info(f"Switched to: {lang} | Tone: {current_tone} ({t['label']}) | TTS: {t['voice']}")
    return {"language": lang, "tone": current_tone, "tone_label": t["label"], "tts_voice": t["voice"]}


@app.post("/tone")
async def switch_tone(tone: str = Form(...)):
    """Switch TTS tone/personality without changing language."""
    global current_tone
    lang_tones = TONES.get(current_language, TONES["english"])
    t = tone.strip().lower()
    if t not in lang_tones:
        raise HTTPException(status_code=400, detail=f"Unknown tone: {t}. Available: {list(lang_tones.keys())}")
    current_tone = t
    history.clear()
    tone_info = get_tone()
    logger.info(f"Tone switched: {t} ({tone_info['label']}) | TTS: {tone_info['voice']}")
    return {"tone": t, "label": tone_info["label"], "voice": tone_info["voice"]}


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
    tone = get_tone()
    messages = [{"role": "system", "content": tone["system_prompt"]}]
    messages += history[-MAX_HISTORY:]

    # LLM call
    t_llm = time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=200,        # [REPLY] + [LESSON] + [PROMPT] — keep it tight
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
        mp3_bytes = await synthesize_audio(reply)
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
