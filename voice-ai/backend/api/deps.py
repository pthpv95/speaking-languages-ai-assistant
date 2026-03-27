from __future__ import annotations

from fastapi import HTTPException, Request


def get_repository(request: Request):
    return request.app.state.repository


def get_conversation_service(request: Request):
    return request.app.state.conversation_service


def get_push_service(request: Request):
    return request.app.state.push_service


async def get_current_user(request: Request) -> dict:
    username = request.headers.get("x-username", "").strip()
    if not username:
        raise HTTPException(status_code=401, detail="X-Username header required")
    repository = get_repository(request)
    return await repository.get_or_create_user(username)


async def get_optional_user(request: Request) -> dict | None:
    username = request.headers.get("x-username", "").strip()
    if not username:
        return None
    repository = get_repository(request)
    return await repository.get_or_create_user(username)
