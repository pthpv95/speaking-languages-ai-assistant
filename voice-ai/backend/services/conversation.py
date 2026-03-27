from __future__ import annotations

import base64
import re
import time
from collections.abc import AsyncIterator

from fastapi import HTTPException

from backend.core.coach_config import get_profile, get_tone_config
from backend.core.config import Settings
from backend.repositories.db import SQLiteRepository
from backend.services.ai import AIService
from backend.services.tts import TTSService


SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|(?<=[.!?。！？])(?=[A-Z\u4e00-\u9fff\[])")


class ConversationService:
    def __init__(
        self,
        settings: Settings,
        repository: SQLiteRepository,
        ai_service: AIService,
        tts_service: TTSService,
        logger,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.ai_service = ai_service
        self.tts_service = tts_service
        self.logger = logger

    async def transcribe_for_conversation(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        conversation_id: int | None,
        user: dict | None = None,
    ) -> str:
        language = "chinese"
        if conversation_id and user:
            conversation = await self.repository.get_conversation(conversation_id, user["id"])
            if conversation:
                language = conversation["language"]

        profile = get_profile(language)
        transcript = await self.ai_service.transcribe(
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type,
            model=profile["asr_model"],
            language=profile["whisper_lang"],
        )
        return transcript

    async def synthesize_replay(self, *, conversation_id: int, user_id: int, text: str) -> dict:
        conversation = await self.repository.get_conversation(conversation_id, user_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="conversation not found")

        started_at = time.monotonic()
        audio_bytes, audio_mime = await self.tts_service.synthesize_audio(
            text, conversation["language"], conversation["tone"]
        )
        return {
            "audio_base64": base64.b64encode(audio_bytes).decode(),
            "audio_mime": audio_mime,
            "tts_ms": round((time.monotonic() - started_at) * 1000),
        }

    async def build_chat_response(self, *, conversation_id: int, user_id: int, transcript: str) -> dict:
        if not transcript.strip():
            raise HTTPException(status_code=400, detail="empty transcript")

        conversation = await self.repository.get_conversation(conversation_id, user_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="conversation not found")

        language = conversation["language"]
        tone = conversation["tone"]
        started_at = time.monotonic()

        await self.repository.add_message(conversation_id, "user", transcript)
        await self._set_title_from_first_message(conversation_id, conversation["title"], transcript)

        messages = await self._build_llm_messages(conversation_id, conversation, language, tone)

        llm_started_at = time.monotonic()
        reply = await self.ai_service.complete_chat(messages=messages)
        llm_ms = (time.monotonic() - llm_started_at) * 1000
        self.logger.info("LLM (%sms): %r", round(llm_ms), reply[:80])

        await self.repository.add_message(conversation_id, "assistant", reply)

        tts_started_at = time.monotonic()
        audio_bytes, audio_mime = await self.tts_service.synthesize_audio(reply, language, tone)
        tts_ms = (time.monotonic() - tts_started_at) * 1000
        total_ms = (time.monotonic() - started_at) * 1000

        self.logger.info("LLM=%sms | TTS=%sms | total=%sms", round(llm_ms), round(tts_ms), round(total_ms))
        return {
            "reply": reply,
            "audio_base64": base64.b64encode(audio_bytes).decode(),
            "audio_mime": audio_mime,
            "llm_ms": round(llm_ms),
            "tts_ms": round(tts_ms),
            "total_ms": round(total_ms),
        }

    async def stream_chat_events(
        self, *, conversation_id: int, username: str, audio_bytes: bytes
    ) -> AsyncIterator[dict]:
        if len(audio_bytes) < 1000:
            raise HTTPException(status_code=400, detail="audio too short")

        user = await self.repository.get_or_create_user(username)
        conversation = await self.repository.get_conversation(conversation_id, user["id"])
        if not conversation:
            raise HTTPException(status_code=404, detail="conversation not found")

        language = conversation["language"]
        tone = conversation["tone"]
        profile = get_profile(language)
        started_at = time.monotonic()

        asr_started_at = time.monotonic()
        transcript = await self.ai_service.transcribe(
            audio_bytes=audio_bytes,
            filename="audio.webm",
            content_type="audio/webm",
            model=profile["asr_model"],
            language=profile["whisper_lang"],
        )
        asr_ms = (time.monotonic() - asr_started_at) * 1000
        if not transcript:
            raise HTTPException(status_code=400, detail="nothing heard")

        yield {"type": "transcript", "text": transcript, "asr_ms": round(asr_ms)}

        await self.repository.add_message(conversation_id, "user", transcript)
        await self._set_title_from_first_message(conversation_id, conversation["title"], transcript)
        messages = await self._build_llm_messages(conversation_id, conversation, language, tone)

        llm_started_at = time.monotonic()
        full_reply = ""
        pending_text = ""
        sentence_index = 0
        tts_total_seconds = 0.0

        async for delta in self.ai_service.stream_chat(messages=messages):
            full_reply += delta
            pending_text += delta

            sentences = self.split_sentences(pending_text)
            if len(sentences) <= 1:
                continue

            for sentence in sentences[:-1]:
                event, elapsed = await self._build_sentence_event(sentence, language, tone, sentence_index)
                tts_total_seconds += elapsed
                yield event["sentence"]
                yield event["audio"]
                sentence_index += 1
            pending_text = sentences[-1]

        llm_ms = (time.monotonic() - llm_started_at) * 1000

        if pending_text.strip():
            event, elapsed = await self._build_sentence_event(pending_text.strip(), language, tone, sentence_index)
            tts_total_seconds += elapsed
            yield event["sentence"]
            yield event["audio"]

        full_reply = full_reply.strip()
        await self.repository.add_message(conversation_id, "assistant", full_reply)

        total_ms = (time.monotonic() - started_at) * 1000
        tts_ms = round(tts_total_seconds * 1000)
        yield {
            "type": "done",
            "reply": full_reply,
            "asr_ms": round(asr_ms),
            "llm_ms": round(llm_ms),
            "tts_ms": tts_ms,
            "total_ms": round(total_ms),
        }

    async def _build_llm_messages(self, conversation_id: int, conversation: dict, language: str, tone: str) -> list[dict]:
        all_messages = await self.repository.get_all_messages(conversation_id)
        user_turn_count = sum(1 for message in all_messages if message["role"] == "user")

        tone_config = get_tone_config(language, tone, self.settings.tts_engine_override)
        system_prompt = self._build_system_prompt(tone_config["system_prompt"], user_turn_count)
        messages = [{"role": "system", "content": system_prompt}]

        summary = await self._maybe_summarize(conversation_id, conversation)
        if summary:
            messages.append({"role": "system", "content": f"Conversation so far: {summary}"})

        recent_messages = await self.repository.get_messages(conversation_id, limit=self.settings.recent_messages)
        messages.extend({"role": message["role"], "content": message["content"]} for message in recent_messages)
        return messages

    async def _maybe_summarize(self, conversation_id: int, conversation: dict) -> str | None:
        total_messages = await self.repository.get_message_count(conversation_id)
        if total_messages <= self.settings.summarize_threshold:
            return conversation.get("summary") or None

        summarized_up_to = conversation.get("summarized_up_to") or 0
        unsummarized = await self.repository.get_messages_after(conversation_id, summarized_up_to)
        if len(unsummarized) <= self.settings.recent_messages:
            return conversation.get("summary") or None

        to_summarize = unsummarized[:-self.settings.recent_messages]
        if not to_summarize:
            return conversation.get("summary") or None

        previous_summary = conversation.get("summary") or ""
        context_parts = []
        if previous_summary:
            context_parts.append(f"Previous summary:\n{previous_summary}\n")
        context_parts.append("New messages to incorporate:\n")
        for message in to_summarize:
            role_label = "User" if message["role"] == "user" else "Coach"
            context_parts.append(f"{role_label}: {message['content']}")
        context = "\n".join(context_parts)

        try:
            summary = await self.ai_service.summarize(context)
            await self.repository.update_summary(conversation_id, summary, to_summarize[-1]["id"])
            self.logger.info(
                "Summarized conversation %s up to msg %s: %r",
                conversation_id,
                to_summarize[-1]["id"],
                summary[:80],
            )
            return summary
        except Exception as exc:
            self.logger.error("Summarization failed: %s", exc)
            return previous_summary or None

    async def _set_title_from_first_message(self, conversation_id: int, current_title: str, transcript: str) -> None:
        if current_title != "New conversation":
            return

        title = transcript[:50].strip()
        if len(transcript) > 50:
            title += "..."
        await self.repository.update_conversation_title(conversation_id, title)

    async def _build_sentence_event(self, sentence: str, language: str, tone: str, index: int) -> tuple[dict, float]:
        started_at = time.monotonic()
        audio_bytes, audio_mime = await self.tts_service.synthesize_audio(sentence, language, tone)
        event = {
            "sentence": {"type": "sentence", "text": sentence, "index": index},
            "audio": {
                "type": "audio",
                "audio_base64": base64.b64encode(audio_bytes).decode(),
                "audio_mime": audio_mime,
                "index": index,
            },
        }
        return event, time.monotonic() - started_at

    @staticmethod
    def split_sentences(text: str) -> list[str]:
        return [part.strip() for part in SENTENCE_SPLIT.split(text) if part.strip()]

    @staticmethod
    def _build_system_prompt(base_prompt: str, user_turn_count: int) -> str:
        is_lesson_turn = user_turn_count >= 4 and (user_turn_count % 3 == 1 or user_turn_count % 3 == 0)
        if is_lesson_turn:
            return base_prompt

        prompt = re.sub(
            r"\[LESSON\].*?(?=\[PROMPT\]|\n\n[A-Z]|\Z)",
            "",
            base_prompt,
            flags=re.DOTALL | re.IGNORECASE,
        )
        prompt = re.sub(r"\[课程\].*?(?=\[话题\]|\n\n|\Z)", "", prompt, flags=re.DOTALL)
        prompt = re.sub(r"(?m)^.*(?:lesson|LESSON|课程).*every.*turns?.*$", "", prompt)
        prompt = re.sub(r"(?m)^.*Only.*\[LESSON\].*$", "", prompt)
        prompt = re.sub(r"(?m)^.*include.*lesson.*$", "", prompt, flags=re.IGNORECASE)
        prompt += (
            "\n\nIMPORTANT: This turn is a CONVERSATION-ONLY turn. "
            "Do NOT include any [LESSON] or teaching tip. "
            "Just reply naturally with [REPLY] and [PROMPT]."
        )
        return prompt
