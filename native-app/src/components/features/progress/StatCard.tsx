import { View, Text, StyleSheet } from "react-native";
import { colors } from "@/constants/colors";

type StatCardProps = {
  label: string;
  value: string;
};

export function StatCard({ label, value }: StatCardProps) {
  return (
    <View style={styles.statCard}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  statCard: {
    flex: 1,
    backgroundColor: colors.accentLight,
    borderRadius: 12,
    borderCurve: "continuous",
    padding: 16,
    alignItems: "center",
    gap: 4,
  },
  statValue: { fontSize: 24, fontWeight: "700", color: colors.accentDark },
  statLabel: { fontSize: 13, color: colors.textSecondary },
});
