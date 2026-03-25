import "../global.css";

import { NativeTabs } from "expo-router/unstable-native-tabs";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { HeroUINativeProvider } from "heroui-native";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "../lib/query-client";

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <QueryClientProvider client={queryClient}>
        <HeroUINativeProvider>
          <NativeTabs>
            <NativeTabs.Trigger name="(home)">
              <NativeTabs.Trigger.Icon sf="house.fill" md="home" />
              <NativeTabs.Trigger.Label>Home</NativeTabs.Trigger.Label>
            </NativeTabs.Trigger>
            <NativeTabs.Trigger name="(chat)">
              <NativeTabs.Trigger.Icon
                sf="bubble.left.and.bubble.right.fill"
                md="chat"
              />
              <NativeTabs.Trigger.Label>Chat</NativeTabs.Trigger.Label>
            </NativeTabs.Trigger>
            <NativeTabs.Trigger name="(progress)">
              <NativeTabs.Trigger.Icon sf="chart.bar.fill" md="bar_chart" />
              <NativeTabs.Trigger.Label>Progress</NativeTabs.Trigger.Label>
            </NativeTabs.Trigger>
          </NativeTabs>
        </HeroUINativeProvider>
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}
