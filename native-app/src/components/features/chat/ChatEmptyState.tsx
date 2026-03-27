import { View, Text, StyleSheet } from "react-native";
import { colors } from "@/constants/colors";

export function ChatEmptyState() {
  return (
    <View style={styles.container}>
      <Text style={styles.emoji}>🎤</Text>
      <Text style={styles.heading}>Start a conversation</Text>
      <Text style={styles.body}>
        Tap the microphone button below to record your voice. The AI coach will
        listen and respond.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingTop: 60,
    maxWidth: 300,
    alignSelf: "center",
  },
  emoji: { fontSize: 48 },
  heading: { fontSize: 22, fontWeight: "600", color: colors.textPrimary },
  body: {
    fontSize: 15,
    color: colors.textSecondary,
    textAlign: "center",
    lineHeight: 22,
  },
});
