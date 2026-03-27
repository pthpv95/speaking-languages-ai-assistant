import { useRef } from "react";
import { View, Text, StyleSheet, ScrollView, Pressable } from "react-native";
import { Stack } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { fetchConfig } from "@/services/api";
import { ChatEmptyState } from "@/components/features/chat/ChatEmptyState";
import { MessageBubble } from "@/components/features/chat/MessageBubble";
import { RecordingControls } from "@/components/features/chat/RecordingControls";
import { useVoiceChat } from "@/hooks/useVoiceChat";
import { colors } from "@/constants/colors";
import { SafeAreaView } from "react-native-safe-area-context";

export default function ChatScreen() {
  const scrollRef = useRef<ScrollView>(null);

  const config = useQuery({
    queryKey: ["config"],
    queryFn: ({ signal }) => fetchConfig(signal),
  });

  const { messages, error, statusText, toggleRecording, replayAudio, clearChat } =
    useVoiceChat(config.data?.available_languages?.[0]);

  return (
    <SafeAreaView style={{ flex: 1 }}>
      <Stack.Screen
        options={{
          title: "Chat",
          headerRight: () => (
            <Pressable onPress={clearChat} style={styles.clearBtn}>
              <Text style={styles.clearBtnText}>Clear</Text>
            </Pressable>
          ),
        }}
      />

      <View style={styles.container}>
        <ScrollView
          ref={scrollRef}
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
        >
          {messages.length === 0 && !error ? (
            <ChatEmptyState />
          ) : (
            messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} onReplay={replayAudio} />
            ))
          )}

          {error && (
            <View style={styles.errorBubble}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}
        </ScrollView>

        <RecordingControls
          statusText={statusText}
          onToggleRecording={toggleRecording}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  scroll: { flex: 1 },
  scrollContent: { padding: 16, gap: 12, paddingBottom: 8 },
  errorBubble: {
    alignSelf: "flex-start",
    padding: 10,
    borderRadius: 12,
    backgroundColor: "#fef2f2",
    borderWidth: 1,
    borderColor: "#fecaca",
  },
  errorText: { fontSize: 13, color: colors.error },
  clearBtn: { paddingHorizontal: 12, paddingVertical: 4 },
  clearBtnText: { fontSize: 14, color: colors.error },
});
