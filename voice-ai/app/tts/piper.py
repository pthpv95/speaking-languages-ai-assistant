"""
Piper TTS — fast, local, offline TTS using ONNX models from HuggingFace.
"""

import io
import logging
import urllib.request
import wave
from pathlib import Path

from app.config import DATA_DIR

logger = logging.getLogger("voice_ai")

_MODELS_DIR = DATA_DIR / "piper_models"
_voice_cache: dict[str, object] = {}


def _ensure_model(voice_name: str) -> Path:
    """Download a Piper voice model from HuggingFace if not already cached."""
    model_dir = _MODELS_DIR / voice_name
    onnx_path = model_dir / f"{voice_name}.onnx"
    json_path = model_dir / f"{voice_name}.onnx.json"
    if onnx_path.exists() and json_path.exists():
        return onnx_path

    model_dir.mkdir(parents=True, exist_ok=True)
    parts = voice_name.split("-")
    locale = parts[0]
    lang = locale.split("_")[0]
    base_url = (
        f"https://huggingface.co/rhasspy/piper-voices/resolve/main"
        f"/{lang}/{locale}/{'-'.join(parts[1:-1])}/{parts[-1]}"
    )

    for fname in [f"{voice_name}.onnx", f"{voice_name}.onnx.json"]:
        url = f"{base_url}/{fname}"
        dest = model_dir / fname
        logger.info(f"Downloading Piper model: {url}")
        urllib.request.urlretrieve(url, dest)

    return onnx_path


def get_voice(voice_name: str):
    """Load a PiperVoice, caching it for reuse."""
    if voice_name not in _voice_cache:
        from piper import PiperVoice

        onnx_path = _ensure_model(voice_name)
        _voice_cache[voice_name] = PiperVoice.load(str(onnx_path))
        logger.info(f"Loaded Piper voice: {voice_name}")
    return _voice_cache[voice_name]


def preload_voices(tone_configs: list[dict]) -> None:
    """Pre-load all Piper voices so first request is fast."""
    for cfg in tone_configs:
        if cfg.get("tts_engine") == "piper":
            try:
                get_voice(cfg["voice"])
            except Exception as e:
                logger.warning(f"Failed to preload Piper voice {cfg['voice']}: {e}")


def synthesize_sync(text: str, voice_name: str, speed: float = 1.0) -> bytes:
    """Synthesize text to WAV bytes (blocking). Run in executor for async."""
    from piper import PiperVoice  # noqa: F811
    from piper.config import SynthesisConfig

    voice = get_voice(voice_name)
    syn_config = SynthesisConfig(length_scale=1.0 / speed if speed else 1.0)

    wav_buf = io.BytesIO()
    wf = wave.open(wav_buf, "wb")
    first_chunk = True
    for chunk in voice.synthesize(text, syn_config=syn_config):
        if first_chunk:
            wf.setnchannels(chunk.sample_channels)
            wf.setsampwidth(chunk.sample_width)
            wf.setframerate(chunk.sample_rate)
            first_chunk = False
        wf.writeframes(chunk.audio_int16_bytes)
    if first_chunk:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
    wf.close()
    return wav_buf.getvalue()
