import { Pressable, Text, StyleSheet } from "react-native";
import { colors } from "@/constants/colors";
import { useAppStore } from "@/stores/appStore";

type MicButtonProps = {
  onPress?: () => void;
};

export function MicButton({ onPress }: MicButtonProps) {
  const recordingState = useAppStore((s) => s.recordingState);
  const isRecording = recordingState === "recording";
  const isProcessing = recordingState === "processing";

  return (
    <Pressable
      style={[
        styles.micButton,
        isRecording && styles.micButtonRecording,
        isProcessing && styles.micButtonDisabled,
      ]}
      onPress={onPress}
      disabled={isProcessing}
    >
      <Text style={styles.micIcon}>{isRecording ? "⏹" : "🎙️"}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  micButton: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.accentLight,
    borderWidth: 2,
    borderColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
    borderCurve: "continuous",
  },
  micButtonRecording: {
    backgroundColor: "#fce4ec",
    borderColor: colors.error,
  },
  micButtonDisabled: {
    opacity: 0.5,
  },
  micIcon: { fontSize: 32 },
});
