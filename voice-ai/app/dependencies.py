"""
FastAPI dependencies — reusable injectable components.
"""

from fastapi import HTTPException, Request
from openai import AsyncOpenAI, OpenAI

from app.config import GROQ_API_KEY
import db

# ── Groq clients (module-level singletons) ───────────────────────────────────

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

async_groq_client = AsyncOpenAI(base_url=GROQ_BASE_URL, api_key=GROQ_API_KEY)
sync_groq_client = OpenAI(base_url=GROQ_BASE_URL, api_key=GROQ_API_KEY)


# ── User dependency ───────────────────────────────────────────────────────────

async def get_current_user(request: Request) -> dict:
    """Extract user from X-Username header. Returns {id, username}.

    Usage in routes:
        @router.get("/example")
        async def example(user: dict = Depends(get_current_user)):
            ...
    """
    username = request.headers.get("x-username", "").strip()
    if not username:
        raise HTTPException(status_code=401, detail="X-Username header required")
    return await db.get_or_create_user(username)
