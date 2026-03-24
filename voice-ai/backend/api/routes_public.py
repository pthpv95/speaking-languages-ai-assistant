from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from backend.core.coach_config import PROFILES, TONES
from backend.schemas import ConfigResponse, HealthResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request) -> HTMLResponse:
    html_path = request.app.state.settings.html_path
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return HTMLResponse(html_path.read_text())


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/config", response_model=ConfigResponse)
async def config(request: Request) -> ConfigResponse:
    available_tones = {
        language: {tone_name: tone["label"] for tone_name, tone in tones.items()}
        for language, tones in TONES.items()
    }
    return ConfigResponse(
        available_languages=list(PROFILES.keys()),
        available_tones=available_tones,
        tts_engine_override=request.app.state.settings.tts_engine_override,
    )


@router.get("/manifest.json")
async def serve_manifest(request: Request) -> FileResponse:
    return FileResponse(request.app.state.settings.manifest_path, media_type="application/manifest+json")


@router.get("/sw.js")
async def serve_service_worker(request: Request) -> FileResponse:
    return FileResponse(
        request.app.state.settings.service_worker_path,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@router.get("/icon-192.png")
async def serve_icon_192(request: Request) -> FileResponse:
    return FileResponse(request.app.state.settings.icon_192_path, media_type="image/png")


@router.get("/icon-512.png")
async def serve_icon_512(request: Request) -> FileResponse:
    return FileResponse(request.app.state.settings.icon_512_path, media_type="image/png")
