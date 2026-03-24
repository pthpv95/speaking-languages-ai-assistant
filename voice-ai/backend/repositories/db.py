from __future__ import annotations

from pathlib import Path

import aiosqlite


class SQLiteRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    async def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.executescript(
                """
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
                    summary     TEXT DEFAULT '',
                    summarized_up_to INTEGER DEFAULT 0,
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
                """
            )
            await db.commit()
            try:
                await db.execute("SELECT summary FROM conversations LIMIT 1")
            except Exception:
                await db.execute("ALTER TABLE conversations ADD COLUMN summary TEXT DEFAULT ''")
                await db.execute("ALTER TABLE conversations ADD COLUMN summarized_up_to INTEGER DEFAULT 0")
                await db.commit()

    async def get_or_create_user(self, username: str) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT id, username FROM users WHERE username = ?", (username,))
            row = await cursor.fetchone()
            if row:
                return dict(row)

            cursor = await db.execute("INSERT INTO users (username) VALUES (?)", (username,))
            await db.commit()
            return {"id": cursor.lastrowid, "username": username}

    async def create_conversation(self, user_id: int, language: str, tone: str) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "INSERT INTO conversations (user_id, language, tone) VALUES (?, ?, ?)",
                (user_id, language, tone),
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT id, title, language, tone, updated_at FROM conversations WHERE id = ?",
                (cursor.lastrowid,),
            )
            row = await cursor.fetchone()
            return dict(row)

    async def list_conversations(self, user_id: int) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, title, language, tone, updated_at
                FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_conversation(self, conv_id: int, user_id: int) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, title, language, tone, summary, summarized_up_to, updated_at
                FROM conversations
                WHERE id = ? AND user_id = ?
                """,
                (conv_id, user_id),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_conversation_title(self, conv_id: int, title: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
                (title, conv_id),
            )
            await db.commit()

    async def update_conversation_settings(
        self, conv_id: int, language: str | None = None, tone: str | None = None
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
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

    async def add_message(self, conv_id: int, role: str, content: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conv_id, role, content),
            )
            await db.execute(
                "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
                (conv_id,),
            )
            await db.commit()

    async def get_messages(self, conv_id: int, limit: int = 10) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT role, content FROM (
                    SELECT id, role, content
                    FROM messages
                    WHERE conversation_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ) recent
                ORDER BY id ASC
                """,
                (conv_id, limit),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_all_messages(self, conv_id: int) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conv_id,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_messages_after(self, conv_id: int, after_id: int) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, role, content
                FROM messages
                WHERE conversation_id = ? AND id > ?
                ORDER BY id ASC
                """,
                (conv_id, after_id),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_message_count(self, conv_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = ?", (conv_id,))
            row = await cursor.fetchone()
            return row[0]

    async def update_summary(self, conv_id: int, summary: str, summarized_up_to: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE conversations SET summary = ?, summarized_up_to = ? WHERE id = ?",
                (summary, summarized_up_to, conv_id),
            )
            await db.commit()
