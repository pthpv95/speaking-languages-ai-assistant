"""
Edge TTS — Microsoft Azure voices. Good for non-English languages. Free, no key.
"""

import io

import edge_tts


async def synthesize(text: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz") -> bytes:
    """Convert text to MP3 bytes using edge-tts."""
    buf = io.BytesIO()
    tts = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    async for chunk in tts.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()
