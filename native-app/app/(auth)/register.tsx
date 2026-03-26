import { View, Text, StyleSheet } from "react-native";
import { Link } from "expo-router";
import { colors } from "@/constants/colors";

export default function RegisterScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Create Account</Text>
      <Text style={styles.subtitle}>Sign up to get started</Text>
      <Link href="/(auth)/login" style={styles.link}>
        Already have an account? Sign in
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    backgroundColor: colors.background,
  },
  title: { fontSize: 28, fontWeight: "700", color: colors.textPrimary },
  subtitle: { fontSize: 16, color: colors.textSecondary },
  link: { fontSize: 14, color: colors.link, marginTop: 20 },
});
