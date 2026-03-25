"""
Static routes — serves HTML, health check, config, and PWA assets.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.config import TTS_ENGINE_OVERRIDE, VOICE_AI_DIR
from app.profiles import PROFILES
from app.tones import TONES

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_path = VOICE_AI_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return HTMLResponse(html_path.read_text())


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/config")
async def config():
    """Return available languages and tones."""
    available_tones = {}
    for lang, tones in TONES.items():
        available_tones[lang] = {k: v["label"] for k, v in tones.items()}
    return {
        "available_languages": list(PROFILES.keys()),
        "available_tones": available_tones,
        "tts_engine_override": TTS_ENGINE_OVERRIDE,
    }


# ── PWA assets ────────────────────────────────────────────────────────────────

@router.get("/manifest.json")
async def serve_manifest():
    return FileResponse(VOICE_AI_DIR / "manifest.json", media_type="application/manifest+json")


@router.get("/sw.js")
async def serve_sw():
    return FileResponse(
        VOICE_AI_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@router.get("/icon-192.png")
async def serve_icon_192():
    return FileResponse(VOICE_AI_DIR / "icon-192.png", media_type="image/png")


@router.get("/icon-512.png")
async def serve_icon_512():
    return FileResponse(VOICE_AI_DIR / "icon-512.png", media_type="image/png")
