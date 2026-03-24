from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.api.deps import get_push_service
from backend.schemas import SendPushResponse, SubscriptionStatusResponse, VapidPublicKeyResponse

router = APIRouter(tags=["push"])


@router.get("/vapid-public-key", response_model=VapidPublicKeyResponse)
async def vapid_public_key(push_service=Depends(get_push_service)) -> VapidPublicKeyResponse:
    return VapidPublicKeyResponse.model_validate(push_service.get_public_key())


@router.post("/subscribe", response_model=SubscriptionStatusResponse)
async def subscribe(request: Request, push_service=Depends(get_push_service)) -> SubscriptionStatusResponse:
    return SubscriptionStatusResponse.model_validate(push_service.subscribe(await request.json()))


@router.post("/unsubscribe", response_model=SubscriptionStatusResponse)
async def unsubscribe(request: Request, push_service=Depends(get_push_service)) -> SubscriptionStatusResponse:
    return SubscriptionStatusResponse.model_validate(push_service.unsubscribe(await request.json()))


@router.post("/send-push", response_model=SendPushResponse)
async def send_push(request: Request, push_service=Depends(get_push_service)) -> SendPushResponse:
    return SendPushResponse.model_validate(push_service.send_push(await request.json()))
