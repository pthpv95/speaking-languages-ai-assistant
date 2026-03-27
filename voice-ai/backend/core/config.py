from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    data_dir: Path
    groq_api_key: str
    tts_engine_override: str | None
    recent_messages: int = 6
    summarize_threshold: int = 10
    summary_model: str = "llama-3.3-70b-versatile"
    summary_max_tokens: int = 200
    chat_model: str = "llama-3.3-70b-versatile"
    vapid_subject: str = "mailto:voiceai@example.com"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "voice_ai.db"

    @property
    def piper_models_dir(self) -> Path:
        return self.data_dir / "piper_models"

    @property
    def html_path(self) -> Path:
        return self.base_dir / "index.html"

    @property
    def manifest_path(self) -> Path:
        return self.base_dir / "manifest.json"

    @property
    def service_worker_path(self) -> Path:
        return self.base_dir / "sw.js"

    @property
    def icon_192_path(self) -> Path:
        return self.base_dir / "icon-192.png"

    @property
    def icon_512_path(self) -> Path:
        return self.base_dir / "icon-512.png"


def get_settings() -> Settings:
    _load_env_file()
    base_dir = Path(__file__).resolve().parents[2]
    data_dir = Path(os.environ.get("DATA_DIR", str(base_dir)))
    groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_api_key:
        raise RuntimeError("GROQ_API_KEY not set; check voice-ai/.env")

    tts_engine_override = os.environ.get("TTS_ENGINE", "").strip().lower() or None
    if tts_engine_override and tts_engine_override not in {"piper", "edge", "groq"}:
        raise RuntimeError(f"TTS_ENGINE={tts_engine_override!r} not valid. Use: piper, edge, groq")

    return Settings(
        base_dir=base_dir,
        data_dir=data_dir,
        groq_api_key=groq_api_key,
        tts_engine_override=tts_engine_override,
    )


def configure_logging() -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return logging.getLogger("voice_ai")
