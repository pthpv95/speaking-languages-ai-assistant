"""
TTS dispatcher — routes to the right engine and handles fallbacks.
"""

import asyncio
import io
import logging
import re
import wave

from app.tones import get_tone_config

logger = logging.getLogger("voice_ai")

# Edge TTS fallback config
_EDGE_FALLBACK = {"voice": "en-US-AriaNeural", "rate": "+0%", "pitch": "+0Hz"}


def wav_to_mp3(wav_bytes: bytes, speed: float = 1.0) -> bytes:
    """Convert WAV bytes to MP3 using lameenc."""
    import lameenc

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


def strip_for_tts(text: str) -> str:
    """Extract spoken text for TTS — reads [REPLY] + [PROMPT], skips [LESSON]."""
    reply_match = re.search(
        r"\[REPLY\]\s*(.*?)(?=\[LESSON\]|\[PROMPT\]|$)", text, re.DOTALL | re.IGNORECASE
    )
    prompt_match = re.search(r"\[PROMPT\]\s*(.*?)$", text, re.DOTALL | re.IGNORECASE)
    lesson_match = re.search(
        r"\[LESSON\]\s*(.*?)(?=\[PROMPT\]|$)", text, re.DOTALL | re.IGNORECASE
    )

    # Chinese variants
    if not reply_match:
        reply_match = re.search(r"\[回复\]\s*(.*?)(?=\[课程\]|\[话题\]|$)", text, re.DOTALL)
    if not prompt_match:
        prompt_match = re.search(r"\[话题\]\s*(.*?)$", text, re.DOTALL)
    if not lesson_match:
        lesson_match = re.search(r"\[课程\]\s*(.*?)(?=\[话题\]|$)", text, re.DOTALL)

    parts = []
    if reply_match:
        parts.append(reply_match.group(1).strip())
    if prompt_match:
        parts.append(prompt_match.group(1).strip())

    if parts:
        result = " ".join(parts)
    else:
        # No markers — strip emoji-prefixed lesson lines, keep everything else
        lines = text.split("\n")
        spoken = []
        for line in lines:
            s = line.strip()
            if s and not re.match(r"^[💬🗣✏️🔊🌍]", s):
                spoken.append(s)
        result = " ".join(spoken)

    # Clean up any remaining markers
    result = re.sub(r"\[(?:REPLY|LESSON|PROMPT|回复|课程|话题)\]\s*", "", result)
    result = re.sub(r"[💬🗣✏️🔊🌍]\s*", "", result)
    return result.strip()


async def synthesize_audio(text: str, language: str, tone: str) -> tuple[bytes, str]:
    """Route to the right TTS engine. Returns (audio_bytes, mime_type)."""
    from app.tts import edge as tts_edge

    tone_cfg = get_tone_config(language, tone)
    engine = tone_cfg.get("tts_engine", "edge")
    tts_text = strip_for_tts(text)
    logger.info(f"TTS input ({engine}): {len(tts_text)} chars -> {tts_text[:80]!r}")

    if engine == "piper" and language == "en":
        try:
            from app.tts import piper as tts_piper

            wav = await asyncio.get_event_loop().run_in_executor(
                None, tts_piper.synthesize_sync, tts_text, tone_cfg["voice"], tone_cfg.get("speed", 1.0)
            )
            return wav, "audio/wav"
        except Exception as e:
            logger.warning(f"Piper TTS failed ({e}), falling back to edge-tts")
            mp3 = await tts_edge.synthesize(
                tts_text, _EDGE_FALLBACK["voice"], _EDGE_FALLBACK["rate"], _EDGE_FALLBACK["pitch"]
            )
            return mp3, "audio/mp3"

    elif engine == "groq":
        try:
            from app.tts import groq as tts_groq

            mp3 = await tts_groq.synthesize(tts_text, tone_cfg["voice"], tone_cfg.get("speed", 1.0))
            return mp3, "audio/mp3"
        except Exception as e:
            if "rate_limit" in str(e) or "429" in str(e):
                logger.warning("Groq TTS rate-limited, falling back to edge-tts")
                mp3 = await tts_edge.synthesize(
                    tts_text, _EDGE_FALLBACK["voice"], _EDGE_FALLBACK["rate"], _EDGE_FALLBACK["pitch"]
                )
                return mp3, "audio/mp3"
            raise

    else:  # edge (default)
        mp3 = await tts_edge.synthesize(
            tts_text,
            tone_cfg["voice"],
            tone_cfg.get("rate", "+0%"),
            tone_cfg.get("pitch", "+0Hz"),
        )
        return mp3, "audio/mp3"
