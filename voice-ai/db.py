from backend.core.config import get_settings
from backend.repositories.db import SQLiteRepository

_repository = SQLiteRepository(get_settings().db_path)


async def init_db():
    await _repository.init_db()


async def get_or_create_user(username: str):
    return await _repository.get_or_create_user(username)


async def create_conversation(user_id: int, language: str = "chinese", tone: str = "hype"):
    return await _repository.create_conversation(user_id, language, tone)


async def list_conversations(user_id: int):
    return await _repository.list_conversations(user_id)


async def get_conversation(conv_id: int, user_id: int):
    return await _repository.get_conversation(conv_id, user_id)


async def update_conversation_title(conv_id: int, title: str):
    await _repository.update_conversation_title(conv_id, title)


async def update_conversation_settings(conv_id: int, language: str | None = None, tone: str | None = None):
    await _repository.update_conversation_settings(conv_id, language, tone)


async def add_message(conv_id: int, role: str, content: str):
    await _repository.add_message(conv_id, role, content)


async def get_messages(conv_id: int, limit: int = 10):
    return await _repository.get_messages(conv_id, limit)


async def get_all_messages(conv_id: int):
    return await _repository.get_all_messages(conv_id)


async def get_messages_after(conv_id: int, after_id: int):
    return await _repository.get_messages_after(conv_id, after_id)


async def get_message_count(conv_id: int):
    return await _repository.get_message_count(conv_id)


async def update_summary(conv_id: int, summary: str, summarized_up_to: int):
    await _repository.update_summary(conv_id, summary, summarized_up_to)


__all__ = [
    "SQLiteRepository",
    "init_db",
    "get_or_create_user",
    "create_conversation",
    "list_conversations",
    "get_conversation",
    "update_conversation_title",
    "update_conversation_settings",
    "add_message",
    "get_messages",
    "get_all_messages",
    "get_messages_after",
    "get_message_count",
    "update_summary",
]
