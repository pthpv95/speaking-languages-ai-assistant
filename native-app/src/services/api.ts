import { API_BASE } from "@/constants/config";
import type {
  HealthResponse,
  ConfigResponse,
  ChatResponse,
  TranscribeResponse,
  UserResponse,
  ConversationResponse,
  ConversationDetailResponse,
} from "@/types/api.types";

const DEFAULT_USERNAME = "mobile-user";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function authHeaders(): Record<string, string> {
  return { "X-Username": DEFAULT_USERNAME };
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      ...authHeaders(),
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(body, res.status);
  }

  return res.json() as Promise<T>;
}

export function fetchHealth(signal?: AbortSignal) {
  return apiFetch<HealthResponse>("/health", { signal });
}

export function fetchConfig(signal?: AbortSignal) {
  return apiFetch<ConfigResponse>("/config", { signal });
}

export function createUser(username: string) {
  return apiFetch<UserResponse>("/api/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username }),
  });
}

export function createConversation(language: string, tone?: string) {
  return apiFetch<ConversationResponse>("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language, tone: tone ?? "friendly" }),
  });
}

export function listConversations() {
  return apiFetch<ConversationResponse[]>("/api/conversations");
}

export function fetchConversation(conversationId: number, signal?: AbortSignal) {
  return apiFetch<ConversationDetailResponse>(`/api/conversations/${conversationId}`, {
    signal,
  });
}

export function postTranscribe(
  fileUri: string,
  conversationId?: number,
  signal?: AbortSignal,
) {
  const form = new FormData();
  form.append("audio", {
    uri: fileUri,
    name: "audio.m4a",
    type: "audio/m4a",
  } as unknown as Blob);
  if (conversationId != null) {
    form.append("conversation_id", String(conversationId));
  }
  return apiFetch<TranscribeResponse>("/transcribe", {
    method: "POST",
    headers: {},
    body: form,
    signal,
  });
}

export function postChat(
  transcript: string,
  conversationId: number,
  signal?: AbortSignal,
) {
  const form = new FormData();
  form.append("transcript", transcript);
  form.append("conversation_id", String(conversationId));
  return apiFetch<ChatResponse>("/chat", {
    method: "POST",
    headers: {},
    body: form,
    signal,
  });
}

export function deleteHistory() {
  return apiFetch<{ status: string }>("/history", { method: "DELETE" });
}
