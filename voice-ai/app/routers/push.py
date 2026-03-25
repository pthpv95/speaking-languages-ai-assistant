"""
PWA push notification routes — VAPID key management, subscribe/unsubscribe, send.
"""

import base64
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request

from app.config import DATA_DIR

logger = logging.getLogger("voice_ai")

router = APIRouter(tags=["push"])


# ── VAPID key management ─────────────────────────────────────────────────────

def _get_vapid_keys() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pub_path = DATA_DIR / ".vapid_public_key.json"
    pem_path = DATA_DIR / ".vapid_private.pem"

    if pub_path.exists() and pem_path.exists():
        pub_data = json.loads(pub_path.read_text())
        return {"private_pem_path": str(pem_path), "public_key": pub_data["public_key"]}

    from py_vapid import Vapid
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    vapid = Vapid()
    vapid.generate_keys()
    raw_pub = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    public_key = base64.urlsafe_b64encode(raw_pub).decode().rstrip("=")
    pem_path.write_bytes(vapid.private_pem())
    pub_path.write_text(json.dumps({"public_key": public_key}))
    return {"private_pem_path": str(pem_path), "public_key": public_key}


_VAPID_KEYS = _get_vapid_keys()
_SUBS_FILE = DATA_DIR / ".push_subs.json"


def _load_subs() -> list[dict]:
    if _SUBS_FILE.exists():
        return json.loads(_SUBS_FILE.read_text())
    return []


def _save_subs(subs: list[dict]) -> None:
    _SUBS_FILE.write_text(json.dumps(subs))


_subscriptions: list[dict] = _load_subs()
logger.info(f"Loaded {len(_subscriptions)} push subscription(s)")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/vapid-public-key")
async def vapid_public_key():
    return {"public_key": _VAPID_KEYS["public_key"]}


@router.post("/subscribe")
async def subscribe(request: Request):
    sub = await request.json()
    endpoints = {s.get("endpoint") for s in _subscriptions}
    if sub.get("endpoint") not in endpoints:
        _subscriptions.append(sub)
        _save_subs(_subscriptions)
    return {"status": "subscribed"}


@router.post("/unsubscribe")
async def unsubscribe(request: Request):
    sub = await request.json()
    _subscriptions[:] = [
        s for s in _subscriptions if s.get("endpoint") != sub.get("endpoint")
    ]
    _save_subs(_subscriptions)
    return {"status": "unsubscribed"}


@router.post("/send-push")
async def send_push(request: Request):
    from pywebpush import webpush, WebPushException

    data = await request.json()
    payload = json.dumps({
        "title": data.get("title", "Voice AI Coach"),
        "body": data.get("body", "Time to practice! Your language coach is ready."),
    })

    sent = 0
    for sub in _subscriptions[:]:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=_VAPID_KEYS["private_pem_path"],
                vapid_claims={"sub": "mailto:voiceai@example.com"},
            )
            sent += 1
        except WebPushException as e:
            if (
                hasattr(e, "response")
                and e.response is not None
                and e.response.status_code in (404, 410)
            ):
                _subscriptions.remove(sub)
                _save_subs(_subscriptions)
        except Exception as e:
            logger.warning(f"Push error: {type(e).__name__}: {e}")

    return {"sent": sent, "total": len(_subscriptions)}
