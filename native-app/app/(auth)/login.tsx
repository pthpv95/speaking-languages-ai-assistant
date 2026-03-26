import { View, Text, StyleSheet } from "react-native";
import { Link } from "expo-router";
import { colors } from "@/constants/colors";

export default function LoginScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Welcome Back</Text>
      <Text style={styles.subtitle}>Sign in to continue</Text>
      <Link href="/(auth)/register" style={styles.link}>
        Don't have an account? Register
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
