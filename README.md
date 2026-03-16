# Voice AI Coach

A voice-based language learning app. Click a button to record your voice, release to send, and hear the AI coach reply — all in under 800ms.

```
[Browser mic] → POST audio → [FastAPI]
                                 ├─ Groq Whisper  (ASR)
                                 ├─ Groq LLM      (reply)
                                 └─ edge-tts      (audio)
              ← MP3 + transcript ─────────────────────────
```

## Supported Languages

English · Chinese · Spanish · French · Japanese

## Prerequisites

- Python 3.10+
- A free [Groq API key](https://console.groq.com)

## Installation

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

# 2. Install dependencies
pip install fastapi "uvicorn[standard]" python-multipart "openai>=1.30.0" edge-tts

# 3. Configure environment
cp voice-ai/.env.example voice-ai/.env
# Edit voice-ai/.env and add your Groq API key:
#   GROQ_API_KEY=gsk_your_key_here
#   LANGUAGE=english
```

## Running the App

```bash
# Option A: Use the start script (macOS/Linux)
cd voice-ai
chmod +x start.sh
./start.sh

# Option B: Run manually
cd voice-ai
../venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Then open http://localhost:8080 in your browser.

For mobile access over HTTPS (required for mic permissions on non-localhost):

```bash
# Generate self-signed certs (one time)
openssl req -x509 -newkey rsa:2048 -keyout voice-ai/key.pem -out voice-ai/cert.pem -days 365 -nodes -subj '/CN=localhost'

# start.sh will automatically serve HTTPS on port 8443
```

## Switching Language

Edit `voice-ai/.env`:

```
LANGUAGE=chinese
```

Restart the server. ASR model, TTS voice, and system prompt all switch automatically.

## Project Structure

```
voice-ai/
├── main.py        # FastAPI backend (ASR, LLM, TTS)
├── index.html     # Single-page frontend
├── sw.js          # Service worker (PWA/push notifications)
├── manifest.json  # PWA manifest
├── start.sh       # Launch script (HTTP + HTTPS)
├── .env           # GROQ_API_KEY + LANGUAGE (not committed)
├── test_api.py    # API smoke test
└── test_key.py    # Groq API key verification
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `401 Unauthorized` | Check `GROQ_API_KEY` in `.env` |
| Mic permission denied | Use `http://localhost` or HTTPS for mobile |
| `422` on `/chat` | Ensure `python-multipart` is installed |
| TTS audio silent | Check internet — edge-tts calls Azure |
| Latency > 1000ms | Check Groq rate limits at console.groq.com |
