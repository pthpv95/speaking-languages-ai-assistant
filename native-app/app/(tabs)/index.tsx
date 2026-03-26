import { View, Text, StyleSheet, ScrollView, ActivityIndicator } from "react-native";
import { router, Stack } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "@/services/api";
import { StatusRow } from "@/components/features/home/StatusRow";
import { colors } from "@/constants/colors";
import { Button, Input } from "heroui-native";

export default function HomeScreen() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => fetchHealth(signal),
  });

  return (
    <>
      <Stack.Screen options={{ title: "Voice AI" }} />
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        contentInsetAdjustmentBehavior="automatic"
      >
        <Text style={styles.title}>Welcome to Voice AI</Text>
        <Text style={styles.subtitle}>
          Your personal language speaking coach
        </Text>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Server Status</Text>
          {health.isLoading && <ActivityIndicator style={styles.loader} />}
          {health.isError && (
            <Text style={styles.errorText}>
              Cannot reach server — is the backend running?
            </Text>
          )}
          {health.data && (
            <View style={styles.statusRows}>
              <StatusRow label="Status" value={health.data.status} />
              <StatusRow label="Language" value={health.data.language} />
              <StatusRow label="ASR Model" value={health.data.asr} />
              <StatusRow label="TTS Voice" value={health.data.tts_voice} />
            </View>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>How it works</Text>
          <Text style={styles.body}>
            1. Go to the Chat tab{"\n"}
            2. Tap the mic to record your voice{"\n"}
            3. Release to send — hear the AI coach reply
          </Text>
        </View>
        <Button onPress={() => router.push("/(auth)/login")} variant='outline' feedbackVariant='scale'>Login</Button>
        <Input />
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, gap: 20 },
  title: { fontSize: 28, fontWeight: "700", color: colors.textPrimary },
  subtitle: { fontSize: 16, color: colors.textSecondary, marginTop: -12 },
  card: {
    backgroundColor: colors.cardBackground,
    borderRadius: 12,
    borderCurve: "continuous",
    padding: 16,
    gap: 10,
  },
  cardTitle: { fontSize: 17, fontWeight: "600", color: colors.textPrimary },
  body: { fontSize: 15, lineHeight: 24, color: "#444" },
  loader: { marginVertical: 8 },
  errorText: { fontSize: 14, color: colors.error },
  statusRows: { gap: 6 },
});
