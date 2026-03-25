"""
Application configuration — loads .env and exposes typed settings.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger("voice_ai")

# ── Data directory (override with DATA_DIR env var for Docker) ────────────────

VOICE_AI_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(VOICE_AI_DIR)))


# ── Load .env into os.environ ─────────────────────────────────────────────────

def _load_env() -> None:
    env_path = VOICE_AI_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_env()


# ── Core settings ─────────────────────────────────────────────────────────────

GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not set — check .env")

# TTS engine override: "piper", "edge", or "groq". Empty = per-tone default.
TTS_ENGINE_OVERRIDE: str | None = os.environ.get("TTS_ENGINE", "").strip().lower() or None

# Default voices per engine+language (used when TTS_ENGINE overrides per-tone config)
TTS_DEFAULTS: dict[str, dict] = {
    "piper": {
        "english": {"voice": "en_US-kristin-medium", "speed": 1.0},
        "chinese": {"voice": "en_US-kristin-medium", "speed": 1.0},
    },
    "edge": {
        "english": {"voice": "en-US-AriaNeural", "rate": "+0%", "pitch": "+0Hz"},
        "chinese": {"voice": "zh-CN-XiaoxiaoNeural", "rate": "+0%", "pitch": "+0Hz"},
    },
    "groq": {
        "english": {"voice": "diana", "speed": 1.0},
        "chinese": {"voice": "diana", "speed": 1.0},
    },
}

if TTS_ENGINE_OVERRIDE:
    if TTS_ENGINE_OVERRIDE not in TTS_DEFAULTS:
        raise RuntimeError(
            f"TTS_ENGINE={TTS_ENGINE_OVERRIDE!r} not valid. Use: piper, edge, groq"
        )
    logger.info(f"TTS engine override: {TTS_ENGINE_OVERRIDE}")


# ── Conversation context config ───────────────────────────────────────────────

RECENT_MESSAGES = 6
SUMMARIZE_THRESHOLD = 10
SUMMARY_MODEL = "llama-3.3-70b-versatile"
SUMMARY_MAX_TOKENS = 200
LLM_MODEL = "llama-3.3-70b-versatile"
LLM_MAX_TOKENS = 200
LLM_TEMPERATURE = 0.7
