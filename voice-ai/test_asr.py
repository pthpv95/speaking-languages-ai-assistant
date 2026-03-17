"""
ASR (transcribe) latency test — sends WAV files of varying durations to /transcribe.
Target: < 500ms per request.

Usage:
  python test_asr.py              # 5 runs, durations 1-5s
  python test_asr.py 10           # 10 runs
  python test_asr.py 5 chinese    # 5 runs, Chinese
"""
import requests, wave, struct, math, io, time, sys, json

BASE = "http://localhost:8080"
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
LANG = sys.argv[2] if len(sys.argv) > 2 else None
TARGET_MS = 500

DURATIONS = [1, 2, 3, 4, 5]  # seconds — cycles through these


def gen_wav(duration=2):
    """Generate a synthetic WAV file (400Hz tone)."""
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

    print(f"\n{'='*60}")
    print(f"  ASR LATENCY TEST — {RUNS} runs, language={lang}, target<{TARGET_MS}ms")
    print(f"  Model: {health.get('asr', 'unknown')}")
    print(f"{'='*60}\n")

    times = []
    sizes = []
    failures = 0

    for i in range(RUNS):
        dur = DURATIONS[i % len(DURATIONS)]
        wav = gen_wav(dur)
        wav_size = wav.getbuffer().nbytes

        t0 = time.monotonic()
        try:
            r = requests.post(
                f"{BASE}/transcribe",
                files={"audio": ("test.wav", wav, "audio/wav")},
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"  Run {i+1}: FAILED — {e}")
            failures += 1
            continue

        ms = round((time.monotonic() - t0) * 1000)
        transcript = data.get("transcript", "")
        error = data.get("error", "")

        times.append(ms)
        sizes.append(wav_size)

        icon = "🟢" if ms < TARGET_MS else "🔴"
        status = f"'{transcript[:50]}'" if transcript else f"(empty: {error})"
        print(f"  {icon} Run {i+1}: {ms:4d}ms  audio={dur}s ({wav_size}B)  → {status}")

    if not times:
        print("\nAll runs failed!")
        sys.exit(1)

    # Summary
    n = len(times)
    avg = sum(times) // n
    p50 = sorted(times)[n // 2]
    p95 = sorted(times)[min(int(n * 0.95), n - 1)]
    worst = max(times)
    best = min(times)

    print(f"\n{'='*60}")
    print(f"  RESULTS ({n}/{RUNS} successful)")
    print(f"{'='*60}")
    print(f"               avg      p50      p95    worst     best")
    print(f"  ASR        {avg:5d}ms  {p50:5d}ms  {p95:5d}ms  {worst:5d}ms  {best:5d}ms")

    passed = sum(1 for t in times if t < TARGET_MS)
    pct = passed * 100 // n
    print(f"\n  Under {TARGET_MS}ms: {passed}/{n} ({pct}%)")

    if pct >= 80:
        print(f"  ✅ PASS — {pct}% of requests under target")
    elif pct >= 50:
        print(f"  ⚠️  MARGINAL — {pct}% under target")
    else:
        print(f"  ❌ FAIL — only {pct}% under target")
        print(f"     avg={avg}ms — check Groq rate limits or try distil-whisper-large-v3-en for English")

    if failures:
        print(f"  ⚠️  {failures} failed request(s)")

    sys.exit(0 if pct >= 80 else 1)


if __name__ == "__main__":
    main()
