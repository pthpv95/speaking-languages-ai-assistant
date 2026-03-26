import { View, Text, StyleSheet, ScrollView } from "react-native";
import { Stack } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { fetchConfig } from "@/services/api";
import { MicButton } from "@/components/features/chat/MicButton";
import { colors } from "@/constants/colors";

export default function ChatScreen() {
  const config = useQuery({
    queryKey: ["config"],
    queryFn: ({ signal }) => fetchConfig(signal),
  });

  return (
    <>
      <Stack.Screen options={{ title: "Chat" }} />
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        contentInsetAdjustmentBehavior="automatic"
      >
        <View style={styles.emptyState}>
          <Text style={styles.emoji}>🎤</Text>
          <Text style={styles.heading}>Start a conversation</Text>
          <Text style={styles.body}>
            Tap the microphone button below to record your voice. The AI coach
            will listen and respond in{" "}
            {config.data?.language ?? "your target language"}.
          </Text>
        </View>

        <View style={styles.micArea}>
          <MicButton />
          <Text style={styles.hint}>Tap to record · Tap again to send</Text>
        </View>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, gap: 32, alignItems: "center", paddingTop: 60 },
  emptyState: { alignItems: "center", gap: 8, maxWidth: 300 },
  emoji: { fontSize: 48 },
  heading: { fontSize: 22, fontWeight: "600", color: colors.textPrimary },
  body: {
    fontSize: 15,
    color: colors.textSecondary,
    textAlign: "center",
    lineHeight: 22,
  },
  micArea: { alignItems: "center", gap: 14, marginTop: 20 },
  hint: { fontSize: 13, color: colors.textMuted },
});
