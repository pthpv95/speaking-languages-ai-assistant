# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Expo React Native app for the Voice AI language coaching platform. Currently scaffolded — connects to the FastAPI backend in `../voice-ai/`.

## Commands

```bash
# Install dependencies
yarn install

# Start Expo dev server
yarn start

# Platform-specific
yarn ios
yarn android
yarn web
```

No test runner is configured yet.

## Stack

- **Expo 55** with React 19 / React Native 0.83
- **HeroUI Native** — component library (Button, BottomSheet, Input, Card, etc.)
- **Tailwind CSS v4** via **Uniwind** — use `className` on RN views (e.g. `className="flex-1 bg-background"`)
- **TypeScript** with strict mode

## Architecture

Entry: `index.ts` → `App.tsx`

Every screen must be wrapped in:
```tsx
<GestureHandlerRootView style={{ flex: 1 }}>
  <HeroUINativeProvider>
    {/* content */}
  </HeroUINativeProvider>
</GestureHandlerRootView>
```

**Styling**: Tailwind utilities via `className` prop (Uniwind transforms these for RN). Metro is configured with `withUniwindConfig` in `metro.config.js` and global styles live in `global.css`.

## Backend API (../voice-ai/)

The native app consumes these endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Status check |
| `/config` | GET | Active language & TTS voice |
| `/transcribe` | POST | Audio blob → transcript text |
| `/chat` | POST | Transcript → AI reply + MP3 base64 |
| `/ws/chat` | WS | Streaming: audio → progressive tokens → TTS |
| `/conversations` | GET/POST | Conversation history (SQLite) |
| `/history` | DELETE | Clear conversation |

Backend runs on `http://localhost:8080` (or HTTPS via self-signed cert).

## Key Conventions

- Use HeroUI Native components over raw RN primitives where available
- Tailwind classes via `className` — not inline `style` objects
- The backend supports multiple languages (english, chinese, spanish, french, japanese) configured via `LANGUAGE` env var
