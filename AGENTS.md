# Repository Guidelines

## Project Structure & Module Organization
This repository has two active apps:

- `voice-ai/`: FastAPI web app and PWA. Core server logic lives in `main.py`, persistence helpers in `db.py`, static client files in `index.html`, `sw.js`, and `manifest.json`, and ad hoc test scripts in `test_*.py`.
- `native-app/`: Expo + React Native prototype. Entry points are `App.tsx` and `index.ts`; shared styling is in `global.css`; app icons and splash assets are under `assets/`.
- `docs/`: product and architecture notes. Use it for longer design discussions, not runtime code.

## Build, Test, and Development Commands
- `cd voice-ai && ../venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080 --reload`: run the FastAPI service locally.
- `cd voice-ai && ./start.sh`: start HTTP on `8080` and HTTPS on `8443` for mobile microphone testing.
- `cd voice-ai && docker compose up --build`: run the web app in Docker with mounted certs and persisted `/data`.
- `python voice-ai/test_api.py`: smoke-test `/health`, `/transcribe`, and `/chat` against a running server.
- `python voice-ai/test_asr.py 5 english` and `python voice-ai/test_latency.py 5 english`: measure ASR and end-to-end latency.
- `cd native-app && npm start` or `npm run ios|android|web`: launch the Expo app.

## Coding Style & Naming Conventions
Follow the existing file style instead of introducing a new formatter. In TypeScript, use 2-space indentation, semicolons, PascalCase for components, and camelCase for hooks/state. In Python, use 4-space indentation, snake_case for functions and variables, and keep modules focused by responsibility. Name tests as `test_*.py`; keep new docs in lowercase kebab-case, for example `docs/new-feature-notes.md`.

## Testing Guidelines
There is no unified test runner yet; tests are executable scripts. Start the FastAPI server before running `voice-ai/test_*.py`. Prefer adding focused endpoint or latency scripts near the feature you changed, and keep them deterministic enough to run against `http://localhost:8080`.

## Commit & Pull Request Guidelines
Recent history mixes short summaries with Conventional Commit prefixes; prefer the clearer pattern: `feat:`, `fix:`, `docs:`, `refactor:`. Keep commits imperative and scoped, for example `feat: add Expo bottom sheet prototype`. PRs should state which app is affected, list local commands run, link the issue if one exists, and include screenshots or short recordings for UI changes.

## Security & Configuration Tips
Do not commit secrets from `voice-ai/.env`, TLS certs, or generated data. Treat Groq keys, VAPID keys, and local certificates as developer-specific. If you change ports, HTTPS behavior, or tunnel settings, update `README.md` or `voice-ai/DEPLOY.md` in the same PR.
