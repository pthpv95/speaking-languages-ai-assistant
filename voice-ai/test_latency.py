"""
Latency load test — measures ASR → LLM → TTS pipeline across multiple runs.
Target: total server time < 1000ms per request.

Usage:
  python test_latency.py              # 5 runs, English
  python test_latency.py 10           # 10 runs
  python test_latency.py 5 chinese    # 5 runs, Chinese
"""
import requests, wave, struct, math, io, base64, time, sys, json

BASE = "http://localhost:8080"
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
LANG = sys.argv[2] if len(sys.argv) > 2 else None
TARGET_MS = 2000

PROMPTS = {
    "english": [
        "Hello, let's practice English today.",
        "I went to the store yesterday.",
        "Can you teach me some slang?",
        "What does break a leg mean?",
        "I want to improve my pronunciation.",
    ],
    "chinese": [
        "你好，我想练习中文。",
        "我昨天去了超市。",
        "教我一些口语吧。",
        "入乡随俗是什么意思？",
        "我想提高我的发音。",
    ],
}


def gen_wav(duration=2):
    """Generate a synthetic WAV file (2s, 400Hz tone)."""
    sr, freq = 16000, 400
    n = sr * duration
    samples = [int(20000 * math.sin(2 * math.pi * freq * i / sr)) for i in range(n)]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(struct.pack(f"<{n}h", *samples))
    buf.seek(0)
    return buf


def main():
    # Health check
    r = requests.get(f"{BASE}/health")
    if r.status_code != 200:
        print(f"Server not running at {BASE}")
        sys.exit(1)
    health = r.json()
    lang = LANG or health.get("language", "english")
    print(f"Server: {json.dumps(health, indent=2)}")

    # Switch language if needed
    if lang != health.get("language"):
        r = requests.post(f"{BASE}/language", data={"language": lang})
        if r.status_code != 200:
            print(f"Failed to switch to {lang}: {r.text}")
            sys.exit(1)
        print(f"Switched to: {lang}")

    prompts = PROMPTS.get(lang, PROMPTS["english"])
    wav = gen_wav()

    print(f"\n{'='*60}")
    print(f"  LATENCY TEST — {RUNS} runs, language={lang}, target<{TARGET_MS}ms")
    print(f"{'='*60}\n")

    asr_times = []
    llm_times = []
    tts_times = []
    total_times = []
    e2e_times = []
    failures = 0

    for i in range(RUNS):
        prompt = prompts[i % len(prompts)]
        wav.seek(0)

        # Clear history each run for consistent results
        requests.delete(f"{BASE}/history")

        t_start = time.monotonic()

        # ASR
        t0 = time.monotonic()
        try:
            r = requests.post(f"{BASE}/transcribe", files={"audio": ("test.wav", wav, "audio/wav")})
            r.raise_for_status()
        except Exception as e:
            print(f"  Run {i+1}: ASR FAILED — {e}")
            failures += 1
            continue
        asr_client = round((time.monotonic() - t0) * 1000)

        # LLM + TTS
        t0 = time.monotonic()
        try:
            r = requests.post(f"{BASE}/chat", data={"transcript": prompt})
            r.raise_for_status()
            d = r.json()
        except Exception as e:
            print(f"  Run {i+1}: CHAT FAILED — {e}")
            failures += 1
            continue
        chat_client = round((time.monotonic() - t0) * 1000)

        e2e = round((time.monotonic() - t_start) * 1000)
        llm_ms = d["llm_ms"]
        tts_ms = d["tts_ms"]
        total_ms = d["total_ms"]
        mp3_size = len(base64.b64decode(d["mp3_base64"]))
        reply_len = len(d["reply"])

        asr_times.append(asr_client)
        llm_times.append(llm_ms)
        tts_times.append(tts_ms)
        total_times.append(total_ms)
        e2e_times.append(e2e)

        icon = "🟢" if total_ms < TARGET_MS else "🔴"
        print(f"  {icon} Run {i+1}: ASR={asr_client}ms  LLM={llm_ms}ms  TTS={tts_ms}ms  "
              f"server={total_ms}ms  e2e={e2e}ms  reply={reply_len}ch  mp3={mp3_size}B")

    if not total_times:
        print("\nAll runs failed!")
        sys.exit(1)

    # Summary
    n = len(total_times)
    avg = lambda t: sum(t) // n
    p50 = lambda t: sorted(t)[n // 2]
    p95 = lambda t: sorted(t)[min(int(n * 0.95), n - 1)]
    worst = lambda t: max(t)

    print(f"\n{'='*60}")
    print(f"  RESULTS ({n}/{RUNS} successful)")
    print(f"{'='*60}")
    print(f"                 avg      p50      p95    worst")
    print(f"  ASR (client) {avg(asr_times):5d}ms  {p50(asr_times):5d}ms  {p95(asr_times):5d}ms  {worst(asr_times):5d}ms")
    print(f"  LLM (server) {avg(llm_times):5d}ms  {p50(llm_times):5d}ms  {p95(llm_times):5d}ms  {worst(llm_times):5d}ms")
    print(f"  TTS (server) {avg(tts_times):5d}ms  {p50(tts_times):5d}ms  {p95(tts_times):5d}ms  {worst(tts_times):5d}ms")
    print(f"  Total(server){avg(total_times):5d}ms  {p50(total_times):5d}ms  {p95(total_times):5d}ms  {worst(total_times):5d}ms")
    print(f"  E2E (client) {avg(e2e_times):5d}ms  {p50(e2e_times):5d}ms  {p95(e2e_times):5d}ms  {worst(e2e_times):5d}ms")

    passed = sum(1 for t in total_times if t < TARGET_MS)
    pct = passed * 100 // n
    print(f"\n  Under {TARGET_MS}ms: {passed}/{n} ({pct}%)")

    if pct >= 80:
        print(f"  ✅ PASS — {pct}% of requests under target")
    elif pct >= 50:
        print(f"  ⚠️  MARGINAL — {pct}% under target, TTS may be slow")
    else:
        print(f"  ❌ FAIL — only {pct}% under target")
        print(f"     Bottleneck: {'TTS' if avg(tts_times) > avg(llm_times) else 'LLM'} "
              f"(avg {max(avg(tts_times), avg(llm_times))}ms)")

    if failures:
        print(f"  ⚠️  {failures} failed request(s)")

    sys.exit(0 if pct >= 80 else 1)


if __name__ == "__main__":
    main()
