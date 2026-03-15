"""
Tests /transcribe and /chat endpoints directly with a synthetic WAV file.
No browser or microphone needed.
"""
import requests, wave, struct, math, io, base64, time

BASE = "http://localhost:8080"

# 1. Health
r = requests.get(f"{BASE}/health")
assert r.status_code == 200, f"Health failed: {r.text}"
print("✅ Health:", r.json())

# 2. Generate a 2s 400Hz WAV (Groq needs >= 1s)
SR = 16000; FREQ = 400; DUR = 2
samples = [int(20000 * math.sin(2 * math.pi * FREQ * i / SR)) for i in range(SR * DUR)]
buf = io.BytesIO()
with wave.open(buf, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(struct.pack(f"<{SR*DUR}h", *samples))
buf.seek(0)

# 3. POST /transcribe
t0 = time.monotonic()
r  = requests.post(f"{BASE}/transcribe", files={"audio": ("test.wav", buf, "audio/wav")})
assert r.status_code == 200, f"Transcribe failed: {r.text}"
asr_ms = round((time.monotonic() - t0) * 1000)
print(f"✅ /transcribe ({asr_ms}ms): {r.json()}")

# 4. POST /chat with a known phrase
t0  = time.monotonic()
r   = requests.post(f"{BASE}/chat", data={"transcript": "Hello, let's practice English today."})
assert r.status_code == 200, f"Chat failed: {r.text}"
d   = r.json()
end = round((time.monotonic() - t0) * 1000)

print(f"✅ /chat   ({end}ms end-to-end from client)")
print(f"   LLM: {d['llm_ms']}ms | TTS: {d['tts_ms']}ms | server total: {d['total_ms']}ms")
print(f"   Reply: {d['reply'][:100]}")
print(f"   MP3 size: {len(base64.b64decode(d['mp3_base64']))} bytes")

# 5. Latency verdict
total = d["total_ms"]
if total < 700:
    print(f"\n🟢 FAST — {total}ms (target <800ms ✅)")
elif total < 1000:
    print(f"\n🟡 OK   — {total}ms (slightly over target)")
else:
    print(f"\n🔴 SLOW — {total}ms (check Groq rate limits)")
