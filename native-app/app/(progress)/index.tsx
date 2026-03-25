import { View, Text, StyleSheet, ScrollView } from "react-native";
import { Stack } from "expo-router";

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

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.statCard}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#fff" },
  content: { padding: 20, gap: 20 },
  title: { fontSize: 28, fontWeight: "700", color: "#1a1a1a" },
  subtitle: { fontSize: 16, color: "#666", marginTop: -12 },
  statsRow: { flexDirection: "row", gap: 12 },
  statCard: {
    flex: 1,
    backgroundColor: "#e8f5e9",
    borderRadius: 12,
    borderCurve: "continuous",
    padding: 16,
    alignItems: "center",
    gap: 4,
  },
  statValue: { fontSize: 24, fontWeight: "700", color: "#2e7d32" },
  statLabel: { fontSize: 13, color: "#666" },
  card: {
    backgroundColor: "#f8f9fa",
    borderRadius: 12,
    borderCurve: "continuous",
    padding: 16,
    gap: 10,
  },
  cardTitle: { fontSize: 17, fontWeight: "600", color: "#1a1a1a" },
  emptyText: { fontSize: 14, color: "#999", lineHeight: 20 },
});
