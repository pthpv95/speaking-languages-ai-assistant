# CLAUDE.md — Voice AI MVP (Web App)

## What This Builds

A single-page web app where the user clicks a button to record their voice,
releases it to send, and hears the AI coach reply — all in under 800ms.

```
[Browser mic button] → HTTP POST audio → [FastAPI]
                                              ├─ Groq Whisper  (ASR ~150ms)
                                              ├─ Groq LLM      (reply ~200ms)
                                              └─ edge-tts      (audio ~200ms)
                   ← MP3 audio + transcript ──────────────────────────────────
```

No VAD. No WebSockets. No mobile SDK. No local model downloads.
User controls start/stop with the button — that replaces VAD entirely.

## Stack

| Role | Tool | Cost |
|------|------|------|
| ASR  | Groq `whisper-large-v3-turbo` | Free tier |
| LLM  | Groq `llama-3.3-70b-versatile` | Free tier |
| TTS  | `edge-tts` (Microsoft Azure voices) | Free, no key |
| Frontend | Plain HTML + JS (no framework) | — |
| Backend  | FastAPI, single file | — |

**Total files:** `main.py` · `index.html` · `.env`

---

## Execution Rules

- Execute **one phase at a time**. Stop and report after each.
- Fix failures before moving forward — never skip a phase.
- All files go into `./voice-ai/`.
- When user input is needed (API key, language), pause and ask.

---

## Phase 1 — Scaffold

```
1. Create ./voice-ai/
2. Create Python venv: python -m venv venv
3. Verify venv created (check venv/bin/python or venv\Scripts\python.exe)
4. Print Python version — must be 3.10+
```

**Stop and report.**

---

## Phase 2 — Install Dependencies

```
pip install --upgrade pip
pip install fastapi "uvicorn[standard]" python-multipart
pip install "openai>=1.30.0"
pip install edge-tts
```

`python-multipart` is required for FastAPI to accept file uploads (the audio blob).
No `torch`, no `funasr`, no `websockets` — VAD and local ASR are gone.

Then create and run `voice-ai/verify_deps.py`:

```python
import fastapi, openai, edge_tts
print("fastapi :", fastapi.__version__)
print("openai  :", openai.__version__)
print("ALL OK")
```

**Stop and report versions.**

---

## Phase 3 — API Key

Ask the user: **"Paste your Groq API key (free at https://console.groq.com)."**

Save to `voice-ai/.env`:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxx
LANGUAGE=english
```

Create and run `voice-ai/test_key.py`:
```python
import os
from openai import OpenAI

key    = open(".env").read().split("\n")[0].split("=",1)[1].strip()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=key)
r = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role":"user","content":"Say: key works"}],
    max_tokens=10,
)
print("OK:", r.choices[0].message.content)
```

**Stop and report. Do NOT proceed if this fails.**

---

## Phase 4 — Write the Backend

Create `voice-ai/main.py` **exactly**:

```python
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
        "asr_model":    "distil-whisper-large-v3-en",   # English-only, fastest
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

profile = PROFILES.get(LANGUAGE, PROFILES["english"])
logger.info(f"Language: {LANGUAGE} | ASR: {profile['asr_model']} | TTS: {profile['tts_voice']}")

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
    tts = edge_tts.Communicate(text, voice=profile["tts_voice"])
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
    return {
        "status":   "ok",
        "language": LANGUAGE,
        "asr":      profile["asr_model"],
        "tts":      profile["tts_voice"],
    }


