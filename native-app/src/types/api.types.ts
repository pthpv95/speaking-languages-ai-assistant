export type HealthResponse = {
  status: string;
  language: string;
  asr: string;
  tts_voice: string;
};

export type ConfigResponse = {
  available_languages: string[];
  available_tones: Record<string, Record<string, string>>;
  tts_engine_override: string | null;
};

export type ChatResponse = {
  reply: string;
  audio_base64: string;
  audio_mime: string;
  llm_ms: number;
  tts_ms: number;
  total_ms: number;
};

export type TranscribeResponse = {
  transcript: string;
  error?: string;
};

export type UserResponse = {
  id: number;
  username: string;
};

export type ConversationResponse = {
  id: number;
  title: string;
  language: string;
  tone: string;
  updated_at: string;
};

export type ConversationMessageResponse = {
  role: string;
  content: string;
  created_at?: string | null;
};

export type ConversationDetailResponse = ConversationResponse & {
  messages: ConversationMessageResponse[];
};

export type ChatMessage = {
  role: "user" | "ai";
  text: string;
  audioBase64?: string;
  audioMime?: string;
  totalMs?: number;
  llmMs?: number;
  ttsMs?: number;
};
