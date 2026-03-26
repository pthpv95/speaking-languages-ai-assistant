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
