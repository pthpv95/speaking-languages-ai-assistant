import { View, Text, Pressable, StyleSheet } from "react-native";
import { colors } from "@/constants/colors";
import type { ChatMessage } from "@/types/api.types";

type MessageBubbleProps = {
  message: ChatMessage;
  onReplay: (msg: ChatMessage) => void;
};

export function MessageBubble({ message, onReplay }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <View style={styles.row}>
      <View style={[styles.bubble, isUser ? styles.userBubble : styles.aiBubble]}>
        <Text style={[styles.text, isUser && styles.userText]}>
          {message.text}
        </Text>

        {!isUser && message.audioBase64 && (
          <Pressable onPress={() => onReplay(message)} style={styles.replayBtn}>
            <Text style={styles.replayText}>🔊 Replay</Text>
          </Pressable>
        )}

        {!isUser && message.totalMs != null && (
          <Text style={styles.latency}>
            {message.totalMs}ms (llm {message.llmMs} · tts {message.ttsMs})
          </Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { width: "100%" },
  bubble: {
    maxWidth: "82%",
    padding: 12,
    borderRadius: 16,
  },
  userBubble: {
    alignSelf: "flex-end",
    backgroundColor: colors.accent,
    borderBottomRightRadius: 4,
  },
  aiBubble: {
    alignSelf: "flex-start",
    backgroundColor: colors.cardBackground,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: "#e8e8e8",
  },
  text: {
    fontSize: 15,
    lineHeight: 22,
    color: colors.textPrimary,
  },
  userText: { color: "#fff" },
  replayBtn: { marginTop: 8 },
  replayText: {
    fontSize: 13,
    color: colors.accent,
    fontWeight: "500",
  },
  latency: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 4,
  },
});
