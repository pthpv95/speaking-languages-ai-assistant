import { useCallback, useEffect, useRef, useState } from "react";
import {
  useAudioRecorder,
  useAudioRecorderState,
  useAudioPlayer,
  useAudioPlayerStatus,
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
} from "expo-audio";
import { useAppStore } from "@/stores/appStore";
import {
  createConversation,
  createUser,
  postChat,
  postTranscribe,
} from "@/services/api";
import type { ChatMessage } from "@/types/api.types";

const RECORDING_OPTIONS = {
  ...RecordingPresets.HIGH_QUALITY,
  android: {
    ...RecordingPresets.HIGH_QUALITY.android,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 64000,
  },
  ios: {
    ...RecordingPresets.HIGH_QUALITY.ios,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 64000,
  },
};

export function useVoiceChat(language = "english") {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [statusText, setStatusText] = useState("ready");
  const [audioSource, setAudioSource] = useState<string | null>(null);
  const [shouldPlay, setShouldPlay] = useState(false);

  const conversationIdRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { setRecordingState, setTimerSeconds, setIsPlaying, reset } = useAppStore();

  // Recording
  const recorder = useAudioRecorder(RECORDING_OPTIONS);
  const recorderState = useAudioRecorderState(recorder);

  // Playback
  const player = useAudioPlayer(audioSource);
  const playerStatus = useAudioPlayerStatus(player);

  // Sync recorder state to store
  useEffect(() => {
    if (recorderState.isRecording) {
      setTimerSeconds(Math.floor(recorderState.durationMillis / 1000));
    }
  }, [recorderState.durationMillis, recorderState.isRecording, setTimerSeconds]);

  // Auto-play when audio source is loaded and ready
  useEffect(() => {
    if (shouldPlay && audioSource && !playerStatus.playing && playerStatus.isLoaded) {
      player.play();
      setShouldPlay(false);
    }
  }, [shouldPlay, audioSource, playerStatus.playing, playerStatus.isLoaded, player]);

  // Detect playback finished
  useEffect(() => {
    if (playerStatus.didJustFinish) {
      setIsPlaying(false);
      setStatusText("ready");
    }
  }, [playerStatus.didJustFinish, setIsPlaying]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const ensureConversation = useCallback(async () => {
    if (conversationIdRef.current != null) return conversationIdRef.current;
    await createUser("mobile-user");
    const conv = await createConversation(language);
    conversationIdRef.current = conv.id;
    return conv.id;
  }, [language]);

  const startRecording = useCallback(async () => {
    setError(null);

    // Stop any playing audio (barge-in)
    if (playerStatus.playing) {
      player.pause();
      setIsPlaying(false);
    }

    const { granted } = await requestRecordingPermissionsAsync();
    if (!granted) {
      setError("Microphone permission denied");
      return;
    }

    await setAudioModeAsync({
      playsInSilentMode: true,
      allowsRecording: true,
    });

    await recorder.prepareToRecordAsync();
    recorder.record();

    setRecordingState("recording");
    setStatusText("recording...");
    setTimerSeconds(0);
  }, [player, playerStatus.playing, recorder, setRecordingState, setTimerSeconds, setIsPlaying]);

  const stopAndProcess = useCallback(async () => {
    setRecordingState("processing");
    setStatusText("transcribing...");

    try {
      await recorder.stop();
      const uri = recorder.uri;

      if (!uri) throw new Error("No recording URI");

      await setAudioModeAsync({ allowsRecording: false });

      // Ensure conversation exists
      const conversationId = await ensureConversation();

      // Step 1: Transcribe
      const transcribeResult = await postTranscribe(uri, conversationId);

      if (transcribeResult.error || !transcribeResult.transcript) {
        setError(transcribeResult.error ?? "Nothing heard - try again");
        reset();
        setStatusText("ready");
        return;
      }

      const transcript = transcribeResult.transcript;
      setMessages((prev) => [...prev, { role: "user", text: transcript }]);

      // Step 2: Chat (LLM + TTS)
      setStatusText("thinking...");
      const chatResult = await postChat(transcript, conversationId);

      const aiMessage: ChatMessage = {
        role: "ai",
        text: chatResult.reply,
        audioBase64: chatResult.audio_base64,
        audioMime: chatResult.audio_mime,
        totalMs: chatResult.total_ms,
        llmMs: chatResult.llm_ms,
        ttsMs: chatResult.tts_ms,
      };
      setMessages((prev) => [...prev, aiMessage]);

      // Step 3: Play audio response
      setStatusText("speaking...");
      setIsPlaying(true);
      const dataUri = `data:${chatResult.audio_mime};base64,${chatResult.audio_base64}`;
      setAudioSource(dataUri);
      setShouldPlay(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong";
      setError(msg);
      reset();
      setStatusText("ready");
    }
  }, [recorder, ensureConversation, reset, setRecordingState, setIsPlaying, player]);

  const toggleRecording = useCallback(async () => {
    if (recorderState.isRecording) {
      await stopAndProcess();
    } else {
      await startRecording();
    }
  }, [recorderState.isRecording, startRecording, stopAndProcess]);

  const replayAudio = useCallback(
    (message: ChatMessage) => {
      if (!message.audioBase64 || !message.audioMime) return;
      setIsPlaying(true);
      const dataUri = `data:${message.audioMime};base64,${message.audioBase64}`;
      setAudioSource(dataUri);
      setShouldPlay(true);
    },
    [setIsPlaying],
  );

  const clearChat = useCallback(() => {
    setMessages([]);
    conversationIdRef.current = null;
    setError(null);
    setStatusText("ready");
    setAudioSource(null);
    setShouldPlay(false);
  }, []);

  return {
    messages,
    error,
    statusText,
    toggleRecording,
    replayAudio,
    clearChat,
  };
}
