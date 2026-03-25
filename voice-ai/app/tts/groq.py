"""
Groq Orpheus TTS — very human-sounding, English only.
"""

import asyncio
import logging

from app.dependencies import sync_groq_client

logger = logging.getLogger("voice_ai")


async def synthesize(text: str, voice: str, speed: float = 1.0) -> bytes:
    """Call Groq Orpheus TTS, return MP3 bytes."""
    from app.tts.engine import wav_to_mp3

    def _call():
        r = sync_groq_client.audio.speech.create(
            model="canopylabs/orpheus-v1-english",
            voice=voice,
            input=text,
            response_format="wav",
        )
        return r.read()

    wav_bytes = await asyncio.get_event_loop().run_in_executor(None, _call)
    return wav_to_mp3(wav_bytes, speed=speed)
