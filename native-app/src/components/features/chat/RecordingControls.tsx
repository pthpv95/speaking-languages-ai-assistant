import { View, Text, StyleSheet } from "react-native";
import { MicButton } from "@/components/features/chat/MicButton";
import { useAppStore } from "@/stores/appStore";
import { colors } from "@/constants/colors";

type RecordingControlsProps = {
  statusText: string;
  onToggleRecording: () => void;
  disabled?: boolean;
};

function formatTimer(secs: number) {
  const m = String(Math.floor(secs / 60)).padStart(2, "0");
  const s = String(secs % 60).padStart(2, "0");
  return `${m}:${s}`;
}

export function RecordingControls({
  statusText,
  onToggleRecording,
  disabled = false,
}: RecordingControlsProps) {
  const recordingState = useAppStore((s) => s.recordingState);
  const timerSeconds = useAppStore((s) => s.timerSeconds);

  return (
    <View style={styles.controls}>
      {recordingState === "recording" && (
        <Text style={styles.timer}>{formatTimer(timerSeconds)}</Text>
      )}

      <MicButton onPress={onToggleRecording} disabled={disabled} />

      <Text
        style={[
          styles.status,
          recordingState === "recording" && styles.statusRecording,
          recordingState === "processing" && styles.statusProcessing,
        ]}
      >
        {statusText}
      </Text>
      {/* <Text style={styles.hint}>Tap to record · Tap again to send</Text> */}
    </View>
  );
}

const styles = StyleSheet.create({
  controls: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: "center",
    gap: 10,
    padding:16,
    backgroundColor: colors.background,
  },
  timer: {
    fontSize: 14,
    fontVariant: ["tabular-nums"],
    color: colors.error,
    letterSpacing: 1,
  },
  status: {
    fontSize: 12,
    color: colors.textMuted,
  },
  statusRecording: { color: colors.error },
  statusProcessing: { color: colors.accent },
  hint: {
    fontSize: 12,
    color: colors.textMuted,
  },
});