@app.get("/config")
async def config():
    """Frontend calls this to know the active language."""
    return {"language": LANGUAGE, "tts_voice": profile["tts_voice"]}


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
    messages = [{"role": "system", "content": profile["system_prompt"]}]
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
```

**Stop and report: confirm main.py written, show line count.**

---

## Phase 5 — Write the Frontend

Create `voice-ai/index.html` **exactly**:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Voice AI Coach</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:     #0d1117;
    --bg1:    #161b22;
    --bg2:    #21262d;
    --line:   #30363d;
    --muted:  #484f58;
    --soft:   #8b949e;
    --text:   #e6edf3;
    --green:  #3fb950;
    --gd:     #0d2a14;
    --gb:     #1a4225;
    --blue:   #58a6ff;
    --red:    #f85149;
    --amber:  #d29922;
    --mono:   'IBM Plex Mono', monospace;
    --sans:   'IBM Plex Sans', sans-serif;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  /* subtle grid bg */
  body::before {
    content: '';
    position: fixed; inset: 0;
    background-image:
      linear-gradient(rgba(63,185,80,.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(63,185,80,.025) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }

  .container {
    width: 100%;
    max-width: 680px;
    padding: 32px 20px 60px;
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  /* ── header ── */
  header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    border-bottom: 1px solid var(--line);
    padding-bottom: 16px;
  }
  header h1 { font-size: 17px; font-weight: 600; color: var(--text); }
  #lang-badge {
    font-family: var(--mono);
    font-size: 11px;
    padding: 2px 9px;
    border-radius: 10px;
    background: var(--gd);
    border: 1px solid var(--gb);
    color: var(--green);
  }
  .header-right { margin-left: auto; display: flex; gap: 8px; align-items: center; }
  #clear-btn {
    font-family: var(--mono);
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 6px;
    border: 1px solid var(--line);
    background: none;
    color: var(--muted);
    cursor: pointer;
    transition: color .15s, border-color .15s;
  }
  #clear-btn:hover { color: var(--red); border-color: var(--red); }

  /* ── conversation ── */
  #conversation {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 240px;
    max-height: 52vh;
    overflow-y: auto;
    padding: 4px 2px;
    scroll-behavior: smooth;
  }
  #conversation::-webkit-scrollbar { width: 4px; }
  #conversation::-webkit-scrollbar-track { background: transparent; }
  #conversation::-webkit-scrollbar-thumb { background: var(--bg2); border-radius: 2px; }

  .bubble {
    max-width: 82%;
    padding: 11px 15px;
    border-radius: 12px;
    font-size: 14px;
    line-height: 1.65;
    animation: popIn .2s ease both;
  }
  @keyframes popIn {
    from { opacity:0; transform: translateY(6px) scale(.97); }
    to   { opacity:1; transform: translateY(0) scale(1); }
  }
  .bubble.user {
    align-self: flex-end;
    background: var(--bg2);
    border: 1px solid var(--line);
    color: var(--text);
    border-bottom-right-radius: 3px;
  }
  .bubble.ai {
    align-self: flex-start;
    background: var(--gd);
    border: 1px solid var(--gb);
    color: var(--text);
    border-bottom-left-radius: 3px;
  }
  .bubble.ai .tip {
    color: var(--green);
    font-family: var(--mono);
    font-size: 12px;
    margin-top: 6px;
    display: block;
  }
  .bubble.error {
    align-self: flex-start;
    background: rgba(248,81,73,.07);
    border: 1px solid rgba(248,81,73,.25);
    color: var(--red);
    font-family: var(--mono);
    font-size: 12px;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    height: 200px;
    color: var(--muted);
    font-size: 13px;
    font-family: var(--mono);
  }
  .empty-state span:first-child { font-size: 28px; }

  /* ── latency badge ── */
  .latency-badge {
    align-self: flex-start;
    font-family: var(--mono);
    font-size: 10px;
    color: var(--muted);
    padding: 2px 8px;
    background: var(--bg2);
    border-radius: 4px;
    margin-top: -6px;
    margin-left: 6px;
  }
  .latency-badge.fast { color: var(--green); }
  .latency-badge.ok   { color: var(--amber); }
  .latency-badge.slow { color: var(--red); }

  /* ── record controls ── */
  .controls {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    padding: 20px 0 4px;
  }

  #record-btn {
    width: 72px; height: 72px;
    border-radius: 50%;
    border: 2px solid var(--green);
    background: var(--gd);
    color: var(--green);
    font-size: 26px;
    cursor: pointer;
    transition: all .2s;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 0 0 rgba(63,185,80,0);
    position: relative;
  }
  #record-btn:hover:not(:disabled) {
    background: var(--gb);
    box-shadow: 0 0 0 6px rgba(63,185,80,.12);
  }
  #record-btn.recording {
    border-color: var(--red);
    background: rgba(248,81,73,.12);
    color: var(--red);
    animation: pulse 1.4s ease infinite;
  }
  #record-btn:disabled {
    border-color: var(--muted);
    background: var(--bg2);
    color: var(--muted);
    cursor: not-allowed;
    animation: none;
  }
  @keyframes pulse {
    0%,100% { box-shadow: 0 0 0 0 rgba(248,81,73,.4); }
    50%      { box-shadow: 0 0 0 10px rgba(248,81,73,0); }
  }

  /* recording timer */
  #timer {
    font-family: var(--mono);
    font-size: 13px;
    color: var(--red);
    min-height: 20px;
    letter-spacing: 1px;
  }

  #status {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--muted);
    min-height: 16px;
    letter-spacing: .5px;
  }
  #status.active { color: var(--green); }
  #status.error  { color: var(--red); }

  /* ── instruction line ── */
  .hint {
    text-align: center;
    font-size: 12px;
    color: var(--muted);
    font-family: var(--mono);
  }

  /* ── pipeline viz (shown while processing) ── */
  #pipeline {
    display: none;
    gap: 6px;
    justify-content: center;
    align-items: center;
    font-family: var(--mono);
    font-size: 11px;
  }
  #pipeline.visible { display: flex; }
  .pipe-step {
    padding: 3px 10px;
    border-radius: 4px;
    border: 1px solid var(--line);
    color: var(--muted);
    background: var(--bg1);
    transition: all .2s;
  }
  .pipe-step.active { border-color: var(--amber); color: var(--amber); background: var(--amber-d, #2a1f07); }
  .pipe-step.done   { border-color: var(--green); color: var(--green); background: var(--gd); }
  .pipe-arrow { color: var(--muted); font-size: 10px; }
</style>
</head>
<body>
<div class="container">

  <header>
    <h1>🎙️ Voice AI Coach</h1>
    <span id="lang-badge">loading…</span>
    <div class="header-right">
      <button id="clear-btn" onclick="clearHistory()">clear chat</button>
    </div>
  </header>

  <!-- Conversation -->
  <div id="conversation">
    <div class="empty-state" id="empty">
      <span>🎤</span>
      <span>Click the mic to start speaking</span>
    </div>
  </div>

  <!-- Pipeline status -->
  <div id="pipeline">
    <span class="pipe-step" id="step-asr">ASR</span>
    <span class="pipe-arrow">→</span>
    <span class="pipe-step" id="step-llm">LLM</span>
    <span class="pipe-arrow">→</span>
    <span class="pipe-step" id="step-tts">TTS</span>
  </div>

  <!-- Controls -->
  <div class="controls">
    <button id="record-btn" onclick="toggleRecord()">🎤</button>
    <div id="timer"></div>
    <div id="status">ready</div>
  </div>

  <div class="hint">Click mic to start · Click again to send</div>

</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────────
let mediaRecorder = null;
let audioChunks   = [];
let recording     = false;
let timerInterval = null;
let timerSeconds  = 0;
let activeAudio   = null;

// ── Init ───────────────────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", async () => {
  try {
    const r = await fetch("/config");
    const c = await r.json();
    document.getElementById("lang-badge").textContent = c.language;
    document.title = `Voice AI — ${c.language}`;
  } catch (e) {
    setStatus("cannot reach server", "error");
  }
});

// ── Record toggle ──────────────────────────────────────────────────────────────
async function toggleRecord() {
  if (recording) {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  // Stop any playing audio (barge-in behaviour)
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    setStatus("mic permission denied", "error");
    return;
  }

  // Prefer webm/opus; fall back to whatever the browser supports
  const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
    ? "audio/webm;codecs=opus"
    : MediaRecorder.isTypeSupported("audio/webm")
    ? "audio/webm"
    : "";

  mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
  audioChunks   = [];

  mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
  mediaRecorder.onstop = () => {
    stream.getTracks().forEach(t => t.stop());
    processAudio();
  };

  mediaRecorder.start(100);
  recording = true;

  const btn = document.getElementById("record-btn");
  btn.classList.add("recording");
  btn.textContent = "⏹";

  timerSeconds = 0;
  timerInterval = setInterval(() => {
    timerSeconds++;
    document.getElementById("timer").textContent =
      `${String(Math.floor(timerSeconds/60)).padStart(2,"0")}:${String(timerSeconds%60).padStart(2,"0")}`;
  }, 1000);

  setStatus("recording…", "active");
}

function stopRecording() {
  if (!mediaRecorder || mediaRecorder.state === "inactive") return;
  clearInterval(timerInterval);
  document.getElementById("timer").textContent = "";
  mediaRecorder.stop();
  recording = false;

  const btn = document.getElementById("record-btn");
  btn.classList.remove("recording");
  btn.textContent = "🎤";
  btn.disabled = true;
}

// ── Process audio: ASR → LLM+TTS ──────────────────────────────────────────────
async function processAudio() {
  const blob = new Blob(audioChunks, {
    type: mediaRecorder.mimeType || "audio/webm",
  });

  if (blob.size < 1000) {
    setStatus("too short — try again", "error");
    document.getElementById("record-btn").disabled = false;
    return;
  }

  showPipeline(true);
  const t0 = performance.now();

  // ── Step 1: ASR ──────────────────────────────────────────────────────────────
  setStep("asr", "active");
  setStatus("transcribing…");

  let transcript;
  try {
    const formData = new FormData();
    formData.append("audio", blob, "audio.webm");
    const r = await fetch("/transcribe", { method: "POST", body: formData });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    transcript = data.transcript;
  } catch (e) {
    showError("ASR failed: " + e.message);
    reset(); return;
  }

  const asrMs = Math.round(performance.now() - t0);
  setStep("asr", "done");

  if (!transcript) {
    showError("Nothing heard — please try again");
    reset(); return;
  }

  addBubble("user", transcript);

  // ── Step 2 + 3: LLM + TTS ────────────────────────────────────────────────────
  setStep("llm", "active");
  setStatus("thinking…");

  let reply, mp3b64, totalMs, llmMs, ttsMs;
  try {
    const formData = new FormData();
    formData.append("transcript", transcript);
    const r = await fetch("/chat", { method: "POST", body: formData });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    reply   = data.reply;
    mp3b64  = data.mp3_base64;
    totalMs = data.total_ms;
    llmMs   = data.llm_ms;
    ttsMs   = data.tts_ms;
  } catch (e) {
    showError("LLM/TTS failed: " + e.message);
    reset(); return;
  }

  setStep("llm", "done");
  setStep("tts", "done");

  const endToEndMs = Math.round(performance.now() - t0);

  addBubble("ai", reply);
  addLatencyBadge(endToEndMs, asrMs, llmMs, ttsMs);

  // ── Play TTS audio ────────────────────────────────────────────────────────────
  setStatus("speaking…", "active");
  try {
    const mp3Bytes  = Uint8Array.from(atob(mp3b64), c => c.charCodeAt(0));
    const audioBlob = new Blob([mp3Bytes], { type: "audio/mp3" });
    const url       = URL.createObjectURL(audioBlob);
    activeAudio     = new Audio(url);
    activeAudio.onended = () => {
      URL.revokeObjectURL(url);
      activeAudio = null;
      setStatus("ready");
    };
    await activeAudio.play();
  } catch (e) {
    setStatus("audio playback error", "error");
  }

  showPipeline(false);
  reset();
}

// ── UI helpers ─────────────────────────────────────────────────────────────────
function addBubble(role, text) {
  const conv = document.getElementById("conversation");
  document.getElementById("empty")?.remove();

  const div = document.createElement("div");
  div.className = `bubble ${role}`;

  if (role === "ai") {
    // Render [Tip: ...] / 【提示：...】 in green
    const formatted = text
      .replace(/\[([^\]]+)\]/g, '<span class="tip">[$1]</span>')
      .replace(/【([^】]+)】/g, '<span class="tip">【$1】</span>');
    div.innerHTML = formatted;
  } else {
    div.textContent = text;
  }

  conv.appendChild(div);
  conv.scrollTop = conv.scrollHeight;
}

function addLatencyBadge(total, asr, llm, tts) {
  const conv  = document.getElementById("conversation");
  const badge = document.createElement("div");
  const cls   = total < 700 ? "fast" : total < 1000 ? "ok" : "slow";
  badge.className = `latency-badge ${cls}`;
  badge.textContent = `${total}ms total (asr ${asr} · llm ${llm} · tts ${tts})`;
  conv.appendChild(badge);
  conv.scrollTop = conv.scrollHeight;
}

function showError(msg) {
  const conv = document.getElementById("conversation");
  document.getElementById("empty")?.remove();
  const div = document.createElement("div");
  div.className = "bubble error";
  div.textContent = "⚠ " + msg;
  conv.appendChild(div);
  conv.scrollTop = conv.scrollHeight;
}

function setStatus(msg, cls = "") {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.className   = cls;
}

function setStep(id, state) {
  const el = document.getElementById("step-" + id);
  if (el) el.className = "pipe-step " + state;
}

function showPipeline(visible) {
  const el = document.getElementById("pipeline");
  el.classList.toggle("visible", visible);
  if (visible) {
    ["asr","llm","tts"].forEach(id => setStep(id, ""));
  }
}

function reset() {
  document.getElementById("record-btn").disabled = false;
  document.getElementById("record-btn").textContent = "🎤";
}

async function clearHistory() {
  await fetch("/history", { method: "DELETE" });
  const conv = document.getElementById("conversation");
  conv.innerHTML = `<div class="empty-state" id="empty">
    <span>🎤</span><span>Click the mic to start speaking</span>
  </div>`;
  setStatus("chat cleared");
  setTimeout(() => setStatus("ready"), 1500);
}
</script>
</body>
</html>
```

