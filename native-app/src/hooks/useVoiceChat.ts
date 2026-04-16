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

const RECORDING_OPTIONS = RecordingPresets.HIGH_QUALITY;

type UseVoiceChatOptions = {
  initialConversationId?: number | null;
  initialMessages?: ChatMessage[];
};

export function useVoiceChat(
  language: string | null,
  { initialConversationId = null, initialMessages = [] }: UseVoiceChatOptions = {},
) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [error, setError] = useState<string | null>(null);
  const [statusText, setStatusText] = useState(
    language ? "ready" : "loading language...",
  );
  const [audioSource, setAudioSource] = useState<string | null>(null);
  const [shouldPlay, setShouldPlay] = useState(false);

  const conversationIdRef = useRef<number | null>(6);//hard code for now
  const isTransitioningRef = useRef(false);

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
      setRecordingState("idle");
      setTimerSeconds(0);
      setIsPlaying(false);
      setStatusText("ready");
    }
  }, [playerStatus.didJustFinish, setIsPlaying, setRecordingState, setTimerSeconds]);

  useEffect(() => {
    setError(null);
    setStatusText(language ? "ready" : "loading language...");

    if (initialConversationId != null) {
      conversationIdRef.current = initialConversationId;
      return;
    }

    conversationIdRef.current = null;
  }, [initialConversationId, language]);

  useEffect(() => {
    setMessages(initialMessages);
  }, [initialMessages]);

  const ensureConversation = useCallback(async () => {
    if (conversationIdRef.current != null) return conversationIdRef.current;
    await createUser("mobile-user");
    if (!language) {
      throw new Error("Language is still loading");
    }
    const conv = await createConversation(language);
    conversationIdRef.current = conv.id;
    return conv.id;
  }, [language]);

  const preparePlaybackSession = useCallback(async () => {
    await setAudioModeAsync({
      playsInSilentMode: true,
      allowsRecording: false,
      interruptionMode: "mixWithOthers",
      shouldRouteThroughEarpiece: false,
    });
  }, []);

  const cleanupRecordingSession = useCallback(async () => {
    try {
      await preparePlaybackSession();
    } catch (err) {
      console.warn("Failed to reset audio mode after recording", err);
    }
  }, [preparePlaybackSession]);

  const startRecording = useCallback(async () => {
    if (isTransitioningRef.current) return;
    if (!language) {
      setError("Language is still loading");
      setStatusText("loading language...");
      return;
    }

    isTransitioningRef.current = true;
    setError(null);

    try {
      // Stop any playing audio (barge-in)
      if (playerStatus.playing) {
        player.pause();
        setIsPlaying(false);
      }

      const { granted } = await requestRecordingPermissionsAsync();
      if (!granted) {
        setError("Microphone permission denied");
        setStatusText("ready");
        return;
      }

      await setAudioModeAsync({
        playsInSilentMode: true,
        allowsRecording: true,
      });

      if (recorderState.mediaServicesDidReset || !recorderState.canRecord) {
        await recorder.prepareToRecordAsync();
      }

      recorder.record();

      setRecordingState("recording");
      setStatusText("recording...");
      setTimerSeconds(0);
    } catch (err) {
      await cleanupRecordingSession();
      const msg = err instanceof Error ? err.message : "Failed to start recording";
      setError(msg);
      setStatusText("ready");
    } finally {
      isTransitioningRef.current = false;
    }
  }, [
    language,
    player,
    playerStatus.playing,
    recorder,
    recorderState.canRecord,
    recorderState.mediaServicesDidReset,
    cleanupRecordingSession,
    setRecordingState,
    setTimerSeconds,
    setIsPlaying,
  ]);

  const stopAndProcess = useCallback(async () => {
    if (isTransitioningRef.current) return;
    isTransitioningRef.current = true;
    setRecordingState("processing");
    setStatusText("transcribing...");

    try {
      await recorder.stop();
      const uri = recorder.uri;

      if (!uri) throw new Error("No recording URI");

      await cleanupRecordingSession();

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
      await preparePlaybackSession();
      setRecordingState("idle");
      setTimerSeconds(0);
      setStatusText("speaking...");
      setIsPlaying(true);
      const dataUri = `data:${chatResult.audio_mime};base64,${chatResult.audio_base64}`;
      setAudioSource(dataUri);
      setShouldPlay(true);
    } catch (err) {
      await cleanupRecordingSession();
      const msg = err instanceof Error ? err.message : "Something went wrong";
      setError(msg);
      reset();
      setStatusText("ready");
    } finally {
      isTransitioningRef.current = false;
    }
  }, [
    recorder,
    ensureConversation,
    cleanupRecordingSession,
    preparePlaybackSession,
    reset,
    setRecordingState,
    setTimerSeconds,
    setIsPlaying,
  ]);

  const toggleRecording = useCallback(async () => {
    if (isTransitioningRef.current) return;
    if (recorderState.isRecording) {
      await stopAndProcess();
    } else {
      await startRecording();
    }
  }, [recorderState.isRecording, startRecording, stopAndProcess]);

  const replayAudio = useCallback(
    async (message: ChatMessage) => {
      if (!message.audioBase64 || !message.audioMime) return;
      await preparePlaybackSession();
      const dataUri = `data:${message.audioMime};base64,${message.audioBase64}`;
      setIsPlaying(true);
      setStatusText("speaking...");
      setAudioSource(dataUri);
      setShouldPlay(true);
    },
    [preparePlaybackSession, setIsPlaying],
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
