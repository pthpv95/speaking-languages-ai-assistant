from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from backend.core.config import Settings


class PushService:
    def __init__(self, settings: Settings, logger) -> None:
        self.settings = settings
        self.logger = logger
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.vapid_keys = self._get_vapid_keys()
        self.subscriptions_file = self.settings.data_dir / ".push_subs.json"
        self.subscriptions: list[dict] = self._load_subscriptions()
        self.logger.info("Loaded %s push subscription(s)", len(self.subscriptions))

    def get_public_key(self) -> dict:
        return {"public_key": self.vapid_keys["public_key"]}

    def subscribe(self, subscription: dict) -> dict:
        endpoints = {item.get("endpoint") for item in self.subscriptions}
        if subscription.get("endpoint") not in endpoints:
            self.subscriptions.append(subscription)
            self._save_subscriptions()
        return {"status": "subscribed"}

    def unsubscribe(self, subscription: dict) -> dict:
        endpoint = subscription.get("endpoint")
        self.subscriptions[:] = [item for item in self.subscriptions if item.get("endpoint") != endpoint]
        self._save_subscriptions()
        return {"status": "unsubscribed"}

    def send_push(self, payload: dict) -> dict:
        body = json.dumps(
            {
                "title": payload.get("title", "Voice AI Coach"),
                "body": payload.get("body", "Time to practice! Your language coach is ready."),
            }
        )
        sent = 0
        for subscription in self.subscriptions[:]:
            try:
                webpush(
                    subscription_info=subscription,
                    data=body,
                    vapid_private_key=self.vapid_keys["private_pem_path"],
                    vapid_claims={"sub": self.settings.vapid_subject},
                )
                sent += 1
            except WebPushException as exc:
                if getattr(exc, "response", None) is not None and exc.response.status_code in (404, 410):
                    self.subscriptions.remove(subscription)
                    self._save_subscriptions()
            except Exception as exc:
                self.logger.warning("Push error: %s: %s", type(exc).__name__, exc)
        return {"sent": sent, "total": len(self.subscriptions)}

    def _get_vapid_keys(self) -> dict:
        public_path = self.settings.data_dir / ".vapid_public_key.json"
        private_path = self.settings.data_dir / ".vapid_private.pem"
        if public_path.exists() and private_path.exists():
            public_data = json.loads(public_path.read_text())
            return {"private_pem_path": str(private_path), "public_key": public_data["public_key"]}

        vapid = Vapid()
        vapid.generate_keys()
        raw_public = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        public_key = base64.urlsafe_b64encode(raw_public).decode().rstrip("=")
        private_path.write_bytes(vapid.private_pem())
        public_path.write_text(json.dumps({"public_key": public_key}))
        return {"private_pem_path": str(private_path), "public_key": public_key}

    def _load_subscriptions(self) -> list[dict]:
        if self.subscriptions_file.exists():
            return json.loads(self.subscriptions_file.read_text())
        return []

    def _save_subscriptions(self) -> None:
        self.subscriptions_file.write_text(json.dumps(self.subscriptions))