**Stop and report: confirm index.html written, show line count.**

---

## Phase 6 — Environment & .gitignore

Create `voice-ai/.gitignore`:
```
.env
venv/
__pycache__/
*.pyc
*.pyo
```

Confirm `voice-ai/.env` has both lines:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxx
LANGUAGE=english
```

Supported `LANGUAGE` values: `english` · `chinese` · `spanish` · `french` · `japanese`

**Stop and report.**

---

## Phase 7 — Start & Verify

Launch the server:
```bash
# macOS/Linux:
cd voice-ai && ../venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# Windows PowerShell:
cd voice-ai
..\venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Wait for: `INFO:     Application startup complete.`

Then run these checks:
```bash
# 1. Health check
curl http://localhost:8080/health
# Expected: {"status":"ok","language":"english","asr":"distil-whisper-large-v3-en",...}

# 2. Config endpoint
curl http://localhost:8080/config
# Expected: {"language":"english","tts_voice":"en-US-JennyNeural"}

# 3. Open the web app in browser
open http://localhost:8080        # macOS
start http://localhost:8080       # Windows
xdg-open http://localhost:8080    # Linux
```

**Stop and paste the health check response. Ask the user to open the browser and confirm the page loads.**

---

## Phase 8 — Smoke Test (API Only)

