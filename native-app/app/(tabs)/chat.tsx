import { useMemo, useRef } from "react";
import { View, Text, StyleSheet, ScrollView, Pressable } from "react-native";
import { Stack } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { fetchConfig, fetchConversation } from "@/services/api";
import { ChatEmptyState } from "@/components/features/chat/ChatEmptyState";
import { MessageBubble } from "@/components/features/chat/MessageBubble";
import { RecordingControls } from "@/components/features/chat/RecordingControls";
import { useVoiceChat } from "@/hooks/useVoiceChat";
import { colors } from "@/constants/colors";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import type { ChatMessage } from "@/types/api.types";

const CONVERSATION_ID = 6;

function mapConversationMessages(
  messages: { role: string; content: string }[] | undefined,
): ChatMessage[] {
  return (messages ?? [])
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message) => ({
      role: message.role === "assistant" ? "ai" : "user",
      text: message.content,
    }));
}

export default function ChatScreen() {
  const scrollRef = useRef<ScrollView>(null);
  const insets = useSafeAreaInsets();

  const config = useQuery({
    queryKey: ["config"],
    queryFn: ({ signal }) => fetchConfig(signal),
  });
  const conversation = useQuery({
    queryKey: ["conversation", CONVERSATION_ID],
    queryFn: ({ signal }) => fetchConversation(CONVERSATION_ID, signal),
  });

  const selectedLanguage =
    conversation.data?.language ?? config.data?.available_languages?.[0] ?? null;
  const seededMessages = useMemo(
    () => mapConversationMessages(conversation.data?.messages),
    [conversation.data?.messages],
  );
  const { messages, error, statusText, toggleRecording, replayAudio, clearChat } =
    useVoiceChat(selectedLanguage, {
      initialConversationId: conversation.data?.id ?? null,
      initialMessages: seededMessages,
    });

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
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
          contentContainerStyle={[
            styles.scrollContent,
            { paddingBottom: 220 + insets.bottom },
          ]}
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
          disabled={!selectedLanguage}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  scroll: { flex: 1 },
  scrollContent: { padding: 16, gap: 12, paddingTop: 20 },
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
