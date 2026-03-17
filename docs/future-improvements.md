# Future Improvements — Premium Options

## Current Performance (Free Tier)

| Step | Avg Latency | Service |
|------|-------------|---------|
| ASR | ~350ms (cold start ~2.5s) | Groq `whisper-large-v3-turbo` |
| LLM | ~500ms | Groq `llama-3.3-70b-versatile` |
| TTS | ~1000ms | edge-tts (Microsoft Azure) |
| **Total** | **~1500ms** | — |

### Known Bottlenecks

- **TTS (edge-tts):** ~800-1200ms per call due to new WebSocket connection to Azure each time. No connection reuse.
- **ASR cold start:** First request ~2.5s while Groq spins up the model. Subsequent requests ~300-400ms.
- **Groq rate limits:** Free tier has 3600 tokens/day limit. Auto-fallback to edge-tts on 429.

---

## TTS Upgrades

| Service | Expected Latency | Quality | Cost | Notes |
|---------|-----------------|---------|------|-------|
| **Cartesia Sonic** | ~200ms | Excellent | Free: 10min/mo, Pro: $5/mo | Purpose-built for real-time. Streaming support. Best latency. |
| **Deepgram Aura** | ~250ms | Good | Free: $200 credit | Fast REST API, simple integration. |
| **ElevenLabs Turbo v2.5** | ~300ms | Best quality | Free: 10k chars/mo, $5/mo | Most natural voices. Multilingual. |
| **OpenAI TTS** | ~400ms | Very good | $15/1M chars | `tts-1` for speed, `tts-1-hd` for quality. |
| **Browser SpeechSynthesis** | ~0ms (client) | Varies by OS | Free | Zero server cost. Eliminates TTS network entirely. Quality depends on browser/OS. |

### Recommendation

**Cartesia Sonic** for lowest latency. **ElevenLabs** for best voice quality. **Browser TTS** as a zero-cost instant option (can run alongside server TTS as user preference).

---

## ASR Upgrades

| Service | Expected Latency | Cost | Notes |
|---------|-----------------|------|-------|
| **Deepgram Nova-2** | ~100-200ms | Free: $200 credit | Streaming support, very fast. |
| **AssemblyAI** | ~200-300ms | Free: 100hrs/mo | Good accuracy, simple API. |
| **Groq whisper-large-v3-turbo** (current) | ~300-400ms | Free tier | Good enough. Cold start is the main issue. |

### Fixing Cold Start

- Add a **warm-up request** on server startup (send a short silent WAV to `/transcribe`).
- Or use a **keep-alive cron** that pings the ASR model every 5 minutes.

---

## LLM Upgrades

| Service | Expected Latency | Cost | Notes |
|---------|-----------------|------|-------|
| **Groq llama-3.3-70b** (current) | ~500ms | Free tier | Good quality, fast inference. |
| **Groq llama-4-scout** | ~300ms | Free tier | Newer, potentially faster. |
| **Cerebras** | ~100-200ms | Free tier available | Fastest LLM inference. Worth testing. |
| **OpenAI gpt-4o-mini** | ~400ms | $0.15/1M input | Good quality, predictable latency. |

---

## Architecture Improvements

### Streaming Pipeline (biggest impact)

Instead of sequential ASR → LLM → TTS, stream each step:

```
Browser audio chunks → ASR (streaming) → LLM (streaming tokens) → TTS (streaming audio)
                                                                  ↓
                                                          Play audio as it arrives
```

- User hears the first word ~500ms after speaking (vs ~1500ms now).
- Requires WebSocket or SSE transport.
- Cartesia + Deepgram both support streaming natively.

### Connection Pooling

- Reuse HTTP/WebSocket connections across TTS calls (current edge-tts creates a new connection each time).
- Use `aiohttp.ClientSession` with connection keep-alive for external API calls.

### Browser-Side TTS Hybrid

- Return text immediately from `/chat`, let browser start speaking via `SpeechSynthesis`.
- Optionally stream higher-quality server TTS in background, swap audio if it arrives in time.
- Zero-latency perceived TTS with quality upgrade when available.

---

## Target Latency Goals

| Tier | Total Latency | Stack |
|------|--------------|-------|
| Current (free) | ~1500ms | Groq Whisper + Groq LLM + edge-tts |
| Mid-tier ($5-10/mo) | ~600-800ms | Deepgram Nova-2 + Groq LLM + Cartesia |
| Premium (streaming) | ~300-500ms first word | Deepgram streaming + Cerebras + Cartesia streaming |
| Hybrid (free + fast) | ~500ms perceived | Groq + Browser TTS + optional server TTS |