Create and run `voice-ai/test_api.py` to verify the backend pipeline without a browser:

```python
"""
Tests /transcribe and /chat endpoints directly with a synthetic WAV file.
No browser or microphone needed.
"""
import requests, wave, struct, math, io, base64, time

BASE = "http://localhost:8080"

# 1. Health
r = requests.get(f"{BASE}/health")
assert r.status_code == 200, f"Health failed: {r.text}"
print("✅ Health:", r.json())

# 2. Generate a 2s 400Hz WAV (Groq needs >= 1s)
SR = 16000; FREQ = 400; DUR = 2
samples = [int(20000 * math.sin(2 * math.pi * FREQ * i / SR)) for i in range(SR * DUR)]
buf = io.BytesIO()
with wave.open(buf, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(struct.pack(f"<{SR*DUR}h", *samples))
buf.seek(0)

# 3. POST /transcribe
t0 = time.monotonic()
r  = requests.post(f"{BASE}/transcribe", files={"audio": ("test.wav", buf, "audio/wav")})
assert r.status_code == 200, f"Transcribe failed: {r.text}"
asr_ms = round((time.monotonic() - t0) * 1000)
print(f"✅ /transcribe ({asr_ms}ms): {r.json()}")

# 4. POST /chat with a known phrase
t0  = time.monotonic()
r   = requests.post(f"{BASE}/chat", data={"transcript": "Hello, let's practice English today."})
assert r.status_code == 200, f"Chat failed: {r.text}"
d   = r.json()
end = round((time.monotonic() - t0) * 1000)

print(f"✅ /chat   ({end}ms end-to-end from client)")
print(f"   LLM: {d['llm_ms']}ms | TTS: {d['tts_ms']}ms | server total: {d['total_ms']}ms")
print(f"   Reply: {d['reply'][:100]}")
print(f"   MP3 size: {len(base64.b64decode(d['mp3_base64']))} bytes")

# 5. Latency verdict
total = d["total_ms"]
if total < 700:
    print(f"\n🟢 FAST — {total}ms (target <800ms ✅)")
elif total < 1000:
    print(f"\n🟡 OK   — {total}ms (slightly over target)")
else:
    print(f"\n🔴 SLOW — {total}ms (check Groq rate limits)")
```

