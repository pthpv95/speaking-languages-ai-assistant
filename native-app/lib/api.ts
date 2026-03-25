const API_BASE = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8080";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(body, res.status);
  }

  return res.json() as Promise<T>;
}

// --- Typed API functions ---

export type HealthResponse = {
  status: string;
  language: string;
  asr: string;
  tts_voice: string;
};

export type ConfigResponse = {
  language: string;
  tts_voice: string;
};

export type ChatResponse = {
  reply: string;
  mp3_base64: string;
  llm_ms: number;
  tts_ms: number;
  total_ms: number;
};

export type TranscribeResponse = {
  transcript: string;
  error?: string;
};

export function fetchHealth(signal?: AbortSignal) {
  return apiFetch<HealthResponse>("/health", { signal });
}

export function fetchConfig(signal?: AbortSignal) {
  return apiFetch<ConfigResponse>("/config", { signal });
}

export function postChat(transcript: string, signal?: AbortSignal) {
  const form = new FormData();
  form.append("transcript", transcript);
  return apiFetch<ChatResponse>("/chat", {
    method: "POST",
    headers: {},
    body: form,
    signal,
  });
}

export function postTranscribe(audioBlob: Blob, signal?: AbortSignal) {
  const form = new FormData();
  form.append("audio", audioBlob, "audio.webm");
  return apiFetch<TranscribeResponse>("/transcribe", {
    method: "POST",
    headers: {},
    body: form,
    signal,
  });
}

export function deleteHistory() {
  return apiFetch<{ status: string }>("/history", { method: "DELETE" });
}
