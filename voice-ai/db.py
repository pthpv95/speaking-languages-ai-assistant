"""
Async SQLite wrapper for Voice AI multi-user support.
Manages users, conversations, and messages.
"""

import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "voice_ai.db"


async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT UNIQUE NOT NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                title       TEXT DEFAULT 'New conversation',
                language    TEXT NOT NULL DEFAULT 'chinese',
                tone        TEXT NOT NULL DEFAULT 'hype',
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role            TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content         TEXT NOT NULL,
                created_at      TEXT DEFAULT (datetime('now'))
            );
        """)
        await db.commit()


async def get_or_create_user(username: str) -> dict:
    """Get existing user or create new one. Returns {id, username}."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Try to find existing
        cursor = await db.execute(
            "SELECT id, username FROM users WHERE username = ?", (username,)
        )
        row = await cursor.fetchone()
        if row:
            return {"id": row["id"], "username": row["username"]}
        # Create new
        cursor = await db.execute(
            "INSERT INTO users (username) VALUES (?)", (username,)
        )
        await db.commit()
        return {"id": cursor.lastrowid, "username": username}


async def create_conversation(user_id: int, language: str = "chinese", tone: str = "hype") -> dict:
    """Create a new conversation. Returns {id, title, language, tone, updated_at}."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO conversations (user_id, language, tone) VALUES (?, ?, ?)",
            (user_id, language, tone),
        )
        await db.commit()
        conv_id = cursor.lastrowid
        cursor = await db.execute(
            "SELECT id, title, language, tone, updated_at FROM conversations WHERE id = ?",
            (conv_id,),
        )
        row = await cursor.fetchone()
        return dict(row)


async def list_conversations(user_id: int) -> list[dict]:
    """List all conversations for a user, newest first."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, language, tone, updated_at FROM conversations "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_conversation(conv_id: int, user_id: int) -> dict | None:
    """Get a single conversation if it belongs to user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, language, tone, updated_at FROM conversations "
            "WHERE id = ? AND user_id = ?",
            (conv_id, user_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_conversation_title(conv_id: int, title: str):
    """Update conversation title."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
            (title, conv_id),
        )
        await db.commit()


async def update_conversation_settings(conv_id: int, language: str | None = None, tone: str | None = None):
    """Update conversation language and/or tone."""
    async with aiosqlite.connect(DB_PATH) as db:
        if language is not None:
            await db.execute(
                "UPDATE conversations SET language = ?, updated_at = datetime('now') WHERE id = ?",
                (language, conv_id),
            )
        if tone is not None:
            await db.execute(
                "UPDATE conversations SET tone = ?, updated_at = datetime('now') WHERE id = ?",
                (tone, conv_id),
            )
        await db.commit()


async def delete_conversation(conv_id: int, user_id: int):
    """Delete a conversation if it belongs to user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conv_id, user_id),
        )
        await db.commit()


async def add_message(conv_id: int, role: str, content: str):
    """Add a message and update conversation's updated_at."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conv_id, role, content),
        )
        await db.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
            (conv_id,),
        )
        await db.commit()


async def get_messages(conv_id: int, limit: int = 10) -> list[dict]:
    """Get last N messages for LLM context (oldest first within the window)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT role, content FROM ("
            "  SELECT id, role, content FROM messages "
            "  WHERE conversation_id = ? ORDER BY id DESC LIMIT ?"
            ") sub ORDER BY id ASC",
            (conv_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_all_messages(conv_id: int) -> list[dict]:
    """Get all messages for UI rendering (oldest first)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT role, content, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id ASC",
            (conv_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