Run: `cd voice-ai && python test_api.py`

**Stop and report the exact latency numbers.**

---

## Phase 9 — Final Report

Print:

```
═══════════════════════════════════════════════════════
  VOICE AI MVP — READY
═══════════════════════════════════════════════════════
  Phase results:
    Phase 1  Scaffold           ✅/❌
    Phase 2  Dependencies       ✅/❌
    Phase 3  API key            ✅/❌
    Phase 4  Backend (main.py)  ✅/❌
    Phase 5  Frontend           ✅/❌
    Phase 6  Env + .gitignore   ✅/❌
    Phase 7  Server running     ✅/❌
    Phase 8  API smoke test     ✅/❌

  Files:
    voice-ai/main.py       ← backend (FastAPI)
    voice-ai/index.html    ← frontend (single HTML file)
    voice-ai/.env          ← GROQ_API_KEY + LANGUAGE

  Endpoints:
    Web app   →  http://localhost:8080
    Health    →  http://localhost:8080/health
    Languages →  change LANGUAGE= in .env, restart

  Measured latency:
    ASR (Groq Whisper) : ___ms
    LLM (Groq)         : ___ms
    TTS (edge-tts)     : ___ms
    Total (server)     : ___ms

  To switch language: edit .env → LANGUAGE=chinese (or spanish/french/japanese)
  then restart uvicorn.
═══════════════════════════════════════════════════════
```

---

## File Structure

```
voice-ai/
├── main.py        ← entire backend (3 routes)
├── index.html     ← entire frontend (no framework, no build step)
├── .env           ← GROQ_API_KEY + LANGUAGE
└── .gitignore
```

---

## Switching Language

Edit `.env`:
```
LANGUAGE=chinese
```
Restart server. That's it — ASR model, TTS voice, and LLM system prompt all switch automatically.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `401 Unauthorized` | Re-check `GROQ_API_KEY` in `.env` |
| Mic permission denied in browser | Use `http://localhost` (not `http://IP`) or enable in browser settings |
| `422 Unprocessable Entity` on `/chat` | Ensure `python-multipart` is installed |
| `module 'edge_tts' has no attribute...` | `pip install --upgrade edge-tts` |
| TTS audio silent (0 bytes) | Check internet — edge-tts calls Azure endpoint |
| Latency > 1000ms | Groq rate limit — check https://console.groq.com/dashboard |
| `index.html not found` | Run uvicorn from inside `voice-ai/` directory |
