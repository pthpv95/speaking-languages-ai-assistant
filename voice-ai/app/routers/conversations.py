"""
User and conversation CRUD routes.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import get_current_user
import db

router = APIRouter(prefix="/api", tags=["conversations"])


@router.post("/users")
async def create_user(request: Request):
    """Create or lookup user. Body: {"username": "..."}"""
    body = await request.json()
    username = body.get("username", "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username required")
    return await db.get_or_create_user(username)


@router.get("/conversations")
async def list_conversations(user: dict = Depends(get_current_user)):
    return await db.list_conversations(user["id"])


@router.post("/conversations")
async def create_conversation(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    language = body.get("language", "chinese")
    tone = body.get("tone", "hype")
    return await db.create_conversation(user["id"], language, tone)


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: int, user: dict = Depends(get_current_user)):
    conv = await db.get_conversation(conv_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    messages = await db.get_all_messages(conv_id)
    return {**conv, "messages": messages}


@router.patch("/conversations/{conv_id}")
async def update_conversation(
    conv_id: int, request: Request, user: dict = Depends(get_current_user)
):
    conv = await db.get_conversation(conv_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")

    body = await request.json()
    if "title" in body:
        await db.update_conversation_title(conv_id, body["title"])
    if "language" in body or "tone" in body:
        await db.update_conversation_settings(
            conv_id, language=body.get("language"), tone=body.get("tone")
        )
    return await db.get_conversation(conv_id, user["id"])
