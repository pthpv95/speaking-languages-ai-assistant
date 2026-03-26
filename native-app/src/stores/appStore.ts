import { create } from "zustand";

type RecordingState = "idle" | "recording" | "processing";

type AppState = {
  recordingState: RecordingState;
  isPlaying: boolean;
  timerSeconds: number;

  setRecordingState: (state: RecordingState) => void;
  setIsPlaying: (playing: boolean) => void;
  setTimerSeconds: (seconds: number) => void;
  reset: () => void;
};

export const useAppStore = create<AppState>((set) => ({
  recordingState: "idle",
  isPlaying: false,
  timerSeconds: 0,

  setRecordingState: (recordingState) => set({ recordingState }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setTimerSeconds: (timerSeconds) => set({ timerSeconds }),
  reset: () => set({ recordingState: "idle", isPlaying: false, timerSeconds: 0 }),
}));
