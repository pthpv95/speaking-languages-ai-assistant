"""
LLM helpers — prompt construction and conversation summarization.
"""

import logging
import re

from app.config import (
    RECENT_MESSAGES,
    SUMMARY_MAX_TOKENS,
    SUMMARY_MODEL,
    SUMMARIZE_THRESHOLD,
)
from app.dependencies import async_groq_client
import db

logger = logging.getLogger("voice_ai")


def build_system_prompt(base_prompt: str, user_turn_count: int) -> str:
    """Dynamically strip [LESSON] instructions on non-lesson turns.

    Lessons appear on turns 4, 6, 9, 12, ... (roughly every 2-3 turns after turn 3).
    """
    is_lesson_turn = user_turn_count >= 4 and (
        user_turn_count % 3 == 1 or user_turn_count % 3 == 0
    )

    if is_lesson_turn:
        return base_prompt

    # Strip lesson-related lines so the LLM won't generate one
    prompt = base_prompt
    prompt = re.sub(
        r"\[LESSON\].*?(?=\[PROMPT\]|\n\n[A-Z]|\Z)",
        "",
        prompt,
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


async def maybe_summarize(conv_id: int, conv: dict) -> str | None:
    """If conversation is long enough, summarize older messages and cache.

    Returns the summary string, or None if not enough messages.
    """
    total = await db.get_message_count(conv_id)
    if total <= SUMMARIZE_THRESHOLD:
        return conv.get("summary") or None

    summarized_up_to = conv.get("summarized_up_to") or 0
    unsummarized = await db.get_messages_after(conv_id, summarized_up_to)

    if len(unsummarized) <= RECENT_MESSAGES:
        return conv.get("summary") or None

    to_summarize = unsummarized[:-RECENT_MESSAGES]
    if not to_summarize:
        return conv.get("summary") or None

    new_max_id = to_summarize[-1]["id"]
    old_summary = conv.get("summary") or ""

    context = ""
    if old_summary:
        context = f"Previous summary:\n{old_summary}\n\nNew messages to incorporate:\n"

    for m in to_summarize:
        role_label = "User" if m["role"] == "user" else "Coach"
        context += f"{role_label}: {m['content']}\n"

    try:
        resp = await async_groq_client.chat.completions.create(
            model=SUMMARY_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize the conversation below in 2-4 concise sentences. "
                        "Capture: user's name/level, topics discussed, key corrections made, "
                        "and where the conversation left off. Write in third person. "
                        "Keep it under 100 words."
                    ),
                },
                {"role": "user", "content": context},
            ],
            max_tokens=SUMMARY_MAX_TOKENS,
            temperature=0.3,
        )
        summary = resp.choices[0].message.content.strip()
        await db.update_summary(conv_id, summary, new_max_id)
        logger.info(f"Summarized conv {conv_id} up to msg {new_max_id}: {summary[:80]!r}")
        return summary
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return old_summary or None
