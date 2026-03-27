from __future__ import annotations

import asyncio
import io
import re
import urllib.request
import wave
from pathlib import Path

from backend.core.coach_config import EDGE_FALLBACK, TONES, get_tone_config
from backend.core.config import Settings
from backend.services.ai import AIService


class TTSService:
    def __init__(self, settings: Settings, ai_service: AIService, logger) -> None:
        self.settings = settings
        self.ai_service = ai_service
        self.logger = logger
        self._piper_voices: dict[str, object] = {}

    def strip_for_tts(self, text: str) -> str:
        reply_match = re.search(r"\[REPLY\]\s*(.*?)(?=\[LESSON\]|\[PROMPT\]|$)", text, re.DOTALL | re.IGNORECASE)
        prompt_match = re.search(r"\[PROMPT\]\s*(.*?)$", text, re.DOTALL | re.IGNORECASE)
        lesson_match = re.search(r"\[LESSON\]\s*(.*?)(?=\[PROMPT\]|$)", text, re.DOTALL | re.IGNORECASE)
        if not reply_match:
            reply_match = re.search(r"\[回复\]\s*(.*?)(?=\[课程\]|\[话题\]|$)", text, re.DOTALL)
        if not prompt_match:
            prompt_match = re.search(r"\[话题\]\s*(.*?)$", text, re.DOTALL)
        if not lesson_match:
            lesson_match = re.search(r"\[课程\]\s*(.*?)(?=\[话题\]|$)", text, re.DOTALL)

        parts: list[str] = []
        if reply_match:
            parts.append(reply_match.group(1).strip())
        if prompt_match:
            parts.append(prompt_match.group(1).strip())

        if parts:
            result = " ".join(parts)
        else:
            spoken_lines = []
            for line in text.splitlines():
                stripped = line.strip()
                if stripped and not re.match(r"^[💬🗣✏️🔊🌍]", stripped):
                    spoken_lines.append(stripped)
            result = " ".join(spoken_lines)

        result = re.sub(r"\[(?:REPLY|LESSON|PROMPT|回复|课程|话题)\]\s*", "", result)
        result = re.sub(r"[💬🗣✏️🔊🌍]\s*", "", result)
        return result.strip()

    def preload_piper_voices(self) -> None:
        for language_tones in TONES.values():
            for tone_config in language_tones.values():
                if tone_config.get("tts_engine") == "piper":
                    try:
                        self._get_piper_voice(tone_config["voice"])
                    except Exception as exc:
                        self.logger.warning("Failed to preload Piper voice %s: %s", tone_config["voice"], exc)

    async def synthesize_audio(self, text: str, language: str, tone: str) -> tuple[bytes, str]:
        tone_config = get_tone_config(language, tone, self.settings.tts_engine_override)
        engine = tone_config.get("tts_engine", "edge")

        if engine == "piper" and language == "english":
            try:
                wav = await self._tts_piper(text, tone_config["voice"], speed=tone_config.get("speed", 1.0))
                return wav, "audio/wav"
            except Exception as exc:
                self.logger.warning("Piper TTS failed (%s), falling back to edge-tts", exc)
                mp3 = await self._tts_edge(
                    text,
                    EDGE_FALLBACK["voice"],
                    EDGE_FALLBACK["rate"],
                    EDGE_FALLBACK["pitch"],
                )
                return mp3, "audio/mp3"

        if engine == "groq":
            try:
                mp3 = await self._tts_groq(text, tone_config["voice"], speed=tone_config.get("speed", 1.0))
                return mp3, "audio/mp3"
            except Exception as exc:
                if "rate_limit" in str(exc) or "429" in str(exc):
                    self.logger.warning("Groq TTS rate-limited, falling back to edge-tts")
                    mp3 = await self._tts_edge(
                        text,
                        EDGE_FALLBACK["voice"],
                        EDGE_FALLBACK["rate"],
                        EDGE_FALLBACK["pitch"],
                    )
                    return mp3, "audio/mp3"
                raise

        mp3 = await self._tts_edge(
            text,
            tone_config["voice"],
            tone_config.get("rate", "+0%"),
            tone_config.get("pitch", "+0Hz"),
        )
        return mp3, "audio/mp3"

    def _ensure_piper_model(self, voice_name: str) -> Path:
        model_dir = self.settings.piper_models_dir / voice_name
        onnx_path = model_dir / f"{voice_name}.onnx"
        json_path = model_dir / f"{voice_name}.onnx.json"
        if onnx_path.exists() and json_path.exists():
            return onnx_path

        model_dir.mkdir(parents=True, exist_ok=True)
        parts = voice_name.split("-")
        locale = parts[0]
        lang = locale.split("_")[0]
        base_url = (
            f"https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            f"{lang}/{locale}/{'-'.join(parts[1:-1])}/{parts[-1]}"
        )

        for file_name in (f"{voice_name}.onnx", f"{voice_name}.onnx.json"):
            url = f"{base_url}/{file_name}"
            destination = model_dir / file_name
            self.logger.info("Downloading Piper model: %s", url)
            urllib.request.urlretrieve(url, destination)

        return onnx_path

    def _get_piper_voice(self, voice_name: str):
        if voice_name not in self._piper_voices:
            from piper import PiperVoice

            onnx_path = self._ensure_piper_model(voice_name)
            self._piper_voices[voice_name] = PiperVoice.load(str(onnx_path))
            self.logger.info("Loaded Piper voice: %s", voice_name)
        return self._piper_voices[voice_name]

    async def _tts_groq(self, text: str, voice: str, speed: float = 1.0) -> bytes:
        spoken_text = self.strip_for_tts(text)
        self.logger.info("TTS input: %s chars -> %r", len(spoken_text), spoken_text[:80])

        def _call() -> bytes:
            response = self.ai_service.sync_client.audio.speech.create(
                model="canopylabs/orpheus-v1-english",
                voice=voice,
                input=spoken_text,
                response_format="wav",
            )
            return response.read()

        wav_bytes = await asyncio.get_running_loop().run_in_executor(None, _call)
        return self._wav_to_mp3(wav_bytes, speed=speed)

    async def _tts_edge(self, text: str, voice: str, rate: str, pitch: str) -> bytes:
        import edge_tts

        buffer = io.BytesIO()
        communicator = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
        async for chunk in communicator.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        return buffer.getvalue()

    async def _tts_piper(self, text: str, voice_name: str, speed: float = 1.0) -> bytes:
        spoken_text = self.strip_for_tts(text)
        self.logger.info("Piper TTS input: %s chars -> %r", len(spoken_text), spoken_text[:80])

        def _synthesize() -> bytes:
            from piper.config import SynthesisConfig

            voice = self._get_piper_voice(voice_name)
            synth_config = SynthesisConfig(length_scale=1.0 / speed if speed else 1.0)
            buffer = io.BytesIO()
            wf = wave.open(buffer, "wb")
            first_chunk = True
            for chunk in voice.synthesize(spoken_text, syn_config=synth_config):
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
            return buffer.getvalue()

        return await asyncio.get_running_loop().run_in_executor(None, _synthesize)

    @staticmethod
    def _wav_to_mp3(wav_bytes: bytes, speed: float = 1.0) -> bytes:
        import lameenc

        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            pcm = wav_file.readframes(wav_file.getnframes())
            rate = wav_file.getframerate()
            channels = wav_file.getnchannels()

        encoder = lameenc.Encoder()
        encoder.set_bit_rate(128)
        encoder.set_in_sample_rate(int(rate * speed))
        encoder.set_channels(channels)
        encoder.set_quality(2)
        return encoder.encode(pcm) + encoder.flush()
