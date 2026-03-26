import { View, Text, StyleSheet } from "react-native";
import { colors } from "@/constants/colors";

type StatusRowProps = {
  label: string;
  value: string;
};

export function StatusRow({ label, value }: StatusRowProps) {
  return (
    <View style={styles.row}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", justifyContent: "space-between" },
  label: { fontSize: 14, color: colors.textSecondary },
  value: { fontSize: 14, fontWeight: "500", color: colors.textPrimary },
});
