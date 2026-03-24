import './global.css';

import { useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { HeroUINativeProvider, Button, BottomSheet } from 'heroui-native';
import { View } from 'react-native';

export default function App() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <HeroUINativeProvider>
        <View className="flex-1 justify-center items-center bg-background">

          <BottomSheet isOpen={isOpen} onOpenChange={setIsOpen}>
            <BottomSheet.Trigger asChild>
              <Button variant="secondary">Open Bottom Sheet</Button>
            </BottomSheet.Trigger>
            <BottomSheet.Portal>
              <BottomSheet.Overlay />
              <BottomSheet.Content>
                <BottomSheet.Close />
                <View className="mb-6 gap-2">
                  <BottomSheet.Title>Hello from HeroUI 👋</BottomSheet.Title>
                  <BottomSheet.Description>
                    This is a simple bottom sheet. Swipe down or tap the overlay to dismiss.
                  </BottomSheet.Description>
                </View>
                <View className="gap-3">
                  <Button onPress={() => setIsOpen(false)}>Confirm</Button>
                  <Button variant="tertiary" onPress={() => setIsOpen(false)}>Cancel</Button>
                </View>
              </BottomSheet.Content>
            </BottomSheet.Portal>
          </BottomSheet>

          <StatusBar style="auto" />
        </View>
      </HeroUINativeProvider>
    </GestureHandlerRootView>
  );
}
