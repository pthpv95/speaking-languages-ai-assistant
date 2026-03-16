# Push Notifications Debugging Journey

## Problem
Adding web push notifications to a PWA running on iOS Safari over a local network with a self-signed certificate.

## Architecture
```
[Browser] → pushManager.subscribe(vapidPublicKey) → [Apple Push Service]
[Server]  → pywebpush.webpush(subscription, vapidPrivateKey) → [Apple Push Service] → [Browser SW]
```

## Issues Encountered & Solutions

### 1. Push API requires HTTPS
**Symptom:** `getUserMedia` and `PushManager` silently unavailable on HTTP.
**Fix:** Added self-signed SSL cert (`openssl req -x509 ...`) and ran uvicorn on port 8443 with `--ssl-keyfile` / `--ssl-certfile`.

### 2. iOS requires "Add to Home Screen"
**Symptom:** `PushManager` was `undefined` even over HTTPS in Safari tab.
**Reason:** iOS Safari only exposes `PushManager` in standalone PWA mode (opened from Home Screen).
**Fix:** Added `manifest.json` with `"display": "standalone"`, service worker, and Apple meta tags. User must tap Share → "Add to Home Screen" → open from there.

### 3. Server reload wiped subscriptions
**Symptom:** Subscription was saved, but push sent to 0 subscribers.
**Reason:** Uvicorn `--reload` restarts the process. In-memory `push_subscriptions = []` was reset.
**Fix:** Persisted subscriptions to `.push_subs.json`, loaded on startup.

### 4. `BadJwtToken` from Apple Push Service
**Symptom:** `403 Forbidden {"reason":"BadJwtToken"}`
**Reason:** The VAPID `sub` claim was `mailto:voiceai@localhost` — Apple rejects localhost emails.
**Fix:** Changed to `mailto:voiceai@example.com`.

### 5. `VapidPkHashMismatch` (the real blocker)
**Symptom:** `400 Bad Request {"reason":"VapidPkHashMismatch"}`
**Reason:** During debugging, VAPID keys were regenerated multiple times. The `.vapid_private.pem` and `.vapid_public_key.json` ended up from **different key pairs**. The browser subscription is cryptographically bound to the VAPID public key used at `pushManager.subscribe()` time. When the server signs with a non-matching private key, Apple rejects it.
**Fix:** Deleted all VAPID files, regenerated a single matching pair atomically in `_get_vapid_keys()`, cleared old subscriptions, re-subscribed on the device.

### 6. pywebpush couldn't parse PEM string
**Symptom:** `ValueError: Could not deserialize key data`
**Reason:** Initially stored the private key as a JSON string. `pywebpush` expects either a file path or a raw key string, not PEM in JSON.
**Fix:** Store private key as a separate `.pem` file, pass file path to `pywebpush`.

### 7. Two server processes had different state
**Symptom:** Push worked from HTTPS server but failed from HTTP server.
**Reason:** HTTP (port 8080) and HTTPS (port 8443) are separate uvicorn processes, each loading `.push_subs.json` at startup independently. HTTP server had stale/corrupt data.
**Fix:** Restarted HTTP server to reload fresh subs file.

## Key Lessons

1. **VAPID keys must be generated once and stored durably.** The public key given to `pushManager.subscribe()` must correspond exactly to the private key used for JWT signing.

2. **iOS push is PWA-only.** The app must be installed to Home Screen and opened from there — Safari tabs don't get `PushManager`.

3. **Always persist push subscriptions.** Server restarts (especially with `--reload`) will lose in-memory data.

4. **Use a real-looking email in VAPID claims.** Apple rejects `mailto:...@localhost`.

5. **Add visible debug logging for mobile.** Without desktop dev tools, an on-screen debug panel is essential for diagnosing push issues on iOS.

## Files Involved
- `main.py` — VAPID key generation, `/subscribe`, `/send-push` endpoints
- `sw.js` — Service worker with `push` event listener
- `index.html` — Push subscription logic, debug panel
- `.vapid_private.pem` — VAPID private key (gitignored)
- `.vapid_public_key.json` — VAPID public key (gitignored)
- `.push_subs.json` — Persisted push subscriptions (gitignored)
