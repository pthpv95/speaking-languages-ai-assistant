import { View, Text, StyleSheet, ScrollView } from "react-native";
import { Stack } from "expo-router";
import { StatCard } from "@/components/features/progress/StatCard";
import { colors } from "@/constants/colors";

export default function ProgressScreen() {
  return (
    <>
      <Stack.Screen options={{ title: "Progress" }} />
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        contentInsetAdjustmentBehavior="automatic"
      >
        <Text style={styles.title}>Your Progress</Text>
        <Text style={styles.subtitle}>
          Track your speaking practice over time
        </Text>

        <View style={styles.statsRow}>
          <StatCard label="Sessions" value="0" />
          <StatCard label="Minutes" value="0" />
          <StatCard label="Streak" value="0 days" />
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Recent Activity</Text>
          <Text style={styles.emptyText}>
            No conversations yet. Start chatting to see your progress here.
          </Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Tips Collected</Text>
          <Text style={styles.emptyText}>
            Language tips from your AI coach will appear here as you practice.
          </Text>
        </View>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, gap: 20 },
  title: { fontSize: 28, fontWeight: "700", color: colors.textPrimary },
  subtitle: { fontSize: 16, color: colors.textSecondary, marginTop: -12 },
  statsRow: { flexDirection: "row", gap: 12 },
  card: {
    backgroundColor: colors.cardBackground,
    borderRadius: 12,
    borderCurve: "continuous",
    padding: 16,
    gap: 10,
  },
  cardTitle: { fontSize: 17, fontWeight: "600", color: colors.textPrimary },
  emptyText: { fontSize: 14, color: colors.textMuted, lineHeight: 20 },
});
